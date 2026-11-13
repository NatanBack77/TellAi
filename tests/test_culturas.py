"""Testes da tabela de culturas (fonte por valor) e do motor de rotação."""
import copy

import numpy as np
import pytest

from src.culturas import ciclo, incerteza, motor, parametros
from src.culturas.ciclo import ClimaPonto
from src.culturas.parametros import Parametros
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
    # demanda hídrica: fechada só onde a Tabela 5 do FAO IWM Manual 3 tem a cultura (2026-11-12)
    assert tab["milho"]["atributos"]["demanda_hidrica_mm_ciclo"]["valor"] == 500
    assert tab["mandioca"]["atributos"]["demanda_hidrica_mm_ciclo"] is None
    assert len(lac) == 34


def test_valor_do_estudo_aparece_na_tabela(tab):
    d = tab["crotalaria_juncea"]["atributos"]["n_fixado_kg_ha"]
    assert d["valor"] == pytest.approx(173.215) and "Perin" in d["fonte"]
    assert tab["guandu"]["atributos"]["palha_ms_kg_ha"]["valor"] == 6130


PERFIL = {"local": "teste", "temp_media_c": 26.0, "chuva_ciclo_mm": 700.0}
P = Parametros(n_sorteios=1000)


def _serie(df, pid="x_ce"):
    return ClimaPonto.de_dataframe(df, pid)


def _cenarios(fabrica_clima, tab, atual="milho", params=P, **kw):
    df = fabrica_clima(**kw)
    return motor.gerar_cenarios({"local": "x_ce"}, atual, tab, clima=_serie(df), params=params)


def test_trapezio():
    assert motor._nota_trapezio(5, 0, 10, 20, 30) == 0.5
    assert motor._nota_trapezio(15, 0, 10, 20, 30) == 1.0
    assert motor._nota_trapezio(30, 0, 10, 20, 30) == 0.0


def test_trapezio_vetorizado_igual_ao_escalar():
    xs = np.array([-5, 0, 5, 10, 15, 20, 25, 30, 40, np.nan])
    v = ciclo.trapezio(xs, 0, 10, 20, 30)
    for x, n in zip(xs[:-1], v[:-1]):
        assert n == motor._nota_trapezio(x, 0, 10, 20, 30)
    assert np.isnan(v[-1])


def test_viabilidade_exclui_fora_da_faixa_absoluta(tab):
    v = motor.viabilidade(tab, "milho", {"temp_media_c": 2.0, "chuva_ciclo_mm": 700})
    assert v["estado"] == "inviavel" and v["motivos"]


def test_viabilidade_indeterminada_sem_perfil_ou_sem_faixa(tab):
    assert motor.viabilidade(tab, "milho", {"temp_media_c": 26})["estado"] == "indeterminada"
    t2 = copy.deepcopy(tab)
    t2["milho"]["atributos"]["chuva_max_abs_mm"] = None
    v = motor.viabilidade(t2, "milho", PERFIL)
    assert v["estado"] == "indeterminada" and any("lacuna" in x for x in v["lacunas"])


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


def test_gerar_cenarios_exige_clima_diario(tab):
    with pytest.raises(ValueError):
        motor.gerar_cenarios(PERFIL, "milho", tab)


def test_cenarios_contrato_aviso_e_faixa_incerteza(tab, fabrica_clima):
    cen = _cenarios(fabrica_clima, tab, chuva_pico=6.0)
    assert len(cen) == 3 and cen[0]["rotacao"] == ["milho", "milho"]
    for c in cen:
        assert motor.validar_cenario(c) == []
        assert "técnico local" in c["aviso"] and c["trechos"] == []
        f = c["faixa_incerteza"]
        assert isinstance(f, dict) and f["min"] <= f["max"] and f["n_sorteios"] == 1000 and f["semente"] == P.semente
        assert "não é intervalo" in f["leitura"].lower() or "não é intervalo" in f["leitura"]
        assert not any("não calculada" in x for x in c["lacunas"])
        assert any("SUPOSIÇÃO (decisão do usuário): duração do ciclo" in s for s in c["suposicoes"])
        assert c["janela_plantio"]["duracao_dias"] > 0
    alt = cen[1]["faixa_incerteza"]
    assert 0 <= alt["p_top3"] <= 1 and 1 <= alt["posicao_p10"] <= alt["posicao_p90"]
    assert "p_top3" not in cen[0]["faixa_incerteza"]  # a cultura atual não entra no ranking


def test_ranking_principal_so_criterios_comuns_e_cobertura(tab, fabrica_clima):
    cen = _cenarios(fabrica_clima, tab)
    for c in cen:
        f = c["faixa_incerteza"]
        assert f["criterios_ranking"] == ["temperatura", "chuva", "familia_diferente"]
        assert f["cobertura"]["ranking_principal"]["peso_coberto"] == pytest.approx(0.65)
        assert set(c["pesos_usados"]) == {"temperatura", "chuva", "familia_diferente"}
        assert c["criterios"]["n_na_biomassa"]["no_ranking_principal"] is False
        assert "complemento_n_palha" in f
    sem_n = [c for c in cen if c["criterios"]["n_na_biomassa"]["nota"] is None]
    assert any(c["faixa_incerteza"]["cobertura"]["completa"]["peso_coberto"] < 1 for c in sem_n) or not sem_n


def test_lacuna_nao_premia_score_principal_independe_de_n_palha(tab, fabrica_clima):
    t2 = copy.deepcopy(tab)
    for c in t2.values():
        c["atributos"]["palha_ms_kg_ha"] = None
        c["atributos"]["n_acumulado_parte_aerea_kg_ha"] = None
    a = _cenarios(fabrica_clima, tab)
    b = _cenarios(fabrica_clima, t2)
    assert [c["rotacao"] for c in a] == [c["rotacao"] for c in b]
    assert [c["score"] for c in a] == [c["score"] for c in b]
    for c in b:
        assert c["criterios"]["palha"]["nota"] is None and "lacuna" in c["criterios"]["palha"]
        assert c["faixa_incerteza"]["cobertura"]["completa"]["peso_coberto"] == pytest.approx(0.65)
        assert any(x.startswith("palha:") for x in c["lacunas"])


def test_atual_sempre_incluida_mesmo_inviavel(tab, fabrica_clima):
    cen = _cenarios(fabrica_clima, tab, tmax=8.0, tmin=2.0)
    assert cen[0]["cultura_atual"] == "milho" and cen[0]["viabilidade"] == "inviavel"
    assert any("Viabilidade da cultura atual" in r for r in cen[0]["riscos_revisao_local"])
    assert all(len(c["rotacao"]) == 2 for c in cen)


def test_chuva_acumulada_no_ciclo_e_melhor_janela(tab, fabrica_clima):
    # chuva só de jan a mai: ciclo de 60 dias iniciado em jun não vê chuva; iniciado em jan-abr vê
    df = fabrica_clima(chuva_pico=8.0)
    cl = _serie(df)
    av = ciclo.notas_ciclo(tab, "milheto", cl, Parametros(ciclo_modo="min"))  # milheto: ciclo_min 60 d (tabela)
    assert av["dur"] == 60 and av["estado"] == "avaliavel"
    k_jul = int(np.where(np.arange(0, 365, 10) == 190)[0][0])  # início ~ 10/jul
    k_jan = 0
    assert np.nanmax(av["chuva"][:, k_jul]) == 0.0
    assert np.nanmean(av["chuva"][:, k_jan]) == pytest.approx(60 * 8.0)
    res = ciclo.resumir(av, ciclo.anos_comuns([av], cl), Parametros(ciclo_modo="min"))
    assert res["adeq_media"] > 0 and res["k"] * 10 < 150  # melhor início dentro da estação chuvosa


def test_ciclo_duracao_vem_da_tabela_e_modo(tab):
    lo = tab["milheto"]["atributos"]["ciclo_min_dias"]["valor"]
    hi = tab["milheto"]["atributos"]["ciclo_max_dias"]["valor"]
    assert ciclo.duracao_ciclo(tab, "milheto", "min")[0] == int(lo)
    assert ciclo.duracao_ciclo(tab, "milheto", "max")[0] == int(hi)
    assert ciclo.duracao_ciclo(tab, "milheto", "medio")[0] == int(round((lo + hi) / 2))


def test_indeterminada_sem_ciclo_ou_sem_faixa_fica_visivel(tab, fabrica_clima):
    t2 = copy.deepcopy(tab)
    t2["sorgo"]["atributos"]["ciclo_max_dias"] = None
    t2["mamona"]["atributos"]["temp_otima_max_c"] = None
    df = fabrica_clima()
    av = motor.avaliar_local(t2, _serie(df), P)
    assert av["culturas"]["sorgo"]["estado"] == "indeterminada" and av["culturas"]["sorgo"]["lacunas"]
    assert av["culturas"]["mamona"]["estado"] == "indeterminada"
    cen = motor.gerar_cenarios({"local": "x"}, "milho", t2, clima=_serie(df), params=P)
    assert any("sorgo" in x and "mamona" in x for x in cen[0]["lacunas"])
    assert all(c["rotacao"][1] not in ("sorgo", "mamona") for c in cen)


def test_janela_com_dado_faltante_e_descartada_nao_preenchida(tab, fabrica_clima):
    df = fabrica_clima(chuva_pico=8.0)
    df.loc[df["data"] == "2010-02-15", "chuva_mm"] = np.nan
    cl = _serie(df)
    assert cl.lacunas and "ausentes" in cl.lacunas[0]
    av = ciclo.notas_ciclo(tab, "milheto", cl, Parametros(ciclo_modo="min"))
    i2010 = cl.anos.index(2010)
    assert np.isnan(av["chuva"][i2010, 0])        # janela de 60 d iniciada 1º/jan contém 15/fev
    assert not np.isnan(av["chuva"][i2010, 20])   # início ~20/jul não contém
    assert not ciclo.anos_comuns([av], cl)[i2010]


def test_locais_com_clima_diferente_tem_scores_e_janelas_diferentes(tab, fabrica_clima):
    umido = _cenarios(fabrica_clima, tab, chuva_pico=9.0)
    seco = _cenarios(fabrica_clima, tab, chuva_pico=3.0, meses_chuva=(3, 4, 5))
    assert umido[0]["score"] != seco[0]["score"]
    assert umido[0]["janela_plantio"]["chuva_ciclo_mm"] != seco[0]["janela_plantio"]["chuva_ciclo_mm"]
    assert umido[0]["janela_plantio"]["melhor_inicio"] != seco[0]["janela_plantio"]["melhor_inicio"]


def test_variacao_entre_anos_aparece_na_distribuicao(tab, fabrica_clima):
    fa = {a: 0.1 for a in range(2001, 2025, 4)}  # 1 em 4 anos com 10% da chuva
    c = _cenarios(fabrica_clima, tab, chuva_pico=6.0, fator_ano=fa)[0]["janela_plantio"]
    assert c["adequacao_entre_anos"]["p10"] < c["adequacao_entre_anos"]["p90"]
    assert c["fracao_anos_viaveis"] < 1


def test_risco_max_parametro_muda_viabilidade(tab, fabrica_clima):
    fa = {a: 0.05 for a in range(2001, 2025, 3)}  # 1/3 dos anos quase sem chuva
    df = fabrica_clima(chuva_pico=6.0, fator_ano=fa)
    rig = motor.avaliar_local(tab, _serie(df), Parametros(risco_max=0.05, n_sorteios=1000))
    lax = motor.avaliar_local(tab, _serie(df), Parametros(risco_max=0.60, n_sorteios=1000))
    n_rig = sum(v["estado"] == "viavel" for v in rig["culturas"].values())
    n_lax = sum(v["estado"] == "viavel" for v in lax["culturas"].values())
    assert n_rig < n_lax


def test_parametros_invalidos_e_suposicoes_declaradas():
    with pytest.raises(ValueError):
        Parametros(ciclo_modo="qualquer")
    with pytest.raises(ValueError):
        Parametros(risco_max=1.0)
    s = " ".join(Parametros(ciclo_modo="max", risco_max=0.2).suposicoes())
    assert "MÁXIMO" in s and "20%" in s and "SUPOSIÇÃO" in s


def test_sensibilidade_ao_ciclo_reportada(tab, fabrica_clima):
    j = _cenarios(fabrica_clima, tab)[1]["janela_plantio"]
    assert set(j["sensibilidade_ciclo"]) == {"min", "max"}


def test_empate_nao_e_alfabetico_renomear_ids_nao_muda_escolha(tab, fabrica_clima):
    ids = list(tab)
    novo = {c: f"c{len(ids) - i:02d}" for i, c in enumerate(ids)}  # ordem alfabética invertida em relação à da tabela
    t2 = {novo[c]: v for c, v in tab.items()}
    a = _cenarios(fabrica_clima, tab)
    b = _cenarios(fabrica_clima, t2, atual=novo["milho"])
    inv = {v: k for k, v in novo.items()}
    assert [c["rotacao"][1] for c in a] == [inv[c["rotacao"][1]] for c in b]
    assert [c["score"] for c in a] == [c["score"] for c in b]


def test_validar_cenario_detecta_nota_sem_fonte(tab, fabrica_clima):
    c = _cenarios(fabrica_clima, tab)[1]
    c["criterios"]["temperatura"]["url"] = None
    assert any("sem fonte" in e for e in motor.validar_cenario(c))


def test_nao_altera_pesos_nem_tabela(tab, fabrica_clima):
    antes, t0 = dict(motor.PESOS), copy.deepcopy(tab)
    _cenarios(fabrica_clima, tab)
    assert motor.PESOS == antes and tab == t0


def test_nenhum_numero_hardcoded_de_cultura_no_motor():
    import re
    from pathlib import Path
    for mod in (motor, ciclo, incerteza, parametros):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        # só pesos/constantes de método; nomes de culturas não aparecem no código
        assert not re.search(r"\b(milho|sorgo|guandu|crotal|caupi|mandioca)", src, re.I), mod.__name__
