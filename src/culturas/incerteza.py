"""Monte Carlo estilo SMAA-2 (Lahdelma e Salminen, 2001; só a ideia, em numpy) para ranking com incerteza.

Cada sorteio escolhe: (1) um vetor de pesos (Dirichlet, opcionalmente ordenado), (2) o ano do clima (mesmo ano para
todas as culturas do ponto) e (3) uma nota Uniforme[0,1] para cada lacuna. O score NÃO é renormalizado: lacuna
entra como incerteza, não é removida nem premiada. Saída por cultura: faixa de score (percentis), intervalo de
posição, índice de aceitabilidade de posição, P(top-N) e empate técnico.

Posição com empate exato: o grupo empatado divide igualmente as posições que ocupa (nenhum desempate por nome).
"""
from __future__ import annotations

import numpy as np

from .parametros import Parametros

LEITURA = ("Sensibilidade do modelo a pesos, lacunas e anos de clima, dentro do que foi declarado em `suposicoes`. "
           "Não é intervalo de confiança estatístico nem chance de a rotação dar certo na roça. A avaliar com técnico local.")


def sortear_pesos(k: int, nomes: list[str], p: Parametros, rng: np.random.Generator) -> np.ndarray:
    """[n_sorteios x k] pesos que somam 1. Com `ordem_pesos`, o maior peso vai ao critério mais importante (SMAA-O)."""
    w = rng.dirichlet(np.full(k, p.dirichlet_alfa), size=p.n_sorteios)
    if p.ordem_pesos:
        ordem = [c for c in p.ordem_pesos if c in nomes]
        resto = [c for c in nomes if c not in ordem]
        ordem += resto  # critérios sem ordem declarada entram no fim (menos importantes)
        w = -np.sort(-w, axis=1)  # decrescente
        pos = [nomes.index(c) for c in ordem]
        out = np.empty_like(w)
        out[:, pos] = w
        w = out
    return w


def _posicoes(score: np.ndarray, tol: float) -> tuple[np.ndarray, np.ndarray]:
    """g = nº de culturas estritamente melhores; e = tamanho do grupo empatado (inclui a própria)."""
    dif = score[:, None, :] - score[:, :, None]  # [s, i, j] = score_j - score_i
    g = (dif > tol).sum(axis=2)
    e = (np.abs(dif) <= tol).sum(axis=2)
    return g, e


def _resumo_ranking(score: np.ndarray, p: Parametros) -> dict:
    """Estatísticas SMAA de um bloco de scores [sorteios x candidatas]."""
    n, c = score.shape
    g, e = _posicoes(score, p.tol_empate)
    aceit = np.zeros((c, c))
    for r in range(c):
        aceit[:, r] = (((g <= r) & (r < g + e)) / e).mean(axis=0)
    topo = min(p.top_n, c)
    p_top = aceit[:, :topo].sum(axis=1)
    mid = g + (e + 1) / 2.0
    return {"aceit": aceit, "p_topo": p_top, "p_1o": aceit[:, 0],
            "pos_p_baixo": np.floor(np.percentile(mid, p.percentil_baixo, axis=0)),
            "pos_p_alto": np.ceil(np.percentile(mid, p.percentil_alto, axis=0)),
            "pos_media": mid.mean(axis=0), "frac_empate": (e > 1).mean(axis=0)}


def _empates_tecnicos(lo: np.ndarray, hi: np.ndarray) -> list[list[int]]:
    """Para cada candidata, índices das OUTRAS com intervalo [lo, hi] sobreposto (não é relação transitiva)."""
    n = len(lo)
    return [[j for j in range(n) if j != i and lo[i] <= hi[j] and lo[j] <= hi[i]] for i in range(n)]


def simular(nota: np.ndarray, criterios: list[str], principais: list[str], ranqueia: np.ndarray, p: Parametros) -> dict:
    """SMAA-2 sobre o tensor de notas.

    nota: [culturas x critérios x anos] (NaN = lacuna; critérios sem variação por ano repetem o valor no eixo dos anos).
    principais: critérios do ranking principal (subconjunto de `criterios`); o modelo 'completo' usa todos.
    ranqueia: máscara das culturas que entram no ranking (as demais, ex. a cultura atual, só recebem faixa de score).
    """
    C, K, Y = nota.shape
    rng = np.random.default_rng(p.semente)
    anos = rng.integers(0, Y, size=p.n_sorteios)
    lac = rng.random((p.n_sorteios, C, K))
    base = np.transpose(nota[:, :, anos], (2, 0, 1))  # [s, c, k]
    notas_s = np.where(np.isnan(base), lac, base)
    saida = {}
    for rotulo, crit in (("principal", principais), ("completo", criterios)):
        idx = [criterios.index(x) for x in crit]
        w = sortear_pesos(len(idx), crit, p, rng)
        score = 100.0 * np.einsum("sk,sck->sc", w, notas_s[:, :, idx])
        lo = np.percentile(score, p.percentil_baixo, axis=0)
        hi = np.percentile(score, p.percentil_alto, axis=0)
        r_idx = np.flatnonzero(ranqueia)
        rk = _resumo_ranking(score[:, r_idx], p) if len(r_idx) else None
        emp = _empates_tecnicos(lo[r_idx], hi[r_idx]) if len(r_idx) else []
        saida[rotulo] = {"criterios": crit, "score_lo": lo, "score_hi": hi, "score_mediana": np.median(score, axis=0),
                         "ranking": rk, "r_idx": r_idx, "empates": emp, "score": score}
    return saida
