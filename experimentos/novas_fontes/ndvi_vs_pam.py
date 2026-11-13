"""O NDVI (e a anomalia dele) acompanha a produtividade municipal do IBGE (PAM)? Testa o limite do escopo: NDVI não é produtividade.

Dados: pam_ce.parquet (SIDRA 1612: rendimento médio, kg/ha, 2015-2023), ndvi_16d.parquet e clima_diario.parquet (pontos com `ibge` em pontos.csv).
Por município e ano: NDVI máximo de janeiro a julho (pico da estação), chuva de fevereiro a maio (quadra chuvosa). Para cada cultura:
anomalia do rendimento (% em relação à média do próprio município nos anos com dado) vs. anomalia do NDVI de pico (diferença para a média do
município). Correlação de Pearson e Spearman agrupadas (município-ano) e por município (mediana). Poucos anos por município (<= 9): resultado descritivo.
Não é modelo de produtividade; serve para dizer quanto o NDVI explica da variação do rendimento.
"""
import sys
from pathlib import Path
RAIZ = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, RAIZ)
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

R = Path(RAIZ)
OUT = Path(__file__).resolve().parent
pam = pd.read_parquet(R / "data/processed/pam_ce.parquet")
pts = pd.read_csv(R / "data/processed/pontos.csv").dropna(subset=["ibge"])
pts["ibge"] = pts["ibge"].astype(int)
ndvi = pd.read_parquet(R / "data/processed/ndvi_16d.parquet")
clima = pd.read_parquet(R / "data/processed/clima_diario.parquet", columns=["ponto_id", "data", "chuva_mm"])
ndvi = ndvi[ndvi["confiabilidade"].isin([0, 1])]
ndvi["ano"], ndvi["mes"] = ndvi["data"].dt.year, ndvi["data"].dt.month
pico = ndvi[ndvi["mes"].between(1, 7)].groupby(["ponto_id", "ano"])["ndvi"].max().rename("ndvi_pico").reset_index()
clima["ano"], clima["mes"] = clima["data"].dt.year, clima["data"].dt.month
chuva = clima[clima["mes"].between(2, 5)].groupby(["ponto_id", "ano"])["chuva_mm"].sum().rename("chuva_fma").reset_index()
m = pico.merge(chuva, on=["ponto_id", "ano"]).merge(pts[["ponto_id", "ibge"]], on="ponto_id")
rend = pam[pam["variavel"] == "rendimento_medio"].dropna(subset=["valor"])
rend = rend[rend["valor"] > 0]
rows = []
for prod, g in rend.groupby("produto"):
    x = g.merge(m, on=["ibge", "ano"])
    if x["ibge"].nunique() < 30 or len(x) < 150:
        continue
    for c in ("ndvi_pico", "chuva_fma"):
        x[c + "_anom"] = x[c] - x.groupby("ibge")[c].transform("mean")
    x["rend_anom"] = 100 * (x["valor"] / x.groupby("ibge")["valor"].transform("mean") - 1)
    x = x[x.groupby("ibge")["valor"].transform("count") >= 5]
    for c in ("ndvi_pico_anom", "chuva_fma_anom"):
        pr, sp = pearsonr(x[c], x["rend_anom"])[0], spearmanr(x[c], x["rend_anom"])[0]
        por_mun = x.groupby("ibge").apply(lambda z: spearmanr(z[c], z["rend_anom"])[0] if len(z) >= 5 else np.nan, include_groups=False)
        rows.append({"produto": prod, "preditor": c, "n_mun": int(x["ibge"].nunique()), "n_obs": len(x), "pearson": pr, "spearman": sp,
                     "r2_pearson": pr ** 2, "mediana_spearman_por_municipio": float(por_mun.median()),
                     "frac_municipios_positivos": float((por_mun > 0).mean())})
r = pd.DataFrame(rows)
r.to_csv(OUT / "ndvi_vs_pam.csv", index=False)
pd.set_option("display.width", 220, "display.max_columns", 20)
print(r.round(3).to_string(index=False))
