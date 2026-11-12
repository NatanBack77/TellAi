"""Testes do app. Fixtures SINTÉTICAS: só verificam o formato, nunca são resultado real."""
import json
import shutil
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.app import logica as L

FIX = Path(__file__).parent / "fixtures"
APP = str(Path(__file__).resolve().parents[1] / "src/app/app.py")
REL = """# Relatório
## Holdout temporal

| Modelo | MAE | RMSE | R² | skill vs. clim. |
|---|---|---|---|---|
| climatologia | 0.034 | 0.051 | -0.003 | 0.000 |
| ridge | 0.035 | 0.052 | -0.046 | -0.021 |

## Cobertura da faixa de incerteza

| Modelo | Meta | CV | Holdout |
|---|---|---|---|
| ridge | 80% | 0.721 | 0.710 |

## Decisão
**Modelo: ridge.** texto
"""


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    cen = tmp_path / "cen"
    cen.mkdir()
    shutil.copy(FIX / "SINTETICO_cenarios_formato.json", cen)
    monkeypatch.setenv("SULCO_CENARIOS_DIR", str(cen))
    monkeypatch.setenv("SULCO_DIAGNOSTICO", str(tmp_path / "nao_existe.json"))
    rel = tmp_path / "rel.md"
    rel.write_text(REL, encoding="utf-8")
    monkeypatch.setenv("SULCO_RELATORIO", str(rel))
    return tmp_path


def textos(at):
    partes = [m.value for m in at.markdown] + [w.value for w in at.warning] + [e.value for e in at.error] \
        + [i.value for i in at.info] + [c.value for c in at.caption] + [m.value for m in at.metric]
    return "\n".join(str(p) for p in partes)


def test_carrega_e_ordena_atual_primeiro(ambiente):
    cen, erros = L.carregar_cenarios()
    assert erros == [] and len(cen) == 3
    sel = L.selecionar(cen, "T01", "cultura_x")
    assert L.e_atual(sel[0]) and not L.e_atual(sel[1])
    assert L.texto_rotacao(sel[1].get("rotacao")) == "cultura_x → cultura_y"


def test_faixa_formatos_e_ausente(ambiente):
    cen, _ = L.carregar_cenarios()
    assert L.faixa(cen[0]) == (1.0, 2.0) and L.faixa(cen[1]) == (2.0, 3.0) and L.faixa(cen[2]) is None


def test_explicacao_so_com_valores_do_json(ambiente):
    cen, _ = L.carregar_cenarios()
    ex = L.explicar(cen[1])
    assert any("valor 22 u" in t and "[1]" in t for t in ex["por_que"])
    assert any("criterio_a" in t for t in ex["beneficios"])      # maior nota
    assert any("criterio_b" in t for t in ex["riscos"])           # menor nota
    # critério sem trecho correspondente => lacuna visível, nunca [n] inventado
    assert any("criterio_b" in t and "sem trecho citado" in t for t in ex["por_que"])


def test_sem_dado_vira_lacuna(ambiente):
    cen, _ = L.carregar_cenarios()
    ex = L.explicar(cen[2])
    assert any("sem nota numérica" in t for t in ex["lacunas"])
    assert any("Sem evidência" in t for t in ex["lacunas"])
    assert L.fmt_num(None) == L.LACUNA
    assert L.explicar({})["beneficios"] == [f"Benefícios: {L.LACUNA}."]


def test_json_ruim_nao_quebra(tmp_path, monkeypatch):
    (tmp_path / "x.json").write_text("{nao e json", encoding="utf-8")
    monkeypatch.setenv("SULCO_CENARIOS_DIR", str(tmp_path))
    cen, erros = L.carregar_cenarios()
    assert cen == [] and len(erros) == 1


def test_relatorio_numeros_reais_do_arquivo(ambiente):
    r = L.ler_relatorio()
    assert r["disponivel"] and r["modelo_escolhido"] == "ridge"
    assert r["holdout"][1]["skill"] == -0.021
    assert r["sem_ganho_no_holdout"] == ["ridge"]


def test_relatorio_real_do_projeto_nao_supera():
    r = L.ler_relatorio(L.RAIZ / "relatorio_modelos.md")
    assert r["disponivel"] and "ridge" in r["sem_ganho_no_holdout"]


def test_relatorio_ausente(tmp_path):
    assert not L.ler_relatorio(tmp_path / "x.md")["disponivel"]


def test_resumo_perfil_com_lacunas():
    p = L.resumo_perfil({"ponto_id": "A", "veranicos": {"por_estacao": [{"maior_veranico_dias": 4}, {"maior_veranico_dias": 9}]}})
    assert p["maior_veranico_dias"] == 9 and p["confianca"] is None and p["tendencias"] == []


def test_app_tres_estrategias_e_rotulo_sintetico(ambiente):
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    t = textos(at)
    assert L.ROTULO_SINTETICO in t
    assert t.count("Estratégia atual: cultura_x") == 1
    assert "Alternativa: cultura_x → cultura_y" in t and "Alternativa: cultura_x → cultura_z" in t
    assert "avaliar com técnico local" in t
    assert "LACUNA: diagnóstico do local não encontrado" in t
    assert "[1] SINTETICO_doc.pdf, p. 2" in t


def test_app_sem_cenarios_mostra_lacuna(tmp_path, monkeypatch):
    monkeypatch.setenv("SULCO_CENARIOS_DIR", str(tmp_path / "vazio"))
    monkeypatch.setenv("SULCO_DIAGNOSTICO", str(tmp_path / "x.json"))
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert any("nenhum cenário" in w.value for w in at.warning)


def test_app_perfil_do_diagnostico(ambiente, monkeypatch):
    d = ambiente / "diag.json"
    d.write_text(json.dumps([{"ponto_id": "T01", "confianca": "media", "periodo": ["2010-01-01", "2023-12-31"],
                              "lacunas": ["lacuna do diag"]}]), encoding="utf-8")
    monkeypatch.setenv("SULCO_DIAGNOSTICO", str(d))
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    t = textos(at)
    assert "media" in t and "lacuna do diag" in t and "tendências não disponíveis" in t


def test_pagina_limites(ambiente):
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.sidebar.radio(key="pagina").set_value("Limites dos dados").run()
    assert not at.exception
    t = textos(at)
    for k in ("250 m", "50 km", "9 km", "não é produtividade", "Não é produtividade", "não prevê o clima",
              "associações históricas", "NÃO supera a média histórica", "-0.021"):
        assert k.lower() in t.lower() or k in str(at.dataframe[0].value), k
