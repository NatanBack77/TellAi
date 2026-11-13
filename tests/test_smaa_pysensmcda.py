"""Confere o cálculo de aceitabilidade de posição contra o pacote `pysensmcda` (MIT), se instalado.

Instalação só em venv temporário (não é dependência do projeto): python -m venv /tmp/v && /tmp/v/bin/pip install pysensmcda pytest
"""
import numpy as np
import pytest

pytest.importorskip("pysensmcda")
pytest.importorskip("pymcdm")
from pymcdm.methods import WSM  # noqa: E402
from pysensmcda import smaa  # noqa: E402

from src.culturas.incerteza import _resumo_ranking  # noqa: E402
from src.culturas.parametros import Parametros  # noqa: E402


def test_aceitabilidade_igual_ao_pysensmcda_com_os_mesmos_pesos():
    rng = np.random.default_rng(1)
    M = rng.random((6, 3))
    W = rng.dirichlet(np.ones(3), size=4000)
    # soma ponderada sem normalização interna, para comparar só a contagem de posições
    res = smaa.simulate(WSM(normalization_function=lambda x, cost=False: x), M, np.ones(3), weights=W,
                        num_samples=4000, seed=0)
    ref = res.rank_acceptability()
    meu = _resumo_ranking(100 * W @ M.T, Parametros(n_sorteios=4000))["aceit"]
    assert np.abs(ref - meu).max() < 1e-12
