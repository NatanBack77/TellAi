"""A1: risco de erosão/escoamento. Dados SINTÉTICOS: testam só a lógica."""
import numpy as np
import pandas as pd

from src.app.secao_risco_solo import secao_risco_solo
from src.culturas import risco_solo as rs

REF = {"carbono_g_kg": {"c1": 10.0, "c2": 15.0, "n_pontos": 99}, "dias_chuva_erosiva_ano": {"c1": 5.0, "c2": 10.0, "n_pontos": 99}}


def _r(declive=2, argila=20, areia=50, c=12, d=7):
    return rs.avaliar_risco(declive, argila, areia, c, d, REF)


def test_classes_declive_fronteiras_embrapa():
    assert rs.classe_declive(0) == "plano" and rs.classe_declive(3) == "plano"
    assert rs.classe_declive(3.1) == "suave ondulado" and rs.classe_declive(8) == "suave ondulado"
    assert rs.classe_declive(13) == "moderadamente ondulado" and rs.classe_declive(20) == "ondulado"
    assert rs.classe_declive(45) == "forte ondulado" and rs.classe_declive(46) == "montanhoso ou escarpado"
    assert rs.classe_declive(None) is None and rs.classe_declive(float("nan")) is None


def test_textura_sibcs():
    assert rs.classe_textura(5, 90) == "arenosa"
    assert rs.classe_textura(20, 50) == "média"
    assert rs.classe_textura(40, 30) == "argilosa"
    assert rs.classe_textura(70, 10) == "muito argilosa"
    assert rs.classe_textura(20, 10) == "siltosa"
    assert rs.classe_textura(None, 10) is None


def test_monotonia_declive():
    ordem = {"baixo": 0, "médio": 1, "alto": 2}
    v = [ordem[_r(declive=x)["classe"]] for x in (1, 5, 10, 15, 25, 60)]
    assert v == sorted(v) and v[0] < v[-1]
    s = [_r(declive=x)["soma_notas"] for x in (1, 5, 10, 15, 25, 60)]
    assert s == sorted(s)


def test_monotonia_carbono_e_chuva():
    assert _r(c=5)["soma_notas"] >= _r(c=12)["soma_notas"] >= _r(c=30)["soma_notas"]
    assert _r(d=20)["soma_notas"] >= _r(d=7)["soma_notas"] >= _r(d=1)["soma_notas"]


def test_formato_mostra_entradas_e_suposicoes():
    r = _r(declive=25, c=5, d=20, argila=70, areia=10)
    assert r["classe"] == "alto" and r["soma_maxima"] == 8
    assert set(r["componentes"]) == {"declive", "textura", "carbono_organico", "chuva_erosiva"}
    assert r["componentes"]["declive"]["valor"] == 25 and r["componentes"]["declive"]["classe"] == "forte ondulado"
    assert all(c["nota_e_suposicao"] for c in r["componentes"].values())
    assert r["cortes_da_soma"]["e_suposicao"] is True


def test_lacuna_quando_falta_dado():
    r = rs.avaliar_risco(None, 20, 50, 12, 7, REF)
    assert r["classe"] is None and any("declive" in l for l in r["lacunas"])
    r = rs.avaliar_risco(5, None, None, None, 7, REF)
    assert r["classe"] is None and len(r["lacunas"]) == 2
    r = rs.avaliar_risco(5, 20, 50, 12, 7, None)  # sem referência = sem corte
    assert r["classe"] is None


def test_aviso_e_tecnico():
    r = _r()
    assert "NÃO é RUSLE" in r["aviso"] and "técnico local" in r["tecnico"]


def test_dias_chuva_erosiva():
    datas = pd.date_range("2001-01-01", "2012-12-31")
    c = pd.DataFrame({"data": datas, "chuva_mm": np.where(datas.day == 1, 12.0, 0.0)})
    v, n, lac = rs.dias_chuva_erosiva_por_ano(c)
    assert v == 12 and n == 12 and lac is None
    v, n, lac = rs.dias_chuva_erosiva_por_ano(c[c.data.dt.year < 2005])
    assert v is None and "mínimo" in lac
    assert rs.dias_chuva_erosiva_por_ano(None)[0] is None


def test_secao_ponto_ausente_e_presente():
    tab = pd.DataFrame({"declive_pct": np.linspace(1, 30, 20), "declive_p90_pct": 5.0, "argila_pct": 20.0, "areia_pct": 50.0,
                        "carbono_g_kg": np.linspace(5, 25, 20), "dias_chuva_erosiva_ano": np.linspace(2, 14, 20)},
                       index=[f"p{i}_ce" for i in range(20)])
    s = secao_risco_solo("p19_ce", tab)
    assert s["disponivel"] and s["classe"] in {"baixo", "médio", "alto"} and s["fontes"] and s["entradas"]
    assert all("url" in f for f in s["fontes"])
    vazio = secao_risco_solo("nao_existe", tab)
    assert not vazio["disponivel"] and vazio["classe"] == "sem dados suficientes" and vazio["lacunas"]
    assert any("técnico local" in a for a in vazio["avisos"])
