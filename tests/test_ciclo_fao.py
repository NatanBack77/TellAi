"""Ciclo FAO-56 (Tabela 11) e chuva anual como padrão (decisões do usuário 2026-11-14) e opção anterior preservada."""
import numpy as np
import pytest

from src.culturas import ciclo, ciclo_fao, motor
from src.culturas.ciclo import ClimaPonto
from src.culturas.parametros import Parametros
from src.culturas.tabela_culturas import carregar

ANTES = Parametros(chuva_modo="ciclo", ciclo_fonte="ecocrop")
FAO11 = {"milho", "feijao_caupi", "feijao_comum", "sorgo", "milheto", "mandioca", "algodao", "amendoim", "girassol", "mamona", "gergelim"}
SEM_FAO = {"guandu", "palma_forrageira", "crotalaria_juncea", "feijao_de_porco", "mucuna"}


@pytest.fixture(scope="module")
def tab():
    return carregar()


@pytest.fixture(scope="module")
def clima():
    n = 24 * 366
    rng = np.random.default_rng(3)
    dia = np.arange(n) % 366
    chuva = np.maximum(rng.normal(0, 3, n), 0) * (dia < 150) * 3
    return ClimaPonto("t", 2001, 2024, 26 + rng.normal(0, 1, n), chuva)


def test_padroes_novos_e_opcao_anterior():
    p = Parametros()
    assert p.chuva_modo == "anual" and p.ciclo_fonte == "fao"
    assert ANTES.chuva_modo == "ciclo" and ANTES.ciclo_fonte == "ecocrop"
    with pytest.raises(ValueError):
        Parametros(ciclo_fonte="outra")


def test_11_culturas_fao_e_5_sem_dado():
    ref = ciclo_fao.ciclos_fao()
    assert set(ref) == FAO11
    assert set(ciclo_fao.sem_fao()) == SEM_FAO


def test_duracoes_escolhidas_pela_regra_unica():
    ref = ciclo_fao.ciclos_fao()
    esperado = {"milho": (140, "rotulo_arido"), "sorgo": (130, "rotulo_arido"), "mamona": (180, "rotulo_arido"),
                "feijao_caupi": (100, "linha_unica"), "girassol": (130, "linha_unica"), "gergelim": (110, "linha_unica"),
                "mandioca": (210, "linha_unica"), "feijao_comum": (100, "mediana_inferior"), "milheto": (105, "mediana_inferior"),
                "algodao": (195, "mediana_inferior"), "amendoim": (140, "mediana_inferior")}
    assert {c: (ref[c]["dias"], ref[c]["regra"]) for c in ref} == esperado
    assert ref["milho"]["dias_min"] == 125 and ref["milho"]["dias_max"] == 180 and ref["milho"]["n_linhas"] == 6
    assert "arid" in ref["milho"]["regiao"].lower() and ref["milho"]["url"].startswith("https://www.fao.org/")
    # mandioca: só o ano 1 (o ano 2, 360 d, não entra na faixa)
    assert ref["mandioca"]["dias_max"] == 210
    # a soma dos estágios difere do total impresso pela FAO em sorgo, caupi e gergelim: o aviso mostra os dois
    assert {c for c, i in ref.items() if not i["soma_confere_total"]} == {"sorgo", "feijao_caupi", "gergelim"}
    assert "imprime total" in ciclo_fao.aviso_fao(ref["sorgo"], "Sorgo")


def test_duracao_fao_vs_ecocrop_na_producao(tab, clima):
    assert ciclo.notas_ciclo(tab, "milho", clima, Parametros())["dur"] == 140             # FAO (padrão novo)
    assert ciclo.notas_ciclo(tab, "milho", clima, ANTES)["dur"] == 215                    # EcoCrop (anterior)
    av = ciclo.notas_ciclo(tab, "guandu", clima, Parametros())                             # sem FAO: mantém EcoCrop
    assert av["dur"] == ciclo.duracao_ciclo(tab, "guandu", "medio")[0]
    assert av["ciclo_info"]["fonte"] == "ecocrop" and "sem dado FAO" in av["ciclo_info"]["motivo"]
    assert ciclo.notas_ciclo(tab, "milho", clima, Parametros(ciclo_modo="min"))["dur"] == 125   # faixa FAO mín–máx
    assert ciclo.notas_ciclo(tab, "milho", clima, Parametros(ciclo_modo="max"))["dur"] == 180
    # override explícito vence a FAO
    assert ciclo.notas_ciclo(tab, "milho", clima, Parametros(ciclo_override=(("milho", 100),)))["dur"] == 100


def test_chuva_anual_compara_365_dias_e_mantem_chuva_do_ciclo(tab, clima):
    a = ciclo.notas_ciclo(tab, "milho", clima, Parametros())
    b = ciclo.notas_ciclo(tab, "milho", clima, Parametros(chuva_modo="ciclo"))
    assert a["dur_chuva"] == 365 and b["dur_chuva"] == a["dur"] == 140
    assert np.array_equal(a["chuva"], b["chuva"], equal_nan=True)                  # chuva do ciclo (informação) é a mesma
    assert np.array_equal(b["chuva"], b["chuva_comparada"], equal_nan=True)
    # primeiro ano, início em 1º/jan: a chuva comparada é a soma dos 365 primeiros dias
    assert a["chuva_comparada"][0, 0] == pytest.approx(clima.chuva[:365].sum())
    assert a["chuva"][0, 0] == pytest.approx(clima.chuva[:140].sum())


def test_janela_com_dado_faltante_continua_descartada(tab, clima):
    c = ClimaPonto("t", 2001, 2024, clima.tmed.copy(), clima.chuva.copy())
    c.chuva[100] = np.nan                                                          # dentro do ciclo e dos 365 dias do início 0 de 2001
    for p in (Parametros(), ANTES):
        av = ciclo.notas_ciclo(tab, "milho", c, p)
        assert not av["valido"][0, 0] and np.isnan(av["nr"][0, 0])
        assert not ciclo.anos_comuns([av], c)[0]                                   # ano inteiro descartado, nunca preenchido


def test_opcao_anterior_reproduz_o_cenario_antigo(tab, clima):
    """Parametros(chuva_modo='ciclo', ciclo_fonte='ecocrop') = resultado do código anterior (ponto médio EcoCrop e chuva do ciclo)."""
    from src.culturas import incerteza  # noqa: F401
    cen = motor.gerar_cenarios({"local": "t"}, "milho", tab, clima=clima, params=Parametros(chuva_modo="ciclo", ciclo_fonte="ecocrop", n_sorteios=300))
    j = cen[0]["janela_plantio"]
    assert j["duracao_dias"] == 215 and j["chuva_modo"] == "ciclo" and j["chuva_comparada_mm"] == j["chuva_ciclo_mm"]
    assert j["chuva_comparada_janela_dias"] == 215
    perfil = cen[0]["criterios"]["chuva"]["valor"]["perfil"]
    assert perfil == pytest.approx(j["chuva_ciclo_mm"], abs=0.1)
    # na opção anterior o aviso do ciclo é o do EcoCrop, não o da FAO
    assert not any("Tabela 11" in x for x in cen[0]["lacunas"])


def test_cenario_novo_declara_suposicoes_e_avisos_por_cultura(tab, clima):
    cen = motor.gerar_cenarios({"local": "t"}, "milho", tab, clima=clima, params=Parametros(n_sorteios=300))
    for c in cen:
        alvo = c["rotacao"][1]
        sup = " ".join(c["suposicoes"]).replace("OUTRAS", "outras")
        assert "Tabela 11 do FAO-56" in sup and "outras regiões" in sup and "chuva ANUAL" in sup
        lac = " ".join(c["lacunas"])
        if alvo in FAO11:
            assert "ciclo de referência de outras regiões" in lac and "Tabela 11" in lac
        else:
            assert "sem dado FAO" in lac and "EcoCrop" in lac
        j = c["janela_plantio"]
        assert j["chuva_comparada_janela_dias"] == 365 and j["ciclo_fonte"] == "fao"
        assert "INFORMAÇÃO" in j["atendimento_hidrico_nota"]
    # a cultura atual (milho) usa a linha 'Arid' da FAO
    assert cen[0]["janela_plantio"]["duracao_dias"] == 140
    assert cen[0]["janela_plantio"]["ciclo_referencia"]["regra"] == "rotulo_arido"
    # P(top-3) e empate técnico continuam calculados nas alternativas
    for c in cen[1:]:
        f = c["faixa_incerteza"]
        assert 0 <= f["p_top3"] <= 1 and isinstance(f["empate_tecnico"], bool) and "empate_tecnico_com" in f


def test_atendimento_hidrico_nao_entra_no_ranking(tab, clima):
    cen = motor.gerar_cenarios({"local": "t"}, "milho", tab, clima=clima, params=Parametros(n_sorteios=300))
    assert "atendimento_hidrico" not in motor.CRITERIOS
    assert all(set(c["faixa_incerteza"]["criterios_ranking"]) <= set(motor.CRITERIOS) for c in cen)
