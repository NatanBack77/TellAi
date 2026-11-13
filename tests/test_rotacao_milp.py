import time

import numpy as np
import pytest

from src.culturas.rotacao_milp import melhor_por_enumeracao, nota_sequencia, otimizar


def _dados(seed=0, C=8, K=12):
    rng = np.random.default_rng(seed)
    cult = [f"c{i}" for i in range(C)]
    adeq = {c: np.clip(rng.normal(0.6, 0.25, K), 0, 1) for c in cult}
    fam = {c: ("Leguminosae" if i % 3 == 0 else f"F{i % 4}") for i, c in enumerate(cult)}
    pal = {c: (None if i == 2 else float(rng.integers(1000, 9000))) for i, c in enumerate(cult)}
    return cult, adeq, fam, pal


@pytest.mark.parametrize("seed", [0, 1, 2])
@pytest.mark.parametrize("regras", [None, {"sem_repetir_seguida": True}, {"min_leguminosas": 2}, {"max_repeticoes": 2, "min_leguminosas": 1}])
def test_milp_acha_o_mesmo_otimo_que_a_enumeracao(seed, regras):
    cult, adeq, fam, pal = _dados(seed)
    r = otimizar(cult, "c1", adeq, fam, pal, T=3, regras=regras)
    seq, v = melhor_por_enumeracao(cult, "c1", adeq, fam, pal, T=3, regras=regras)
    assert r["viavel"] and r["sequencia"][0] == "c1" and r["otimo_provado"]
    assert nota_sequencia(r["sequencia"], cult, adeq, fam, pal) == pytest.approx(v, abs=1e-6)


def test_robusto_cvar_bate_com_a_enumeracao_e_nao_piora_o_pior_caso():
    cult, adeq, fam, pal = _dados(3)
    r = otimizar(cult, "c1", adeq, fam, pal, T=3, robusto_beta=0.25)
    seq, v = melhor_por_enumeracao(cult, "c1", adeq, fam, pal, T=3, robusto_beta=0.25)
    assert nota_sequencia(r["sequencia"], cult, adeq, fam, pal, robusto_beta=0.25) == pytest.approx(v, abs=1e-6)
    esp = otimizar(cult, "c1", adeq, fam, pal, T=3)
    pior = lambda s: np.sort(np.mean([adeq[c] for c in s], axis=0))[:3].mean()      # média dos 3 piores anos (25% de 12)
    assert pior(r["sequencia"]) >= pior(esp["sequencia"]) - 1e-9


def test_regra_inviavel_nao_inventa_resposta():
    cult, adeq, fam, pal = _dados(0, C=4)
    r = otimizar(cult, "c1", adeq, fam, pal, T=3, regras={"min_leguminosas": 3, "max_repeticoes": 1})   # impossível
    assert r["viavel"] is False and r["sequencia"] is None


def test_horizonte_longo_resolve_rapido():
    cult, adeq, fam, pal = _dados(4, C=16)
    t = time.perf_counter()
    r = otimizar(cult, "c1", adeq, fam, pal, T=6, regras={"sem_repetir_seguida": True, "min_leguminosas": 2})
    assert r["viavel"] and len(r["sequencia"]) == 6 and time.perf_counter() - t < 25
    assert all(a != b for a, b in zip(r["sequencia"][:-1], r["sequencia"][1:]))


def test_cultura_atual_fora_das_candidatas_falha():
    cult, adeq, fam, pal = _dados()
    with pytest.raises(ValueError):
        otimizar(cult, "nao_existe", adeq, fam, pal)
