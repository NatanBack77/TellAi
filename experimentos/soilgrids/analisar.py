"""Análise das previsões guardadas. Uso: analisar.py selecao | confirma.
Skill = 1 - RMSE/RMSE_climatologia (anomalia: clim = prever 0), por ano, nas mesmas linhas para todas as variantes.
Pareado por ano contra a base DO MESMO modelo (ridge-persistência, xgboost-persistência). IC = percentil de bootstrap sobre anos (10000).
N total (Bonferroni): ver N_TOTAL."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.modelos.walkforward import _ic_inferior
OUT = Path(__file__).resolve().parent
# N total: novas_fontes 8 + ensemble 12 + conformal 6 + ACI 6 + soilgrids (5 variantes x 2 modelos) 10 = 42
N_ANT = {"novas_fontes": 8, "ensemble": 12, "conformal": 6, "aci": 6}
N_PROPRIO = 10
N_TOTAL = sum(N_ANT.values()) + N_PROPRIO
ALFA = 0.05 / N_TOTAL
VAR_SOLO = ["v1_solo", "v2_ad", "v3_inter", "v4_solo", "v4_ref"]


def skill_ano(p):
    g = p.assign(e2=(p.anomalia_ndvi - p.pred) ** 2, c2=p.anomalia_ndvi ** 2).groupby(["variante", "modelo", "ano"])[["e2", "c2"]].mean()
    return (1 - np.sqrt(g.e2 / g.c2)).rename("skill").reset_index()


def pareado(sk, var, mod, ref=None):
    a = sk[(sk.variante == var) & (sk.modelo == mod)].set_index("ano").skill
    b = sk[(sk.variante == "base") & (sk.modelo == mod)].set_index("ano").skill if ref is None else ref
    return (a - b.reindex(a.index)).dropna()


def cobertura(p, alvo=0.8, k=3, por_faixa=False):
    """Conformal temporal: quantil do |resíduo| dos k anos de teste anteriores (mesma variante/modelo), global ou por faixa. Cobertura/largura por ano."""
    p = p.assign(r=(p.anomalia_ndvi - p.pred).abs())
    anos = sorted(p.ano.unique()); linhas = []
    for Y in anos[k:]:
        cal = p[p.ano.isin(anos[anos.index(Y) - k:anos.index(Y)])]; te = p[p.ano == Y]
        if por_faixa:
            q = cal.groupby("faixa").r.quantile(alvo); qq = te.faixa.map(q).to_numpy()
        else:
            qq = np.full(len(te), cal.r.quantile(alvo))
        te = te.assign(cob=(te.r <= qq), larg=2 * qq)
        linhas.append({"ano": Y, "cob": te.cob.mean(), "larg": te.larg.mean(), **{f"cob_f{f}": g.cob.mean() for f, g in te.groupby("faixa")}})
    return pd.DataFrame(linhas)


def principal(modo):
    arq = "pred_selecao.pq" if modo == "selecao" else "pred_confirmacao.pq"
    P = pd.read_parquet(OUT / arq)
    sk = skill_ano(P)
    pl = {}
    for s in (11, 12, 13):
        f = OUT / f"pred_selecao_placebo{s}.pq"
        if modo == "selecao" and f.exists():
            pl[s] = skill_ano(pd.read_parquet(f))
    linhas = []
    for mod in ("ridge", "xgboost"):
        for var in ["base"] + VAR_SOLO:
            a = sk[(sk.variante == var) & (sk.modelo == mod)].set_index("ano").skill
            if a.empty: continue
            d = pareado(sk, var, mod)
            r = {"variante": var, "modelo": mod, "skill_media": a.mean(), "dif_vs_base": d.mean() if var != "base" else 0.0,
                 "ic_inf_corrigido": _ic_inferior(d.to_numpy(), ALFA, 10000, 42) if var != "base" else np.nan,
                 "ic_inf_5pct_sem_correcao": _ic_inferior(d.to_numpy(), 0.05, 10000, 42) if var != "base" else np.nan,
                 "frac_anos_dif_positiva": (d > 0).mean() if var != "base" else np.nan, "anos": len(a)}
            if modo == "selecao" and var in ("v1_solo", "v2_ad", "v3_inter", "v4_solo") and pl:
                dp = [pareado(s, var, mod, s[(s.variante == "base") & (s.modelo == mod)].set_index("ano").skill).mean() for s in pl.values()]
                r["placebo_dif_media"], r["placebo_dif_max"] = float(np.mean(dp)), float(np.max(dp))
            linhas.append(r)
    T = pd.DataFrame(linhas)
    T.to_csv(OUT / f"{modo}_resumo.csv", index=False); sk.to_csv(OUT / f"{modo}_skill_por_ano.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(f"N_TOTAL={N_TOTAL}, alfa corrigido={ALFA:.5f}"); print(T.round(4).to_string(index=False))
    if modo != "selecao":
        return
    # estação, viés por ano, conformal
    ext = []
    for (v, m), g in P.groupby(["variante", "modelo"]):
        for f, h in g.groupby("faixa"):
            ext.append({"variante": v, "modelo": m, "faixa": f, "rmse": np.sqrt(((h.anomalia_ndvi - h.pred) ** 2).mean()),
                        "skill": 1 - np.sqrt(((h.anomalia_ndvi - h.pred) ** 2).mean() / (h.anomalia_ndvi ** 2).mean()),
                        "r2": 1 - ((h.anomalia_ndvi - h.pred) ** 2).sum() / ((h.anomalia_ndvi - h.anomalia_ndvi.mean()) ** 2).sum()})
    E = pd.DataFrame(ext); E.to_csv(OUT / "selecao_por_estacao.csv", index=False)
    print("\nSkill por faixa de estação:"); print(E.pivot_table(index=["modelo", "variante"], columns="faixa", values="skill").round(4).to_string())
    B = []
    for (v, m, y), g in P.groupby(["variante", "modelo", "ano"]):
        B.append({"variante": v, "modelo": m, "ano": y, "vies": (g.anomalia_ndvi - g.pred).mean()})
    B = pd.DataFrame(B); B.to_csv(OUT / "selecao_vies_por_ano.csv", index=False)
    bs = B.groupby(["modelo", "variante"]).vies.agg(rms_vies_ano=lambda x: np.sqrt((x ** 2).mean()), min="min", max="max")
    print("\nViés por ano (resíduo médio): RMS, min, max"); print(bs.round(4).to_string())
    C = []
    for (v, m), g in P.groupby(["variante", "modelo"]):
        for alvo in (0.8, 0.9):
            for pf in (False, True):
                c = cobertura(g, alvo, 3, pf)
                C.append({"variante": v, "modelo": m, "alvo": alvo, "por_faixa": pf, "cob_media": c.cob.mean(), "cob_pior_ano": c.cob.min(),
                          "largura_media": c.larg.mean(), "cob_pior_faixa": c[[x for x in c.columns if x.startswith("cob_f")]].mean().min()})
    C = pd.DataFrame(C); C.to_csv(OUT / "selecao_conformal.csv", index=False)
    print("\nConformal temporal k=3 (cobertura média / pior ano / largura / pior faixa):")
    print(C[C.modelo == "ridge"].round(4).to_string(index=False)); print(C[(C.modelo == "xgboost")].round(4).to_string(index=False))


if __name__ == "__main__":
    principal(sys.argv[1])
