"""Avaliacao com 195 pontos (protocolo docs/05_EXPERIMENTOS.md). NAO altera src/modelos/.

Uso:
  python avaliar.py selecao  [placebo]   -> so 2010-2021 (base, persistencia, so_persistencia, pers_lags4)
  python avaliar.py confirma             -> UMA vez, 2022-2024, so persistencia e pers_lags4
  python avaliar.py sm  [placebo]        -> variantes com SMAP (selecao nos anos com treino SMAP)
  python avaliar.py sm_confirma          -> UMA vez, finalistas SMAP (se houver)
"""
import sys
from pathlib import Path
RAIZ = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, RAIZ)
import numpy as np
import pandas as pd
from src.modelos.walkforward import VARIANTES, Variante, extra_persistencia, walk_forward, resumir
from src.modelos.entrada import carregar_config, carregar_entradas
from src.modelos.features import nomes_features

OUT = Path(__file__).resolve().parent
cfg = carregar_config()
SEL = list(range(2010, 2022))
CON = [2022, 2023, 2024]


def ex_lags4(d):  # identica a experimentos/expC_features/expC.py
    d, c = extra_persistencia(d)
    g = d.groupby("ponto_id")
    gap = g["data"].diff().dt.days
    ok = (gap <= 17) & (gap.shift(1) <= 17) & (gap.shift(2) <= 17) & d["ponto_id"].eq(d["ponto_id"].shift(3))
    d["anom_lag3"] = g["anomalia_ndvi"].shift(3).where(ok)
    ok4 = ok & (gap.shift(3) <= 17) & d["ponto_id"].eq(d["ponto_id"].shift(4))
    d["anom_lag4"] = g["anomalia_ndvi"].shift(4).where(ok4)
    return d, c + ["anom_lag3", "anom_lag4"]


PL4 = Variante("pers_lags4", "lags 1-4", extra=ex_lags4)
ESC = lambda n: [VARIANTES[x] for x in n]
pd.set_option("display.width", 250, "display.max_columns", 30)
COLS = ["variante", "modelo", "skill_media", "skill_agregada", "skill_ic_inf_corrigido", "frac_anos_positivos",
        "dif_vs_base_media", "dif_vs_base_ic_inf"]


def rodar_sel(placebo):
    vs = ESC(["base", "persistencia", "so_persistencia"]) + [PL4]
    N = len(vs)
    ent = carregar_entradas(cfg)
    ent["umidade_solo"] = None
    res = walk_forward(ent, cfg, vs, SEL, placebo=placebo)
    res.to_pickle(OUT / f"res_sel{'_placebo' if placebo else ''}.pkl")
    for base in ("base", "persistencia"):
        t = resumir(res, SEL, [], n_variantes=N, base=base)
        print("== SELECAO 2010-2021, base =", base, "N =", N, "placebo =", placebo)
        print(t[COLS].round(4).to_string(index=False))
    pa = res[res.modelo == "ridge"].pivot(index="ano_teste", columns="variante", values="skill").round(3)
    print(pa.to_string())
    print("n linhas teste por ano (comum):", res[(res.variante == "base") & (res.modelo == "ridge")].set_index("ano_teste")["n"].to_dict())
    ing = res[res.modelo == "ingenua"].groupby("variante")["skill"].mean()
    print("ingenua skill media:", ing.round(4).to_dict())


def rodar_conf():
    vs = ESC(["persistencia"]) + [PL4, VARIANTES["base"]]
    ent = carregar_entradas(cfg)
    ent["umidade_solo"] = None
    res = walk_forward(ent, cfg, vs, CON)
    res.to_pickle(OUT / "res_confirmacao.pkl")
    print("== CONFIRMACAO SELADA 2022-2024 (executada uma vez)")
    print(res[res.modelo.isin(["ridge", "xgboost", "ingenua"])].groupby(["variante", "modelo"])["skill"].agg(["mean", "min", "max"]).round(4))
    print(res[res.modelo == "ridge"].pivot(index="ano_teste", columns="variante", values="skill").round(4))


# ---------------------------------------------------------------- SMAP
def smap_ent():
    return carregar_entradas(cfg)


def make_sm(ent, lag):
    """sm_raiz: media de 7 dias terminando em t-lag-1 (estritamente passado). Corrigido (rascunho original falhava no rename)."""
    um = ent["umidade_solo"][["ponto_id", "data", "sm_raiz"]].copy()
    um["data"] = pd.to_datetime(um["data"])
    pedacos = []
    for pid, g in um.groupby("ponto_id"):
        s = g.set_index("data")["sm_raiz"].sort_index().asfreq("D")
        r = s.rolling(7, min_periods=5).mean().shift(lag + 1)
        pedacos.append(pd.DataFrame({"ponto_id": str(pid), "data": r.index, f"sm_raiz_l{lag}": r.to_numpy()}))
    tab = pd.concat(pedacos, ignore_index=True)
    nome = f"sm_raiz_l{lag}"

    def ex(d):
        d, c = extra_persistencia(d)
        d = d.merge(tab, on=["ponto_id", "data"], how="left", validate="m:1")
        return d, c + [nome]
    return ex


def rodar_sm(placebo):
    ent = smap_ent()
    cols_sm = [c for c in nomes_features(cfg, True) if c.startswith("sm_")]
    # controle: mesma amostra, sem colunas de umidade
    ctrl = Variante("persistencia", "controle sem SM", extra=extra_persistencia, remover=tuple(cols_sm))
    v_pers_sm = Variante("pers_sm", "persistencia + sm (features padrao do pacote: media movel)", extra=extra_persistencia)
    v_l14 = Variante("pers_sm_l14", "persistencia + sm_raiz defasada 14 d", extra=make_sm(ent, 14), remover=tuple(cols_sm))
    v_l30 = Variante("pers_sm_l30", "persistencia + sm_raiz defasada 30 d", extra=make_sm(ent, 30), remover=tuple(cols_sm))
    vs = [ctrl, v_pers_sm, v_l14, v_l30]
    N = 4 + 4 + 2 + 1  # ver RESULTADO.md: N total = 4 variantes NDVI (base, pers, so_pers, lags4) + 3 SMAP + ... (calculado abaixo)
    anos = list(range(2018, 2022))
    res = walk_forward(ent, cfg, vs, anos, placebo=placebo)
    res.to_pickle(OUT / f"res_sm{'_placebo' if placebo else ''}.pkl")
    NT = 4 + 3     # base, persistencia, so_persistencia, pers_lags4 + pers_sm, pers_sm_l14, pers_sm_l30
    t = resumir(res, anos, [], n_variantes=NT, base="persistencia")
    print("== SMAP selecao", anos, "N total (Bonferroni) =", NT, "placebo =", placebo)
    print(t[COLS].round(4).to_string(index=False))
    print(res[res.modelo == "ridge"].pivot(index="ano_teste", columns="variante", values="skill").round(4))
    print(res[res.modelo == "ridge"].groupby("variante")["n"].sum().to_dict())


def rodar_sm_conf():
    """UMA vez: finalista SMAP pers_sm vs controle (mesma amostra), 2022-2024. Treino 2015+ (sm so existe desde 2015)."""
    ent = smap_ent()
    cols_sm = [c for c in nomes_features(cfg, True) if c.startswith("sm_")]
    ctrl = Variante("persistencia", "controle sem SM", extra=extra_persistencia, remover=tuple(cols_sm))
    v = Variante("pers_sm", "persistencia + sm (media movel padrao)", extra=extra_persistencia)
    res = walk_forward(ent, cfg, [ctrl, v], CON)
    res.to_pickle(OUT / "res_sm_confirmacao.pkl")
    print("== CONFIRMACAO SELADA SMAP 2022-2024 (executada uma vez)")
    print(res[res.modelo.isin(["ridge", "xgboost", "ingenua"])].groupby(["variante", "modelo"])["skill"].agg(["mean", "min", "max"]).round(4))
    print(res[res.modelo == "ridge"].pivot(index="ano_teste", columns="variante", values="skill").round(4))
    print(res[res.modelo == "ridge"].groupby("variante")["n"].sum().to_dict())


if __name__ == "__main__":
    a = sys.argv[1]
    pl = "placebo" in sys.argv[2:]
    {"selecao": lambda: rodar_sel(pl), "confirma": rodar_conf, "sm": lambda: rodar_sm(pl), "sm_confirma": rodar_sm_conf}[a]()
