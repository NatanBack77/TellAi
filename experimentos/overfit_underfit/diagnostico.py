"""Diagnóstico de overfitting e underfitting do modelo de anomalia de NDVI (persistência), só anos de SELEÇÃO (2010-2021).

NÃO usa 2022-2024 (selados) e NÃO ajusta o modelo de produção: é só diagnóstico. Se algo apontar mudança, vira variante a testar pelo protocolo.
Testes:
 1. Lacuna treino x teste (walk-forward): RMSE no treino (dentro da amostra) vs. no ano seguinte, ridge e xgboost.
    Ressalva: a anomalia do treino usa climatologia calculada com os próprios anos (otimista); o teste usa só o passado.
 2. Curva de aprendizado: teste de 2021 e 2018 treinando com os últimos k anos (k = 4..N).
 3. Varredura de complexidade do XGBoost (n_estimators x max_depth, lr fixo) e do alpha do Ridge: erro de treino x de teste.
    Os parâmetros de produção (200 árvores, profundidade 3, alpha do config) ficam marcados.
 4. Resíduos: viés por ano e por estação; autocorrelação lag-1 dos resíduos por ponto (alta = informação sobrando = underfit).
 5. Generalização espacial: erro em células nunca vistas (GroupKFold por célula, dentro de 2001-2021) vs. erro no tempo.
"""
import sys
import warnings
from pathlib import Path
RAIZ = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, RAIZ)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conformal_A1"))
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

import conformal_wf as cw
from src.modelos.preditivo import ajustar_modelo

warnings.filterwarnings("ignore")
OUT = Path(__file__).resolve().parent
cfg = cw.cfg
SEED = cfg["semente"]
ANOS = [2012, 2015, 2018, 2021]
rm = lambda y, p: float(np.sqrt(np.mean((np.asarray(y) - np.asarray(p)) ** 2)))


def xgb(n=200, depth=3):
    p = dict(cfg["preditivo"]["xgboost"])
    p.update(n_estimators=n, max_depth=depth)
    return XGBRegressor(**p, objective="reg:squarederror", tree_method="hist", random_state=SEED, n_jobs=4)


def ridge(alpha):
    return Pipeline([("s", StandardScaler()), ("r", Ridge(alpha=alpha))])


def main():
    df, cols = cw.preparar()
    dados = {Y: cw.tabela_ano(df, cols, Y) for Y in sorted(set(ANOS) | set(range(2010, 2022)))}
    # ---- 1. lacuna treino x teste (todos os anos de seleção)
    r1 = []
    for Y in range(2010, 2022):
        d, cf, anos_tr = dados[Y]
        tr, te = d[d["ano"] < Y], d[d["ano"] == Y]
        for nome in ("ridge", "xgboost"):
            m, _ = ajustar_modelo(nome, tr[cf], tr["anomalia_ndvi"].to_numpy(), tr["celula_power"].to_numpy(), cfg)
            r1.append({"ano": Y, "modelo": nome, "rmse_treino": rm(tr["anomalia_ndvi"], m.predict(tr[cf])),
                       "rmse_teste": rm(te["anomalia_ndvi"], m.predict(te[cf])), "rmse_clim_teste": rm(te["anomalia_ndvi"], 0 * te["anomalia_ndvi"])})
    r1 = pd.DataFrame(r1)
    r1["razao_teste_treino"] = r1["rmse_teste"] / r1["rmse_treino"]
    r1.to_csv(OUT / "t1_lacuna.csv", index=False)
    print("== 1. lacuna treino x teste (média sobre 2010-2021)")
    print(r1.groupby("modelo")[["rmse_treino", "rmse_teste", "razao_teste_treino", "rmse_clim_teste"]].mean().round(4).to_string(), flush=True)
    # ---- 2. curva de aprendizado
    r2 = []
    for Y in (2018, 2021):
        d, cf, anos_tr = dados[Y]
        te = d[d["ano"] == Y]
        for k in range(4, len(anos_tr) + 1, 2):
            tr = d[d["ano"].isin(anos_tr[-k:])]
            for nome in ("ridge", "xgboost"):
                m, _ = ajustar_modelo(nome, tr[cf], tr["anomalia_ndvi"].to_numpy(), tr["celula_power"].to_numpy(), cfg)
                r2.append({"ano_teste": Y, "k_anos": k, "modelo": nome, "n": len(tr),
                           "rmse_treino": rm(tr["anomalia_ndvi"], m.predict(tr[cf])), "rmse_teste": rm(te["anomalia_ndvi"], m.predict(te[cf]))})
    r2 = pd.DataFrame(r2)
    r2.to_csv(OUT / "t2_curva_aprendizado.csv", index=False)
    print("== 2. curva de aprendizado (teste 2018 e 2021; RMSE de teste por nº de anos de treino)")
    print(r2.pivot_table(index="k_anos", columns=["modelo", "ano_teste"], values="rmse_teste").round(4).to_string(), flush=True)
    # ---- 3. varredura de complexidade
    r3 = []
    for Y in ANOS:
        d, cf, anos_tr = dados[Y]
        tr, te = d[d["ano"] < Y], d[d["ano"] == Y]
        for n in (25, 50, 100, 200, 400, 800):
            for depth in (1, 2, 3, 4, 6):
                m = xgb(n, depth).fit(tr[cf], tr["anomalia_ndvi"])
                r3.append({"ano": Y, "n_estimators": n, "max_depth": depth, "rmse_treino": rm(tr["anomalia_ndvi"], m.predict(tr[cf])),
                           "rmse_teste": rm(te["anomalia_ndvi"], m.predict(te[cf]))})
        for a in (1e-3, 1e-1, 1, 10, 100, 1e3, 1e4):
            m = ridge(a).fit(tr[cf], tr["anomalia_ndvi"])
            r3.append({"ano": Y, "n_estimators": None, "max_depth": None, "alpha": a, "rmse_treino": rm(tr["anomalia_ndvi"], m.predict(tr[cf])),
                       "rmse_teste": rm(te["anomalia_ndvi"], m.predict(te[cf]))})
    r3 = pd.DataFrame(r3)
    r3.to_csv(OUT / "t3_complexidade.csv", index=False)
    g = r3[r3["max_depth"].notna()].groupby(["n_estimators", "max_depth"])[["rmse_treino", "rmse_teste"]].mean().reset_index()
    print("== 3a. XGBoost: RMSE médio (anos 2012, 2015, 2018, 2021). Produção = 200 árvores, profundidade 3")
    print(g.pivot(index="n_estimators", columns="max_depth", values="rmse_teste").round(4).to_string())
    print("   treino:")
    print(g.pivot(index="n_estimators", columns="max_depth", values="rmse_treino").round(4).to_string())
    ga = r3[r3["max_depth"].isna()].groupby("alpha")[["rmse_treino", "rmse_teste"]].mean()
    print("== 3b. Ridge por alpha"); print(ga.round(4).to_string(), flush=True)
    # ---- 4. resíduos (ridge e xgboost de produção) em 2012..2021 (cada ano com treino só anterior)
    r4 = []
    for Y in range(2012, 2022):
        d, cf, anos_tr = dados[Y]
        tr, te = d[d["ano"] < Y], d[d["ano"] == Y].copy()
        m, _ = ajustar_modelo("xgboost", tr[cf], tr["anomalia_ndvi"].to_numpy(), tr["celula_power"].to_numpy(), cfg)
        te["res"] = te["anomalia_ndvi"] - m.predict(te[cf])
        r4.append(te[["ponto_id", "data", "ano", "faixa", "res", "anomalia_ndvi"]])
    r4 = pd.concat(r4).sort_values(["ponto_id", "data"])
    ac = r4.groupby("ponto_id")["res"].apply(lambda s: s.autocorr(1)).mean()
    print("== 4. resíduos XGBoost: viés médio", round(float(r4["res"].mean()), 5), "| autocorr lag-1 média por ponto", round(float(ac), 3))
    print("   viés por ano:", r4.groupby("ano")["res"].mean().round(4).to_dict())
    print("   viés por faixa de estação:", r4.groupby("faixa")["res"].mean().round(4).to_dict())
    print("   R2 por faixa:", {int(f): round(1 - float((x['res'] ** 2).sum() / ((x['anomalia_ndvi'] - x['anomalia_ndvi'].mean()) ** 2).sum()), 3)
                               for f, x in r4.groupby("faixa")}, flush=True)
    r4.groupby("ano")["res"].agg(["mean", "std"]).to_csv(OUT / "t4_residuos_por_ano.csv")
    # ---- 5. generalização espacial (dentro de 2001-2021, sem tocar 2022+)
    d, cf, anos_tr = dados[2021]
    d = d[d["ano"] <= 2021]
    r5 = []
    for nome in ("ridge", "xgboost"):
        err = []
        for tri, tei in GroupKFold(n_splits=5).split(d, groups=d["celula_power"]):
            tr, te = d.iloc[tri], d.iloc[tei]
            m, _ = ajustar_modelo(nome, tr[cf], tr["anomalia_ndvi"].to_numpy(), tr["celula_power"].to_numpy(), cfg)
            err.append((len(te), rm(te["anomalia_ndvi"], m.predict(te[cf])), rm(te["anomalia_ndvi"], 0 * te["anomalia_ndvi"])))
        e = np.array(err)
        r5.append({"modelo": nome, "rmse_celulas_novas": float(np.average(e[:, 1], weights=e[:, 0])),
                   "rmse_clim": float(np.average(e[:, 2], weights=e[:, 0]))})
    r5 = pd.DataFrame(r5); r5["skill_celulas_novas"] = 1 - r5["rmse_celulas_novas"] / r5["rmse_clim"]
    r5.to_csv(OUT / "t5_espacial.csv", index=False)
    print("== 5. células nunca vistas (GroupKFold por célula, 2001-2021; mistura tempo)")
    print(r5.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
