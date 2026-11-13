"""Outros algoritmos e ensembles para a anomalia de NDVI (com persistência), pelo protocolo de docs/05_EXPERIMENTOS.md.

Uso:
  python ensemble_wf.py selecao                 -> 2010-2021, todos os candidatos (N conta para o Bonferroni)
  python ensemble_wf.py confirma m1,m2,...      -> UMA vez, 2022-2024, só os finalistas + ridge (referência)

Regras: hiperparâmetros FIXOS a priori (abaixo; nada ajustado olhando o teste); mesmas linhas de teste para todos os modelos;
base = ridge com persistência (o modelo atual); ensembles por média simples ou NNLS calibrado só em anos de treino.
Candidatos (N = 12): ridge, xgboost, hgb, rf, et, enet, mlp, e_rx, e_rxh, e_arvores, e_todos, stack_nnls.
"""
import sys
import warnings
from pathlib import Path
RAIZ = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, RAIZ)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conformal_A1"))
import numpy as np
import pandas as pd
from scipy.optimize import nnls
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import ElasticNet
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import conformal_wf as cw
from src.modelos.preditivo import ajustar_modelo
from src.modelos.walkforward import resumir

warnings.filterwarnings("ignore")
OUT = Path(__file__).resolve().parent
cfg = cw.cfg
SEED = cfg["semente"]
SINGLES = ["ridge", "xgboost", "hgb", "rf", "et", "enet", "mlp"]
ENSEMBLES = {"e_rx": ["ridge", "xgboost"], "e_rxh": ["ridge", "xgboost", "hgb"],
             "e_arvores": ["xgboost", "hgb", "rf", "et"], "e_todos": SINGLES}
STACK_BASE = ["ridge", "xgboost", "hgb", "rf"]
TODOS = SINGLES + list(ENSEMBLES) + ["stack_nnls"]


def fabrica(nome):
    if nome == "hgb":
        return HistGradientBoostingRegressor(max_depth=4, learning_rate=0.05, max_iter=300, min_samples_leaf=50,
                                             l2_regularization=1.0, random_state=SEED)
    if nome == "rf":
        return RandomForestRegressor(n_estimators=300, min_samples_leaf=30, max_features=0.5, n_jobs=4, random_state=SEED)
    if nome == "et":
        return ExtraTreesRegressor(n_estimators=300, min_samples_leaf=30, max_features=0.5, n_jobs=4, random_state=SEED)
    if nome == "enet":
        return Pipeline([("s", StandardScaler()), ("m", ElasticNet(alpha=0.001, l1_ratio=0.5, max_iter=5000))])
    if nome == "mlp":
        return Pipeline([("s", StandardScaler()), ("m", MLPRegressor(hidden_layer_sizes=(32, 16), alpha=1e-2, max_iter=300,
                                                                     early_stopping=True, random_state=SEED))])
    raise ValueError(nome)


def ajustar(nome, tr, cf):
    X, y = tr[cf], tr["anomalia_ndvi"].to_numpy()
    if nome in ("ridge", "xgboost"):
        return ajustar_modelo(nome, X, y, tr["celula_power"].to_numpy(), cfg)[0]
    return fabrica(nome).fit(X, y)


def previsoes_ano(d, cf, anos_tr, Y, nomes):
    tr, te = d[d["ano"] < Y], d[d["ano"] == Y]
    P = {}
    for n in nomes:
        P[n] = ajustar(n, tr, cf).predict(te[cf])
    return tr, te, P


def pesos_stack(d, cf, anos_tr):
    """NNLS nos 3 últimos anos antes de Y (modelos ajustados só nos anos anteriores a eles)."""
    corte = anos_tr[-3]
    prop, cal = d[d["ano"] < corte], d[(d["ano"] >= corte) & (d["ano"] <= anos_tr[-1])]
    M = np.column_stack([ajustar(n, prop, cf).predict(cal[cf]) for n in STACK_BASE])
    w, _ = nnls(M, cal["anomalia_ndvi"].to_numpy())
    return w / w.sum() if w.sum() > 0 else np.full(len(w), 1 / len(w))


def rodar(anos, nomes):
    df, cols = cw.preparar()
    linhas = []
    for Y in anos:
        d, cf, anos_tr = cw.tabela_ano(df, cols, Y)
        base_n = sorted(set(n for n in nomes if n in SINGLES)
                        | {x for n in nomes if n in ENSEMBLES for x in ENSEMBLES[n]}
                        | (set(STACK_BASE) if "stack_nnls" in nomes else set()))
        tr, te, P = previsoes_ano(d, cf, anos_tr, Y, base_n)
        y = te["anomalia_ndvi"].to_numpy()
        for n in nomes:
            if n in SINGLES:
                p = P[n]
            elif n in ENSEMBLES:
                p = np.mean([P[x] for x in ENSEMBLES[n]], axis=0)
            else:
                w = pesos_stack(d, cf, anos_tr)
                p = np.column_stack([P[x] for x in STACK_BASE]) @ w
            r, rc = float(np.sqrt(np.mean((y - p) ** 2))), float(np.sqrt(np.mean(y ** 2)))
            linhas.append({"ano_teste": Y, "variante": n, "modelo": "x", "n": len(y), "rmse": r, "rmse_clim": rc,
                           "skill": 1 - r / rc})
        print("ano", Y, "ok", flush=True)
    return pd.DataFrame(linhas)


if __name__ == "__main__":
    modo = sys.argv[1]
    pd.set_option("display.width", 220, "display.max_columns", 30)
    cols = ["variante", "skill_media", "skill_ic_inf_corrigido", "frac_anos_positivos", "dif_vs_base_media",
            "dif_vs_base_ic_inf", "skill_confirmacao"]
    if modo == "selecao":
        anos = list(range(2010, 2022))
        res = rodar(anos, TODOS)
        res.to_csv(OUT / "selecao_linhas.csv", index=False)
        t = resumir(res, anos, [], n_variantes=len(TODOS), base="ridge", modelo_base="x")
        t.to_csv(OUT / "selecao_resumo.csv", index=False)
        print(t[cols].round(4).to_string(index=False))
    else:
        fin = sys.argv[2].split(",")
        nomes = ["ridge"] + [f for f in fin if f != "ridge"]
        res = rodar([2022, 2023, 2024], nomes)
        res.to_csv(OUT / "confirmacao_linhas.csv", index=False)
        t = res.groupby("variante").apply(lambda x: pd.Series({"skill_media": x["skill"].mean(),
                                                               "rmse_medio": x["rmse"].mean()}), include_groups=False)
        t["dif_vs_ridge"] = t["skill_media"] - t.loc["ridge", "skill_media"]
        t.to_csv(OUT / "confirmacao_resumo.csv")
        print(t.round(4).to_string())
