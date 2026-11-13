"""D52: persistência na produção (preditivo/cenarios/relatorio). Dados SINTÉTICOS: só testam lógica e ausência de vazamento."""
import copy

import numpy as np
import pandas as pd
import pytest

from src.modelos import relatorio
from src.modelos.cenarios import (
    aplicar_cenario, sensibilidade_comparada, simular, simular_comparado, treinar_para_cenarios,
)
from src.modelos.entrada import carregar_config
from src.modelos.features import (
    NOMES_PERSISTENCIA, adicionar_anomalia, adicionar_persistencia, construir_dataset, nomes_features,
)
from src.modelos.preditivo import _avisos_cobertura, avaliar, preparar_tabela_modelagem, salvar_metricas
from src.modelos.sintetico import gerar_sinteticos
from src.modelos.walkforward import VARIANTES, extra_persistencia, walk_forward


@pytest.fixture(scope="module")
def cfg():
    return carregar_config()


@pytest.fixture(scope="module")
def ent(tmp_path_factory):
    d = tmp_path_factory.mktemp("sint_pers")
    arqs = gerar_sinteticos(d, n_celulas=6, pontos_por_celula=2, ano_ini=2005, ano_fim=2019)
    return {k: pd.read_parquet(v) for k, v in arqs.items()}


@pytest.fixture(scope="module")
def ds(ent, cfg):
    return construir_dataset(ent, cfg)


@pytest.fixture(scope="module")
def res(ds, cfg):
    return avaliar(ds, cfg, sintetico=True)


def _copia(e):
    return {k: (None if v is None else v.copy()) for k, v in e.items()}


# --- mesma construção da validação ------------------------------------------------------
def test_producao_usa_a_mesma_funcao_do_walkforward():
    assert extra_persistencia is adicionar_persistencia
    assert NOMES_PERSISTENCIA == ["anom_lag1", "anom_lag2"]


def test_holdout_da_producao_bate_com_o_walkforward_do_primeiro_ano(ds, cfg, ent, res):
    """Treino < Y e teste Y: o RMSE do 1º ano do holdout da produção tem de ser IGUAL ao do walk-forward validado."""
    Y = res["divisao"]["anos_teste"][0]
    wf = walk_forward(ent, cfg, [VARIANTES["persistencia"]], [Y], modelos=("ridge", "xgboost"))
    for m in ("ridge", "xgboost"):
        rm_wf = float(wf[(wf["modelo"] == m)]["rmse"].iloc[0])
        rm_pr = res["holdout_temporal"]["por_ano"][str(Y)][m]["rmse"]
        assert rm_pr == pytest.approx(rm_wf, rel=1e-9)
    n_wf = int(wf[wf["modelo"] == "ridge"]["n"].iloc[0])
    assert res["holdout_temporal"]["por_ano"][str(Y)]["n"] == n_wf


# --- vazamento --------------------------------------------------------------------------
def test_alterar_ndvi_e_clima_a_partir_de_t_nao_muda_features_de_t_ou_anteriores(ent, cfg):
    d0, _, teste_anos, cols = preparar_tabela_modelagem(construir_dataset(ent, cfg), cfg)
    T = pd.Timestamp(f"{teste_anos[1]}-06-01")          # dentro do holdout: climatologia (treino) não muda
    alt = _copia(ent)
    alt["ndvi"].loc[alt["ndvi"]["data"] >= T, "ndvi"] = 0.99
    alt["clima"].loc[alt["clima"]["data"] >= T, ["chuva_mm", "tmax_c"]] *= 7.0
    d1, _, _, cols1 = preparar_tabela_modelagem(construir_dataset(alt, cfg), cfg)
    assert cols == cols1 and {"anom_lag1", "anom_lag2"} <= set(cols)
    k = ["ponto_id", "data"]
    a = d0[d0["data"] <= T].set_index(k)[cols].sort_index()
    b = d1[d1["data"] <= T].set_index(k)[cols].sort_index()
    pd.testing.assert_frame_equal(a, b)                              # t e anteriores: idênticas (inclui as lags)
    # controle: depois de T a feature de persistência MUDA (o teste enxerga mudança quando ela existe)
    c0 = d0[d0["data"] > T].set_index(k)["anom_lag1"].sort_index()
    c1 = d1[d1["data"] > T].set_index(k)["anom_lag1"].sort_index()
    assert not c0.equals(c1)


def test_features_de_persistencia_do_treino_nao_veem_o_teste(ds, cfg):
    a, treino_anos, teste_anos, _ = preparar_tabela_modelagem(ds, cfg)
    alt = ds.copy()
    alt.loc[alt["ano"].isin(teste_anos), "ndvi"] += 5.0
    b, _, _, _ = preparar_tabela_modelagem(alt, cfg)
    ta, tb = a[a["ano"].isin(treino_anos)], b[b["ano"].isin(treino_anos)]
    pd.testing.assert_frame_equal(ta.reset_index(drop=True), tb.reset_index(drop=True))


def test_climatologia_da_anomalia_so_dos_anos_de_treino_no_holdout(ds, cfg):
    d, treino_anos, _, _ = preparar_tabela_modelagem(ds, cfg)
    ref = adicionar_anomalia(ds, treino_anos, cfg)
    ref = ref.set_index(["ponto_id", "data"])
    x = d.set_index(["ponto_id", "data"])
    np.testing.assert_allclose(x["ndvi_clim"].to_numpy(), ref.loc[x.index, "ndvi_clim"].to_numpy())
    # lag1 = anomalia (com climatologia de TREINO) do composto anterior
    t = x.reset_index().sort_values(["ponto_id", "data"])
    ant = ref["anomalia_ndvi"].groupby(level=0).shift(1)
    ok = t["anom_lag1"].notna().to_numpy()
    np.testing.assert_allclose(t["anom_lag1"].to_numpy()[ok], ant.loc[pd.MultiIndex.from_frame(t[["ponto_id", "data"]])].to_numpy()[ok])


# --- ordem, reprodutibilidade -----------------------------------------------------------
def test_tabela_nao_depende_da_ordem_das_linhas(ds, cfg):
    a, *_ = preparar_tabela_modelagem(ds, cfg)
    b, *_ = preparar_tabela_modelagem(ds.sample(frac=1.0, random_state=3).reset_index(drop=True), cfg)
    pd.testing.assert_frame_equal(a, b)


def test_avaliacao_com_persistencia_nao_depende_da_ordem(ds, cfg, res):
    outra = avaliar(ds.sample(frac=1.0, random_state=1).reset_index(drop=True), cfg, sintetico=True)
    assert outra["holdout_temporal"]["modelos"]["ridge"]["rmse"] == pytest.approx(
        res["holdout_temporal"]["modelos"]["ridge"]["rmse"], rel=1e-9)


def test_reprodutivel_com_persistencia(ds, cfg, res):
    outra = avaliar(copy.deepcopy(ds), cfg, sintetico=True)
    assert outra["holdout_temporal"] == res["holdout_temporal"]
    assert outra["comparativo"] == res["comparativo"]
    assert outra["decisao"] == res["decisao"]


# --- composto ausente / não consecutivo => NaN e fora do treino, nunca preenchido ---------
def test_composto_ausente_vira_nan_e_linha_sai_do_treino(ent, cfg):
    pid = "P000"
    base = construir_dataset(ent, cfg)
    d0, _, teste_anos, cols = preparar_tabela_modelagem(base, cfg)
    alvo = d0[(d0["ponto_id"] == pid) & (d0["ano"] == teste_anos[0])].sort_values("data")
    X = alvo["data"].iloc[5]                                    # remove o composto X (como cobertura de nuvem)
    alt = _copia(ent)
    alt["ndvi"] = alt["ndvi"][~((alt["ndvi"]["ponto_id"] == pid) & (alt["ndvi"]["data"] == X))]
    ds1 = construir_dataset(alt, cfg)
    d1, *_ = preparar_tabela_modelagem(ds1, cfg)
    datas = d1[d1["ponto_id"] == pid].set_index("data")
    seguintes = sorted(ds1[(ds1["ponto_id"] == pid) & (ds1["data"] > X)]["data"])[:2]
    for s in seguintes:                                          # os 2 compostos seguintes dependem de X
        assert s not in datas.index                             # sem o par consecutivo => fora (não preenchida)
    assert not d1[cols].isna().any().any()                      # nenhuma linha restante tem NaN
    # sem persistência essas linhas existiriam (a saída é causada só pela persistência)
    d_sem, *_ = preparar_tabela_modelagem(ds1, cfg, False)
    sem = d_sem[d_sem["ponto_id"] == pid].set_index("data")
    assert all(s in sem.index for s in seguintes if s in set(d0["data"]))


def test_gap_maior_que_17_dias_e_nan():
    d = pd.DataFrame({"ponto_id": ["p"] * 4, "data": pd.to_datetime(["2010-01-01", "2010-01-17", "2010-02-18", "2010-03-06"]),
                      "anomalia_ndvi": [1.0, 2.0, 3.0, 4.0]})
    out, novas = adicionar_persistencia(d)
    assert novas == ["anom_lag1", "anom_lag2"]
    assert np.isnan(out.loc[2, "anom_lag1"]) and np.isnan(out.loc[2, "anom_lag2"])    # buraco de 32 d
    assert out.loc[3, "anom_lag1"] == 3.0 and np.isnan(out.loc[3, "anom_lag2"])       # lag2 atravessa o buraco
    assert adicionar_persistencia(d, max_gap_dias=40)[0].loc[2, "anom_lag1"] == 2.0   # limite é parâmetro


def test_lags_nao_atravessam_pontos():
    d = pd.DataFrame({"ponto_id": ["a", "a", "b", "b"], "data": pd.to_datetime(["2010-01-01", "2010-01-17"] * 2),
                      "anomalia_ndvi": [1.0, 2.0, 3.0, 4.0]})
    out, _ = adicionar_persistencia(d)
    assert np.isnan(out.loc[2, "anom_lag1"]) and out.loc[3, "anom_lag1"] == 3.0


# --- opção mantida: só-clima e SMAP desligado ---------------------------------------------
def test_flag_desligada_devolve_o_modelo_anterior(ds, cfg):
    d, _, _, cols = preparar_tabela_modelagem(ds, cfg, False)
    assert cols == nomes_features(cfg, False) and "anom_lag1" not in d.columns
    c2 = copy.deepcopy(cfg)
    c2["preditivo"]["usar_persistencia"] = False
    r = avaliar(ds, c2, sintetico=True)
    assert r["comparativo"] is None and not r["persistencia"]["usada"]
    assert not any(c.startswith("anom_lag") for c in r["features"])


def test_padrao_e_com_persistencia_e_sem_smap(res, cfg):
    assert cfg["preditivo"]["usar_persistencia"] is True and cfg["preditivo"]["usar_umidade_solo"] is False
    assert res["persistencia"]["usada"] and res["features"][-2:] == ["anom_lag1", "anom_lag2"]
    assert not any(c.startswith("sm_") for c in res["features"]) and not res["umidade_solo_smap"]["usada"]


def test_smap_so_entra_se_ligado(ent, cfg):
    assert "umidade_solo" in ent and ent["umidade_solo"] is not None
    assert not any(c.startswith("sm_") for c in construir_dataset(ent, cfg).columns)
    c2 = copy.deepcopy(cfg)
    c2["preditivo"]["usar_umidade_solo"] = True
    assert any(c.startswith("sm_raiz") for c in construir_dataset(ent, c2).columns)


def test_comparativo_tem_as_tres_linhas_nas_linhas_certas(res):
    c = res["comparativo"]
    assert set(c) >= {"com_persistencia", "so_clima_mesmas_linhas", "so_clima_todas_as_linhas"}
    assert c["com_persistencia"]["n_teste"] == c["so_clima_mesmas_linhas"]["n_teste"]       # mesmas linhas
    assert c["so_clima_todas_as_linhas"]["n_teste"] >= c["com_persistencia"]["n_teste"]
    assert not any(f.startswith("anom_lag") for f in c["so_clima_mesmas_linhas"]["features"])


# --- cenários -----------------------------------------------------------------------------
@pytest.fixture(scope="module")
def mcs(ds, cfg):
    return (treinar_para_cenarios(ds, cfg, "ridge"), treinar_para_cenarios(ds, cfg, "ridge", usar_persistencia=False))


@pytest.fixture(scope="module")
def base(ds, cfg):
    d, tr, _, _ = preparar_tabela_modelagem(ds, cfg)
    return d[d["ano"].isin(tr)].head(60)


def test_cenario_nao_altera_features_de_persistencia(mcs, base):
    mc_p, _ = mcs
    x = aplicar_cenario(base, mc_p.cols, fator_chuva=0.5, delta_tmax_c=2.0)
    for c in ("anom_lag1", "anom_lag2", "dias_secos_consecutivos", "quinzena_sin"):
        pd.testing.assert_series_equal(x[c], base[c])
    assert not x["chuva_ac_30d"].equals(base["chuva_ac_30d"])


def test_limites_declaram_que_persistencia_nao_reage(mcs, base):
    mc_p, mc_c = mcs
    s_p, s_c = simular(mc_p, base), simular(mc_c, base)
    assert s_p["com_persistencia"] and "memória do NDVI" in s_p["limites"] and "reagem pouco" in s_p["limites"]
    assert not s_c["com_persistencia"] and "memória do NDVI" not in s_c["limites"]
    assert "causalidade" in s_p["aviso"]


def test_extrapolacao_por_persistencia_fora_da_faixa_sem_numero(mcs, base):
    mc_p, _ = mcs
    b = base.copy()
    b["anom_lag1"] = 50.0
    s = simular(mc_p, b)
    assert s["extrapolacao"] is True and s["anomalia_ndvi_prevista"] is None and s["faixa_incerteza"] is None
    assert any(f["feature"] == "anom_lag1" for f in s["features_fora_da_faixa"])


def test_persistencia_ausente_na_base_do_cenario_nao_e_preenchida(mcs, base):
    from src.modelos.entrada import DadosInvalidos
    mc_p, _ = mcs
    b = base.copy()
    b.iloc[0, b.columns.get_loc("anom_lag2")] = np.nan
    with pytest.raises(DadosInvalidos):
        simular(mc_p, b)


def test_simular_comparado_mesmas_linhas_e_variacao_coerente(mcs, base):
    mc_p, mc_c = mcs
    r = simular_comparado(mc_p, mc_c, base, fator_chuva=0.9)
    for k in ("com_persistencia", "so_clima"):
        e = r[k]
        assert not e["extrapolacao"] and e["variacao"] == pytest.approx(e["cenario"] - e["neutro"])
    assert r["n_linhas_base"] == len(base)
    assert r["razao_com_sobre_so_clima"] == pytest.approx(r["com_persistencia"]["variacao"] / r["so_clima"]["variacao"])


def test_sensibilidade_comparada_estrutura_e_regra_de_faixa(ds, cfg):
    s = sensibilidade_comparada(ds, cfg, nomes=("ridge",), cenarios=((0.9, 0.0), (50.0, 0.0)))
    a, b = s["modelos"]["ridge"]
    assert a["n_linhas_usadas"] > 0 and np.isfinite(a["com_persistencia"]["variacao"]) and np.isfinite(a["so_clima"]["variacao"])
    assert b["n_linhas_fora_da_faixa"] > 0 and b["n_linhas_usadas"] < a["n_linhas_usadas"]   # x50 extrapola: linhas fora ficam sem número
    assert a["n_linhas_usadas"] + a["n_linhas_fora_da_faixa"] == b["n_linhas_usadas"] + b["n_linhas_fora_da_faixa"]
    assert sensibilidade_comparada(ds, cfg, nomes=("ridge",), cenarios=((0.9, 0.0),)) ["modelos"]["ridge"][0] == a   # reprodutível


# --- conformal e relatório ----------------------------------------------------------------
def test_aviso_de_cobertura_abaixo_da_meta_nao_maquia():
    h = {n: {"metas": {"80": {"meta": 0.8, "cobertura": 0.70}, "90": {"meta": 0.9, "cobertura": 0.91}}} for n in ("ridge", "xgboost")}
    av = _avisos_cobertura(h)
    assert len(av) == 2 and "80% (real 70.0%)" in av[0] and "90%" not in av[0]
    h["ridge"]["metas"]["80"]["cobertura"] = 0.79
    assert len(_avisos_cobertura(h)) == 1                                       # tolerância 0,02


def test_relatorio_real_mostra_as_duas_linhas_e_a_sensibilidade(res, ds, cfg, tmp_path):
    real = copy.deepcopy(res)
    real["dados_sinteticos"] = False
    real["sensibilidade_cenarios"] = sensibilidade_comparada(ds, cfg, nomes=("ridge",), cenarios=((0.9, 0.0),))
    md = relatorio.gerar(salvar_metricas(real, tmp_path)).read_text(encoding="utf-8")
    for txt in ("Só clima × com persistência", "só clima (modelo anterior, todas as linhas)", "com persistência (produção)",
                "Cobertura conformal real no holdout", "Sensibilidade a cenários, com e sem persistência", "memória do NDVI"):
        assert txt in md


def test_relatorio_sintetico_continua_sem_metricas(res, tmp_path):
    md = relatorio.gerar(salvar_metricas(res, tmp_path)).read_text(encoding="utf-8")
    assert "RMSE" not in md and "skill" not in md and "Só clima ×" not in md
