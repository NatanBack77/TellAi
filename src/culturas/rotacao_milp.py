"""Rotação por Programação Linear Inteira Mista (MILP; `scipy.optimize.milp`, sem dependência nova).

Escolhe UMA sequência de T safras (a 1ª é a cultura atual) que maximiza uma nota aditiva, com regras DURAS opcionais e, se pedido, um critério ROBUSTO ao clima.
É um complemento ao simulador SMAA de `rotacao.py`, não substituto: o MILP devolve um ótimo para pesos fixos; o SMAA mostra o quanto o ranking
depende dos pesos e das lacunas (empate técnico). Onde o MILP ajuda: horizonte longo (5+ safras, onde enumerar explode), regras duras (ex.: ao menos
uma leguminosa; nunca a mesma cultura duas vezes seguidas) e otimização contra anos ruins (CVaR). Onde NÃO ajuda: separar alternativas empatadas
(isso depende de dado novo) e tratar lacunas (aqui valem 0,5 neutro, declarado; o SMAA trata lacuna como incerteza).

Variáveis: x[t,c] binária (cultura c na safra t); z[t,c,c'] = x[t,c] AND x[t+1,c'] (recompensas de transição) ligadas por restrições de FLUXO
(sum_c' z = x[t,c]; sum_c z = x[t+1,c']), mais apertadas que z <= x (modelo de fluxo de Alfandari et al., 2011; 10x a 100x mais rápido).
Nota por safra (média de 0 a 1): w_adeq * adequação ao clima + w_palha * palha normalizada; por transição: w_div * (família muda) + w_leg * (leguminosa -> não leguminosa).
Robusto (CVaR de nível beta): maximiza a média da adequação nos beta% piores anos de clima (Rockafellar e Uryasev), com o mesmo ano de clima nas T safras (SUPOSIÇÃO).
"""
from __future__ import annotations

import itertools

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

LEGUMINOSA = "Leguminosae"


def _indices(T: int, C: int):
    nx = T * C
    nz = (T - 1) * C * C
    return nx, nz, (lambda t, c: t * C + c), (lambda t, c, d: nx + (t * C + c) * C + d)


def otimizar(culturas: list[str], atual: str, adeq_por_ano: dict[str, np.ndarray], familia: dict[str, str | None], palha: dict[str, float | None],
             T: int = 3, pesos: dict | None = None, regras: dict | None = None, robusto_beta: float | None = None, limite_s: float = 30.0) -> dict:
    """Melhor sequência de T safras. `adeq_por_ano[c]`: adequação (0-1) de c em cada ano de clima. Devolve sequência, nota e status do solver."""
    if atual not in culturas:
        raise ValueError("a cultura atual precisa estar entre as candidatas")
    w = {"adeq": 1.0, "palha": 1.0, "div": 1.0, "leg": 1.0, **(pesos or {})}
    regras = regras or {}
    C = len(culturas)
    pos = {c: i for i, c in enumerate(culturas)}
    A = np.array([adeq_por_ano[c] for c in culturas], float)          # [C, anos]
    K = A.shape[1]
    s_adeq = A.mean(axis=1)
    pal = np.array([np.nan if palha.get(c) is None else palha[c] for c in culturas], float)
    if np.isnan(pal).all() or np.nanmax(pal) == np.nanmin(pal):
        s_pal = np.full(C, 0.5)
    else:
        s_pal = (pal - np.nanmin(pal)) / (np.nanmax(pal) - np.nanmin(pal))
    s_pal = np.where(np.isnan(s_pal), 0.5, s_pal)                       # lacuna = 0,5 neutro (declarado)
    leg = np.array([familia.get(c) == LEGUMINOSA for c in culturas])
    div = np.array([[0.0 if (familia.get(a) is None or familia.get(a) == familia.get(b)) else 1.0 for b in culturas] for a in culturas])
    legt = np.array([[1.0 if (leg[a] and not leg[b]) else 0.0 for b in range(C)] for a in range(C)])
    nx, nz, X, Z = _indices(T, C)
    nrob = (1 + K) if robusto_beta else 0                              # eta + u_k
    n = nx + nz + nrob
    cobj = np.zeros(n)
    wsum = w["adeq"] + w["palha"] + w["div"] + w["leg"]
    for t in range(T):
        for c in range(C):
            nota = w["palha"] * s_pal[c] + (0.0 if robusto_beta else w["adeq"] * s_adeq[c])
            cobj[X(t, c)] = nota / T
    for t in range(T - 1):
        for c in range(C):
            for d in range(C):
                cobj[Z(t, c, d)] = (w["div"] * div[c, d] + w["leg"] * legt[c, d]) / max(T - 1, 1)
    if robusto_beta:
        ie, iu = nx + nz, nx + nz + 1
        cobj[ie] = w["adeq"]                                           # eta - 1/(K beta) sum u
        cobj[iu:iu + K] = -w["adeq"] / (K * robusto_beta)
    A_ub, b_ub, A_eq, b_eq = [], [], [], []
    for t in range(T):                                                 # uma cultura por safra
        r = np.zeros(n); r[[X(t, c) for c in range(C)]] = 1; A_eq.append(r); b_eq.append(1)
    r = np.zeros(n); r[X(0, pos[atual])] = 1; A_eq.append(r); b_eq.append(1)   # safra 1 = cultura atual
    for t in range(T - 1):                                             # modelo de FLUXO: sum_d z[t,c,d] = x[t,c] e sum_c z[t,c,d] = x[t+1,d]
        for c in range(C):
            r = np.zeros(n); r[[Z(t, c, d) for d in range(C)]] = 1; r[X(t, c)] = -1; A_eq.append(r); b_eq.append(0)
        for d in range(C):
            r = np.zeros(n); r[[Z(t, c, d) for c in range(C)]] = 1; r[X(t + 1, d)] = -1; A_eq.append(r); b_eq.append(0)
    if regras.get("sem_repetir_seguida"):
        for t in range(T - 1):
            for c in range(C):
                r = np.zeros(n); r[X(t, c)] = 1; r[X(t + 1, c)] = 1; A_ub.append(r); b_ub.append(1)
    if regras.get("min_leguminosas"):
        r = np.zeros(n)
        for t in range(T):
            for c in np.flatnonzero(leg):
                r[X(t, c)] = -1
        A_ub.append(r); b_ub.append(-regras["min_leguminosas"])
    if regras.get("max_repeticoes"):
        for c in range(C):
            r = np.zeros(n); r[[X(t, c) for t in range(T)]] = 1; A_ub.append(r); b_ub.append(regras["max_repeticoes"])
    if robusto_beta:                                                   # u_k >= eta - S_k ; S_k = soma de adeq no ano k
        for k in range(K):
            r = np.zeros(n); r[nx + nz + 1 + k] = -1; r[nx + nz] = 1
            for t in range(T):
                for c in range(C):
                    r[X(t, c)] -= A[c, k] / T
            A_ub.append(r); b_ub.append(0)
    cons = []
    if A_eq:
        cons.append(LinearConstraint(np.array(A_eq), b_eq, b_eq))
    if A_ub:
        cons.append(LinearConstraint(np.array(A_ub), -np.inf, b_ub))
    integ = np.zeros(n); integ[:nx] = 1
    lb, ub = np.zeros(n), np.ones(n)
    if robusto_beta:
        lb[nx + nz:] = -np.inf; ub[nx + nz:] = np.inf; lb[nx + nz + 1:] = 0
    res = milp(-cobj, constraints=cons, integrality=integ, bounds=Bounds(lb, ub), options={"time_limit": limite_s})
    if res.x is None:
        return {"status": res.message, "sequencia": None, "viavel": False}
    xs = np.round(res.x[:nx]).reshape(T, C)
    seq = [culturas[int(np.argmax(xs[t]))] for t in range(T)]
    return {"status": res.message, "viavel": True, "sequencia": seq, "objetivo": float(-res.fun), "otimo_provado": bool(res.status == 0),
            "robusto_beta": robusto_beta, "horizonte": T, "regras": regras}


def nota_sequencia(seq, culturas, adeq_por_ano, familia, palha, pesos=None, robusto_beta=None) -> float:
    """Mesma nota do MILP calculada por fora (para conferir o ótimo por enumeração)."""
    w = {"adeq": 1.0, "palha": 1.0, "div": 1.0, "leg": 1.0, **(pesos or {})}
    T = len(seq)
    pal = np.array([np.nan if palha.get(c) is None else palha[c] for c in culturas], float)
    s_pal = np.full(len(culturas), 0.5) if (np.isnan(pal).all() or np.nanmax(pal) == np.nanmin(pal)) else (pal - np.nanmin(pal)) / (np.nanmax(pal) - np.nanmin(pal))
    s_pal = dict(zip(culturas, np.where(np.isnan(s_pal), 0.5, s_pal)))
    tot = sum(w["palha"] * s_pal[c] / T for c in seq)
    if robusto_beta:
        S = np.mean([adeq_por_ano[c] for c in seq], axis=0)            # por ano de clima
        k = len(S)
        # CVaR exato (Rockafellar e Uryasev): maximo sobre eta de eta - E[(eta - S)+]/beta, atingido num dos valores de S
        etas = np.unique(S)
        tot += w["adeq"] * max(e - np.maximum(e - S, 0).sum() / (k * robusto_beta) for e in etas)
    else:
        tot += w["adeq"] * np.mean([np.mean(adeq_por_ano[c]) for c in seq])
    for a, b in zip(seq[:-1], seq[1:]):
        fa, fb = familia.get(a), familia.get(b)
        tot += (w["div"] * (0.0 if (fa is None or fa == fb) else 1.0)
                + w["leg"] * (1.0 if (fa == LEGUMINOSA and fb != LEGUMINOSA) else 0.0)) / max(T - 1, 1)
    return float(tot)


def melhor_por_enumeracao(culturas, atual, adeq_por_ano, familia, palha, T=3, pesos=None, regras=None, robusto_beta=None):
    regras = regras or {}
    melhor, nota = None, -np.inf
    for resto in itertools.product(culturas, repeat=T - 1):
        s = (atual,) + resto
        if regras.get("sem_repetir_seguida") and any(a == b for a, b in zip(s[:-1], s[1:])):
            continue
        if regras.get("min_leguminosas") and sum(familia.get(c) == LEGUMINOSA for c in s) < regras["min_leguminosas"]:
            continue
        if regras.get("max_repeticoes") and max(s.count(c) for c in set(s)) > regras["max_repeticoes"]:
            continue
        v = nota_sequencia(s, culturas, adeq_por_ano, familia, palha, pesos, robusto_beta)
        if v > nota + 1e-12:
            melhor, nota = s, v
    return list(melhor) if melhor else None, float(nota)
