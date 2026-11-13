"""Walk-forward proprio (nao altera src/modelos/) que devolve previsoes POR LINHA, para estratificar por estacao.
Reproduz a logica de src/modelos/walkforward.walk_forward (treino so anos < Y, climatologia so anos < Y,
universo de teste comum a todas as variantes). Apenas anos de SELECAO sao permitidos (guarda abaixo)."""
import copy, sys
from pathlib import Path
RAIZ = str(Path(__file__).resolve().parents[2]); sys.path.insert(0, RAIZ)
import numpy as np, pandas as pd
from src.modelos.walkforward import _preparar_fold, _merge
from src.modelos.features import construir_dataset, nomes_features
from src.modelos.preditivo import ajustar_modelo

ANOS_PERMITIDOS = set(range(2010, 2022))

def prever_linhas(entradas, cfg, variantes, anos_teste, placebo=False, modelos=("ridge",), min_treino=8, semente=None):
    assert set(anos_teste) <= ANOS_PERMITIDOS, "so 2010-2021 (selecao); 2022-2024 e selado"
    semente = cfg["semente"] if semente is None else semente
    prep = {}
    for v in variantes:
        cfg_v = _merge(copy.deepcopy(cfg), v.cfg_patch)
        df = construir_dataset(entradas, cfg_v)
        com_umid = any(c.startswith("sm_raiz") for c in df.columns)
        cols = [] if v.remover == "*" else [c for c in nomes_features(cfg_v, com_umid) if c not in v.remover]
        prep[v.nome] = (df, cols, cfg_v, v)
    anos_todos = sorted(next(iter(prep.values()))[0]["ano"].unique())
    out = []
    for Y in anos_teste:
        anos_tr = [a for a in anos_todos if a < Y]
        folds = {n: _preparar_fold(df, cols, cfg_v, v, anos_tr, placebo, semente) for n, (df, cols, cfg_v, v) in prep.items()}
        univ = None
        for n, (d, _) in folds.items():
            ks = set(d.loc[(d["ano"] == Y) & d["_ok"], "_chave"]); univ = ks if univ is None else univ & ks
        for v in variantes:
            d, cols_f = folds[v.nome]
            tr = d[(d["ano"] < Y) & d["_ok"]]; te = d[(d["ano"] == Y) & d["_chave"].isin(univ)]
            for nome in modelos:
                mod, _ = ajustar_modelo(nome, tr[cols_f], tr["anomalia_ndvi"].to_numpy(), tr["celula_power"].to_numpy(), prep[v.nome][2])
                p = te[["ponto_id", "data", "slot", "anomalia_ndvi"]].copy()
                p["pred"] = mod.predict(te[cols_f]); p["ano_teste"] = Y; p["variante"] = v.nome; p["modelo"] = nome
                out.append(p)
    return pd.concat(out, ignore_index=True)
