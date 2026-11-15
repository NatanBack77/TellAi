import copy
import json

import numpy as np
import pandas as pd
import pytest

from src.modelos import relatorio
from src.modelos.cenarios import simular, treinar_para_cenarios
from src.modelos.entrada import DadosInvalidos, carregar_config
from src.modelos.features import construir_dataset
from src.modelos.preditivo import (
    avaliar, conformal_split, decidir_modelo, dividir_celulas_calibracao, importancia_contribuicoes,
    preparar_tabela_modelagem, quantil_conformal, salvar_metricas,
)
from src.modelos.sintetico import gerar_sinteticos


@pytest.fixture(scope="module")
def cfg():
    cfg = carregar_config()
    # dados SINTÉTICOS (anos 2005-2019): sem os anos fixos da produção (config.yaml); vale `holdout_anos` (últimos N anos presentes)
    cfg["preditivo"].pop("anos_treino", None), cfg["preditivo"].pop("anos_holdout", None)
    return cfg


@pytest.fixture(scope="module")
def dataset(cfg, tmp_path_factory):
    d = tmp_path_factory.mktemp("sint_cen")
    arqs = gerar_sinteticos(d, n_celulas=8, pontos_por_celula=2, ano_ini=2005, ano_fim=2019)
    return construir_dataset({k: pd.read_parquet(v) for k, v in arqs.items()}, cfg)


@pytest.fixture(scope="module")
def res(dataset, cfg):
    return avaliar(dataset, cfg, sintetico=True)


# --- conformal --------------------------------------------------------------------------
def test_quantil_conformal_valor_conhecido():
    r = np.arange(1, 10, dtype=float)          # n = 9; alpha 0.2 -> k = ceil(10*0.8) = 8
    assert quantil_conformal(r, 0.2) == 8.0
    assert quantil_conformal(r[:3], 0.05) == float("inf")   # amostra pequena => sem faixa
    assert quantil_conformal(np.array([]), 0.2) == float("inf")


def test_calibracao_em_celulas_distintas_e_deterministica(dataset, cfg):
    cels = dataset["celula_power"].unique()
    a = dividir_celulas_calibracao(cels, 0.25, 42)
    assert a == dividir_celulas_calibracao(cels, 0.25, 42)
    assert not set(a[0]) & set(a[1]) and set(a[0]) | set(a[1]) == set(map(str, cels))
    with pytest.raises(DadosInvalidos):
        dividir_celulas_calibracao(["a", "b"], 0.25, 42)


def test_conformal_split_sem_celula_compartilhada_entre_treino_calibracao_e_teste(dataset, cfg):
    d, tr_anos, _, cols = preparar_tabela_modelagem(dataset, cfg)
    treino = d[d["ano"].isin(tr_anos)]
    cels = sorted(treino["celula_power"].unique())
    teste = treino[treino["celula_power"] == cels[0]]
    out = conformal_split(treino[treino["celula_power"] != cels[0]], teste, cols, cfg, "ridge")
    assert not set(out["celulas_treino_proprio"]) & set(out["celulas_calibracao"])
    assert cels[0] not in out["celulas_treino_proprio"] + out["celulas_calibracao"]
    assert set(out["metas"]) == {"80", "90"}


def test_cobertura_90_maior_que_80_e_larguras_ordenadas(res):
    m = res["holdout_temporal"]["conformal"]["ridge"]["metas"]
    assert m["90"]["quantil"] >= m["80"]["quantil"]
    cv = res["cv_grupos"]["conformal"]["ridge"]
    assert cv["90"]["cobertura_media_ponderada"] >= cv["80"]["cobertura_media_ponderada"]
    assert len(cv["80"]["cobertura_por_fold"]) == res["divisao"]["n_folds"]


# --- decisão e explicação ----------------------------------------------------------------
def _fold(s):
    return {"modelos": {"xgboost": {"skill_vs_ridge": s}}}


def _hold(s, sc=0.1):
    return {"modelos": {"xgboost": {"skill_vs_ridge": s, "skill_vs_climatologia": sc},
                        "ridge": {"skill_vs_climatologia": sc}}}


def test_decisao_xgboost_so_se_consistente():
    assert decidir_modelo([_fold(.1), _fold(.2), _fold(.05)], _hold(.1))["modelo"] == "xgboost"
    assert decidir_modelo([_fold(.1), _fold(-.2), _fold(-.05)], _hold(.1))["modelo"] == "ridge"   # maioria negativa
    assert decidir_modelo([_fold(.1), _fold(.2), _fold(.05)], _hold(-.1))["modelo"] == "ridge"    # holdout negativo
    assert decidir_modelo([_fold(.5), _fold(-.1), _fold(-.1)], _hold(.1))["modelo"] == "ridge"    # média negativa


def test_decisao_avisa_se_nao_supera_climatologia():
    d = decidir_modelo([_fold(-.1)] * 3, _hold(-.1, sc=-0.2))
    assert d["modelo"] == "ridge" and "NÃO supera a climatologia" in d["aviso"]
    assert d["criterio_aprovado_pelo_usuario"] is True


def test_saida_traz_decisao_e_explicacao_explicativa(res, cfg):
    assert res["decisao"]["modelo"] in {"ridge", "xgboost"}
    assert res["explicacao"]["explicativo_apenas"] is True
    assert set(res["explicacao"]["importancia_media_abs"]) == set(res["features"])


def test_importancia_contribuicoes_ignora_feature_irrelevante(cfg):
    from xgboost import XGBRegressor
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"a": rng.normal(size=300), "b": rng.normal(size=300)})
    m = XGBRegressor(n_estimators=50, max_depth=2, random_state=0, n_jobs=1).fit(X, 3 * X["a"])
    imp = importancia_contribuicoes(m, X, ["a", "b"])["importancia_media_abs"]
    assert imp["a"] > 10 * imp["b"]


# --- vazamento / reprodutibilidade ------------------------------------------------------
def test_avaliacao_nao_depende_da_ordem_das_linhas(dataset, cfg, res):
    emb = dataset.sample(frac=1.0, random_state=1).reset_index(drop=True)
    outra = avaliar(emb, cfg, sintetico=True)
    a, b = res["holdout_temporal"]["modelos"]["ridge"], outra["holdout_temporal"]["modelos"]["ridge"]
    assert a["rmse"] == pytest.approx(b["rmse"], rel=1e-6)


def test_mudar_ndvi_do_holdout_nao_altera_metricas_do_treino(dataset, cfg, res):
    _, _, teste_anos, _ = preparar_tabela_modelagem(dataset, cfg)
    alt = dataset.copy()
    alt.loc[alt["ano"].isin(teste_anos), "ndvi"] += 3.0
    outra = avaliar(alt, cfg, sintetico=True)
    assert outra["cv_grupos"]["resumo"] == res["cv_grupos"]["resumo"]
    assert outra["cv_grupos"]["conformal"] == res["cv_grupos"]["conformal"]


def test_reprodutivel_conformal_e_decisao(dataset, cfg, res):
    outra = avaliar(copy.deepcopy(dataset), cfg, sintetico=True)
    assert outra["holdout_temporal"]["conformal"] == res["holdout_temporal"]["conformal"]
    assert outra["decisao"] == res["decisao"]
    assert outra["explicacao"] == res["explicacao"]


# --- cenários ----------------------------------------------------------------------------
@pytest.fixture(scope="module")
def mc(dataset, cfg):
    return treinar_para_cenarios(dataset, cfg, "ridge")


@pytest.fixture(scope="module")
def base(dataset, cfg):
    d, tr, _, cols = preparar_tabela_modelagem(dataset, cfg)
    return d[d["ano"].isin(tr)].head(40)


def test_cenario_neutro_sem_extrapolacao_e_com_faixa(mc, base):
    s = simular(mc, base)
    assert s["extrapolacao"] is False and isinstance(s["anomalia_ndvi_prevista"], float)
    lo, hi = s["faixa_incerteza"]["90"]
    assert lo < s["anomalia_ndvi_prevista"] < hi
    assert "não prevê o clima" in s["aviso"] and "causalidade" in s["aviso"] and s["limites"]


def test_menos_chuva_reduz_anomalia_prevista_no_sintetico(mc, base):
    """Fluxo: no sintético o NDVI cresce com a chuva por construção (não é resultado)."""
    neutro, seco = simular(mc, base), simular(mc, base, fator_chuva=0.9)
    if not seco["extrapolacao"]:
        assert seco["anomalia_ndvi_prevista"] < neutro["anomalia_ndvi_prevista"]


def test_extrapolacao_nao_devolve_numero(mc, base):
    s = simular(mc, base, fator_chuva=50.0)
    assert s["extrapolacao"] is True
    assert s["anomalia_ndvi_prevista"] is None and s["faixa_incerteza"] is None
    assert "Extrapolação não confiável" in s["mensagem"]
    assert any(f["feature"].startswith("chuva_ac_") for f in s["features_fora_da_faixa"])
    assert simular(mc, base, delta_tmax_c=40.0)["extrapolacao"] is True


def test_cenario_entradas_invalidas(mc, base):
    with pytest.raises(DadosInvalidos):
        simular(mc, base.iloc[0:0])
    with pytest.raises(ValueError):
        simular(mc, base, fator_chuva=-1)
    quebrada = base.copy()
    quebrada.iloc[0, quebrada.columns.get_loc(mc.cols[0])] = np.nan
    with pytest.raises(DadosInvalidos):
        simular(mc, quebrada)


# --- faixa ACI por estação ----------------------------------------------------------------
def test_faixa_aci_por_estacao_formato_e_finita(mc, base):
    assert mc.metodo_faixa == "aci" and "ACI por estação, gamma" in mc.metodo_descricao
    assert set(mc.quantis_estacao) == {"80", "90"}
    for v in mc.quantis_estacao.values():
        assert set(v) == {0, 1, 2, 3} and all(np.isfinite(q) and q >= 0 for q in v.values())
    s = simular(mc, base)
    assert "ACI por estação, gamma" in s["metodo_faixa"] and s["estacoes_base"] and s["faixa_por_estacao"]
    for k in ("80", "90"):
        lo, hi = s["faixa_incerteza"][k]
        assert lo <= s["anomalia_ndvi_prevista"] <= hi
    larg = {k: s["faixa_incerteza"][k][1] - s["faixa_incerteza"][k][0] for k in ("80", "90")}
    assert larg["90"] >= larg["80"]
    assert "causalidade" in s["aviso"] and "não prevê o clima" in s["aviso"]


def test_faixa_usa_a_estacao_da_base_e_a_mais_larga_se_mistura(mc, base):
    est = (base["slot"] // 6).clip(upper=3)
    uma = est.unique()[0]
    so_uma = simular(mc, base[est == uma])
    assert so_uma["estacoes_base"] == [int(uma)]
    lo, hi = so_uma["faixa_incerteza"]["80"]
    assert (hi - lo) / 2 == pytest.approx(mc.quantis_estacao["80"][int(uma)])
    mista = simular(mc, base)
    meia = (mista["faixa_incerteza"]["80"][1] - mista["faixa_incerteza"]["80"][0]) / 2
    assert meia == pytest.approx(max(mc.quantis_estacao["80"][f] for f in mista["estacoes_base"]))


def test_faixa_aci_reprodutivel_e_extrapolacao_sem_numero(dataset, cfg, mc, base):
    outro = treinar_para_cenarios(copy.deepcopy(dataset), cfg, "ridge")
    assert outro.quantis_estacao == mc.quantis_estacao
    s = simular(mc, base, fator_chuva=50.0)
    assert s["extrapolacao"] is True and s["faixa_incerteza"] is None and s["anomalia_ndvi_prevista"] is None


def test_faixa_aci_nao_depende_de_anos_futuros_ao_de_referencia(dataset, cfg, mc):
    from src.modelos.conformal_aci import aci_walk_forward
    a = aci_walk_forward(dataset, cfg, [2012, 2013], [2014], retornar_faixas=True)["faixas_finais"]
    alt = dataset.copy()
    alt.loc[alt["ano"] > 2014, "ndvi"] = 0.99
    b = aci_walk_forward(alt, cfg, [2012, 2013], [2014], retornar_faixas=True)["faixas_finais"]
    assert a["ano_referencia"] == 2014 and a["alpha_final"] == b["alpha_final"]
    for f in range(4):
        np.testing.assert_array_equal(a["residuos_ordenados"][f], b["residuos_ordenados"][f])
        assert np.all(np.diff(a["residuos_ordenados"][f]) >= 0)


def test_aci_com_retornar_faixas_nao_muda_as_metricas(dataset, cfg):
    from src.modelos.conformal_aci import aci_walk_forward
    a = aci_walk_forward(dataset, cfg, [2012, 2013], [2014, 2015])
    b = aci_walk_forward(dataset, cfg, [2012, 2013], [2014, 2015], retornar_faixas=True)
    assert "faixas_finais" not in a and {k: v for k, v in b.items() if k != "faixas_finais"} == a


def test_metodo_antigo_split_ainda_disponivel(dataset, cfg, base):
    antigo = treinar_para_cenarios(dataset, cfg, "ridge", metodo_faixa="split")
    s = simular(antigo, base)
    assert antigo.metodo_faixa == "split" and set(antigo.quantis) == {"80", "90"} and "faixa_por_estacao" not in s
    assert "split conformal" in s["metodo_faixa"]
    with pytest.raises(ValueError):
        treinar_para_cenarios(dataset, cfg, "ridge", metodo_faixa="outro")


def test_calibracao_insuficiente_vira_lacuna_sem_numero(cfg, tmp_path):
    arqs = gerar_sinteticos(tmp_path, n_celulas=8, pontos_por_celula=2, ano_ini=2010, ano_fim=2015)   # poucos anos para o ACI
    ds = construir_dataset({k: pd.read_parquet(v) for k, v in arqs.items()}, cfg)
    m = treinar_para_cenarios(ds, cfg, "ridge")
    assert any("ACI indisponível" in l for l in m.lacunas)
    d, tr, _, _ = preparar_tabela_modelagem(ds, cfg)
    s = simular(m, d[d["ano"].isin(tr)].head(20))
    assert s["extrapolacao"] is False and s["faixa_incerteza"] == {"80": None, "90": None}


# --- relatório ---------------------------------------------------------------------------
def test_relatorio_sintetico_nao_tem_metricas(res, tmp_path):
    caminho = salvar_metricas(res, tmp_path)
    md = relatorio.gerar(caminho).read_text(encoding="utf-8")
    assert relatorio.gerar(caminho).name == "SINTETICO_relatorio_modelos.md"
    assert "DADOS SINTÉTICOS" in md and "RMSE" not in md and "skill" not in md


def test_relatorio_real_tem_secoes(res, tmp_path):
    real = copy.deepcopy(res)
    real["dados_sinteticos"] = False
    caminho = salvar_metricas(real, tmp_path)
    assert caminho.name == "metricas.json"
    md = relatorio.gerar(caminho).read_text(encoding="utf-8")
    for secao in ("Métricas por fold", "Holdout temporal", "Cobertura", "Decisão XGBoost vs. Ridge", "Lacunas"):
        assert secao in md
    assert json.loads(caminho.read_text(encoding="utf-8"))["decisao"]["modelo"] in md
