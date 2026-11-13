"""Testes do Monte Carlo estilo SMAA-2 (src/culturas/incerteza.py). Notas aqui são SINTÉTICAS (só lógica)."""
import numpy as np
import pytest

from src.culturas import incerteza as I
from src.culturas.parametros import Parametros

CRIT = ["a", "b"]


def _tensor(linhas):
    """linhas: lista de [nota_a, nota_b] por cultura (NaN = lacuna) -> [cult x crit x 1 ano]."""
    return np.array(linhas, dtype=float)[:, :, None]


def test_reprodutivel_mesma_semente_e_muda_com_outra():
    t = _tensor([[1, 0.2], [0.4, 0.9], [0.7, 0.7]])
    r = np.ones(3, bool)
    a = I.simular(t, CRIT, CRIT, r, Parametros(n_sorteios=500))
    b = I.simular(t, CRIT, CRIT, r, Parametros(n_sorteios=500))
    c = I.simular(t, CRIT, CRIT, r, Parametros(n_sorteios=500, semente=1))
    assert np.array_equal(a["principal"]["score"], b["principal"]["score"])
    assert not np.array_equal(a["principal"]["score"], c["principal"]["score"])


def test_aceitabilidade_valor_analitico_dois_criterios():
    # A=(1,0), B=(0,1), pesos uniformes no simplex: A vence se w1 > 0,5 => P = 0,5
    t = _tensor([[1, 0], [0, 1]])
    s = I.simular(t, CRIT, CRIT, np.ones(2, bool), Parametros(n_sorteios=20000))
    rk = s["principal"]["ranking"]
    assert rk["p_1o"][0] == pytest.approx(0.5, abs=0.02)
    assert rk["aceit"].sum(axis=0) == pytest.approx([1, 1]) and rk["aceit"].sum(axis=1) == pytest.approx([1, 1])


def test_empate_exato_divide_posicao_sem_ordem_alfabetica():
    t = _tensor([[0.5, 0.5], [0.5, 0.5], [0.1, 0.1], [0.05, 0.05]])  # duas idênticas e duas piores
    r = np.ones(4, bool)
    um = I.simular(t, CRIT, CRIT, r, Parametros(n_sorteios=300, top_n=1))["principal"]["ranking"]
    assert um["p_topo"][:2] == pytest.approx([0.5, 0.5]) and um["p_topo"][2:] == pytest.approx([0, 0])
    dois = I.simular(t, CRIT, CRIT, r, Parametros(n_sorteios=300, top_n=2))
    assert dois["principal"]["ranking"]["p_topo"] == pytest.approx([1, 1, 0, 0])
    assert 1 in dois["principal"]["empates"][0] and 0 in dois["principal"]["empates"][1]
    # inverter a ordem das linhas (equivale a trocar a ordem alfabética) só inverte os resultados
    inv = I.simular(t[::-1], CRIT, CRIT, r, Parametros(n_sorteios=300, top_n=1))["principal"]["ranking"]
    assert inv["p_topo"] == pytest.approx(um["p_topo"][::-1])


def test_p_topn_soma_n_vagas():
    rng = np.random.default_rng(3)
    t = rng.random((8, 2, 1))
    s = I.simular(t, CRIT, CRIT, np.ones(8, bool), Parametros(n_sorteios=800, top_n=3))
    assert s["principal"]["ranking"]["p_topo"].sum() == pytest.approx(3.0)


def test_lacuna_nao_e_removida_nem_premiada():
    # A: b = 1,0; B: lacuna em b; C: b = 0,0; D: b = 0,5 (= esperança de U[0,1]). Mesma nota em a.
    t = _tensor([[0.6, 1.0], [0.6, np.nan], [0.6, 0.0], [0.6, 0.5]])
    s = I.simular(t, CRIT, CRIT, np.ones(4, bool), Parametros(n_sorteios=6000))
    sc = s["principal"]["score"]
    m = sc.mean(axis=0)
    assert m[0] > m[1] > m[2]                       # lacuna fica ENTRE nota alta e nota zero (não é premiada)
    assert m[1] == pytest.approx(m[3], abs=1.5)     # e vale, em média, como um valor intermediário
    larg = s["principal"]["score_hi"] - s["principal"]["score_lo"]
    assert larg[1] > larg[3]                        # a incerteza aparece como faixa mais larga que a do dado conhecido
    assert sc[:, 1].std() > sc[:, 3].std()          # renormalizar (remover b) daria score fixo; aqui ele varia


def test_ano_do_clima_e_o_mesmo_para_todas_as_culturas():
    # duas culturas com notas opostas por ano: se o ano fosse sorteado separado, haveria sorteios com ambas altas
    t = np.zeros((2, 1, 2))
    t[0, 0] = [1.0, 0.0]
    t[1, 0] = [0.0, 1.0]
    s = I.simular(t, ["a"], ["a"], np.ones(2, bool), Parametros(n_sorteios=1000))
    sc = s["principal"]["score"]
    assert np.all(np.abs(sc[:, 0] + sc[:, 1] - 100.0) < 1e-9)


def test_ordem_dos_pesos_respeitada_e_pesos_somam_1():
    p = Parametros(n_sorteios=300, ordem_pesos=("b", "a", "c"))
    w = I.sortear_pesos(3, ["a", "b", "c"], p, np.random.default_rng(0))
    assert np.allclose(w.sum(axis=1), 1) and (w[:, 1] >= w[:, 0]).all() and (w[:, 0] >= w[:, 2]).all()


def test_cultura_nao_ranqueada_recebe_faixa_mas_sem_posicao():
    t = _tensor([[0.2, 0.2], [0.9, 0.9], [0.8, 0.8]])
    s = I.simular(t, CRIT, CRIT, np.array([False, True, True]), Parametros(n_sorteios=300))
    assert s["principal"]["score_lo"][0] <= s["principal"]["score_hi"][0]
    assert list(s["principal"]["r_idx"]) == [1, 2]


def test_empate_tecnico_por_sobreposicao_de_intervalos():
    assert I._empates_tecnicos(np.array([0, 5, 20]), np.array([10, 15, 30])) == [[1], [0], []]
