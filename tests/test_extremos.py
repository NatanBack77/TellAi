"""A4: calor e chuva extrema. Clima SINTÉTICO: testa só a lógica."""
import numpy as np
import pandas as pd

from src.app.secao_risco_solo import secao_extremos
from src.culturas import extremos as ex


def _clima(anos=range(2001, 2025), tendencia_calor=0.0, tendencia_chuva=0.0, seed=0):
    rng = np.random.default_rng(seed)
    datas = pd.date_range(f"{min(anos)}-01-01", f"{max(anos)}-12-31")
    k = (datas.year - min(anos)).to_numpy()
    tmax = 32 + 2 * np.sin(2 * np.pi * datas.day_of_year / 365) + rng.normal(0, 1, len(datas)) + tendencia_calor * k
    chuva = np.where(rng.random(len(datas)) < 0.3, rng.gamma(2.0, 6.0, len(datas)), 0.0) * (1 + tendencia_chuva * k)
    return pd.DataFrame({"data": datas, "tmax_c": tmax, "chuva_mm": chuva})


def test_formato_e_definicoes_declaradas():
    r = ex.resumo_extremos(_clima())
    assert r["disponivel"]
    t = r["tabela_por_ano"]
    assert list(t["ano"]) == list(range(2001, 2025))
    assert {"dias_quentes", "dias_chuva_extrema", "rx1day_mm"} <= set(t.columns)
    d = r["definicoes"]
    assert "percentil 90" in d["calor"] and "percentil 95" in d["chuva_extrema"] and "etccdi" in d["fonte_definicao"]
    assert d["limiar_chuva_extrema_mm"] > 0


def test_fracao_perto_do_nominal():
    # relativo ao próprio clima: ~10% dos dias quentes, ~5% dos dias chuvosos extremos
    t, _ = ex.indices_extremos(_clima())
    assert 0.07 < t["dias_quentes"].sum() / 8766 < 0.13
    clima = _clima()
    n_chuvosos = (clima.chuva_mm >= 1).sum()
    assert 0.03 < t["dias_chuva_extrema"].sum() / n_chuvosos < 0.07


def test_tendencia_detecta_calor_crescente_e_nao_inventa_em_estacionario():
    r = ex.resumo_extremos(_clima(tendencia_calor=0.1))
    tq = r["tendencias"]["dias_quentes"]
    assert tq["resultado"] == "calculada" and tq["inclinacao_por_ano"] > 0 and tq["mann_kendall"] == "increasing"
    est = ex.resumo_extremos(_clima(seed=3))["tendencias"]["dias_quentes"]
    assert est["inclinacao_por_ano"] < tq["inclinacao_por_ano"]


def test_monotonia_chuva_extrema_com_chuva_crescente():
    a = ex.resumo_extremos(_clima(tendencia_chuva=0.0))["tabela_por_ano"]["chuva_em_dias_extremos_mm"].iloc[-5:].mean()
    b = ex.resumo_extremos(_clima(tendencia_chuva=0.2))["tabela_por_ano"]["chuva_em_dias_extremos_mm"].iloc[-5:].mean()
    assert b > a


def test_lacuna_sem_dado_ou_serie_curta():
    for c in (None, pd.DataFrame(), _clima(anos=range(2001, 2006)), pd.DataFrame({"data": [1], "x": [2]})):
        r = ex.resumo_extremos(c)
        assert not r["disponivel"] and r["lacunas"]
        assert r["tendencias"]["dias_quentes"]["resultado"] is None


def test_ano_incompleto_vira_lacuna():
    c = _clima()
    c = c[~((c.data.dt.year == 2010) & (c.data.dt.month > 3))]
    r = ex.resumo_extremos(c)
    assert any("2010" in l for l in r["lacunas"])
    assert np.isnan(r["tabela_por_ano"].set_index("ano").loc[2010, "dias_quentes"])


def test_avisos_escala_e_tecnico():
    s = secao_extremos("x_ce", _clima())
    txt = " ".join(s["avisos"])
    assert "50 km" in txt and "técnico local" in txt and "frágil" in txt
    sem = secao_extremos("y_ce", pd.DataFrame())
    assert not sem["disponivel"] and sem["lacunas"] and "50 km" in " ".join(sem["avisos"])
