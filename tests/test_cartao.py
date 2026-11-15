"""AP1 (cartão do município) e mapa (zoom órbita -> município, fundo liso). Dados REAIS do repositório; pulam se faltarem."""
import json
import re
import time
from pathlib import Path

import pandas as pd
import pytest

from src.app import cartao as CT
from src.app import mapa_vista as MV
from src.app import mvp as M

RAIZ = Path(__file__).resolve().parents[1]
APP = str(RAIZ / "src/app/app.py")
pytestmark = pytest.mark.skipif(not (RAIZ / "data/processed/clima_diario.parquet").is_file(), reason="dados locais ausentes")


@pytest.fixture(scope="module")
def cartao_quixada():
    calc = M.calcular("quixada_ce", "milho", "sem")
    rot = M.calcular_rotacao("quixada_ce", "milho", "sem", n_sorteios=800)
    return CT.montar_cartao("quixada_ce", "milho", "sem", calc=calc, rotacao=rot), calc, rot


def _numeros(txt: str) -> list[float]:
    return [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:,\d+)?", txt)]


def test_cartao_tem_lacunas_empate_aviso_e_nao_promete(cartao_quixada):
    c, _, rot = cartao_quixada
    t = CT.cartao_texto(c)
    assert "LACUNA" in t and "EMPATE TÉCNICO" in t and t.rstrip().endswith("A avaliar com técnico local.")
    assert "empate técnico com" in t and "O que levar ao técnico" in t and "Melhor janela de plantio" in t and "solo nu" in t.lower()
    assert "Quixadá (CE)" in t                                         # nome oficial (D4)
    assert "rende mais" not in t.lower() and "garante" not in t.lower() and "lucro" in t         # só negando ("nem de lucro")
    for e in rot["estrategias"]:                                       # os 3 caminhos aparecem, com a sequência
        assert " > ".join(e["nomes"]) in t


def test_cartao_nenhum_numero_fora_dos_dados(cartao_quixada):
    """Todo número do texto aparece nos dados de origem (diagnóstico, janela, rotação, risco, solo, pontos), arredondado ou como %."""
    c, calc, rot = cartao_quixada
    d = M.diagnostico_local("quixada_ce")
    from src.app import secao_risco_solo as SRS
    fontes = json.dumps({"rot": rot, "calc_janela": M.vulnerabilidade_cultura_atual("quixada_ce", "milho", calc, d),
                         "solo": M.solo_estimado("quixada_ce"), "risco": SRS.secao_risco_solo("quixada_ce"),
                         "pt": M.carregar_pontos().set_index("ponto_id").loc["quixada_ce"][["lat", "lon"]].to_dict(),
                         "frases": [d["solo_nu"]["frase"], d["estresse_frase"], d["confianca_nota"]]}, default=str, ensure_ascii=False)
    permitidos = _numeros(fontes.replace(".", ","))                     # números do JSON (ponto decimal -> vírgula)
    # 'empate técnico com N outras sequências': N é a CONTAGEM de `empate_tecnico_com` de cada estratégia (cartao.py), derivada dos dados e não
    # escrita neles; com a matriz de rotação nova (7bb3e12d) o empate passou a ter dezenas de sequências (79), e a contagem antes só coincidia por acaso.
    permitidos += [float(len(e.get("empate_tecnico_com") or [])) for e in rot["estrategias"]]
    permitidos += [x * 100 for x in permitidos]
    permitidos += [abs(x) for x in permitidos]
    texto = CT.cartao_texto(c)
    for n in _numeros(texto):
        assert any(abs(n - p) <= 0.51 for p in permitidos), f"número {n} do cartão não está nos dados"


def test_cartao_ponto_com_poucos_pixels_tem_aviso_proprio():
    c = CT.montar_cartao("petrolina_pe", "milho", "sem")
    t = CT.cartao_texto(c)
    assert "Poucos pixels" in t and "LACUNA" in t and "A avaliar com técnico local." in t


def test_html_e_pdf_de_uma_folha(cartao_quixada):
    c = cartao_quixada[0]
    h = CT.cartao_html(c)
    assert h.startswith("<!doctype html>") and "@page" in h and "<script" not in h and "http" not in h
    assert "A avaliar com técnico local." in h
    pdf = CT.cartao_pdf(c)
    if pdf is None:
        pytest.skip("fpdf2 não instalado")
    assert pdf[:5] == b"%PDF-" and CT.n_paginas_pdf(pdf) == 1


def test_cartao_sem_dados_vira_lacuna(monkeypatch):
    monkeypatch.setattr(M, "diagnostico_local", lambda pid: None)
    c = CT.montar_cartao("quixada_ce", "milho", "sem", calc=None, rotacao={"estrategias": [], "lacunas": ["sem alternativas"]})
    t = CT.cartao_texto(c)
    assert "LACUNA: diagnóstico do local não encontrado." in t and "LACUNA: sem alternativas" in t and "LACUNA: janela não calculada" in t


# ------------------------------------------------------------------------------------------------ mapa
def test_vista_zoom_so_com_a_caixa_ligada_e_desligada_por_padrao(monkeypatch):
    monkeypatch.delenv("SULCO_ABERTURA_ZOOM", raising=False)
    assert MV.abertura_padrao() is False
    pts = M.carregar_pontos()
    off = MV.parametros_vista(pts, "quixada_ce", False)
    on = MV.parametros_vista(pts, "quixada_ce", True)
    assert off["zoom"] == MV.ZOOM_REGIAO and "transitionDuration" not in off
    r = pts.set_index("ponto_id").loc["quixada_ce"]
    assert on["zoom"] == MV.ZOOM_MUNICIPIO > off["zoom"] and on["latitude"] == r["lat"] and on["longitude"] == r["lon"] and on["transitionDuration"] > 0
    assert MV.parametros_vista(pts, "ponto_inexistente", True)["zoom"] == MV.ZOOM_REGIAO     # sem ponto: visão da região
    assert MV.vista(pts, "quixada_ce", True).zoom == MV.ZOOM_MUNICIPIO
    assert MV.camada_fundo_liso().id == "fundo_liso"


# ------------------------------------------------------------------------------------------------ tela
def test_tela_cartao_mapa_e_tempo_por_selecao():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.multiselect(key="culturas").set_value(["milho"]).run()
    assert not at.exception
    assert at.checkbox(key="mapa_zoom").value is False and at.checkbox(key="mapa_offline").value is False
    assert any("Cartão do município" in s.value for s in at.subheader)
    assert len(at.get("download_button")) in (2, 3)          # perfil JSON + cartão HTML sempre; PDF se fpdf2
    t0 = time.perf_counter()
    at.checkbox(key="mapa_zoom").check().run()
    t1 = time.perf_counter() - t0
    assert not at.exception and t1 < 5.0
    t0 = time.perf_counter()
    at.checkbox(key="mapa_offline").check().run()
    assert not at.exception and time.perf_counter() - t0 < 5.0
    t0 = time.perf_counter()
    at.session_state["local"] = "petrolina_pe"
    at.run()
    assert not at.exception and time.perf_counter() - t0 < 5.0
    assert any("Poucos pixels" in w.value for w in at.warning)            # aviso próprio do solo na tela
