"""Sensibilidade do score do motor de rotação aos PESOS dos critérios (material de apoio à decisão).

NÃO define pesos. Roda o motor (src/culturas/motor.py, sem alterá-lo) com muitos conjuntos de pesos e mede
quanto o ranking e o top-3 mudam. Também mostra o efeito de culturas com lacunas (score com menos critérios).

Suposições DESTE script (não são dado de fonte; só servem para montar um perfil de teste):
- S1 perfil climático = média, sobre os anos 2001-2024, de uma janela de `dias` dias a partir de um dia/mês
  fixo (padrão: 120 dias desde 01/02). A janela é arbitrária; por isso o relatório repete com outras janelas.
- S2 temperatura do perfil = média de (tmax+tmin)/2 na janela; chuva = soma na janela (média entre anos).
- S3 amostra de pontos = sorteio com semente fixa entre os pontos do Ceará (id terminado em '_ce').

Uso: python -m src.culturas.sensibilidade [--saida data/processed/sensibilidade_pesos.json]
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import motor
from .tabela_culturas import carregar

RAIZ = Path(__file__).resolve().parents[2]
CRITERIOS = list(motor.PESOS)  # ordem fixa dos 5 critérios do motor
SEMENTE = 20240601
JANELAS = {"120d_desde_01fev": (2, 1, 120), "150d_desde_01jan": (1, 1, 150), "90d_desde_01mar": (3, 1, 90)}


# ---------------------------------------------------------------- perfis
def escolher_pontos(pontos: pd.DataFrame, n: int = 10, semente: int = SEMENTE) -> list[str]:
    ce = sorted(pontos.loc[pontos["ponto_id"].str.endswith("_ce"), "ponto_id"])
    rng = np.random.default_rng(semente)
    return sorted(rng.choice(ce, size=min(n, len(ce)), replace=False).tolist())


def perfil_do_ponto(clima: pd.DataFrame, ponto: str, mes: int, dia: int, dias: int) -> dict:
    d = clima[clima["ponto_id"] == ponto]
    temps, chuvas = [], []
    for ano in sorted(d["data"].dt.year.unique()):
        ini = pd.Timestamp(year=int(ano), month=mes, day=dia)
        j = d[(d["data"] >= ini) & (d["data"] < ini + pd.Timedelta(days=dias))]
        if len(j) < dias:  # janela incompleta: descarta o ano (não preenche)
            continue
        temps.append(((j["tmax_c"] + j["tmin_c"]) / 2).mean())
        chuvas.append(j["chuva_mm"].sum())
    if not temps:
        return {"local": ponto, "temp_media_c": None, "chuva_ciclo_mm": None}
    return {"local": ponto, "temp_media_c": round(float(np.mean(temps)), 2),
            "chuva_ciclo_mm": round(float(np.mean(chuvas)), 1)}


# ---------------------------------------------------------------- pesos
def pesos_dirichlet(n: int = 1000, semente: int = SEMENTE) -> np.ndarray:
    return np.random.default_rng(semente).dirichlet(np.ones(len(CRITERIOS)), size=n)


def pesos_grade(passo: float = 0.1) -> np.ndarray:
    k = round(1 / passo)
    comb = [c for c in itertools.product(range(k + 1), repeat=len(CRITERIOS)) if sum(c) == k]
    return np.array(comb, dtype=float) / k


def peso_base() -> np.ndarray:
    return np.array([motor.PESOS[c] for c in CRITERIOS])


# ---------------------------------------------------------------- notas (vêm do motor)
def notas_do_ponto(tab: dict, perfil: dict, atual: str) -> tuple[list[str], np.ndarray, dict]:
    """Candidatas viáveis (ordem alfabética) e matriz de notas [cultura x critério] (NaN = lacuna), via motor."""
    via = {c: motor.viabilidade(tab, c, perfil) for c in tab}
    cand = sorted(c for c in tab if c != atual and via[c]["estado"] == "viavel")
    estados = {c: via[c]["estado"] for c in tab if c != atual}
    if not cand:
        return [], np.zeros((0, len(CRITERIOS))), estados
    pont = motor.pontuar(tab, perfil, atual, [atual] + cand)
    m = np.array([[np.nan if pont[c]["notas"][k] is None else pont[c]["notas"][k] for k in CRITERIOS] for c in cand])
    return cand, m, estados


def scores(notas: np.ndarray, W: np.ndarray, criterios: list[int] | None = None) -> np.ndarray:
    """Score [n_pesos x n_culturas] como no motor: renormalizado pelos pesos dos critérios COM nota; arredonda a 0,1.
    `criterios`: restringe a esses índices (ex.: só os comuns). NaN onde nenhum critério tem nota."""
    nt = notas if criterios is None else notas[:, criterios]
    Wt = W if criterios is None else W[:, criterios]
    usado = ~np.isnan(nt)
    num = Wt @ np.where(usado, nt, 0.0).T
    den = Wt @ usado.T.astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        s = np.where(den > 0, 100 * num / den, np.nan)
    return np.round(s, 1)


def ordem(s: np.ndarray) -> np.ndarray:
    """Índices das culturas do melhor ao pior por linha; empate -> ordem alfabética (igual ao motor); NaN por último."""
    chave = np.where(np.isnan(s), -1.0, s)
    return np.argsort(-chave, axis=1, kind="stable")


def posicoes(o: np.ndarray) -> np.ndarray:
    p = np.empty_like(o)
    linhas = np.arange(o.shape[0])[:, None]
    p[linhas, o] = np.arange(o.shape[1])[None, :]
    return p


def spearman_pares(pos: np.ndarray, n_pares: int = 500, semente: int = SEMENTE) -> float:
    """Média da correlação de postos (Spearman) entre pares sorteados de conjuntos de pesos."""
    n, m = pos.shape
    if m < 3:
        return float("nan")
    rng = np.random.default_rng(semente)
    a, b = rng.integers(0, n, n_pares), rng.integers(0, n, n_pares)
    x, y = pos[a].astype(float), pos[b].astype(float)
    x -= x.mean(1, keepdims=True)
    y -= y.mean(1, keepdims=True)
    den = np.sqrt((x ** 2).sum(1) * (y ** 2).sum(1))
    ok = den > 0
    return float(((x * y).sum(1)[ok] / den[ok]).mean())


# ---------------------------------------------------------------- análise
def analisar_ponto(tab: dict, perfil: dict, atual: str, W: np.ndarray) -> dict | None:
    cand, notas, _ = notas_do_ponto(tab, perfil, atual)
    if len(cand) < 2:
        return None
    s = scores(notas, W)
    o = ordem(s)
    top3 = o[:, :3]
    k = min(3, len(cand))
    freq = {cand[i]: float((top3 == i).any(1).mean()) for i in range(len(cand))}
    base = ordem(scores(notas, peso_base()[None, :]))[0, :k]
    # empate no corte do top-3 (3º == 4º score) e efeito do desempate: o motor desempata por ordem alfabética
    ss = np.take_along_axis(s, o, axis=1)
    empate_corte = (ss[:, k - 1] == ss[:, k]) if len(cand) > k else np.zeros(len(W), bool)
    n = len(cand)
    o_inv = (n - 1) - ordem(s[:, ::-1])  # mesma ordenação com desempate alfabético invertido
    top3_inv = o_inv[:, :k]
    muda_desempate = np.array([set(a) != set(b) for a, b in zip(top3, top3_inv)])
    s_base = scores(notas, peso_base()[None, :])[0]
    inter = np.array([len(set(t[:k]) & set(base)) for t in top3])
    return {
        "n_candidatas": len(cand),
        "candidatas": cand,
        "freq_top3": dict(sorted(freq.items(), key=lambda kv: -kv[1])),
        "top3_base": [cand[i] for i in base],
        "top1_igual_base_pct": round(100 * float((o[:, 0] == base[0]).mean()), 1),
        "top3_igual_base_como_conjunto_pct": round(100 * float((inter == k).mean()), 1),
        "media_cultura_do_top3_base_que_permanece": round(float(inter.mean()), 2),
        "spearman_medio_entre_pesos": round(spearman_pares(posicoes(o)), 3),
        "empate_no_corte_top3_pct": round(100 * float(empate_corte.mean()), 1),
        "top3_muda_com_desempate_invertido_pct": round(100 * float(muda_desempate.mean()), 1),
        "n_candidatas_com_score_100_nos_pesos_base": int((s_base == 100).sum()),
        "n_top1_distintos": int(len(set(o[:, 0]))),
    }


def n_criterios_por_cultura(tab: dict, atual: str) -> dict[str, int]:
    """Quantos critérios (de 5) têm nota para a cultura, com base em todo o catálogo viável-ou-não (pontuar com todas)."""
    perfil = {"local": "x", "temp_media_c": 26.0, "chuva_ciclo_mm": 700.0}
    pont = motor.pontuar(tab, perfil, atual, list(tab))
    return {c: len(CRITERIOS) - len(pont[c]["criterios_sem_nota"]) for c in tab if c != atual}


def efeito_lacunas(tab: dict, perfil: dict, atual: str, W: np.ndarray) -> dict | None:
    """Compara 3 formas de ranquear: A) motor (cada cultura renormalizada nos critérios que tem);
    B) só critérios comuns a todas as candidatas; C) intervalo [lacuna=0 ; lacuna=1] (limites, não nota)."""
    cand, notas, _ = notas_do_ponto(tab, perfil, atual)
    if len(cand) < 3:
        return None
    comuns = [j for j in range(len(CRITERIOS)) if not np.isnan(notas[:, j]).any()]
    completa = ~np.isnan(notas).any(1)
    sa = scores(notas, W)
    sb = scores(notas, W, comuns)
    oa, ob = ordem(sa), ordem(sb)
    k = 3
    pa, pb = posicoes(oa).astype(float), posicoes(ob).astype(float)
    # correlação de postos A x B por conjunto de pesos
    xa, xb = pa - pa.mean(1, keepdims=True), pb - pb.mean(1, keepdims=True)
    den = np.sqrt((xa ** 2).sum(1) * (xb ** 2).sum(1))
    rho = np.where(den > 0, (xa * xb).sum(1) / np.where(den > 0, den, 1), np.nan)
    topa, topb = oa[:, :k], ob[:, :k]
    # fração de vagas no top-3 ocupadas por culturas com critérios completos
    comp_a = completa[topa].mean()
    comp_b = completa[topb].mean()
    # limites: lacuna = 0 (pior caso) e lacuna = 1 (melhor caso) — apenas para ver se o ranking é decidível
    peso_tot = W.sum(1, keepdims=True)
    nz = np.where(np.isnan(notas), 0.0, notas)
    miss = np.isnan(notas).astype(float)
    inf = np.round(100 * (W @ nz.T) / peso_tot, 1)
    sup = np.round(100 * (W @ (nz + miss).T) / peso_tot, 1)
    # cultura com score do motor acima do limite inferior de todas as demais com lacuna e do superior das incompletas?
    # medida simples: nº médio de candidatas cujo intervalo [inf,sup] se sobrepõe ao da melhor segundo o motor
    melhor = oa[:, 0]
    ar = np.arange(len(W))
    sob = ((sup >= inf[ar, melhor][:, None]) & (inf <= sup[ar, melhor][:, None])).sum(1) - 1
    return {
        "criterios_comuns": [CRITERIOS[j] for j in comuns],
        "n_com_5_criterios": int(completa.sum()),
        "n_com_menos_criterios": int((~completa).sum()),
        "spearman_motor_vs_comuns_medio": round(float(np.nanmean(rho)), 3),
        "top3_motor_pct_vagas_culturas_5crit": round(100 * float(comp_a), 1),
        "top3_comuns_pct_vagas_culturas_5crit": round(100 * float(comp_b), 1),
        "top1_igual_motor_vs_comuns_pct": round(100 * float((oa[:, 0] == ob[:, 0]).mean()), 1),
        "top3_igual_motor_vs_comuns_como_conjunto_pct": round(
            100 * float(np.mean([set(a) == set(b) for a, b in zip(topa, topb)])), 1),
        "media_candidatas_com_intervalo_sobreposto_ao_1o": round(float(sob.mean()), 2),
        "score_base_medio_culturas_5crit": round(float(scores(notas, peso_base()[None, :])[0][completa].mean()), 1),
        "score_base_medio_culturas_menos_crit": round(float(scores(notas, peso_base()[None, :])[0][~completa].mean()), 1),
        "top3_base_motor": [cand[i] for i in ordem(scores(notas, peso_base()[None, :]))[0, :3]],
        "top3_base_comuns": [cand[i] for i in ordem(scores(notas, peso_base()[None, :], comuns))[0, :3]],
    }


def nota_varia_com_candidatas(tab: dict, perfis: dict[str, dict], atual: str) -> dict:
    """A nota de N/palha é min-max entre as candidatas viáveis: a mesma cultura recebe notas diferentes por ponto."""
    out: dict[str, list[float]] = {}
    for p, perfil in perfis.items():
        cand, notas, _ = notas_do_ponto(tab, perfil, atual)
        for i, c in enumerate(cand):
            if not np.isnan(notas[i, CRITERIOS.index("n_na_biomassa")]):
                out.setdefault(c, []).append(round(float(notas[i, CRITERIOS.index("n_na_biomassa")]), 2))
    return {c: {"min": min(v), "max": max(v), "n_pontos": len(v)} for c, v in sorted(out.items())}


def rodar(atual: str = "milho", n_pontos: int = 10, n_dirichlet: int = 1000, tabela: dict | None = None,
          clima: pd.DataFrame | None = None, pontos: pd.DataFrame | None = None) -> dict:
    tab = tabela if tabela is not None else carregar()
    clima = clima if clima is not None else pd.read_parquet(RAIZ / "data/processed/clima_diario.parquet")
    pontos = pontos if pontos is not None else pd.read_csv(RAIZ / "data/processed/pontos.csv")
    ids = escolher_pontos(pontos, n_pontos)
    Wd, Wg = pesos_dirichlet(n_dirichlet), pesos_grade(0.1)
    res = {"cultura_atual": atual, "pontos": ids, "n_pesos_dirichlet": len(Wd), "n_pesos_grade_0_1": len(Wg),
           "pesos_base": motor.PESOS, "semente": SEMENTE, "n_culturas_tabela": len(tab),
           "n_criterios_por_cultura": n_criterios_por_cultura(tab, atual), "janelas": {}}
    for nome, (mes, dia, dias) in JANELAS.items():
        perfis = {p: perfil_do_ponto(clima, p, mes, dia, dias) for p in ids}
        j = {"perfis": perfis, "por_ponto": {}, "lacunas": {}}
        for p, perfil in perfis.items():
            if perfil["temp_media_c"] is None:
                continue
            a = analisar_ponto(tab, perfil, atual, Wd)
            ag = analisar_ponto(tab, perfil, atual, Wg)
            if a:
                a["grade_spearman_medio"] = ag["spearman_medio_entre_pesos"]
                a["grade_top1_igual_base_pct"] = ag["top1_igual_base_pct"]
                j["por_ponto"][p] = a
            el = efeito_lacunas(tab, perfil, atual, Wd)
            if el:
                j["lacunas"][p] = el
        pp = j["por_ponto"]
        if pp:
            agg: dict[str, list[float]] = {}
            for a in pp.values():
                for c, f in a["freq_top3"].items():
                    agg.setdefault(c, []).append(f)
            j["resumo"] = {
                "freq_top3_media_pct": dict(sorted(((c, round(100 * float(np.mean(v)), 1)) for c, v in agg.items()),
                                                   key=lambda kv: -kv[1])),
                "freq_top3_n_pontos_em_que_aparece_candidata": {c: len(v) for c, v in agg.items()},
                "spearman_medio": round(float(np.nanmean([a["spearman_medio_entre_pesos"] for a in pp.values()])), 3),
                "top1_igual_base_pct_medio": round(float(np.mean([a["top1_igual_base_pct"] for a in pp.values()])), 1),
                "top3_conjunto_igual_base_pct_medio": round(
                    float(np.mean([a["top3_igual_base_como_conjunto_pct"] for a in pp.values()])), 1),
                "empate_no_corte_top3_pct_medio": round(float(np.mean([a["empate_no_corte_top3_pct"] for a in pp.values()])), 1),
                "top3_muda_com_desempate_invertido_pct_medio": round(
                    float(np.mean([a["top3_muda_com_desempate_invertido_pct"] for a in pp.values()])), 1),
                "n_pontos_analisados": len(pp)}
            lz = j["lacunas"]
            if lz:
                j["resumo"]["lacunas_medias"] = {k: round(float(np.mean([v[k] for v in lz.values()])), 2) for k in (
                    "spearman_motor_vs_comuns_medio", "top3_motor_pct_vagas_culturas_5crit",
                    "top3_comuns_pct_vagas_culturas_5crit", "top1_igual_motor_vs_comuns_pct",
                    "top3_igual_motor_vs_comuns_como_conjunto_pct", "media_candidatas_com_intervalo_sobreposto_ao_1o",
                    "score_base_medio_culturas_5crit", "score_base_medio_culturas_menos_crit")}
        j["nota_N_varia_por_ponto"] = nota_varia_com_candidatas(tab, perfis, atual)
        res["janelas"][nome] = j
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--atual", default="milho")
    ap.add_argument("--saida", default=str(RAIZ / "data/processed/sensibilidade_pesos.json"))
    a = ap.parse_args()
    r = rodar(a.atual)
    Path(a.saida).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in r.items() if k != "janelas"}, ensure_ascii=False, indent=1))
    for nome, j in r["janelas"].items():
        print("\n==", nome)
        print(json.dumps(j.get("resumo"), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
