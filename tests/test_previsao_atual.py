"""Previsão com os dados atuais (original + 2025+): modelo de treino NÃO muda, data do alvo vem dos dados, sem data duplicada,
clima final vazio vira lacuna e a previsão retrospectiva confere com o prospectivo 2025+ (modelos diferentes: ver docs/21/DADOS_2025_NA_PREVISAO.md)."""
import copy
import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.coleta.unir_2025 import garantir_atuais
from src.modelos import previsao as P
from src.modelos.entrada import RAIZ, DadosInvalidos, carregar_config, carregar_entradas
from src.modelos.features import construir_dataset
from src.modelos.preditivo import anos_explicitos, avaliar, preparar_tabela_modelagem
from src.modelos.sintetico import gerar_sinteticos

_P = RAIZ / "data/processed"
_REAL = all((_P / f).is_file() for f in ("clima_diario.parquet", "ndvi_16d.parquet", "clima_2025plus.parquet", "ndvi_2025plus.parquet",
                                         "modelos/metricas.json"))
pytestmark = pytest.mark.skipif(not _REAL, reason="parquets e metricas.json locais ausentes")


# ------------------------------------------------------------------ anos fixos no config (sintético, rápido)
def test_config_fixa_anos_de_treino_e_holdout():
    p = carregar_config()["preditivo"]
    tr, ho = anos_explicitos(p)
    assert tr == list(range(2001, 2022)) and ho == [2022, 2023, 2024]


def test_anos_fixos_nao_se_deslocam_com_dados_novos(tmp_path):
    cfg = carregar_config()
    cfg["preditivo"].update(anos_treino={"de": 2005, "ate": 2021}, anos_holdout={"de": 2022, "ate": 2024})
    ent26 = {k: pd.read_parquet(v) for k, v in gerar_sinteticos(tmp_path, n_celulas=3, pontos_por_celula=1, ano_ini=2005, ano_fim=2026).items()}
    ent24 = {k: d[d["data"] <= "2024-12-31"] for k, d in ent26.items()}      # a MESMA série, sem os dois anos novos
    a, tr_a, te_a, cols = preparar_tabela_modelagem(construir_dataset(ent24, cfg), cfg)
    b, tr_b, te_b, _ = preparar_tabela_modelagem(construir_dataset(ent26, cfg), cfg)
    assert te_a == te_b == [2022, 2023, 2024] and tr_a == tr_b == list(range(2005, 2022))
    assert b["ano"].max() == 2024                                     # 2025-2026 nunca entram na tabela de modelagem
    # a tabela de treino/teste tem de ser idêntica com ou sem 2025-2026 nos dados
    assert len(a) == len(b)
    pd.testing.assert_frame_equal(a[["ponto_id", "data", "anomalia_ndvi"] + cols].reset_index(drop=True),
                                  b[["ponto_id", "data", "anomalia_ndvi"] + cols].reset_index(drop=True))
    sem = copy.deepcopy(cfg)
    sem["preditivo"].pop("anos_treino"), sem["preditivo"].pop("anos_holdout")
    _, _, te_legado, _ = preparar_tabela_modelagem(construir_dataset(ent26, sem), sem)
    assert te_legado == [2024, 2025, 2026]                            # o comportamento antigo (últimos N presentes) deslocaria o holdout


def test_anos_fixos_ausentes_no_dado_sao_erro_explicito(tmp_path):
    cfg = carregar_config()
    ent = {k: pd.read_parquet(v) for k, v in gerar_sinteticos(tmp_path, n_celulas=3, pontos_por_celula=1, ano_ini=2010, ano_fim=2020).items()}
    with pytest.raises(DadosInvalidos, match="anos fixos"):
        preparar_tabela_modelagem(construir_dataset(ent, cfg), cfg)    # config pede 2001-2024: 2021+ não existem aqui
    c2 = copy.deepcopy(cfg)
    c2["preditivo"].pop("anos_holdout")
    with pytest.raises(DadosInvalidos, match="juntos"):
        anos_explicitos(c2["preditivo"])


# ------------------------------------------------------------------ metricas.json não muda (regressão numérica, dados reais)
@pytest.fixture(scope="module")
def avaliacao_real():
    cfg = carregar_config()
    return avaliar(construir_dataset(carregar_entradas(cfg), cfg), cfg)    # SÓ arquivos originais (sem 2025+)


def test_metricas_json_nao_muda_com_anos_fixos(avaliacao_real):
    """Mesmos n, anos, RMSE/skill e cobertura do arquivo gravado. Ridge, climatologia, ACI e contagens: iguais (1e-9).
    XGBoost: tolerância pequena e declarada, porque o arquivo gravado em 2026-11-13 já difere do código atual em ~5e-6 de RMSE
    (xgboost 3.4.1; o código ANTES desta mudança dá o mesmo que o de agora, medido em 2026-11-14)."""
    m = json.loads((_P / "modelos/metricas.json").read_text(encoding="utf-8"))
    n = avaliacao_real
    assert n["divisao"] == m["divisao"] and n["divisao"]["anos_teste"] == [2022, 2023, 2024] and n["divisao"]["anos_treino"][-1] == 2021
    hm, hn = m["holdout_temporal"], n["holdout_temporal"]
    assert (hn["n_treino"], hn["n_teste"]) == (hm["n_treino"], hm["n_teste"]) == (62318, 8052)
    assert hn["por_ano"].keys() == hm["por_ano"].keys() and all(hn["por_ano"][a]["n"] == hm["por_ano"][a]["n"] for a in hm["por_ano"])
    for mod, tol in (("climatologia", 1e-9), ("ridge", 1e-9), ("xgboost", 2e-4)):
        for k in ("rmse", "mae", "skill_vs_climatologia"):
            assert hn["modelos"][mod][k] == pytest.approx(hm["modelos"][mod][k], abs=tol), (mod, k)
        for meta in ("80", "90"):
            tolc = 1e-9 if mod != "xgboost" else 3e-3
            assert hn["conformal"][mod]["metas"][meta]["cobertura"] == pytest.approx(hm["conformal"][mod]["metas"][meta]["cobertura"], abs=tolc)
    for meta in ("80", "90"):          # ACI por estação (Ridge): igual
        for k in ("cobertura", "pior_ano", "pior_estacao"):
            assert n["conformal_aci"]["metas"][meta][k] == pytest.approx(m["conformal_aci"]["metas"][meta][k], abs=1e-9)
    assert n["decisao"]["modelo"] == m["decisao"]["modelo"] == "xgboost"


# ------------------------------------------------------------------ previsão com dados atuais
@pytest.fixture(scope="module")
def ctx():
    return P.carregar_ou_treinar()


def test_modelo_treina_so_nos_anos_fixos_e_inferencia_usa_dados_atuais(ctx):
    assert ctx["treino_anos"] == list(range(2001, 2022)) and ctx["teste_anos"] == [2022, 2023, 2024]
    assert ctx["arquivos_inferencia"].startswith("clima_atual/ndvi_atual") and ctx["lacuna_dados"] is None
    novo_n = pd.read_parquet(_P / "ndvi_2025plus.parquet")
    novo_c = pd.read_parquet(_P / "clima_2025plus.parquet")
    assert ctx["entradas"]["ndvi"]["data"].max() == novo_n["data"].max() and ctx["entradas"]["clima"]["data"].max() == novo_c["data"].max()
    assert ctx["ds"]["ano"].max() >= 2026 and ctx["mc"] is not None
    orig = pd.read_parquet(_P / "ndvi_16d.parquet")
    assert orig["data"].max() < pd.Timestamp("2025-01-01")             # os originais (treino) continuam terminando em 2024


def test_alvo_e_o_composto_seguinte_ao_ultimo_valido_e_vem_dos_dados(ctx):
    nd = ctx["entradas"]["ndvi"]
    aceitos = set(carregar_config()["ndvi"]["confiabilidade_aceita"])
    for pid in ("quixada_ce", "sobral_ce", "petrolina_pe", "fortaleza_ce"):
        r = P.prever_um_composto(pid, ctx)
        ult = pd.Timestamp(r["ultimo_composto_observado"])
        linha = nd[(nd["ponto_id"] == pid) & (nd["data"] == ult)].iloc[0]
        assert linha["confiabilidade"] in aceitos and not np.isnan(linha["ndvi"])        # é observação válida do arquivo
        assert ult > pd.Timestamp("2025-12-31")                                          # não é mais o fim de 2024
        assert pd.Timestamp(r["composto_alvo"]) == P._proxima_data(ult) and pd.Timestamp(r["composto_alvo"]) > nd[nd["ponto_id"] == pid]["data"].where(
            nd["confiabilidade"].isin(aceitos) & nd["ndvi"].notna()).max()
        assert r["clima_ate"] < r["composto_alvo"] <= r["clima_disponivel_ate"] or r["anomalia_ndvi_prevista"] is None
    # a data do alvo acompanha o dado: tirando o último composto válido de um ponto, o alvo recua um composto
    ent = copy.deepcopy(ctx["entradas"])
    r0 = P.prever_um_composto("quixada_ce", ctx)
    ent["ndvi"] = ent["ndvi"][~((ent["ndvi"]["ponto_id"] == "quixada_ce") & (ent["ndvi"]["data"] >= pd.Timestamp(r0["ultimo_composto_observado"])))]
    c2 = {**ctx, "entradas": ent, "ds": construir_dataset(ent, ctx["cfg"])}
    r1 = P.prever_um_composto("quixada_ce", c2)
    assert r1["composto_alvo"] == r0["ultimo_composto_observado"] and r1["ultimo_composto_observado"] < r0["ultimo_composto_observado"]


def test_sobral_nao_tem_mais_data_duplicada_nem_com_dados_originais(ctx):
    """Causa: a linha-alvo era acrescentada à série de clima mesmo quando o alvo já estava nela (último composto válido de sobral_ce =
    2024-12-02; 2024-12-18 tem confiabilidade 3). Não era defeito da coleta nem do arquivo: 0 duplicatas nos parquets."""
    r = P.prever_um_composto("sobral_ce", ctx)
    assert r["anomalia_ndvi_prevista"] is not None and r.get("lacuna") is None
    ent = carregar_entradas(ctx["cfg"])                                                    # só originais: alvo 2024-12-18 dentro do clima
    c2 = {**ctx, "entradas": ent, "ds": construir_dataset(ent, ctx["cfg"])}
    ro = P.prever_um_composto("sobral_ce", c2)
    assert ro["ultimo_composto_observado"] == "2024-12-02" and ro["composto_alvo"] == "2024-12-18" and ro["anomalia_ndvi_prevista"] is not None
    erros = [p for p in sorted(ctx["ds"]["ponto_id"].unique()) if _erro(p, c2)]
    assert erros == []                                                                     # nenhum dos 195 pontos levanta mais DadosInvalidos


def _erro(pid, c):
    try:
        P.prever_um_composto(pid, c)
        return False
    except DadosInvalidos:
        return True


def test_clima_final_vazio_vira_lacuna_com_motivo_e_nao_e_preenchido(ctx):
    r0 = P.prever_um_composto("quixada_ce", ctx)
    alvo = pd.Timestamp(r0["composto_alvo"])
    ent = copy.deepcopy(ctx["entradas"])
    cl = ent["clima"]
    m = (cl["ponto_id"] == "quixada_ce") & (cl["data"] >= alvo - pd.Timedelta(days=3))        # os 3 últimos dias que o modelo precisa viram NaN
    cl.loc[m, ["chuva_mm", "tmax_c", "tmin_c"]] = np.nan
    r = P.prever_um_composto("quixada_ce", {**ctx, "entradas": ent})
    assert r["anomalia_ndvi_prevista"] is None and r["faixa_incerteza"] is None and "exige clima" in r["lacuna"]
    assert r["clima_disponivel_ate"] == str((alvo - pd.Timedelta(days=4)).date())
    # buraco interno numa janela (cobertura exigida de 90% nas médias, 100% nas somas): sem número, motivo declarado
    ent2 = copy.deepcopy(ctx["entradas"])
    cl2 = ent2["clima"]
    cl2.loc[(cl2["ponto_id"] == "quixada_ce") & (cl2["data"] == alvo - pd.Timedelta(days=10)), "chuva_mm"] = np.nan
    r2 = P.prever_um_composto("quixada_ce", {**ctx, "entradas": ent2})
    assert r2["anomalia_ndvi_prevista"] is None and "features ausentes" in r2["lacuna"]


def test_ultimos_dias_do_clima_do_arquivo_sao_nan_e_o_aviso_de_provisorio_aparece(ctx):
    cl = ctx["entradas"]["clima"]
    q = cl[cl["ponto_id"] == "quixada_ce"]
    fim_arquivo = q["data"].max()
    ok = q.dropna(subset=["chuva_mm", "tmax_c"])["data"].max()
    r = P.prever_um_composto("quixada_ce", ctx)
    assert r["clima_disponivel_ate"] == str(ok.date()) and ok <= fim_arquivo
    assert any("provisórios" in x and "hipótese" in x for x in r["lacunas"])


def test_previsao_nao_vaza_clima_nem_ndvi_do_alvo_em_diante(ctx):
    r0 = P.prever_um_composto("quixada_ce", ctx)
    alvo = pd.Timestamp(r0["composto_alvo"])
    ent = copy.deepcopy(ctx["entradas"])
    cl = ent["clima"]
    cl.loc[(cl["ponto_id"] == "quixada_ce") & (cl["data"] >= alvo), ["chuva_mm", "tmax_c"]] = 999.0
    r = P.prever_um_composto("quixada_ce", {**ctx, "entradas": ent})
    assert r["anomalia_ndvi_prevista"] == r0["anomalia_ndvi_prevista"]


def test_cache_com_arquivos_atuais_e_impressao_digital(ctx):
    c = P.carregar_ou_treinar()
    assert c["origem"] == "cache em disco" and c["impressao"] == ctx["impressao"]
    cfg = carregar_config()
    nome, _ = P.nome_do_modelo()
    a = P._impressao(cfg, nome)
    assert a == P._impressao(cfg, nome) and c["impressao_dados_atuais"]
    cfg2 = copy.deepcopy(cfg)
    cfg2["preditivo"]["anos_holdout"] = {"de": 2022, "ate": 2023}
    assert P._impressao(cfg2, nome) != a                                        # mudar os anos fixos invalida o modelo em cache
    # a impressão do modelo depende só do que treina; a dos arquivos atuais é à parte
    assert P._impressao(cfg, nome, ("clima_atual", "ndvi_atual"), com_config=False) == c["impressao_dados_atuais"]


def test_garantir_atuais_e_chamado_sem_precisar_de_rede():
    garantir_atuais(carregar_config())
    assert (_P / "clima_diario_atual.parquet").is_file() and (_P / "ndvi_16d_atual.parquet").is_file()


# ------------------------------------------------------------------ conferência com o prospectivo 2025+
def test_previsao_um_passo_confere_com_prospectivo_2025_nao_igual_porque_o_modelo_e_outro(ctx):
    """Prospectivo: modelo congelado treinado 2001-2024, climatologia 2001-2024. Produção: treino 2001-2021. Compara em unidades de NDVI."""
    csv = pd.read_csv(RAIZ / "experimentos/prospectivo_2025/previsoes_2025plus.csv", parse_dates=["data"])
    amostra = csv.sort_values(["ponto_id", "data"]).iloc[::150]
    cfg, ds = ctx["cfg"], ctx["ds"]
    from src.modelos.features import adicionar_anomalia
    c24 = adicionar_anomalia(ds, list(range(2001, 2025)), cfg)[["ponto_id", "data", "ndvi_clim"]]
    c21 = adicionar_anomalia(ds, ctx["treino_anos"], cfg)[["ponto_id", "data", "ndvi_clim"]]
    dif, a, b = [], [], []
    for _, x in amostra.iterrows():
        r = P.prever_um_composto(x["ponto_id"], ctx, composto_alvo=x["data"])
        assert r["anomalia_ndvi_prevista"] is not None and r["composto_alvo"] == str(x["data"].date())
        k = (c21["ponto_id"] == x["ponto_id"]) & (c21["data"] == x["data"])
        l24 = c24[(c24["ponto_id"] == x["ponto_id"]) & (c24["data"] == x["data"])]["ndvi_clim"].iloc[0]
        a.append(c21[k]["ndvi_clim"].iloc[0] + r["anomalia_ndvi_prevista"])
        b.append(l24 + x["p_xgb"])
    a, b = np.array(a), np.array(b)
    assert len(a) > 30 and np.mean(np.abs(a - b)) < 0.02 and np.corrcoef(a, b)[0, 1] > 0.99   # medido no total (5.147 linhas): 0,0061 e 0,9991


def test_arquivo_de_comparacao_do_experimento_bate_com_o_prospectivo():
    j = json.loads((RAIZ / "experimentos/prospectivo_2025/comparacao_pipeline_novo.json").read_text(encoding="utf-8"))
    assert j["linhas_em_comum"] == j["linhas_csv_prospectivo"] == j["linhas_pipeline_novo_2025plus"] == 5147
    assert j["skill_prospectivo_vs_clim24"] == pytest.approx(0.254, abs=1e-3) and j["amostra_prever_um_composto"]["dif_max_abs_vs_lote"] < 1e-9


# ------------------------------------------------------------------ API
def test_api_previsao_devolve_data_nova_e_campos_de_sempre():
    from src.api.main import app
    c = TestClient(app)
    j = c.get("/modelo/previsao/quixada_ce").json()
    assert j["composto_alvo"] > "2026-01-01" and j["ultimo_composto_observado"] < j["composto_alvo"] and j["clima_ate"] < j["composto_alvo"]
    assert j["dados_inferencia"].startswith("clima_atual/ndvi_atual") and j["anos_treino"] == [2001, 2021]
    assert j["anomalia_ndvi_prevista"] is not None and set(j["faixa_incerteza"]) == {"80", "90"} and j["limites_declarados"] and j["aviso"]
    s = c.get("/modelo/previsao/sobral_ce")
    assert s.status_code == 200 and s.json()["anomalia_ndvi_prevista"] is not None            # antes: 503 (data duplicada)
    assert c.get("/modelo/previsao/fortaleza_ce").json()["lacuna"].startswith("compostos anteriores não consecutivos")
    assert c.get("/modelo/previsao/nao_existe").status_code == 404
