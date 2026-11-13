import pytest
from fastapi.testclient import TestClient

from src.api.main import app

c = TestClient(app)


def test_saude_e_municipios():
    assert c.get("/saude").json()["status"] in ("ok", "parcial")
    m = c.get("/municipios").json()
    assert len(m) == 195 and set(m[0]) == {"ponto_id", "lat", "lon", "celula_power"}


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


def test_limites_e_previsao_501():
    j = c.get("/limites").json()
    assert "xgboost" in j["holdout_temporal"]["modelos"]
    assert c.get("/modelo/previsao/quixada_ce").status_code == 501


def test_evidencias_vazio():
    r = c.get("/evidencias", params={"q": "zzzqqq xxxyyy"})
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.json()["sem_evidencia"] is True
