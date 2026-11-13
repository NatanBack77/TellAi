"""Testes da análise de sensibilidade dos pesos (src/culturas/sensibilidade.py)."""
import numpy as np
import pandas as pd
import pytest

from src.culturas import motor, sensibilidade as S
from src.culturas.tabela_culturas import carregar

PERFIL = {"local": "t", "temp_media_c": 26.0, "chuva_ciclo_mm": 600.0}


@pytest.fixture(scope="module")
def tab():
    return carregar()


def test_pesos_dirichlet_reprodutivel_e_somam_1():
    a, b = S.pesos_dirichlet(50, 1), S.pesos_dirichlet(50, 1)
    assert np.array_equal(a, b) and a.shape == (50, 5)
    assert np.allclose(a.sum(1), 1) and (a >= 0).all()
    assert not np.array_equal(a, S.pesos_dirichlet(50, 2))


def test_grade_completa():
    g = S.pesos_grade(0.1)
    assert g.shape == (1001, 5) and np.allclose(g.sum(1), 1)


def test_scores_iguais_ao_motor_para_pesos_diferentes(tab, monkeypatch):
    cand, notas, _ = S.notas_do_ponto(tab, PERFIL, "milho")
    assert cand
    for w in S.pesos_dirichlet(5, 7):
        for k, v in zip(S.CRITERIOS, w):
            monkeypatch.setitem(motor.PESOS, k, float(v))
        pont = motor.pontuar(tab, PERFIL, "milho", ["milho"] + cand)
        esperado = np.array([pont[c]["score"] for c in cand])
        assert np.allclose(S.scores(notas, w[None, :])[0], esperado)


def test_ordem_desempate_alfabetico_e_nan_por_ultimo():
    s = np.array([[50.0, 80.0, 80.0, np.nan]])
    assert S.ordem(s)[0].tolist() == [1, 2, 0, 3]
    assert S.posicoes(S.ordem(s))[0].tolist() == [2, 0, 1, 3]


def test_spearman_identico_e_invertido():
    pos = np.tile(np.arange(5), (10, 1))
    assert S.spearman_pares(pos) == pytest.approx(1.0)
    pos[::2] = pos[::2][:, ::-1]
    assert S.spearman_pares(pos, 400) < 1.0


def test_score_sem_criterio_com_nota_vira_nan():
    assert np.isnan(S.scores(np.array([[np.nan] * 5]), S.peso_base()[None, :])[0, 0])


def test_perfil_descarta_ano_incompleto_e_calcula_media():
    dias = pd.date_range("2001-01-01", "2002-01-20")
    clima = pd.DataFrame({"ponto_id": "p", "data": dias, "chuva_mm": 1.0, "tmax_c": 30.0, "tmin_c": 20.0})
    p = S.perfil_do_ponto(clima, "p", 1, 1, 30)
    assert p["temp_media_c"] == 25.0 and p["chuva_ciclo_mm"] == 30.0
    # janela 10/01 + 30 d: 2001 completo; 2002 só tem 11 dias, logo é descartado (não preenche)
    assert S.perfil_do_ponto(clima, "p", 1, 10, 30)["chuva_ciclo_mm"] == 30.0
    # só dados parciais => sem perfil
    parcial = clima[clima["data"] >= "2002-01-01"]
    assert S.perfil_do_ponto(parcial, "p", 1, 1, 30)["temp_media_c"] is None


def test_escolher_pontos_so_ce_e_reprodutivel():
    df = pd.DataFrame({"ponto_id": [f"a{i}_ce" for i in range(20)] + ["x_pe", "y_pb"]})
    a = S.escolher_pontos(df, 10)
    assert a == S.escolher_pontos(df, 10) and len(set(a)) == 10 and all(x.endswith("_ce") for x in a)


def test_analisar_ponto_frequencias_coerentes(tab):
    r = S.analisar_ponto(tab, PERFIL, "milho", S.pesos_dirichlet(200))
    assert r is not None
    f = r["freq_top3"]
    assert all(0 <= v <= 1 for v in f.values())
    assert sum(f.values()) == pytest.approx(min(3, r["n_candidatas"]))
    assert -1 <= r["spearman_medio_entre_pesos"] <= 1
    assert 0 <= r["empate_no_corte_top3_pct"] <= 100


def test_efeito_lacunas_e_n_criterios(tab):
    r = S.efeito_lacunas(tab, PERFIL, "milho", S.pesos_dirichlet(100))
    assert r is not None and "temperatura" in r["criterios_comuns"]
    assert r["n_com_5_criterios"] + r["n_com_menos_criterios"] == len(S.notas_do_ponto(tab, PERFIL, "milho")[0])
    n = S.n_criterios_por_cultura(tab, "milho")
    assert all(0 <= v <= 5 for v in n.values()) and "milho" not in n


def test_nao_altera_pesos_do_motor(tab):
    antes = dict(motor.PESOS)
    S.analisar_ponto(tab, PERFIL, "milho", S.pesos_dirichlet(20))
    assert motor.PESOS == antes


def test_mc_de_pesos_usa_o_mesmo_sorteio_da_sensibilidade():
    """Os pesos do Monte Carlo (incerteza.py) são os mesmos Dirichlet(1) que a análise de pesos usa."""
    from src.culturas import incerteza
    from src.culturas.parametros import Parametros
    w = incerteza.sortear_pesos(len(S.CRITERIOS), S.CRITERIOS, Parametros(n_sorteios=100), np.random.default_rng(7))
    assert np.array_equal(w, S.pesos_dirichlet(100, 7))


def test_sensibilidade_continua_usando_perfil_anual_e_desempate_alfabetico_legado(tab):
    """A análise do doc 06 (perfil + desempate alfabético) é do motor LEGADO; o novo ranking não desempata por nome."""
    s = np.array([[80.0, 80.0]])
    assert S.ordem(s)[0].tolist() == [0, 1]
    from src.culturas import incerteza
    from src.culturas.parametros import Parametros
    t = np.array([[0.8, 0.8], [0.8, 0.8]])[:, :, None]
    for lin in (t, t[::-1]):
        rk = incerteza.simular(lin, ["a", "b"], ["a", "b"], np.ones(2, bool), Parametros(n_sorteios=200, top_n=1))
        assert rk["principal"]["ranking"]["p_topo"].tolist() == pytest.approx([0.5, 0.5])
