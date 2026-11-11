"""Monta tabela larga das bandas e os parquets de cada variante (mesma estrutura do ndvi_16d)."""
import json
from pathlib import Path
import numpy as np, pandas as pd
QUI = Path(__file__).parent; CACHE = QUI / "cache"; SNAP = QUI.parent / "dados13"
tar = json.load(open(QUI / "tarefas.json"))
FILL = {"evi": -3000, "red": -1000, "nir": -1000, "viq": -1}
ESC = {"evi": 1e-4, "red": 1e-4, "nir": 1e-4, "viq": 1}
rows = []
for pid, lat, lon, b, d0, d1 in tar:
    j = json.loads((CACHE / f"{pid}__{b}__{d0}_{d1}.json").read_text())
    for s in j["subset"]:
        rows.append((pid, s["calendar_date"], b, float(s["data"][0])))
long = pd.DataFrame(rows, columns=["ponto_id", "data", "b", "v"])
w = long.pivot_table(index=["ponto_id", "data"], columns="b", values="v", aggfunc="first").reset_index()
w["data"] = pd.to_datetime(w["data"])
for b in FILL:
    w[b] = w[b].where(w[b] != FILL[b]) * ESC[b]
w["evi"] = w["evi"].where(w["evi"].between(-0.2, 1.0))
for b in ("red", "nir"): w[b] = w[b].where(w[b].between(0, 1))
w["savi"] = 1.5 * (w["nir"] - w["red"]) / (w["nir"] + w["red"] + 0.5)
nd = pd.read_parquet(SNAP / "ndvi_16d.parquet")
m = nd.merge(w, on=["ponto_id", "data"], how="left", validate="1:1")
print("linhas", len(nd), "sem banda no cache:", int(m["red"].isna().sum() - nd["ndvi"].isna().sum()))
# checagem de consistencia: NDVI recalculado vs NDVI do snapshot
chk = (m["nir"] - m["red"]) / (m["nir"] + m["red"])
print("max|NDVI_calc - NDVI|:", float((chk - m["ndvi"]).abs().max()), "mediana", float((chk - m["ndvi"]).abs().median()))
viq = m["viq"]
v = viq.fillna(0).astype(int)
modland = v & 3; aer = (v >> 6) & 3; adj = (v >> 8) & 1; mix = (v >> 10) & 1; shd = (v >> 15) & 1
m["viq_bom"] = ((modland == 0) & (aer != 3) & (adj == 0) & (mix == 0) & (shd == 0)) & viq.notna()
print("viq_bom frac:", m.loc[viq.notna(), "viq_bom"].mean())
print(pd.crosstab(m["confiabilidade"], m["viq_bom"]))
print(m[["ndvi", "evi", "savi", "red", "nir"]].describe().round(3))
# mascara comum: todas as linhas onde os 3 indices existem (comparacao pareada nas mesmas linhas)
comum = m[["ndvi", "evi", "savi"]].notna().all(axis=1)
print("linhas com 3 indices:", int(comum.sum()), "de", int(m["ndvi"].notna().sum()))
m.to_parquet(QUI / "bandas_largas.parquet", index=False)
D = QUI / "variantes"; D.mkdir(exist_ok=True)
def salva(nome, idx, filtro=None):
    o = m[["ponto_id", "data", "confiabilidade"]].copy()
    o["ndvi"] = m[idx].where(comum)
    if filtro is not None:
        o.loc[~filtro, "ndvi"] = np.nan
    o[["ponto_id", "data", "ndvi", "confiabilidade"]].to_parquet(D / f"{nome}.parquet", index=False)
    print(nome, int(o["ndvi"].notna().sum()))
salva("ndvi", "ndvi"); salva("evi", "evi"); salva("savi", "savi")
salva("ndvi_conf0", "ndvi", m["confiabilidade"] == 0)
salva("ndvi_viq", "ndvi", m["viq_bom"])
