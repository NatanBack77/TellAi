"""Células nunca vistas: GroupKFold(5) por célula POWER, 2001-2021 (mistura tempo: otimista, mesmo desenho de overfit_underfit/diagnostico.py).
Anomalia com climatologia de 2001-2021 (como no diagnóstico). Reporta skill agrupada e diferença pareada POR ANO (linhas de teste de todas as dobras)
contra a base do mesmo modelo. Placebo: solo permutado entre pontos (sementes 11, 12, 13)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import nucleo as N
from sklearn.model_selection import GroupKFold
from src.modelos.preditivo import ajustar_modelo
from src.modelos.walkforward import _ic_inferior
OUT = Path(__file__).resolve().parent

def rodar(d0, cf0, Z):
    res = []
    grupos = d0["celula_power"].to_numpy()
    for tri, tei in GroupKFold(n_splits=5).split(d0, groups=grupos):
        tr0, te0 = d0.iloc[tri], d0.iloc[tei]
        for nome in N.MODELOS:
            P, cache = {}, None
            for v in ("base", "v1_solo", "v2_ad", "v3_inter"):
                dd, ex = N.colunas_solo(d0, Z, v); cf = cf0 + ex
                tr, te = dd.iloc[tri], dd.iloc[tei]
                mod, _ = ajustar_modelo(nome, tr[cf], tr["anomalia_ndvi"].to_numpy(), tr["celula_power"].to_numpy(), N.cfg)
                P[v] = mod.predict(te[cf])
                if v == "base": cache = (mod, tr)
            mod, tr = cache
            via_solo, _ = N.vies_ponto(tr, mod.predict(tr[cf0]), Z, te0["ponto_id"])
            P["v4_solo"] = P["base"] + te0["ponto_id"].map(via_solo).to_numpy()
            for v, p in P.items():
                x = te0[["ponto_id", "celula_power", "ano", "faixa", "anomalia_ndvi"]].copy(); x["variante"], x["modelo"], x["pred"] = v, nome, p
                res.append(x)
    return pd.concat(res)

if __name__ == "__main__":
    df = N.carregar_df()
    d0, cf0 = N.preparar_fold(df, N.nomes_features(N.cfg, False), list(range(2001, 2022)))
    d0 = d0[d0["_ok"] & (d0["ano"] <= 2021)].reset_index(drop=True)
    print("linhas", len(d0), "celulas", d0.celula_power.nunique(), flush=True)
    out = {"real": rodar(d0, cf0, N.mapa_solo(None))}
    for s in (11, 12, 13):
        out[f"placebo{s}"] = rodar(d0, cf0, N.mapa_solo(s)); print("placebo", s, flush=True)
    linhas = []
    for k, R in out.items():
        g = R.assign(e2=(R.anomalia_ndvi - R.pred) ** 2, c2=R.anomalia_ndvi ** 2).groupby(["modelo", "variante", "ano"])[["e2", "c2"]].mean()
        sk = (1 - np.sqrt(g.e2 / g.c2)).rename("skill").reset_index()
        for (m, v), h in sk.groupby(["modelo", "variante"]):
            b = sk[(sk.modelo == m) & (sk.variante == "base")].set_index("ano").skill
            d = (h.set_index("ano").skill - b)
            linhas.append({"cenario": k, "modelo": m, "variante": v, "skill_media_anos": h.skill.mean(), "dif_vs_base": d.mean(),
                           "ic_inf_5pct": _ic_inferior(d.to_numpy(), 0.05, 10000, 42), "frac_anos_pos": (d > 0).mean()})
    T = pd.DataFrame(linhas); T.to_csv(OUT / "celulas_novas.csv", index=False)
    pd.set_option("display.width", 200)
    print(T[T.variante != "base"].round(4).to_string(index=False)); print(T[(T.variante == "base") & (T.cenario == "real")].round(4).to_string(index=False))
