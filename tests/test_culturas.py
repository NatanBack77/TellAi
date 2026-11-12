"""Testes da tabela de culturas (fonte por valor) e do motor de rotação."""
import copy

import pytest

from src.culturas import motor
from src.culturas.tabela_culturas import (CAMINHO_PADRAO, TabelaInvalida, carregar, carregar_linhas, lacunas,
                                          validar)


@pytest.fixture(scope="module")
def tab():
    return carregar()


def test_tabela_real_valida():
    assert validar(carregar_linhas(CAMINHO_PADRAO)) == []


def test_todo_valor_verificado_tem_fonte_url_pagina_trecho():
    for r in carregar_linhas():
        if r["status"] == "verificado":
            assert r["fonte"] and r["url"].startswith("http") and r["pagina"] and r["trecho"]
        else:
            assert not r["valor"] and r["contexto"]


def test_validador_falha_sem_url():
    linhas = carregar_linhas()
    i = next(k for k, r in enumerate(linhas) if r["status"] == "verificado")
    linhas[i]["url"] = ""
    assert any("url" in e for e in validar(linhas))


def test_validador_falha_sem_fonte_e_valor_fora_do_trecho():
    linhas = carregar_linhas()
    i = next(k for k, r in enumerate(linhas) if r["status"] == "verificado" and r["atributo"] == "temp_min_abs_c")
    l2 = copy.deepcopy(linhas)
    l2[i]["fonte"] = ""
    assert any("fonte" in e for e in validar(l2))
    l3 = copy.deepcopy(linhas)
    l3[i]["valor"] = "99"
    assert any("trecho" in e for e in validar(l3))


def test_validador_falha_lacuna_com_valor_e_sem_motivo():
    linhas = carregar_linhas()
    i = next(k for k, r in enumerate(linhas) if r["status"] == "lacuna")
    l2 = copy.deepcopy(linhas)
    l2[i]["valor"] = "5"
    assert any("lacuna" in e for e in validar(l2))
    l3 = copy.deepcopy(linhas)
    l3[i]["contexto"] = ""
    assert any("motivo" in e for e in validar(l3))


def test_carregar_invalida_levanta(tmp_path):
    import csv
    linhas = carregar_linhas()
    linhas[0]["status"] = "verificado"
    linhas[0]["url"] = ""
    p = tmp_path / "t.csv"
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
    with pytest.raises(TabelaInvalida):
        carregar(p)


def test_lacunas_conhecidas_registradas(tab):
    lac = lacunas(tab)
    assert "mamona: palha_ms_kg_ha" in lac
    assert "milho: n_fixado_kg_ha" in lac
    assert all(c["atributos"]["demanda_hidrica_mm_ciclo"] is None for c in tab.values())


def test_valor_do_estudo_aparece_na_tabela(tab):
    d = tab["crotalaria_juncea"]["atributos"]["n_fixado_kg_ha"]
    assert d["valor"] == pytest.approx(173.215) and "Perin" in d["fonte"]
    assert tab["guandu"]["atributos"]["palha_ms_kg_ha"]["valor"] == 6130


PERFIL = {"local": "teste", "temp_media_c": 26.0, "chuva_ciclo_mm": 700.0}


def test_trapezio():
    assert motor._nota_trapezio(5, 0, 10, 20, 30) == 0.5
    assert motor._nota_trapezio(15, 0, 10, 20, 30) == 1.0
    assert motor._nota_trapezio(30, 0, 10, 20, 30) == 0.0


def test_viabilidade_exclui_fora_da_faixa_absoluta(tab):
    v = motor.viabilidade(tab, "milho", {"temp_media_c": 2.0, "chuva_ciclo_mm": 700})
    assert v["estado"] == "inviavel" and v["motivos"]


def test_viabilidade_indeterminada_sem_perfil_ou_sem_faixa(tab):
    assert motor.viabilidade(tab, "milho", {"temp_media_c": 26})["estado"] == "indeterminada"
    t2 = copy.deepcopy(tab)
    t2["milho"]["atributos"]["chuva_max_abs_mm"] = None
    v = motor.viabilidade(t2, "milho", PERFIL)
    assert v["estado"] == "indeterminada" and any("lacuna" in x for x in v["lacunas"])


def test_cenarios_contrato_e_aviso(tab):
    cen = motor.gerar_cenarios(PERFIL, "milho", tab)
    assert len(cen) == 3
    assert cen[0]["rotacao"] == ["milho", "milho"]
    for c in cen:
        assert motor.validar_cenario(c) == []
        assert c["faixa_incerteza"] is None and c["trechos"] == []
        assert "técnico local" in c["aviso"]
        assert any("faixa_incerteza" in x for x in c["lacunas"])


def test_atual_sempre_incluida_mesmo_inviavel(tab):
    cen = motor.gerar_cenarios({"local": "x", "temp_media_c": 2.0, "chuva_ciclo_mm": 700}, "milho", tab)
    assert cen[0]["cultura_atual"] == "milho" and cen[0]["viabilidade"] == "inviavel"
    assert any("Viabilidade da cultura atual" in r for r in cen[0]["riscos_revisao_local"])
    assert all(len(c["rotacao"]) == 2 for c in cen)


def test_criterio_sem_dado_e_lacuna_e_fora_do_score(tab):
    t2 = copy.deepcopy(tab)
    for c in t2.values():
        c["atributos"]["palha_ms_kg_ha"] = None
    cen = motor.gerar_cenarios(PERFIL, "milho", t2)
    for c in cen:
        assert "palha" not in c["pesos_usados"]
        assert c["criterios"]["palha"]["nota"] is None and "lacuna" in c["criterios"]["palha"]
        assert any(x.startswith("palha:") for x in c["lacunas"])


def test_score_renormalizado_so_com_criterios_disponiveis(tab):
    p = motor.pontuar(tab, PERFIL, "milho", ["milho", "sorgo"])
    for c in p.values():
        soma = sum(c["pesos_usados"].values())
        esperado = round(100 * sum(w * c["notas"][k] for k, w in c["pesos_usados"].items()) / soma, 1)
        assert c["score"] == esperado


def test_mesma_familia_nota_zero_e_diferente_um(tab):
    p = motor.pontuar(tab, PERFIL, "milho", ["milho", "sorgo", "guandu"])
    assert p["milho"]["notas"]["familia_diferente"] == 0.0  # mesma família (EcoCrop: Gramineae)
    assert p["sorgo"]["notas"]["familia_diferente"] == 0.0
    assert p["guandu"]["notas"]["familia_diferente"] == 1.0


def test_validar_cenario_detecta_nota_sem_fonte(tab):
    c = motor.gerar_cenarios(PERFIL, "milho", tab)[1]
    c["criterios"]["temperatura"]["url"] = None
    assert any("sem fonte" in e for e in motor.validar_cenario(c))


def test_nenhum_numero_hardcoded_de_cultura_no_motor():
    import re
    from pathlib import Path
    src = Path(motor.__file__).read_text(encoding="utf-8")
    # só pesos/constantes de método; nomes de culturas não aparecem no código do motor
    assert not re.search(r"\b(milho|sorgo|guandu|crotal)", src, re.I)
