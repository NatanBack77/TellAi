"""Diagnosticos complementares: motivo de descarte das linhas 2025+ e bootstrap so de 2025 e so de 2026."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pandas as pd
import prospectivo as P
ent = P.carregar(); ds = P.construir_dataset(ent, P.cfg)
d, cols = P.preparar(ds, 2025)
n = d[d["ano"] >= 2025]
sai = {"linhas_ndvi_valido_2025plus": int(len(n)), "sem_clima_completo": int((~n["completo"]).sum()),
       "sem_anomalia(slot<3 anos)": int(n["anomalia_ndvi"].isna().sum()),
       "sem_lag1": int(n["anom_lag1"].isna().sum()), "sem_lag2_mas_lag1_ok": int((n["anom_lag1"].notna() & n["anom_lag2"].isna()).sum()),
       "testaveis": int(n["_ok"].sum())}
te = pd.read_csv(P.OUT / "previsoes_2025plus.csv", parse_dates=["data"]); te["ano"] = te["data"].dt.year
for a in (2025, 2026):
    x = te[te["ano"] == a]
    sai[f"boot_{a}"] = {"xgb": P.boot_skill(x, "e_xgb", "anomalia_ndvi", "data"), "ridge": P.boot_skill(x, "e_ridge", "anomalia_ndvi", "data"),
                        "ingenua": P.boot_skill(x, "e_ing", "anomalia_ndvi", "data"), "n": int(len(x))}
print(json.dumps(sai, indent=1, ensure_ascii=False))
(P.OUT / "extras.json").write_text(json.dumps(sai, indent=1, ensure_ascii=False))
