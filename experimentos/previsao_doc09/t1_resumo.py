"""Resumo do teste 1: skill por horizonte x estacao (so 2010-2021), IC bootstrap sobre anos, comparacao pareada."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
D = Path(__file__).parent
rng = np.random.default_rng(42)

def ic(v, a=0.05, n=10000):
    v = np.asarray(v, float)
    m = rng.choice(v, size=(n, len(v))).mean(axis=1)
    return np.percentile(m, 100 * a / 2), np.percentile(m, 100 * (1 - a / 2))

def tabela(arq):
    r = pd.read_pickle(D / arq)
    r["mes"] = pd.to_datetime(r["data"]).dt.month
    r["estacao"] = np.where(r["mes"].between(2, 5), "chuvosa(fev-mai)", "resto(jun-jan)")
    r["e2"] = (r["anomalia_ndvi"] - r["pred"]) ** 2; r["y2"] = r["anomalia_ndvi"] ** 2
    out = {}
    for (h, est, var, ano), g in r.groupby(["h", "estacao", "variante", "ano_teste"]):
        out[(h, est, var, ano)] = (1 - np.sqrt(g.e2.sum() / g.y2.sum()), len(g))
    s = pd.Series({k: v[0] for k, v in out.items()}); n = pd.Series({k: v[1] for k, v in out.items()})
    s.index.names = n.index.names = ["h", "estacao", "variante", "ano"]
    # linhas "todas"
    return s, n, r

def resumo(arq):
    s, n, r = tabela(arq)
    # skill todas estacoes
    r2 = r.copy(); r2["estacao"] = "todas"
    allr = pd.concat([r, r2])
    sk = allr.groupby(["h", "estacao", "variante", "ano_teste"]).apply(lambda g: 1 - np.sqrt(g.e2.sum() / g.y2.sum()), include_groups=False)
    nn = allr.groupby(["h", "estacao", "variante", "ano_teste"]).size()
    linhas = []
    for (h, est), _ in sk.groupby(level=[0, 1]):
        u = sk.loc[(h, est)].unstack("variante")          # anos x variantes
        for v in u.columns:
            m = u[v].mean(); lo, hi = ic(u[v].dropna())
            linha = {"h": h, "estacao": est, "variante": v, "skill_media": m, "ic95_lo": lo, "ic95_hi": hi,
                     "anos_pos": f"{int((u[v] > 0).sum())}/{u[v].notna().sum()}", "n_linhas": int(nn.loc[(h, est, v)].sum())}
            if v != "pers_lags4":
                d = (u["pers_lags4"] - u[v]).dropna()
                linha["pers_lags4_menos_este"] = d.mean()
            linhas.append(linha)
        # contribuicao do clima: pers_lags4 - so_lags4 ; base - 0
        d = (u["pers_lags4"] - u["so_lags4"]).dropna(); lo, hi = ic(d)
        linhas.append({"h": h, "estacao": est, "variante": "CLIMA_ADICIONA(pers_lags4-so_lags4)", "skill_media": d.mean(),
                       "ic95_lo": lo, "ic95_hi": hi, "anos_pos": f"{int((d > 0).sum())}/{len(d)}", "n_linhas": int(nn.loc[(h, est, 'pers_lags4')].sum())})
    return pd.DataFrame(linhas)

if __name__ == "__main__":
    pd.set_option("display.width", 250, "display.max_rows", 500)
    arq = sys.argv[1]
    t = resumo(arq)
    t.to_csv(D / (arq.replace(".pkl", "_resumo.csv")), index=False)
    for est in ("todas", "chuvosa(fev-mai)", "resto(jun-jan)"):
        print("=====", est, arq)
        x = t[t.estacao == est].pivot(index="variante", columns="h", values="skill_media").round(4)
        print(x.to_string())
        print("IC95 (lo,hi) pers_lags4 / CLIMA_ADICIONA:")
        for v in ("pers_lags4", "CLIMA_ADICIONA(pers_lags4-so_lags4)", "base"):
            y = t[(t.estacao == est) & (t.variante == v)]
            print(v, [(int(a), round(b, 3), round(c, 3), d) for a, b, c, d in zip(y.h, y.ic95_lo, y.ic95_hi, y.anos_pos)])
