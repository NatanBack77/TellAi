"""Rota POST /conversa (src/api/rota_conversa.py) montada num app à parte: o `main.py` não é editado aqui. SEM rede, SEM IA (modo template)."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.rota_conversa import router

PID = "quixada_ce"


@pytest.fixture(scope="module")
def cli():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_rodada_a_rodada_com_o_estado_devolvido(cli):
    r = cli.post("/conversa", json={"mensagem": "o que dá para plantar aqui?"})
    assert r.status_code == 200 and r.json()["acao"] == "perguntar" and r.json()["pede"] == "municipio"
    r2 = cli.post("/conversa", json={"mensagem": "o que dá para plantar aqui?", "ponto_id": PID, "estado": r.json()["estado"]})
    j = r2.json()
    assert r2.status_code == 200 and j["acao"] == "responder" and j["pede"] == "foco" and len(j["chips"]) == 4 and j["origem"] == "template"
    assert j["assistente"].startswith("Assistente automático") and j["fontes"] and all(f["origem"] for f in j["fontes"])
    r3 = cli.post("/conversa", json={"mensagem": j["chips"][0]["texto"], "ponto_id": PID, "estado": json.loads(json.dumps(j["estado"]))})
    assert r3.json()["estado"]["foco"] == "agua" and r3.json()["pergunta"] is None


def test_perfil_e_cultura_atual_validados(cli):
    ok = cli.post("/conversa", json={"mensagem": "quero economizar água", "ponto_id": PID, "perfil": {"prioridade": "agua"}})
    assert ok.status_code == 200
    assert cli.post("/conversa", json={"mensagem": "oi", "ponto_id": "nao_existe_xx"}).status_code == 404
    assert cli.post("/conversa", json={"mensagem": "oi", "cultura_atual": "melancia"}).status_code == 422
    assert cli.post("/conversa", json={"mensagem": "oi", "perfil": {"municipio": "Quixadá"}}).status_code == 422       # perfil de chat não leva município
    assert cli.post("/conversa", json={"mensagem": "oi", "perfil": {"campo_inventado": 1}}).status_code == 422
    assert cli.post("/conversa", json={"mensagem": "oi", "campo_extra": 1}).status_code == 422
    assert cli.post("/conversa", json={"mensagem": ""}).status_code == 422


def test_estado_adulterado_nao_derruba_a_rota(cli):
    r = cli.post("/conversa", json={"mensagem": "milho e feijão de corda", "ponto_id": PID,
                                    "estado": {"culturas": ["../x", "milho"], "pendente": "executar", "turnos": "muitos"}})
    assert r.status_code == 200 and r.json()["estado"]["culturas"] in (["milho", "feijao_caupi"], ["milho"])
