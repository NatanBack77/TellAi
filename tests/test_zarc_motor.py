import dataclasses

import numpy as np
import pandas as pd
import pytest

from src.culturas import ciclo, zarc
from src.culturas.parametros import Parametros
from src.culturas.tabela_culturas import CAMINHO_PADRAO, carregar_linhas
from src.modelos.entrada import RAIZ

pytestmark = pytest.mark.skipif(not zarc.CAMINHO.exists(), reason="zarc_ce.parquet ausente (python -m src.coleta.zarc)")


@pytest.fixture(scope="module")
def pontos():
    return pd.read_csv(RAIZ / "data/processed/pontos.csv").dropna(subset=["ibge"])


@pytest.fixture(scope="module")
def geo(pontos):
    return int(pontos[pontos["ponto_id"] == "quixada_ce"]["ibge"].iloc[0])


def test_janela_formato_e_ordem_de_risco(geo):
    j20, j30, j40 = (zarc.janela(geo, "milho", r) for r in (20, 30, 40))
    assert j30["permitido"] is not None and len(j30["permitido"]) == 36
    assert not (j20["permitido"] & ~j30["permitido"]).any() and not (j30["permitido"] & ~j40["permitido"]).any()
    assert j40["permitido"].any()


def test_solo_todos_e_mais_conservador_que_qualquer(geo):
    q, t = zarc.janela(geo, "milho", 30, "qualquer")["permitido"], zarc.janela(geo, "milho", 30, "todos")["permitido"]
    assert not (t & ~q).any()
    with pytest.raises(ValueError):
        zarc.janela(geo, "milho", 30, "x")


def test_sem_zarc_vira_lacuna_nunca_inventa(geo):
    assert zarc.janela(geo, "mucuna")["permitido"] is None             # cultura sem correspondência
    assert zarc.janela(geo, "sorgo")["permitido"] is None              # ambígua: fora do mapa
    assert zarc.janela(None, "milho")["permitido"] is None             # ponto sem IBGE
    assert "IBGE" in zarc.janela(None, "milho")["motivo"]
    assert zarc.janela(1234567, "milho")["permitido"] is None          # município sem ZARC


def test_parametros_validam_zarc():
    assert Parametros().usar_zarc is False                             # padrão desligado
    with pytest.raises(ValueError):
        Parametros(zarc_risco=25)
    with pytest.raises(ValueError):
        Parametros(zarc_solo="x")
    assert any("ZARC LIGADO" in s for s in Parametros(usar_zarc=True).suposicoes())
    assert not any("ZARC LIGADO" in s for s in Parametros().suposicoes())


@pytest.fixture(scope="module")
def tab():
    from src.culturas.tabela_culturas import carregar
    return carregar()


@pytest.fixture(scope="module")
def clima(geo):
    d = pd.read_parquet(RAIZ / "data/processed/clima_diario.parquet")
    return ciclo.ClimaPonto.de_dataframe(d, "quixada_ce")


def test_desligado_nao_muda_nada(tab, clima):
    a = ciclo.notas_ciclo(tab, "milho", clima, Parametros())
    b = ciclo.notas_ciclo(tab, "milho", clima, dataclasses.replace(Parametros(), usar_zarc=False, zarc_risco=40))
    np.testing.assert_array_equal(a["nt"], b["nt"])
    assert a["zarc"] is None


def test_zarc_zera_so_inicios_fora_da_janela(tab, clima, geo):
    p0, p1 = Parametros(), Parametros(usar_zarc=True)
    a, b = ciclo.notas_ciclo(tab, "milho", clima, p0), ciclo.notas_ciclo(tab, "milho", clima, p1)
    perm = zarc.janela(geo, "milho", 30)["permitido"]
    ok = perm[zarc.decendios_do_inicio(np.arange(0, 365, p1.passo_inicio_dias))]
    np.testing.assert_array_equal(b["nt"][:, ok], a["nt"][:, ok])           # dentro: igual
    assert np.nansum(b["nt"][:, ~ok]) == 0 and np.nansum(b["nr"][:, ~ok]) == 0   # fora: nota 0
    assert np.array_equal(np.isnan(a["nt"]), np.isnan(b["nt"]))             # NaN não vira 0
    assert b["zarc"]["aplicado"] and b["zarc"]["inicios_permitidos"] == int(ok.sum())


def test_cultura_sem_zarc_usa_janela_aproximada_das_anuais(tab, clima, geo):
    """Sem isso, as culturas sem ZARC (adubação verde, sorgo) levariam vantagem sobre as zoneadas."""
    a = ciclo.notas_ciclo(tab, "mucuna", clima, Parametros())
    b = ciclo.notas_ciclo(tab, "mucuna", clima, Parametros(usar_zarc=True))
    z = b["zarc"]
    assert z["aplicado"] is True and z["aproximada"] is True and "anuais" in z["aviso"]
    ap = zarc.janela_aproximada_anuais(geo, 30)["permitido"]
    ok = ap[zarc.decendios_do_inicio(np.arange(0, 365, 10))]
    np.testing.assert_array_equal(b["nt"][:, ok], a["nt"][:, ok])
    assert np.nansum(b["nt"][:, ~ok]) == 0
    assert zarc.janela_aproximada_anuais(None)["permitido"] is None          # sem IBGE: sem janela, sem inventar


def test_aproximada_cobre_ao_menos_cada_cultura_anual(geo):
    ap = zarc.janela_aproximada_anuais(geo, 30)
    for c in zarc.ANUAIS:
        j = zarc.janela(geo, c, 30)["permitido"]
        if j is not None:
            assert not (j & ~ap["permitido"]).any()                         # a união contém cada janela


def test_solo_especifico_e_subconjunto_de_qualquer_e_cai_em_qualquer_sem_linhas(geo):
    q = zarc.janela(geo, "milho", 30, "qualquer")["permitido"]
    for s in ("arenoso", "medio", "argiloso"):
        j = zarc.janela(geo, "milho", 30, s)
        assert j["permitido"] is not None and not (j["permitido"] & ~q).any()
    assert Parametros(zarc_solo="arenoso").zarc_solo == "arenoso"
    with pytest.raises(ValueError):
        Parametros(zarc_solo="rochoso")

