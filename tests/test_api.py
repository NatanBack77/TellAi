import pytest
from fastapi.testclient import TestClient

from src.api.main import app

c = TestClient(app)


def test_saude_e_municipios():
    assert c.get("/saude").json()["status"] in ("ok", "parcial")
    m = c.get("/municipios").json()
    assert len(m) == 195 and set(m[0]) == {"ponto_id", "nome", "lat", "lon", "celula_power", "ibge"}


def test_diagnostico():
    pid = c.get("/municipios").json()[0]["ponto_id"]
    r = c.get(f"/diagnostico/{pid}").json()
    assert {"solo_nu", "estresse", "veranicos", "tendencia", "confianca", "lacunas"} <= set(r)
    assert c.get("/diagnostico/nao_existe").status_code == 404


def test_cenarios_contrato_e_renda():
    body = {"ponto_id": "quixada_ce", "cultura_atual": "milho", "prioridade": "renda", "n_sorteios": 500}
    r = c.post("/cenarios", json=body)
    assert r.status_code == 200
    cens = r.json()["cenarios"]
    assert len(cens) == 3
    for k in ("local", "cultura_atual", "rotacao", "score", "faixa_incerteza", "criterios", "lacunas",
              "riscos_revisao_local", "trechos", "janela_plantio"):
        assert k in cens[0]
    assert any("renda" in l for l in cens[0]["lacunas"])
    sem = c.post("/cenarios", json={**body, "prioridade": "sem"}).json()["cenarios"]
    assert [x["rotacao"] for x in sem] == [x["rotacao"] for x in cens]   # renda não altera ranking


def test_cenarios_validacao():
    assert c.post("/cenarios", json={"ponto_id": "quixada_ce", "cultura_atual": "x", "prioridade": "sem"}).status_code == 422
    assert c.post("/cenarios", json={"ponto_id": "quixada_ce", "cultura_atual": "milho", "prioridade": "sem",
                                     "extra": 1}).status_code == 422


def test_limites():
    j = c.get("/limites").json()
    assert "xgboost" in j["holdout_temporal"]["modelos"]


def test_previsao_um_composto_com_faixa_e_limites():
    r = c.get("/modelo/previsao/quixada_ce")
    assert r.status_code == 200
    j = r.json()
    assert j["composto_alvo"] > j["ultimo_composto_observado"] and j["clima_ate"] < j["composto_alvo"]
    assert j["anomalia_ndvi_prevista"] is not None and set(j["faixa_incerteza"]) == {"80", "90"}
    lo, hi = j["faixa_incerteza"]["90"]
    assert lo < j["anomalia_ndvi_prevista"] < hi
    assert "1 composto" in j["limites_declarados"][0] and "ACI" in j["metodo_faixa"]


def test_previsao_sem_persistencia_vira_lacuna_e_ponto_inexistente_404():
    j = c.get("/modelo/previsao/fortaleza_ce").json()   # compostos anteriores não consecutivos nos dados
    assert j["anomalia_ndvi_prevista"] is None and j["faixa_incerteza"] is None and "consecutivos" in j["lacuna"]
    assert c.get("/modelo/previsao/nao_existe").status_code == 404


def test_solo_estimado_e_lacuna():
    j = c.get("/solo/quixada_ce").json()
    assert j["estimado"]["textura"] in ("arenoso", "médio", "argiloso") and "SoilGrids" in j["aviso"] + str(j["estimado"])
    assert c.get("/solo/nao_existe").status_code == 404


def test_zarc_janela_e_lacuna():
    j = c.get("/zarc/quixada_ce/milho", params={"risco": 30, "solo": "medio"}).json()
    assert j["geocodigo_ibge"] == 2311306 and len(j["decendios_permitidos"]) == 36
    assert j["n_decendios_permitidos"] == sum(j["decendios_permitidos"])
    assert c.get("/zarc/quixada_ce/milho", params={"risco": 25}).status_code == 422
    assert c.get("/zarc/quixada_ce/cultura_x").status_code == 422
    sob = c.get("/zarc/sobral_ce/milho").json()           # sem código IBGE: lacuna explícita, não janela inventada
    assert sob["decendios_permitidos"] is None and "IBGE" in sob["motivo"]


def test_rotacao_tres_safras():
    body = {"ponto_id": "quixada_ce", "cultura_atual": "milho", "prioridade": "solo", "n_sorteios": 200}
    j = c.post("/rotacao", json=body).json()
    assert j["horizonte_safras"] == 3 and len(j["estrategias"]) == 3 and j["suposicoes"]
    assert c.post("/rotacao", json={**body, "rotacao_atual": ["feijao_caupi", "milho", "milho"]}).status_code == 422
    assert c.post("/rotacao", json={**body, "n_sorteios": 5}).status_code == 422


def test_cenario_de_clima_limites_e_resposta():
    body = {"ponto_id": "quixada_ce", "cultura_atual": "milho", "fator_chuva": 0.8, "delta_t": 1.0}
    j = c.post("/cenarios/clima", json=body).json()
    assert j["linhas"] and isinstance(j["extrapolacao"], bool) and "não previsão" in j["aviso"]
    assert c.post("/cenarios/clima", json={**body, "fator_chuva": 0.2}).status_code == 422    # fora dos limites do app


def test_plano_milp_e_proposta():
    j = c.post("/plano", json={"ponto_id": "quixada_ce", "cultura_atual": "milho", "n_sorteios": 20}).json()
    assert j["status"] == "proposta" and j["top"] and "PROPOSTA" in j["aviso"]
    assert all(0 < x["p_otima"] <= 1 for x in j["top"])


def test_evidencias_vazio():
    r = c.get("/evidencias", params={"q": "zzzqqq xxxyyy"})
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.json()["sem_evidencia"] is True
