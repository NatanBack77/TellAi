"""Módulo 2: modelo preditivo — "quanto a vegetação responde ao clima?".

Alvo: anomalia de NDVI no período t. Modelos comparados:
  climatologia (anomalia = 0), Ridge (mesmas features) e XGBoost.

Validação SEM vazamento (CV aleatória é proibida e há teste que vigia o código-fonte):
  1. GroupKFold agrupando por `celula_power`, dentro do PERÍODO DE TREINO.
  2. Holdout temporal: treino até o ano N-h, teste nos últimos h anos (h = holdout_anos).
A climatologia do alvo vem só dos anos de treino (`adicionar_anomalia`).
Hiperparâmetros: Ridge escolhe alpha por validação interna agrupada usando só dados de treino;
XGBoost usa parâmetros fixos do config.yaml. Nada é ajustado olhando o teste.

Este módulo mede associação histórica; não prevê clima, não prevê produtividade e não prova causalidade.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from .diagnostico import _json_seguro
from .entrada import DadosInvalidos
from .features import adicionar_anomalia, nomes_features, resumir_dataset

MODELOS = ("climatologia", "ridge", "xgboost")
METRICAS = ("mae", "rmse", "r2", "skill_vs_climatologia")
AVISO_ASSOCIACAO = ("O modelo captura associações históricas entre clima e NDVI; não é causalidade e não "
                    "prevê o clima futuro nem a produtividade.")


# ----------------------------------------------------------------------------- métricas
def metricas(y: np.ndarray, pred: np.ndarray) -> dict:
    y, pred = np.asarray(y, dtype=float), np.asarray(pred, dtype=float)
    erro = y - pred
    sst = float(np.sum((y - y.mean()) ** 2)) if len(y) > 1 else 0.0
    return {
        "mae": float(np.mean(np.abs(erro))),
        "rmse": float(np.sqrt(np.mean(erro ** 2))),
        "r2": float(1 - np.sum(erro ** 2) / sst) if sst > 0 else float("nan"),
        "n": int(len(y)),
    }


def skill(rmse_modelo: float, rmse_base: float) -> float:
    """skill = 1 - RMSE_modelo / RMSE_baseline (> 0 = melhor que o baseline)."""
    return float(1 - rmse_modelo / rmse_base) if rmse_base and rmse_base > 0 else float("nan")


# ----------------------------------------------------------------------------- modelos
class ClimatologiaBaseline:
    """Anomalia prevista = 0 (a vegetação fica na média climatológica do slot)."""

    def fit(self, X, y=None):
        return self

    def predict(self, X):
        return np.zeros(len(X))


def ajustar_modelo(nome: str, X: pd.DataFrame, y: np.ndarray, grupos: np.ndarray, cfg: dict):
    """Ajusta um modelo SÓ com o treino recebido. Devolve (modelo, info)."""
    p = cfg["preditivo"]
    if nome == "climatologia":
        return ClimatologiaBaseline().fit(X, y), {}
    if nome == "ridge":
        pipe = Pipeline([("escala", StandardScaler()), ("ridge", Ridge())])
        n_grupos = len(np.unique(grupos))
        if n_grupos < 3:
            pipe.set_params(ridge__alpha=1.0).fit(X, y)
            return pipe, {"alpha": 1.0, "aviso": "poucas células no treino: alpha fixo em 1.0"}
        gs = GridSearchCV(pipe, {"ridge__alpha": p["ridge_alphas"]}, cv=GroupKFold(n_splits=min(3, n_grupos)),
                          scoring="neg_root_mean_squared_error")
        gs.fit(X, y, groups=grupos)
        return gs.best_estimator_, {"alpha": float(gs.best_params_["ridge__alpha"])}
    if nome == "xgboost":
        m = XGBRegressor(**p["xgboost"], objective="reg:squarederror", tree_method="hist",
                         random_state=cfg["semente"], n_jobs=1)
        return m.fit(X, y), {"parametros": dict(p["xgboost"])}
    raise ValueError(f"modelo desconhecido: {nome}")


def _avaliar_conjunto(treino: pd.DataFrame, teste: pd.DataFrame, cols: list[str], cfg: dict) -> dict:
    """Ajusta os 3 modelos no treino e mede no teste. Skills calculadas aqui."""
    saida, rmse = {}, {}
    for nome in MODELOS:
        mod, info = ajustar_modelo(nome, treino[cols], treino["anomalia_ndvi"].to_numpy(),
                                   treino["celula_power"].to_numpy(), cfg)
        m = metricas(teste["anomalia_ndvi"].to_numpy(), mod.predict(teste[cols]))
        saida[nome] = {**m, "info": info}
        rmse[nome] = m["rmse"]
    for nome in MODELOS:
        saida[nome]["skill_vs_climatologia"] = 0.0 if nome == "climatologia" else skill(rmse[nome], rmse["climatologia"])
    saida["xgboost"]["skill_vs_ridge"] = skill(rmse["xgboost"], rmse["ridge"])
    return saida


# ----------------------------------------------------------------------------- preparo e divisão
def dividir_anos(anos, holdout_anos: int) -> tuple[list[int], list[int]]:
    anos = sorted({int(a) for a in anos})
    if len(anos) < holdout_anos + 3:
        raise DadosInvalidos(f"Anos insuficientes ({len(anos)}) para holdout de {holdout_anos} anos "
                             "e treino com pelo menos 3 anos.")
    return anos[:-holdout_anos], anos[-holdout_anos:]


def preparar_tabela_modelagem(df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, list[int], list[int], list[str]]:
    """Aplica o alvo (climatologia só do treino) e mantém linhas completas. Devolve (tabela, anos_treino, anos_teste, cols)."""
    treino_anos, teste_anos = dividir_anos(df["ano"].unique(), cfg["preditivo"]["holdout_anos"])
    com_umid = any(c.startswith("sm_raiz") for c in df.columns)
    cols = nomes_features(cfg, com_umid)
    d = adicionar_anomalia(df, treino_anos, cfg)
    d = d[d["completo"] & d["anomalia_ndvi"].notna()].reset_index(drop=True)
    return d, treino_anos, teste_anos, cols


# ----------------------------------------------------------------------------- avaliação
def avaliar(df: pd.DataFrame, cfg: dict, sintetico: bool = False) -> dict:
    """Avalia climatologia, Ridge e XGBoost por GroupKFold (célula) e por holdout temporal."""
    p = cfg["preditivo"]
    d, treino_anos, teste_anos, cols = preparar_tabela_modelagem(df, cfg)
    treino = d[d["ano"].isin(treino_anos)]
    teste = d[d["ano"].isin(teste_anos)]
    if len(treino) < p["min_linhas_treino"] or teste.empty:
        raise DadosInvalidos(f"Linhas insuficientes: treino={len(treino)} (mínimo {p['min_linhas_treino']}), "
                             f"teste={len(teste)}.")
    celulas_treino = treino["celula_power"].nunique()
    if celulas_treino < 2:
        raise DadosInvalidos("É preciso pelo menos 2 células POWER distintas para validação agrupada.")
    resumo_ds = resumir_dataset(df, cfg)
    lacunas = list(resumo_ds["lacunas"])
    if sintetico:
        lacunas.insert(0, "DADOS SINTÉTICOS: as métricas só testam o fluxo; NÃO são resultado do projeto.")

    n_folds = min(p["n_folds"], celulas_treino)
    if n_folds < p["n_folds"]:
        lacunas.append(f"Apenas {celulas_treino} células no treino: GroupKFold com {n_folds} folds "
                       f"(config pedia {p['n_folds']}).")
    folds = []
    gkf = GroupKFold(n_splits=n_folds)
    for i, (idx_tr, idx_va) in enumerate(gkf.split(treino, groups=treino["celula_power"]), start=1):
        tr, va = treino.iloc[idx_tr], treino.iloc[idx_va]
        folds.append({"fold": i,
                      "celulas_treino": sorted(tr["celula_power"].unique().tolist()),
                      "celulas_validacao": sorted(va["celula_power"].unique().tolist()),
                      "n_treino": int(len(tr)), "n_validacao": int(len(va)),
                      "modelos": _avaliar_conjunto(tr, va, cols, cfg)})

    def agrega(nome, chave):
        v = np.array([f["modelos"][nome].get(chave, np.nan) for f in folds], dtype=float)
        return {"media": float(np.nanmean(v)), "desvio": float(np.nanstd(v, ddof=1)) if len(v) > 1 else float("nan")}

    resumo_cv = {nome: {m: agrega(nome, m) for m in ("mae", "rmse", "r2", "skill_vs_climatologia")} for nome in MODELOS}
    resumo_cv["xgboost"]["skill_vs_ridge"] = agrega("xgboost", "skill_vs_ridge")

    holdout = {"anos_treino": [treino_anos[0], treino_anos[-1]], "anos_teste": teste_anos,
               "n_treino": int(len(treino)), "n_teste": int(len(teste)),
               "modelos": _avaliar_conjunto(treino, teste, cols, cfg)}
    if len(teste) < 30:
        lacunas.append(f"Holdout com poucas linhas ({len(teste)}): métricas instáveis.")

    return {
        "dados_sinteticos": bool(sintetico),
        "features": cols,
        "alvo": "anomalia_ndvi = NDVI - climatologia do slot (climatologia só dos anos de treino)",
        "divisao": {"anos_treino": treino_anos, "anos_teste": teste_anos, "n_celulas_treino": int(celulas_treino),
                    "n_folds": int(n_folds)},
        "cv_grupos": {"folds": folds, "resumo": resumo_cv},
        "holdout_temporal": holdout,
        "dataset": {k: resumo_ds[k] for k in ("n_linhas", "n_completas", "n_pontos", "n_celulas", "anos")},
        "lacunas": lacunas,
        "confianca": "baixa" if resumo_ds["n_celulas"] < p["min_celulas_aviso"] else "media",
        "confianca_nota": "heurística: 'baixa' com menos de min_celulas_aviso células POWER distintas; não é probabilidade",
        "aviso": AVISO_ASSOCIACAO,
    }


def salvar_metricas(resultado: dict, pasta: str | Path) -> Path:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    nome = "SINTETICO_metricas.json" if resultado["dados_sinteticos"] else "metricas.json"
    caminho = pasta / nome
    caminho.write_text(json.dumps(_json_seguro(resultado), ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


if __name__ == "__main__":
    import sys

    from .entrada import RAIZ, carregar_config, carregar_entradas
    from .features import construir_dataset

    cfg = carregar_config()
    sint = "--sintetico" in sys.argv
    if sint:
        d = "data/processed/sintetico"
        cfg["caminhos"].update(clima=f"{d}/SINTETICO_clima_diario.parquet", ndvi=f"{d}/SINTETICO_ndvi_16d.parquet",
                               umidade_solo=f"{d}/SINTETICO_umidade_solo.parquet", saida=f"{d}/modelos")
    res = avaliar(construir_dataset(carregar_entradas(cfg), cfg), cfg, sintetico=sint)
    print("salvo em", salvar_metricas(res, RAIZ / cfg["caminhos"]["saida"]))
    if sint:
        print("Fluxo OK. Métricas omitidas: dados sintéticos não são resultado do projeto.")
    else:
        for nome, m in res["holdout_temporal"]["modelos"].items():
            print(nome, {k: round(m[k], 4) for k in ("mae", "rmse", "r2", "skill_vs_climatologia")})
