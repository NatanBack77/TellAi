"""Testes do staging FAO (src/culturas/fao_staging.py) e do parâmetro opcional ciclo_override."""
import copy

import numpy as np
import pytest

from src.culturas import ciclo, fao_staging as fs
from src.culturas.parametros import Parametros
from src.culturas.tabela_culturas import carregar


@pytest.fixture(scope="module")
def linhas():
    return fs.carregar()


def _l(**kw):
    base = dict(cultura_id="milho", atributo="kc_mid", valor="1.20", unidade="adimensional", regiao_da_fonte="x", fonte="FAO",
                url="https://www.fao.org/x", pagina_tabela="Tabela 12", trecho="Maize | 1.20 | 0.35", mapeamento_fao="direta",
                conversao="", observacao="")
    base.update(kw)
    return base


def test_arquivo_real_valida():
    assert fs.validar(fs.carregar_linhas()) == []


def test_linha_valida_e_rejeicoes():
    assert fs.validar([_l()]) == []
    assert any("não aparece no trecho" in e for e in fs.validar([_l(valor="1.25")]))
    assert any("fonte" in e for e in fs.validar([_l(fonte="")]))
    assert any("URL" in e for e in fs.validar([_l(url="")]))
    assert any("URL" in e for e in fs.validar([_l(url="fao.org/x")]))
    assert any("não numérico" in e for e in fs.validar([_l(valor="abc")]))
    assert any("fora da faixa" in e for e in fs.validar([_l(valor="9", trecho="9")]))
    assert any("desconhecido" in e for e in fs.validar([_l(atributo="inventado")]))


def test_ponto_de_milhar_e_conversao():
    assert fs.validar([_l(atributo="palha_ms_kg_ha", valor="9153", trecho="Pigeon pea 9.153 240 13")]) == []
    assert any("não aparece" in e for e in fs.validar([_l(atributo="palha_ms_kg_ha", valor="7000", trecho="7 to 8 t/ha")]))
    assert fs.validar([_l(atributo="palha_ms_kg_ha", valor="7000", trecho="7 to 8 t/ha", conversao="7 t/ha x 1000")]) == []


def test_lacuna_exige_motivo_e_sem_valor():
    ok = _l(atributo=fs.ATRIBUTO_LACUNA, valor="", trecho="", pagina_tabela="-", observacao="nao consta")
    assert fs.validar([ok]) == []
    assert fs.validar([dict(ok, observacao="")])
    assert fs.validar([dict(ok, valor="1")])


def test_valores_conferidos_com_fonte(linhas):
    # valores da Tabela 24 (Ky) e Tabela 11 (milho Nigeria 20/35/40/30) lidos do HTML da FAO
    assert fs.valores(linhas, "milho", "ky_total") == [1.25]
    assert fs.valores(linhas, "sorgo", "ky_total") == [0.9]
    assert 125.0 in fs.valores(linhas, "milho", "ciclo_dias_total")
    assert fs.valores(linhas, "feijao_comum", "kc_ini") == [0.4]   # exemplo do cap. 6: feijao seco 0.4 / 1.15 / 0.35


def test_lacunas_declaradas(linhas):
    sem = fs.culturas_sem_dado(linhas)
    assert set(sem) == {"guandu", "palma_forrageira", "crotalaria_juncea", "feijao_de_porco", "mucuna"}


def test_ciclo_override_padrao_nao_muda_resultado():
    tab = carregar()
    n = 24 * 366
    rng = np.random.default_rng(1)
    clima = ciclo.ClimaPonto("t", 2001, 2024, 26 + rng.normal(0, 1, n), np.maximum(rng.normal(2, 4, n), 0))
    # opção anterior (ciclo_fonte='ecocrop'): ponto médio do EcoCrop; o padrão novo ('fao') é testado em test_ciclo_fao.py
    p0, p1 = Parametros(ciclo_fonte="ecocrop"), Parametros(ciclo_fonte="ecocrop", ciclo_override=())
    a0, a1 = ciclo.notas_ciclo(tab, "milho", clima, p0), ciclo.notas_ciclo(tab, "milho", clima, p1)
    assert a0["dur"] == a1["dur"] == 215
    assert ciclo.notas_ciclo(tab, "milho", clima, Parametros(ciclo_override=()))["dur"] == 140   # padrão novo: FAO
    assert np.array_equal(a0["nt"], a1["nt"], equal_nan=True) and np.array_equal(a0["nr"], a1["nr"], equal_nan=True)
    # injetar exatamente o ponto médio também não muda nada
    a2 = ciclo.notas_ciclo(tab, "milho", clima, Parametros(ciclo_fonte="ecocrop", ciclo_override=(("milho", 215),)))
    assert np.array_equal(a0["nr"], a2["nr"], equal_nan=True)
    # injetar outro valor muda a duração só dessa cultura
    a3 = ciclo.notas_ciclo(tab, "milho", clima, Parametros(ciclo_fonte="ecocrop", ciclo_override=(("milho", 125),)))
    assert a3["dur"] == 125
    assert ciclo.notas_ciclo(tab, "sorgo", clima, Parametros(ciclo_fonte="ecocrop", ciclo_override=(("milho", 125),)))["dur"] == 195


def test_ciclo_override_invalido():
    with pytest.raises(ValueError):
        Parametros(ciclo_override=(("milho", 0),))
