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


def test_pagina_limites(ambiente):
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.radio(key="pagina").set_value("Limites dos dados").run()
    assert not at.exception
    t = textos(at)
    for k in ("250 m", "50 km", "9 km", "não é produtividade", "Não é produtividade", "não prevê o clima",
              "associações históricas", "NÃO supera a média histórica", "-0.021"):
        assert k.lower() in t.lower() or k in " ".join(str(d.value) for d in at.dataframe), k
    assert "59 células" in t   # contagem real de pontos.csv


def _cenarios_do_motor(pasta):
    """Gera cenários com o motor sobre clima SINTÉTICO (formato novo de faixa_incerteza)."""
    from src.culturas import motor
    from src.culturas.ciclo import ClimaPonto
    from src.culturas.parametros import Parametros
    from src.culturas.tabela_culturas import carregar
    from tests.conftest import clima_sintetico
    cens = motor.gerar_cenarios({"local": "T9"}, "milho", carregar(),
                                clima=ClimaPonto.de_dataframe(clima_sintetico("T9"), "T9"), params=Parametros(n_sorteios=500))
    for c in cens:
        c["local"] = {"ponto_id": "T9", "nome": "Ponto teste"}
        c["atual"] = c["rotacao"][1] == "milho"
    (pasta / "cens.json").write_text(json.dumps(cens, ensure_ascii=False), encoding="utf-8")
    return cens


def test_resumo_incerteza_formatos_antigos_nao_disponivel(ambiente):
    cen, _ = L.carregar_cenarios()
    assert [L.resumo_incerteza(c)["disponivel"] for c in cen] == [False, False, False]


def test_resumo_incerteza_do_motor_so_com_valores_do_json(tmp_path):
    cens = _cenarios_do_motor(tmp_path)
    r = L.resumo_incerteza(cens[1])
    f = cens[1]["faixa_incerteza"]
    assert r["disponivel"] and r["faixa"] == (f["score_p10"], f["score_p90"])
    txt = " ".join(r["linhas"] + r["cobertura"] + r["janela"] + r["empate"])
    assert f"{f['p_top3'] * 100:.0f}%" in txt and "primeiras" in txt and "do peso total" in txt
    assert "duração suposta" in txt and cens[1]["janela_plantio"]["melhor_inicio"] in txt
    assert "não entra no ranking" in " ".join(L.resumo_incerteza(cens[0])["linhas"])
