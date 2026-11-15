"""Confere o pipeline NOVO (src/modelos/previsao.py: modelo de produção treinado 2001-2021 + dados atuais) contra
`previsoes_2025plus.csv` (modelo congelado treinado 2001-2024, climatologia 2001-2024).  NAO altera src/ nem retreina nada.

    python experimentos/prospectivo_2025/comparar_pipeline_novo.py     (grava comparacao_pipeline_novo.json nesta pasta)

As duas previsoes NAO sao o mesmo modelo (treino e climatologia do alvo diferem), entao a comparacao e feita em unidades de NDVI
(anomalia + climatologia do respectivo modelo) e a diferenca e DOCUMENTADA, nao forcada a zero."""
import json, sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import numpy as np, pandas as pd
from src.modelos import previsao as P
from src.modelos.features import adicionar_anomalia, adicionar_persistencia

OUT = Path(__file__).resolve().parent
ctx = P.carregar_ou_treinar()
cfg, mc, ds = ctx["cfg"], ctx["mc"], ctx["ds"]
pers = cfg["preditivo"].get("persistencia_max_gap_dias", 17)
csv = pd.read_csv(OUT / "previsoes_2025plus.csv", parse_dates=["data"])

# lado de producao: climatologia 2001-2021, modelo de producao (so o que ja estava treinado), 1 passo, dados atuais
d, _ = adicionar_persistencia(adicionar_anomalia(ds, ctx["treino_anos"], cfg), pers)
d["clim21"] = d["ndvi"] - d["anomalia_ndvi"]
# lado do prospectivo: climatologia 2001-2024
d24 = adicionar_anomalia(ds, list(range(2001, 2025)), cfg)[["ponto_id", "data", "ndvi_clim"]].rename(columns={"ndvi_clim": "clim24"})
d = d.merge(d24, on=["ponto_id", "data"])
d = d[(d["ano"] >= 2025) & d["completo"] & d["anomalia_ndvi"].notna() & d[["anom_lag1", "anom_lag2"]].notna().all(axis=1)].copy()
X = d[mc.cols]
fora = np.zeros(len(d), bool)
for c, (lo, hi) in mc.faixas.items():
    fora |= ((X[c] < lo) | (X[c] > hi)).to_numpy()
d["p_prod"] = mc.modelo.predict(X)
m = d.merge(csv[["ponto_id", "data", "p_xgb", "anomalia_ndvi"]].rename(columns={"anomalia_ndvi": "anom24_obs"}), on=["ponto_id", "data"])
m["ndvi_prev_prod"] = m["clim21"] + m["p_prod"]
m["ndvi_prev_pros"] = m["clim24"] + m["p_xgb"]
m["ndvi_obs"] = m["ndvi"]
rm = lambda e: float(np.sqrt(np.mean(np.square(e))))
res = {"modelo_producao": mc.nome, "treino_producao": ctx["treino_anos"][0:1] + ctx["treino_anos"][-1:],
       "linhas_csv_prospectivo": int(len(csv)), "linhas_pipeline_novo_2025plus": int(len(d)), "linhas_em_comum": int(len(m)),
       "linhas_sem_numero_por_extrapolacao_no_pipeline_novo": int(fora.sum()),
       "dif_ndvi_prev_media_abs": float((m["ndvi_prev_prod"] - m["ndvi_prev_pros"]).abs().mean()),
       "dif_ndvi_prev_max_abs": float((m["ndvi_prev_prod"] - m["ndvi_prev_pros"]).abs().max()),
       "correlacao_ndvi_prev": float(m[["ndvi_prev_prod", "ndvi_prev_pros"]].corr().iloc[0, 1]),
       "rmse_ndvi_producao": rm(m["ndvi_obs"] - m["ndvi_prev_prod"]), "rmse_ndvi_prospectivo": rm(m["ndvi_obs"] - m["ndvi_prev_pros"]),
       "rmse_ndvi_clim21": rm(m["ndvi_obs"] - m["clim21"]), "rmse_ndvi_clim24": rm(m["ndvi_obs"] - m["clim24"])}
res["skill_producao_vs_clim21"] = 1 - res["rmse_ndvi_producao"] / res["rmse_ndvi_clim21"]
res["skill_prospectivo_vs_clim24"] = 1 - res["rmse_ndvi_prospectivo"] / res["rmse_ndvi_clim24"]
# consistencia: a rota prever_um_composto (retrospectiva, alvo dado) reproduz o lote nas mesmas linhas
amostra = m.sort_values(["ponto_id", "data"]).iloc[::max(1, len(m) // 40)].head(40)
difs = []
for _, r in amostra.iterrows():
    out = P.prever_um_composto(r["ponto_id"], ctx, composto_alvo=r["data"])
    difs.append(abs(out["anomalia_ndvi_prevista"] - r["p_prod"]) if out["anomalia_ndvi_prevista"] is not None else np.nan)
res["amostra_prever_um_composto"] = {"n": len(difs), "sem_numero": int(np.isnan(difs).sum()), "dif_max_abs_vs_lote": float(np.nanmax(difs))}
(OUT / "comparacao_pipeline_novo.json").write_text(json.dumps(res, ensure_ascii=False, indent=2))
print(json.dumps(res, ensure_ascii=False, indent=2))
