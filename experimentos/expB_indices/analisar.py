import sys, pickle
from pathlib import Path
RAIZ = str(__import__("pathlib").Path(__file__).resolve().parents[2])
sys.path.insert(0, RAIZ)
import numpy as np, pandas as pd
from src.modelos.walkforward import resumir, _ic_inferior
QUI = Path(__file__).parent
N = 10; A = 0.05 / N
pd.set_option("display.width", 250, "display.max_columns", 30)
for arq in ("res.pkl", "res_placebo.pkl"):
    if not (QUI / arq).exists(): continue
    R = pickle.load(open(QUI / arq, "rb"))
    print("=====", arq, list(R))
    linhas = []
    for ds, r in R.items():
        t = resumir(r, range(2010, 2022), [], n_variantes=N)
        t.insert(0, "dataset", ds); linhas.append(t)
        # n linhas de teste por ano
    T = pd.concat(linhas)
    cols = ["dataset", "variante", "modelo", "skill_media", "skill_agregada", "skill_ic_inf_corrigido", "frac_anos_positivos"]
    print(T[cols].sort_values(["variante", "modelo", "dataset"]).round(4).to_string(index=False))
    # diferenca pareada por ano contra NDVI (mesma variante/modelo)
    sk = pd.concat([r.assign(dataset=ds) for ds, r in R.items()])
    if "ndvi" in R:
        out = []
        for (v, m), g in sk.groupby(["variante", "modelo"]):
            p = g.pivot(index="ano_teste", columns="dataset", values="skill")
            for ds in p.columns:
                if ds == "ndvi": continue
                d = (p[ds] - p["ndvi"]).dropna().to_numpy()
                rng = np.random.default_rng(42)
                mm = rng.choice(d, size=(10000, len(d))).mean(1)
                out.append((v, m, ds, d.mean(), np.percentile(mm, 100 * A), np.percentile(mm, 100 * (1 - A)),
                            np.percentile(mm, 2.5), np.percentile(mm, 97.5), (d > 0).mean()))
        D = pd.DataFrame(out, columns=["variante", "modelo", "dataset", "dif_media", "ic_inf_bonf", "ic_sup_bonf", "ic95_inf", "ic95_sup", "frac_anos_melhor"])
        print("--- dif pareada (skill_ds - skill_ndvi) por ano; IC bootstrap sobre 12 anos")
        print(D.sort_values(["variante", "modelo", "dataset"]).round(4).to_string(index=False))
    n = sk[(sk.modelo == "ridge") & (sk.variante == "base")].pivot(index="ano_teste", columns="dataset", values="n")
    print("n teste por ano (ridge/base):\n", n.T.to_string())
