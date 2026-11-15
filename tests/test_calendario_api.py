"""Rotas POST /calendario (src/api/rota_calendario.py) e POST /conversa com `plantios`, montadas num app à parte (o `main.py` não é editado aqui).
Sem rede, sem IA (modo template). Hoje = 14/11/2026 (injetado na rota)."""
import json
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import rota_calendario as RC
from src.api.rota_calendario import router as rota_calendario
from src.api.rota_conversa import router as rota_conversa

PID = "quixada_ce"
HOJE = date(2026, 11, 14)


@pytest.fixture(scope="module")
def cli():
    app = FastAPI()
    app.include_router(rota_calendario)
    app.include_router(rota_conversa)
    RC._hoje = lambda: HOJE
    yield TestClient(app)


def test_calendario_devolve_o_calculo_e_os_fatos_com_origem(cli):
    r = cli.post("/calendario", json={"ponto_id": PID, "plantios": [{"cultura": "milho", "quando": {"mes": 2, "parte": "comeco"}},
                                                                     {"cultura": "feijao_caupi", "quando": "2026-03-10", "ciclo_dias": 70},
                                                                     {"cultura": "sorgo", "quando": {"data": "2026-12-01"}}], "proximas": False})
    assert r.status_code == 200
    j = r.json()
    assert j["hoje"] == "2026-11-14" and [p["status"] for p in j["plantios"]] == ["ciclo_concluido", "ciclo_concluido", "planejamento"]
    milho, caupi, sorgo = j["plantios"]
    assert milho["ciclo"]["fonte"] == "fao" and milho["ciclo"]["dias_ref"] == 140 and milho["quando"]["precisao"] == "decendio"
    assert milho["zarc"]["situacao"] == "fora" and milho["chuva"]["n_anos"] >= 10 and "mm" in json.dumps(milho["chuva"]) and milho["verde"]["disponivel"]
    assert caupi["ciclo"]["fonte"] == "informado" and caupi["colheita"]["unica"] is True and caupi["zarc"]["situacao"] == "dentro"
    assert sorgo["zarc"]["situacao"] == "sem_zoneamento" and "chuva" not in sorgo and sorgo["dias_para_plantar"] == 17
    assert j["fatos"] and all(f["origem"] and f["id"] and f["plantio"] in (0, 1, 2) for f in j["fatos"])
    assert "quixadá" not in json.dumps(j["fatos"], ensure_ascii=False).lower() and PID not in json.dumps(j["fatos"])
    assert len(j["limites"]) == 3


def test_calendario_valida_o_schema_com_422(cli):
    base = {"ponto_id": PID, "plantios": [{"cultura": "milho", "quando": {"mes": 2}}]}
    assert cli.post("/calendario", json={**base, "proximas": False}).status_code == 200
    ruins = [{**base, "ponto_id": "nao_existe_xx"}, {**base, "plantios": []}, {**base, "plantios": [{"cultura": "melancia", "quando": {"mes": 2}}]},
             {**base, "plantios": [{"cultura": "milho", "quando": {"mes": 13}}]}, {**base, "plantios": [{"cultura": "milho", "quando": {"mes": 2}, "nome": "x"}]},
             {**base, "plantios": [{"cultura": "milho", "quando": {"mes": 2}, "ciclo_dias": 3}]}, {**base, "plantios": [{"cultura": "milho", "quando": {"mes": 2, "data": "2026-02-01"}}]},
             {**base, "hoje": "2020-01-01"}, {**base, "proibidas": ["melancia"]}, {**base, "plantios": [{"cultura": "milho", "quando": {"de": "2026-03-07", "ate": "2026-03-01"}}]},
             {**base, "plantios": [{"cultura": "milho", "quando": {"mes": 2}}] * 13}]
    codigos = [cli.post("/calendario", json=r).status_code for r in ruins]
    assert codigos == [404] + [422] * 10, codigos


def test_calendario_data_impossivel_vira_esclarecimento_e_nao_quebra(cli):
    r = cli.post("/calendario", json={"ponto_id": PID, "plantios": [{"cultura": "milho", "quando": {"data": "2029-01-01"}}], "proximas": False})
    p = r.json()["plantios"][0]
    assert r.status_code == 200 and p["status"] == "esclarecimento" and "longe" in p["esclarecimento"] and "chuva" not in p


def test_calendario_proximas_usa_a_matriz_e_as_regras_do_agricultor(cli):
    r = cli.post("/calendario", json={"ponto_id": PID, "plantios": [{"cultura": "feijao_caupi", "quando": {"mes": 3}}], "proibidas": ["milho"]})
    pr = r.json()["plantios"][0]["proximas"]
    assert pr["disponivel"] and "milho" not in pr["favoraveis"] and "milho" in pr["nao_quer"] and pr["origem"].startswith("src.culturas.matriz_rotacao")


def test_conversa_aceita_plantios_no_estado_e_no_perfil_sem_quebrar_o_contrato(cli):
    pl = {"cultura": "milho", "quando": {"mes": 2, "parte": "comeco"}, "ciclo_dias": None, "manejo": "sequeiro"}
    r = cli.post("/conversa", json={"mensagem": "como choveu?", "ponto_id": PID, "estado": {"plantios": [pl]}})
    j = r.json()
    assert r.status_code == 200 and j["acao"] == "responder" and "choveram" in j["resposta"] and j["calendario"]["tema"] == "chuva"
    assert j["estado"]["plantios"] == [pl] and j["pergunta"] and j["pede"] == "confirmacao" and j["fontes"] and j["assistente"].startswith("Assistente automático")
    r2 = cli.post("/conversa", json={"mensagem": "como choveu?", "ponto_id": PID, "perfil": {"plantios": [pl]}})
    assert r2.status_code == 200 and r2.json()["calendario"]["plantio"]["cultura"] == "milho"
    # o contrato antigo segue igual
    ant = cli.post("/conversa", json={"mensagem": "o que dá para plantar aqui?", "ponto_id": PID})
    assert ant.status_code == 200 and ant.json()["calendario"] is None and ant.json()["pede"] == "foco"


def test_conversa_plantios_fora_do_schema_sao_422(cli):
    ruim = {"cultura": "melancia", "quando": {"mes": 2}}
    assert cli.post("/conversa", json={"mensagem": "oi", "estado": {"plantios": [ruim]}}).status_code == 422
    assert cli.post("/conversa", json={"mensagem": "oi", "perfil": {"plantios": [ruim]}}).status_code == 422
    assert cli.post("/conversa", json={"mensagem": "oi", "perfil": {"plantios": [{"cultura": "milho", "quando": {"mes": 2}, "nome": "Zé"}]}}).status_code == 422
    assert cli.post("/conversa", json={"mensagem": "oi", "estado": {"plantios": "milho"}}).status_code == 422


def test_conversa_passo_a_passo_pela_api_ate_a_resposta(cli):
    est = None
    for msg in ("plantei milho em março", "no meio", "120 dias", "sim"):
        j = cli.post("/conversa", json={"mensagem": msg, "ponto_id": PID, "estado": est}).json()
        est = j["estado"]
    assert j["acao"] == "responder" and est["plantios"][0]["ciclo_dias"] == 120 and est["plantios"][0]["quando"]["parte"] == "meio"
    assert "pelo ciclo que você informou" in j["resposta"].lower() and j["calendario"]["indice"] == 0
