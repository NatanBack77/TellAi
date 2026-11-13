"""Módulo 2: modelo preditivo — "quanto a vegetação responde ao clima?".

Alvo: anomalia de NDVI no período t. Modelos comparados:
  climatologia (anomalia = 0), Ridge (mesmas features) e XGBoost.

Validação SEM vazamento (CV aleatória é proibida e há teste que vigia o código-fonte):
  1. GroupKFold agrupando por `celula_power`, dentro do PERÍODO DE TREINO.
  2. Holdout temporal: treino até o ano N-h, teste nos últimos h anos (h = holdout_anos).
A climatologia do alvo vem só dos anos de treino (`adicionar_anomalia`).
Persistência (D52, `preditivo.usar_persistencia`, padrão ligada): anomalia dos 2 compostos anteriores do ponto
(`features.adicionar_persistencia`, a MESMA função validada em `walkforward.py`). Com ela o relatório traz as DUAS
linhas (só clima e com persistência); `usar_persistencia: false` devolve o comportamento anterior.
Hiperparâmetros: Ridge escolhe alpha por validação interna agrupada usando só dados de treino;
XGBoost usa parâmetros fixos do config.yaml. Nada é ajustado olhando o teste.

Este módulo mede associação histórica; não prevê clima, não prevê produtividade e não prova causalidade.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.linear_model import Ridge
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from .diagnostico import _json_seguro
from .entrada import DadosInvalidos
from .features import adicionar_anomalia, adicionar_persistencia, nomes_features, resumir_dataset

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


def _avaliar_conjunto(treino: pd.DataFrame, teste: pd.DataFrame, cols: list[str], cfg: dict,
                      por_ano: bool = False) -> dict:
    """Ajusta os 3 modelos no treino e mede no teste. Skills calculadas aqui.

    `por_ano=True` acrescenta `saida["por_ano"]` (RMSE/skill por ano de teste, mesmos modelos já ajustados):
    só descritivo, serve para conferir com o walk-forward ano a ano.
    """
    saida, rmse, preds = {}, {}, {}
    for nome in MODELOS:
        mod, info = ajustar_modelo(nome, treino[cols], treino["anomalia_ndvi"].to_numpy(),
                                   treino["celula_power"].to_numpy(), cfg)
        preds[nome] = mod.predict(teste[cols])
        m = metricas(teste["anomalia_ndvi"].to_numpy(), preds[nome])
        saida[nome] = {**m, "info": info}
        rmse[nome] = m["rmse"]
    for nome in MODELOS:
        saida[nome]["skill_vs_climatologia"] = 0.0 if nome == "climatologia" else skill(rmse[nome], rmse["climatologia"])
    saida["xgboost"]["skill_vs_ridge"] = skill(rmse["xgboost"], rmse["ridge"])
    if por_ano:
        y = teste["anomalia_ndvi"].to_numpy()
        anos = teste["ano"].to_numpy()
        saida["por_ano"] = {}
        for a in sorted(set(anos.tolist())):
            k = anos == a
            r = {n: float(np.sqrt(np.mean((y[k] - preds[n][k]) ** 2))) for n in MODELOS}
            saida["por_ano"][str(int(a))] = {"n": int(k.sum()), **{
                n: {"rmse": r[n], "skill_vs_climatologia": 0.0 if n == "climatologia" else skill(r[n], r["climatologia"])}
                for n in MODELOS}}
    return saida


# ----------------------------------------------------------------------------- preparo e divisão
def dividir_anos(anos, holdout_anos: int) -> tuple[list[int], list[int]]:
    anos = sorted({int(a) for a in anos})
    if len(anos) < holdout_anos + 3:
        raise DadosInvalidos(f"Anos insuficientes ({len(anos)}) para holdout de {holdout_anos} anos "
                             "e treino com pelo menos 3 anos.")
    return anos[:-holdout_anos], anos[-holdout_anos:]


def usar_persistencia_cfg(cfg: dict, usar: bool | None = None) -> bool:
    return bool(cfg["preditivo"].get("usar_persistencia", False)) if usar is None else bool(usar)


def preparar_tabela_modelagem(df: pd.DataFrame, cfg: dict, usar_persistencia: bool | None = None,
                              so_linhas_com_persistencia: bool = False
                              ) -> tuple[pd.DataFrame, list[int], list[int], list[str]]:
    """Aplica o alvo (climatologia só do treino) e mantém linhas completas. Devolve (tabela, anos_treino, anos_teste, cols).

    `usar_persistencia=None` segue `cfg['preditivo']['usar_persistencia']`. Com persistência, as features
    `anom_lag1/2` entram em `cols` e a linha sem os dois lags consecutivos sai (nunca é preenchida).
    `so_linhas_com_persistencia=True` com `usar_persistencia=False` dá o modelo só-clima NAS MESMAS linhas
    do modelo com persistência (comparação justa). A tabela é sempre ordenada por (ponto_id, data).
    """
    p = cfg["preditivo"]
    usar = usar_persistencia_cfg(cfg, usar_persistencia)
    treino_anos, teste_anos = dividir_anos(df["ano"].unique(), p["holdout_anos"])
    com_umid = any(c.startswith("sm_raiz") for c in df.columns)
    cols = nomes_features(cfg, com_umid)
    d = adicionar_anomalia(df, treino_anos, cfg)
    d, novas = adicionar_persistencia(d, p.get("persistencia_max_gap_dias", 17))   # ordena por (ponto, data)
    ok = d["completo"] & d["anomalia_ndvi"].notna()
    if usar or so_linhas_com_persistencia:
        ok &= d[novas].notna().all(axis=1)
    if usar:
        cols = cols + novas
    else:
        d = d.drop(columns=novas)
    return d[ok].reset_index(drop=True), treino_anos, teste_anos, cols


# ----------------------------------------------------------------------------- conformal (passo 7)
def dividir_celulas_calibracao(celulas, fracao: float, semente: int) -> tuple[list[str], list[str]]:
    """Separa CÉLULAS (nunca linhas) do treino em 'treino próprio' e 'calibração', de forma determinística."""
    cel = sorted(str(c) for c in set(celulas))
    n_cal = max(1, int(round(fracao * len(cel))))
    if len(cel) - n_cal < 2:
        raise DadosInvalidos(f"Células insuficientes ({len(cel)}) para separar treino e calibração.")
    ordem = np.random.default_rng(semente).permutation(len(cel))
    cal = sorted(cel[i] for i in ordem[:n_cal])
    return sorted(set(cel) - set(cal)), cal


def quantil_conformal(residuos_abs: np.ndarray, alpha: float) -> float:
    """Quantil de split conformal com correção de amostra finita: ceil((n+1)(1-alpha))/n. inf se n for pequeno."""
    n = len(residuos_abs)
    k = math.ceil((n + 1) * (1 - alpha))
    return float("inf") if n == 0 or k > n else float(np.sort(residuos_abs)[k - 1])


def conformal_split(treino: pd.DataFrame, teste: pd.DataFrame, cols: list[str], cfg: dict, nome: str) -> dict:
    """Treino / calibração / teste em grupos (células) distintos para a calibração.

    O modelo é ajustado só nas células de treino próprio; o quantil dos resíduos vem das células de calibração;
    a cobertura é medida no `teste`. Devolve cobertura empírica e largura para cada meta (ex.: 80%, 90%).
    """
    p = cfg["preditivo"]
    cel_tr, cel_cal = dividir_celulas_calibracao(treino["celula_power"].unique(),
                                                 p["conformal_fracao_calibracao"], cfg["semente"])
    tr = treino[treino["celula_power"].isin(cel_tr)]
    cal = treino[treino["celula_power"].isin(cel_cal)]
    mod, _ = ajustar_modelo(nome, tr[cols], tr["anomalia_ndvi"].to_numpy(), tr["celula_power"].to_numpy(), cfg)
    res_cal = np.abs(cal["anomalia_ndvi"].to_numpy() - mod.predict(cal[cols]))
    y, pred = teste["anomalia_ndvi"].to_numpy(), mod.predict(teste[cols])
    saida = {"celulas_treino_proprio": cel_tr, "celulas_calibracao": cel_cal, "n_calibracao": int(len(cal)),
             "n_teste": int(len(teste)), "metas": {}}
    for alvo in p["cobertura_alvos"]:
        q = quantil_conformal(res_cal, 1 - alvo)
        cob = float(np.mean(np.abs(y - pred) <= q)) if np.isfinite(q) else float("nan")
        saida["metas"][f"{int(round(alvo * 100))}"] = {
            "meta": float(alvo), "quantil": q, "cobertura": cob,
            "largura_media": 2 * q if np.isfinite(q) else float("nan")}
    return saida


def _conformal_conjunto(treino, teste, cols, cfg) -> dict:
    return {nome: conformal_split(treino, teste, cols, cfg, nome) for nome in MODELOS}


def _resumir_conformal(folds: list[dict], cfg: dict) -> dict:
    """Cobertura de CV por modelo/meta: média ponderada pelo nº de linhas de validação + valor por fold."""
    out = {}
    for nome in MODELOS:
        out[nome] = {}
        for alvo in cfg["preditivo"]["cobertura_alvos"]:
            k = f"{int(round(alvo * 100))}"
            cobs = np.array([f["conformal"][nome]["metas"][k]["cobertura"] for f in folds], dtype=float)
            pesos = np.array([f["conformal"][nome]["n_teste"] for f in folds], dtype=float)
            ok = ~np.isnan(cobs)
            media = float(np.average(cobs[ok], weights=pesos[ok])) if ok.any() else float("nan")
            out[nome][k] = {"meta": float(alvo), "cobertura_media_ponderada": media,
                            "cobertura_por_fold": [None if np.isnan(c) else float(c) for c in cobs]}
    return out


# ----------------------------------------------------------------------------- decisão XGBoost vs Ridge (passo 8)
def decidir_modelo(folds: list[dict], holdout: dict) -> dict:
    """Critério aprovado pelo usuário: XGBoost só vence se skill_vs_ridge > 0
    (a) na média dos folds, (b) no holdout temporal e (c) em mais da metade dos folds. Senão, Ridge."""
    sk = np.array([f["modelos"]["xgboost"]["skill_vs_ridge"] for f in folds], dtype=float)
    media = float(np.nanmean(sk))
    frac = float(np.mean(sk > 0))
    sk_h = float(holdout["modelos"]["xgboost"]["skill_vs_ridge"])
    cond = {"media_folds_positiva": bool(media > 0), "holdout_positivo": bool(sk_h > 0),
            "maioria_folds_positiva": bool(frac > 0.5)}
    usa_xgb = all(cond.values())
    escolhido = "xgboost" if usa_xgb else "ridge"
    motivo = ("XGBoost superou o Ridge nos três testes do critério." if usa_xgb else
              "XGBoost não superou o Ridge de forma consistente (" +
              ", ".join(k for k, v in cond.items() if not v) + "); mantém-se o Ridge, mais simples.")
    aviso = None
    if not holdout["modelos"][escolhido]["skill_vs_climatologia"] > 0:
        aviso = (f"O modelo escolhido ({escolhido}) NÃO supera a climatologia no holdout; "
                 "a previsão de anomalia não agrega valor sobre a média histórica.")
    return {"modelo": escolhido, "criterio": cond, "skill_vs_ridge_media_folds": media,
            "fracao_folds_xgb_melhor": frac, "skill_vs_ridge_holdout": sk_h, "motivo": motivo,
            "aviso": aviso, "criterio_aprovado_pelo_usuario": True}


# ----------------------------------------------------------------------------- explicação (passo 9)
def importancia_contribuicoes(modelo: XGBRegressor, X: pd.DataFrame, cols: list[str]) -> dict:
    """Contribuição média absoluta por feature (`pred_contribs` do XGBoost = valores de Shapley de árvore).
    SÓ EXPLICATIVO: descreve o modelo, não valida nada nem indica causalidade. (D3: `shap` não instalado.)"""
    contrib = modelo.get_booster().predict(xgb.DMatrix(X[cols]), pred_contribs=True)[:, :-1]  # última coluna = viés
    imp = np.abs(contrib).mean(axis=0)
    return {"metodo": "xgboost pred_contribs (valores de Shapley de árvore)", "explicativo_apenas": True,
            "importancia_media_abs": {cols[i]: float(imp[i]) for i in np.argsort(-imp)}}


def _nucleo(d: pd.DataFrame, treino_anos, teste_anos, cols: list[str], cfg: dict) -> dict:
    """GroupKFold por célula (dentro do treino) + holdout temporal + conformal, para UM conjunto de features/linhas."""
    p = cfg["preditivo"]
    treino = d[d["ano"].isin(treino_anos)]
    teste = d[d["ano"].isin(teste_anos)]
    if len(treino) < p["min_linhas_treino"] or teste.empty:
        raise DadosInvalidos(f"Linhas insuficientes: treino={len(treino)} (mínimo {p['min_linhas_treino']}), "
                             f"teste={len(teste)}.")
    celulas_treino = treino["celula_power"].nunique()
    if celulas_treino < 2:
        raise DadosInvalidos("É preciso pelo menos 2 células POWER distintas para validação agrupada.")
    lacunas = []
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
                      "modelos": _avaliar_conjunto(tr, va, cols, cfg),
                      "conformal": _conformal_conjunto(tr, va, cols, cfg)})

    def agrega(nome, chave):
        v = np.array([f["modelos"][nome].get(chave, np.nan) for f in folds], dtype=float)
        return {"media": float(np.nanmean(v)), "desvio": float(np.nanstd(v, ddof=1)) if len(v) > 1 else float("nan")}

    resumo_cv = {nome: {m: agrega(nome, m) for m in ("mae", "rmse", "r2", "skill_vs_climatologia")} for nome in MODELOS}
    resumo_cv["xgboost"]["skill_vs_ridge"] = agrega("xgboost", "skill_vs_ridge")
    mods_h = _avaliar_conjunto(treino, teste, cols, cfg, por_ano=True)
    por_ano_h = mods_h.pop("por_ano")
    holdout = {"anos_treino": [treino_anos[0], treino_anos[-1]], "anos_teste": teste_anos,
               "n_treino": int(len(treino)), "n_teste": int(len(teste)), "modelos": mods_h, "por_ano": por_ano_h,
               "conformal": _conformal_conjunto(treino, teste, cols, cfg)}
    if len(teste) < 30:
        lacunas.append(f"Holdout com poucas linhas ({len(teste)}): métricas instáveis.")
    if any(not np.isfinite(m["quantil"]) for m in holdout["conformal"]["ridge"]["metas"].values()):
        lacunas.append("Calibração conformal com poucas linhas: faixa de incerteza indisponível em alguma meta.")
    return {"treino": treino, "teste": teste, "celulas_treino": int(celulas_treino), "n_folds": int(n_folds),
            "folds": folds, "resumo_cv": resumo_cv, "holdout": holdout, "lacunas": lacunas,
            "conformal_cv": _resumir_conformal(folds, cfg)}


def _resumo_comparativo(nuc: dict, cols: list[str]) -> dict:
    """Versão enxuta de um núcleo para a tabela lado a lado do relatório."""
    h = nuc["holdout"]
    return {
        "features": cols, "n_treino": h["n_treino"], "n_teste": h["n_teste"],
        "holdout": {n: {k: h["modelos"][n][k] for k in ("mae", "rmse", "r2", "skill_vs_climatologia")} for n in MODELOS},
        "holdout_por_ano": h["por_ano"],
        "cv_skill_vs_climatologia": {n: nuc["resumo_cv"][n]["skill_vs_climatologia"]["media"] for n in MODELOS},
        "conformal_holdout": {n: {k: {"cobertura": v["cobertura"], "largura_media": v["largura_media"]}
                                  for k, v in h["conformal"][n]["metas"].items()} for n in MODELOS},
        "conformal_cv": {n: {k: v["cobertura_media_ponderada"] for k, v in nuc["conformal_cv"][n].items()} for n in MODELOS},
        "xgboost_skill_vs_ridge_holdout": h["modelos"]["xgboost"]["skill_vs_ridge"],
    }


def _avisos_cobertura(holdout_conformal: dict, tol: float = 0.02) -> list[str]:
    """Declara (sem maquiar) cobertura real do holdout abaixo da meta, para Ridge e XGBoost."""
    out = []
    for n in ("ridge", "xgboost"):
        abaixo = [f"{k}% (real {v['cobertura']*100:.1f}%)" for k, v in holdout_conformal[n]["metas"].items()
                  if np.isfinite(v["cobertura"]) and v["cobertura"] < v["meta"] - tol]
        if abaixo:
            out.append(f"Cobertura conformal do holdout abaixo da meta em {n}: " + "; ".join(abaixo) +
                       ". A faixa é calibrada em células do período de treino e não reproduz a cobertura nominal "
                       "em outro período: NÃO deve ser lida como garantia nominal (não foi ajustada para 'bater' a meta).")
    return out


# ----------------------------------------------------------------------------- avaliação
def avaliar(df: pd.DataFrame, cfg: dict, sintetico: bool = False, usar_persistencia: bool | None = None) -> dict:
    """Avalia climatologia, Ridge e XGBoost por GroupKFold (célula) e por holdout temporal.

    `usar_persistencia` (None = config): com persistência, o resultado principal usa `anom_lag1/2` e vem em
    `comparativo` também: com_persistencia, so_clima_mesmas_linhas (justo) e so_clima_todas_as_linhas (o modelo anterior).
    """
    usar = usar_persistencia_cfg(cfg, usar_persistencia)
    d, treino_anos, teste_anos, cols = preparar_tabela_modelagem(df, cfg, usar)
    nuc = _nucleo(d, treino_anos, teste_anos, cols, cfg)
    treino, teste = nuc["treino"], nuc["teste"]
    resumo_ds = resumir_dataset(df, cfg)
    lacunas = list(resumo_ds["lacunas"])
    if sintetico:
        lacunas.insert(0, "DADOS SINTÉTICOS: as métricas só testam o fluxo; NÃO são resultado do projeto.")
    lacunas += nuc["lacunas"]
    p = cfg["preditivo"]
    holdout = nuc["holdout"]
    xgb_final, _ = ajustar_modelo("xgboost", treino[cols], treino["anomalia_ndvi"].to_numpy(),
                                  treino["celula_power"].to_numpy(), cfg)
    decisao = decidir_modelo(nuc["folds"], holdout)
    if sintetico:
        decisao["motivo"] = "[SINTÉTICO — só fluxo] " + decisao["motivo"]
    else:
        lacunas += _avisos_cobertura(holdout["conformal"])

    comparativo = None
    if usar:
        d0, _, _, cols0 = preparar_tabela_modelagem(df, cfg, False, so_linhas_com_persistencia=True)
        d1, _, _, cols1 = preparar_tabela_modelagem(df, cfg, False)
        comparativo = {
            "com_persistencia": _resumo_comparativo(nuc, cols),
            "so_clima_mesmas_linhas": _resumo_comparativo(_nucleo(d0, treino_anos, teste_anos, cols0, cfg), cols0),
            "so_clima_todas_as_linhas": _resumo_comparativo(_nucleo(d1, treino_anos, teste_anos, cols1, cfg), cols1),
            "nota": ("so_clima_mesmas_linhas = modelo sem persistência avaliado nas MESMAS linhas do modelo com persistência "
                     "(comparação justa); so_clima_todas_as_linhas = o modelo anterior, que mantém linhas sem composto "
                     "anterior consecutivo. Cada skill é relativa à climatologia das PRÓPRIAS linhas."),
        }
        if not sintetico:
            lacunas.append("Persistência: o ganho vem da memória do NDVI (autocorrelação), não do clima; "
                           "cenários de chuva/temperatura reagem pouco. Linhas sem 2 compostos anteriores "
                           "consecutivos (≤ %d d) ficam fora do treino e do teste (não são preenchidas)."
                           % p.get("persistencia_max_gap_dias", 17))

    return {
        "dados_sinteticos": bool(sintetico),
        "features": cols,
        "persistencia": {"usada": bool(usar), "max_gap_dias": int(p.get("persistencia_max_gap_dias", 17)),
                         "funcao": "features.adicionar_persistencia (a mesma de walkforward.extra_persistencia)"},
        "umidade_solo_smap": {"usada": any(c.startswith("sm_") for c in cols),
                              "opcao": "preditivo.usar_umidade_solo (padrão false; ver D52)"},
        "alvo": "anomalia_ndvi = NDVI - climatologia do slot (climatologia só dos anos de treino)",
        "divisao": {"anos_treino": treino_anos, "anos_teste": teste_anos, "n_celulas_treino": nuc["celulas_treino"],
                    "n_folds": nuc["n_folds"]},
        "cv_grupos": {"folds": nuc["folds"], "resumo": nuc["resumo_cv"], "conformal": nuc["conformal_cv"]},
        "holdout_temporal": holdout,
        "comparativo": comparativo,
        "decisao": decisao,
        "explicacao": importancia_contribuicoes(xgb_final, teste, cols),
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
    if "--sem-persistencia" in sys.argv:        # modelo só-clima (comportamento anterior)
        cfg["preditivo"]["usar_persistencia"] = False
    if "--com-smap" in sys.argv:                # opção desligada por padrão (D52)
        cfg["preditivo"]["usar_umidade_solo"] = True
    if sint:
        d = "data/processed/sintetico"
        cfg["caminhos"].update(clima=f"{d}/SINTETICO_clima_diario.parquet", ndvi=f"{d}/SINTETICO_ndvi_16d.parquet",
                               umidade_solo=f"{d}/SINTETICO_umidade_solo.parquet", saida=f"{d}/modelos")
    ds = construir_dataset(carregar_entradas(cfg), cfg)
    res = avaliar(ds, cfg, sintetico=sint)
    if not sint and res["persistencia"]["usada"]:
        from .cenarios import sensibilidade_comparada
        res["sensibilidade_cenarios"] = sensibilidade_comparada(ds, cfg)
    from .relatorio import gerar

    caminho = salvar_metricas(res, RAIZ / cfg["caminhos"]["saida"])
    print("salvo em", caminho)
    print("relatório em", gerar(caminho))
    if not sint:
        print("decisão:", res["decisao"]["modelo"])
    if sint:
        print("Fluxo OK. Métricas omitidas: dados sintéticos não são resultado do projeto.")
    else:
        for nome, m in res["holdout_temporal"]["modelos"].items():
            print(nome, {k: round(m[k], 4) for k in ("mae", "rmse", "r2", "skill_vs_climatologia")})
