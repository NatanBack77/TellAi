import numpy as np
import pandas as pd
import pytest

from src.app.secao_balanco_renda import secao_balanco_hidrico, secao_forragem
from src.culturas import balanco_hidrico as bh


def test_ra_reproduz_exemplo_8_da_fao56():
    """FAO-56 Exemplo 8: 3 set (J=246), 20°S -> Ra = 32.2 MJ m-2 d-1 = 13.1 mm/dia."""
    ra = float(bh.radiacao_extraterrestre_mj(-20.0, 246))
    assert ra == pytest.approx(32.2, abs=0.1)
    assert float(bh.radiacao_extraterrestre_mm(-20.0, 246)) == pytest.approx(13.1, abs=0.1)


def test_eto_hargreaves_formula_eq52():
    # 0.0023 * (25 + 17.8) * sqrt(10) * 15 (valores de teste da fórmula, não dado agronômico)
    assert float(bh.eto_hargreaves(30.0, 20.0, 15.0)) == pytest.approx(0.0023 * 42.8 * np.sqrt(10.0) * 15.0)


def test_eto_monotonica_na_amplitude_e_nan_sem_dado():
    assert bh.eto_hargreaves(32, 20, 15) > bh.eto_hargreaves(30, 20, 15)
    assert np.isnan(bh.eto_hargreaves(np.nan, 20, 15)) and np.isnan(bh.eto_hargreaves(18, 20, 15))   # Tmax < Tmin: sem valor


def test_latitude_invalida():
    with pytest.raises(ValueError):
        bh.radiacao_extraterrestre_mj(95, 10)


def test_quinzena_id():
    q = bh.quinzena_id(pd.to_datetime(["2020-01-01", "2020-01-15", "2020-01-16", "2020-12-31"]))
    assert list(q) == [1, 1, 2, 24]


def _clima(n_dias=730, chuva=2.0):
    d = pd.date_range("2001-01-01", periods=n_dias)
    return pd.DataFrame({"data": d, "chuva_mm": chuva, "tmax_c": 32.0, "tmin_c": 21.0, "radiacao": 20.0})


def test_saldo_quinzenal_e_lacuna_com_poucos_dias():
    c = _clima()
    c.loc[c["data"].between("2001-01-01", "2001-01-10"), "tmax_c"] = np.nan     # 10 dias sem dado: quinzena 1/2001 fica NaN
    s = bh.saldo_quinzenal(c, -5.0)
    assert np.isnan(s[(s["ano"] == 2001) & (s["quinzena"] == 1)]["saldo_mm"].iloc[0])
    r = s[(s["ano"] == 2002) & (s["quinzena"] == 2)].iloc[0]
    assert r["saldo_mm"] == pytest.approx(r["chuva_mm"] - r["eto_mm"])


def test_climatologia_exige_anos_minimos():
    cl = bh.climatologia_quinzenal(_clima(), -5.0, min_anos=10)      # só 2 anos
    assert cl["saldo_mm"].isna().all()


def test_conferencia_radiacao_so_confere():
    c = bh.conferencia_radiacao(_clima(), -5.0)
    assert c["disponivel"] and 0 < c["razao_media_rs_ra"] < 1 and "Conferência" in c["nota"]


def test_secao_com_avisos_e_lacunas():
    s = secao_balanco_hidrico("quixada_ce")
    assert len(s["quinzenas"]) == 24 and "NÃO o consumo da cultura" in s["aviso"]
    assert any("Kc" in x for x in s["lacunas"]) and any("Penman" in x for x in s["lacunas"])
    anual = sum(q["eto_mm"] for q in s["quinzenas"])
    assert 500 < anual < 4000        # sanidade de ordem de grandeza (ETo anual em mm), não resultado
    assert secao_balanco_hidrico("nao_existe")["quinzenas"] == []


def test_forragem_e_lacuna_sem_numero_inventado():
    f = secao_forragem()
    assert {i["cultura"] for i in f["itens"]} == {"palma", "sorgo", "milheto"}
    assert all(i["valor"] is None and i["lacuna"] and i["lido"] for i in f["itens"])
