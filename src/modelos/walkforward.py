"""Validação walk-forward (expanding window, 1 ano à frente) para comparar VARIANTES do modelo preditivo.

Objetivo: dizer, sem se enganar, se uma ideia (nova feature, alvo normalizado, ...) melhora a previsão da
anomalia de NDVI sobre a climatologia. Garantias contra "modelo alucinado":

1. Walk-forward: para o ano de teste Y, treino = só anos < Y; climatologia do alvo = só anos < Y.
2. Todas as variantes são avaliadas nas MESMAS linhas de teste (interseção das linhas válidas de cada variante),
   senão uma variante que descarta linhas difíceis pareceria melhor.
3. Métricas SEMPRE na escala original da anomalia (alvo normalizado é convertido de volta antes do RMSE).
4. Anos de SELEÇÃO (decidem) e anos de CONFIRMAÇÃO (selados: só olhados no fim, uma vez) são separados.
5. Correção por número de variantes testadas (Bonferroni no limite inferior do IC bootstrap sobre anos).
6. Controle placebo: embaralha as features entre anos dentro de (ponto, slot); a skill tem de ficar <= 0.
   Se o placebo "melhora", há vazamento e nenhum resultado vale.
7. Melhoria só é declarada se: skill vs. climatologia > 0 com IC (corrigido) acima de 0, maioria dos anos positivos,
   melhor que a variante base (pareado por ano) e skill > 0 na confirmação.

Mede associação histórica; não é previsão do clima nem de produtividade.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from .entrada import DadosInvalidos
from .features import adicionar_anomalia, adicionar_persistencia, construir_dataset, nomes_features
from .preditivo import ajustar_modelo, skill

MODELOS_WF = ("ridge", "xgboost")


# ----------------------------------------------------------------------------- variantes
@dataclass
class Variante:
    nome: str
    descricao: str = ""
    cfg_patch: dict = field(default_factory=dict)          # sobrescreve chaves do config (ex.: janelas de chuva)
    extra: Callable | None = None                          # (d) -> (d, [novas colunas]); só pode usar o passado
    remover: tuple | str = ()                              # features base a retirar ("*" = todas: sobra só o que `extra` cria)
    alvo_z: bool = False                                   # treinar anomalia / desvio do ponto (treino), prever na escala original


def _merge(base: dict, patch: dict) -> dict:
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


# MESMA função da produção (features.adicionar_persistencia): validação e produção não podem divergir.
extra_persistencia = adicionar_persistencia


VARIANTES = {
    "base": Variante("base", "features atuais (controle)"),
    "persistencia": Variante("persistencia", "+ anomalia dos 2 compostos anteriores", extra=extra_persistencia),
    "janelas_longas": Variante("janelas_longas", "chuva acumulada 30/60/90/120/180 d",
                               cfg_patch={"preditivo": {"janelas_chuva_dias": [30, 60, 90, 120, 180]}}),
    "so_persistencia": Variante("so_persistencia", "SÓ anomalia dos compostos anteriores (sem clima): mede o que o clima acrescenta",
                                extra=extra_persistencia, remover="*"),
    "alvo_z": Variante("alvo_z", "alvo normalizado pelo desvio do ponto", alvo_z=True),
    "persistencia_z": Variante("persistencia_z", "persistência + alvo normalizado", extra=extra_persistencia, alvo_z=True),
}


# ----------------------------------------------------------------------------- núcleo
def _chave(d: pd.DataFrame) -> pd.Series:
    return d["ponto_id"].astype(str) + "|" + d["data"].dt.strftime("%Y-%m-%d")


def _placebo(d: pd.DataFrame, cols: list[str], semente: int) -> pd.DataFrame:
    """Embaralha as linhas de features entre anos dentro de (ponto, slot): quebra clima->NDVI, mantém a distribuição."""
    rng = np.random.default_rng(semente)
    d = d.copy()
    for _, idx in d.groupby(["ponto_id", "slot"]).groups.items():
        idx = np.asarray(list(idx))
        d.loc[idx, cols] = d.loc[rng.permutation(idx), cols].to_numpy()
    return d


def _preparar_fold(df, cols, cfg_v, v: Variante, anos_tr, placebo: bool, semente: int):
    d = adicionar_anomalia(df, anos_tr, cfg_v).sort_values(["ponto_id", "data"]).reset_index(drop=True)
    cols_f = list(cols)
    if v.extra is not None:
        d, novas = v.extra(d)
        cols_f += novas
    if placebo:
        d = _placebo(d, cols_f, semente)
    d["_ok"] = d[cols_f].notna().all(axis=1) & d["anomalia_ndvi"].notna() & d["completo"]
    d["_chave"] = _chave(d)
    return d, cols_f


def walk_forward(entradas: dict, cfg: dict, variantes: list[Variante], anos_teste: list[int],
                 placebo: bool = False, modelos=MODELOS_WF, min_anos_treino: int = 8,
                 semente: int | None = None) -> pd.DataFrame:
    """Devolve uma linha por (ano_teste, variante, modelo) com RMSE/MAE no conjunto de teste COMUM."""
    semente = cfg["semente"] if semente is None else semente
    prep = {}
    for v in variantes:
        cfg_v = _merge(copy.deepcopy(cfg), v.cfg_patch)
        df = construir_dataset(entradas, cfg_v)
        com_umid = any(c.startswith("sm_raiz") for c in df.columns)
        cols = [] if v.remover == "*" else [c for c in nomes_features(cfg_v, com_umid) if c not in v.remover]
        prep[v.nome] = (df, cols, cfg_v)
    anos_todos = sorted(next(iter(prep.values()))[0]["ano"].unique())
    linhas = []
    for Y in anos_teste:
        anos_tr = [a for a in anos_todos if a < Y]
        if len(anos_tr) < min_anos_treino:
            raise DadosInvalidos(f"Ano de teste {Y} tem só {len(anos_tr)} anos de treino (< {min_anos_treino}).")
        folds = {n: _preparar_fold(df, cols, cfg_v, next(x for x in variantes if x.nome == n), anos_tr, placebo, semente)
                 for n, (df, cols, cfg_v) in prep.items()}
        universo = None
        for n, (d, _) in folds.items():
            ks = set(d.loc[(d["ano"] == Y) & d["_ok"], "_chave"])
            universo = ks if universo is None else universo & ks
        if not universo:
            raise DadosInvalidos(f"Sem linhas de teste comuns a todas as variantes em {Y}.")
        for v in variantes:
            d, cols_f = folds[v.nome]
            tr = d[(d["ano"] < Y) & d["_ok"]]
            te = d[(d["ano"] == Y) & d["_chave"].isin(universo)]
            y_te = te["anomalia_ndvi"].to_numpy()
            if v.alvo_z:
                sig = tr.groupby("ponto_id")["anomalia_ndvi"].std()
                glob = float(tr["anomalia_ndvi"].std())
                s_tr = tr["ponto_id"].map(sig).fillna(glob).replace(0, glob).to_numpy()
                s_te = te["ponto_id"].map(sig).fillna(glob).replace(0, glob).to_numpy()
                y_tr = tr["anomalia_ndvi"].to_numpy() / s_tr
            else:
                s_te = np.ones(len(te))
                y_tr = tr["anomalia_ndvi"].to_numpy()
            rmse_clim = float(np.sqrt(np.mean(y_te ** 2)))
            if "anom_lag1" in cols_f:      # baseline ingênuo: repetir a última anomalia observada
                err0 = y_te - te["anom_lag1"].to_numpy()
                r0 = float(np.sqrt(np.mean(err0 ** 2)))
                linhas.append({"ano_teste": int(Y), "variante": v.nome, "modelo": "ingenua", "n": int(len(te)),
                               "rmse": r0, "mae": float(np.mean(np.abs(err0))), "rmse_clim": rmse_clim,
                               "skill": skill(r0, rmse_clim), "n_treino": int(len(tr)), "placebo": bool(placebo)})
            for nome in modelos:
                mod, _ = ajustar_modelo(nome, tr[cols_f], y_tr, tr["celula_power"].to_numpy(), prep[v.nome][2])
                pred = mod.predict(te[cols_f]) * s_te
                err = y_te - pred
                linhas.append({"ano_teste": int(Y), "variante": v.nome, "modelo": nome, "n": int(len(te)),
                               "rmse": float(np.sqrt(np.mean(err ** 2))), "mae": float(np.mean(np.abs(err))),
                               "rmse_clim": rmse_clim, "skill": skill(float(np.sqrt(np.mean(err ** 2))), rmse_clim),
                               "n_treino": int(len(tr)), "placebo": bool(placebo)})
    return pd.DataFrame(linhas)


# ----------------------------------------------------------------------------- estatística
def _ic_inferior(valores: np.ndarray, alpha: float, n_boot: int, semente: int) -> float:
    """Limite inferior unilateral (percentil alpha) do bootstrap da média sobre ANOS."""
    v = np.asarray(valores, dtype=float)
    if len(v) < 2:
        return float("nan")
    rng = np.random.default_rng(semente)
    medias = rng.choice(v, size=(n_boot, len(v)), replace=True).mean(axis=1)
    return float(np.percentile(medias, 100 * alpha))


def resumir(res: pd.DataFrame, anos_selecao, anos_confirmacao, n_variantes: int | None = None, base: str = "base",
            modelo_base: str = "ridge", alpha: float = 0.05, n_boot: int = 10000, semente: int = 42) -> pd.DataFrame:
    """Uma linha por (variante, modelo). Critérios de 'melhoria válida' na docstring do módulo."""
    n_var = n_variantes or res["variante"].nunique()
    a = alpha / n_var                                       # Bonferroni pelo nº de variantes testadas
    sel = res[res["ano_teste"].isin(list(anos_selecao))]
    con = res[res["ano_teste"].isin(list(anos_confirmacao))]
    ref = sel[(sel["variante"] == base) & (sel["modelo"] == modelo_base)].set_index("ano_teste")["skill"]
    out = []
    for (var, mod), g in sel.groupby(["variante", "modelo"]):
        sk = g.set_index("ano_teste")["skill"]
        pooled = 1 - np.sqrt((g["n"] * g["rmse"] ** 2).sum() / (g["n"] * g["rmse_clim"] ** 2).sum())
        dif = (sk - ref.reindex(sk.index)).dropna()
        c = con[(con["variante"] == var) & (con["modelo"] == mod)]
        linha = {"variante": var, "modelo": mod, "anos_selecao": int(len(sk)),
                 "skill_media": float(sk.mean()), "skill_agregada": float(pooled),
                 "skill_ic_inf_corrigido": _ic_inferior(sk.to_numpy(), a, n_boot, semente),
                 "frac_anos_positivos": float((sk > 0).mean()),
                 "dif_vs_base_media": float(dif.mean()) if len(dif) else float("nan"),
                 "dif_vs_base_ic_inf": _ic_inferior(dif.to_numpy(), a, n_boot, semente) if len(dif) else float("nan"),
                 "skill_confirmacao": float(c["skill"].mean()) if len(c) else float("nan"),
                 "anos_confirmacao": int(len(c)), "n_variantes_testadas": int(n_var)}
        eh_base = (var == base and mod == modelo_base)
        linha["melhoria_valida"] = bool(
            linha["skill_media"] > 0 and linha["skill_ic_inf_corrigido"] > 0 and linha["frac_anos_positivos"] >= 0.6
            and (eh_base or linha["dif_vs_base_ic_inf"] > 0) and linha["skill_confirmacao"] > 0)
        out.append(linha)
    return pd.DataFrame(out).sort_values("skill_media", ascending=False).reset_index(drop=True)


if __name__ == "__main__":
    import sys

    from .entrada import RAIZ, carregar_config, carregar_entradas

    cfg = carregar_config()
    sint = "--sintetico" in sys.argv
    if sint:
        d = "data/processed/sintetico"
        cfg["caminhos"].update(clima=f"{d}/SINTETICO_clima_diario.parquet", ndvi=f"{d}/SINTETICO_ndvi_16d.parquet",
                               umidade_solo=f"{d}/SINTETICO_umidade_solo.parquet")
    elif "--dados" in sys.argv:
        pasta = sys.argv[sys.argv.index("--dados") + 1]
        cfg["caminhos"].update(clima=f"{pasta}/clima_diario.parquet", ndvi=f"{pasta}/ndvi_16d.parquet",
                               umidade_solo=f"{pasta}/umidade_solo.parquet")
    w = cfg["walkforward"]
    nomes = sys.argv[sys.argv.index("--variantes") + 1].split(",") if "--variantes" in sys.argv else list(VARIANTES)
    ent = carregar_entradas(cfg)   # caminho absoluto em --dados sobrepõe a raiz (pathlib)
    anos = list(range(w["anos_selecao"][0], w["anos_confirmacao"][1] + 1))
    res = walk_forward(ent, cfg, [VARIANTES[n] for n in nomes], anos, placebo="--placebo" in sys.argv)
    sel = list(range(w["anos_selecao"][0], w["anos_selecao"][1] + 1))
    con = list(range(w["anos_confirmacao"][0], w["anos_confirmacao"][1] + 1))
    tab = resumir(res, sel, con, n_variantes=len(nomes))
    if sint:
        print("Fluxo OK (sintético): métricas omitidas.")
    else:
        pd.set_option("display.width", 200, "display.max_columns", 20)
        print(tab.round(4).to_string(index=False))
