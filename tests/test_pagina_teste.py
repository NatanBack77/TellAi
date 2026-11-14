"""Página de teste do chat (GET /teste) e contador de gasto (GET /chat/gasto): sem rede, sem chave real."""
import json

from fastapi.testclient import TestClient

from src.api.main import app
from src.api import pagina_teste as pt

c = TestClient(app)


def test_pagina_carrega_e_traz_as_culturas():
    r = c.get("/teste")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "Sulco" in r.text and "milho" in r.text and "/chat" in r.text and "a avaliar com técnico local" in r.text.lower()
    assert "__CULTURAS__" not in r.text


def test_respostas_entram_por_textcontent_e_nao_como_html():
    html = c.get("/teste").text
    assert "innerHTML" not in html and "document.write" not in html and "eval(" not in html


def test_lista_de_culturas_nao_quebra_o_script():
    out = pt.renderizar({"x": "</script><img src=x onerror=alert(1)> & ' \""})
    assert "</script><img" not in out.split("const CULTURAS =")[1].split(";")[0]


def test_gasto_nao_vaza_chave(monkeypatch):
    r = c.get("/chat/gasto")
    assert r.status_code == 200
    d = r.json()
    assert {"chamadas_dia", "teto_chamadas_dia", "tokens_entrada_dia", "tokens_saida_dia"} <= set(d)
    assert "sk-" not in json.dumps(d)


def test_pagina_nao_esta_no_openapi():
    assert "/teste" not in c.get("/openapi.json").json()["paths"]
