"""Experimento C: features novas (so dados existentes). Uso: python expC.py [placebo nome1,nome2]"""
import sys
from pathlib import Path
RAIZ = str(__import__("pathlib").Path(__file__).resolve().parents[2])
sys.path.insert(0, RAIZ)
import numpy as np
import pandas as pd
from src.modelos import walkforward as wf
from src.modelos.walkforward import Variante, extra_persistencia, walk_forward, resumir
from src.modelos.entrada import carregar_config, carregar_entradas

SP = Path(__file__).resolve().parent.parent   # experimentos/ (contém dados13/)
OUT = SP / "expC_features"
cfg = carregar_config()
cfg["caminhos"]["clima"] = str(SP / "dados13" / "clima_diario.parquet")
cfg["caminhos"]["ndvi"] = str(SP / "dados13" / "ndvi_16d.parquet")
cfg["caminhos"]["umidade_solo"] = str(SP / "dados13" / "NAO_EXISTE.parquet")
ent = carregar_entradas(cfg)


# ---------------------------------------------------------------- clima diario -> features (shift(1): so ate t-1)
def _dias_desde(ev, teto=120):
    out = np.full(len(ev), np.nan)
    last = None
    for i, e in enumerate(ev):
        if e:
            last = i
            out[i] = 0
        elif last is not None:
            out[i] = min(i - last, teto)
        elif i >= teto:
            out[i] = teto
    return out


def diario_ponto(cl):
    s = cl.sort_values("data").set_index("data")
    s = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"))
    r, tx, tn, rad = (s[c].shift(1) for c in ("chuva_mm", "tmax_c", "tmin_c", "radiacao"))  # estritamente < t
    o = pd.DataFrame(index=s.index)
    for w in (30, 60, 90):
        o[f"r{w}"] = r.rolling(w, min_periods=w).sum()
    ev = r >= 5
    o["dias_desde_5mm"] = _dias_desde(ev.fillna(False).to_numpy())
    o["n_ev60"] = ev.astype(float).where(r.notna()).rolling(60, min_periods=60).sum()
    chov = r.where(r >= 1)
    o["intens60"] = (chov.fillna(0).rolling(60, min_periods=60).sum()
                     / chov.notna().astype(float).rolling(60, min_periods=60).sum().clip(lower=1))
    o["tmin30"] = tn.rolling(30, min_periods=27).mean()
    o["rad30"] = rad.rolling(30, min_periods=27).mean()
    o["dtr30"] = (tx - tn).rolling(30, min_periods=27).mean()
    # ETo Hargreaves & Samani (1985), forma com radiacao: ETo = 0.0135*(Tmed+17.8)*Rs/2.45
    # (Rs em MJ/m2/d; POWER da kWh/m2/d => *3.6; 2.45 MJ/kg = calor latente de vaporizacao)
    eto = (0.0135 * ((tx + tn) / 2 + 17.8) * (rad * 3.6 / 2.45)).clip(lower=0)
    for w in (30, 60):
        o[f"def{w}"] = o[f"r{w}"] - eto.rolling(w, min_periods=w).sum()
    o.index.name = "data"
    return o.reset_index().assign(ponto_id=str(cl["ponto_id"].iloc[0]))


DIA = pd.concat([diario_ponto(cl) for _, cl in ent["clima"].groupby("ponto_id")], ignore_index=True)


def _merge_diario(d, cols):
    m = d.merge(DIA[["ponto_id", "data"] + cols], on=["ponto_id", "data"], how="left", validate="m:1")
    assert len(m) == len(d)
    return m


def _anos_treino(d):
    """Anos de treino do fold = os k primeiros anos, k = max(n_ref) (adicionar_anomalia usa anos < Y)."""
    anos = sorted(d["ano"].unique())
    k = int(d["n_ref"].max())
    return anos[:k]


def _clim_stats(d, cols):
    a = _anos_treino(d)
    g = d[d["ano"].isin(a)].groupby(["ponto_id", "slot"])[cols]
    return g.mean(), g.std(), g.count()


# ---------------------------------------------------------------- extras de persistencia
def ex_pers(d):
    return extra_persistencia(d)


def ex_lags4(d):
    d, c = extra_persistencia(d)
    g = d.groupby("ponto_id")
    gap = g["data"].diff().dt.days
    ok = (gap <= 17) & (gap.shift(1) <= 17) & (gap.shift(2) <= 17) & d["ponto_id"].eq(d["ponto_id"].shift(3))
    d["anom_lag3"] = g["anomalia_ndvi"].shift(3).where(ok)
    ok4 = ok & (gap.shift(3) <= 17) & d["ponto_id"].eq(d["ponto_id"].shift(4))
    d["anom_lag4"] = g["anomalia_ndvi"].shift(4).where(ok4)
    return d, c + ["anom_lag3", "anom_lag4"]


def ex_ano_ant(d):
    d, c = extra_persistencia(d)
    ant = d[["ponto_id", "slot", "ano", "anomalia_ndvi"]].copy()
    ant["ano"] += 1
    ant = ant.rename(columns={"anomalia_ndvi": "anom_ano_ant"})
    d = d.merge(ant, on=["ponto_id", "slot", "ano"], how="left", validate="1:1")
    return d, c + ["anom_ano_ant"]


def ex_ma3(d):
    d, c = ex_lags4(d)
    d["anom_ma3"] = d[["anom_lag1", "anom_lag2", "anom_lag3"]].mean(axis=1, skipna=False)
    return d, ["anom_lag1", "anom_lag2", "anom_ma3"]


# ---------------------------------------------------------------- extras de clima
def _anom_chuva(d, z=False):
    d = _merge_diario(d, ["r30", "r60", "r90"])
    cols = ["r30", "r60", "r90"]
    mu, sd, n = _clim_stats(d, cols)
    key = pd.MultiIndex.from_frame(d[["ponto_id", "slot"]])
    novas = []
    for c in cols:
        m = mu[c].reindex(key).to_numpy()
        s = sd[c].reindex(key).to_numpy()
        k = n[c].reindex(key).to_numpy()
        v = d[c].to_numpy() - m
        if z:
            v = v / np.where(s > 0, s, np.nan)
        v = np.where(k >= 5, v, np.nan)
        nm = ("spi_" if z else "anom_") + c
        d[nm] = v
        novas.append(nm)
    return d, novas


def ex_clima_anom(d):
    return _anom_chuva(d, False)


def ex_pers_clima_anom(d):
    d, c = ex_pers(d)
    d, n = _anom_chuva(d, False)
    return d, c + n


def ex_pers_spi(d):
    d, c = ex_pers(d)
    d, n = _anom_chuva(d, True)
    return d, c + n


EV = ["dias_desde_5mm", "n_ev60", "intens60"]
TERM = ["tmin30", "rad30", "dtr30"]
DEF = ["def30", "def60"]


def _mk(cols):
    def f(d):
        return _merge_diario(d, cols), list(cols)
    return f


def _pers_mais(cols):
    def f(d):
        d, c = ex_pers(d)
        return _merge_diario(d, cols), c + list(cols)
    return f


def ex_pers_inter(d):
    d, c = ex_pers(d)
    d, _ = _anom_chuva(d, False)
    novas = []
    for v in ("anom_r60", "anom_r90"):
        for t in ("sin", "cos"):
            d[f"{v}_x_{t}"] = d[v] * d[f"quinzena_{t}"]
            novas.append(f"{v}_x_{t}")
    # as colunas anom_r60/90 tambem entram (efeito principal)
    for t in ("sin", "cos"):
        d[f"r60_x_{t}"] = d["chuva_ac_60d"] * d[f"quinzena_{t}"]
        novas.append(f"r60_x_{t}")
    return d, c + ["anom_r60", "anom_r90"] + novas


def ex_pers_tudo(d):
    d, c = ex_pers(d)
    return _merge_diario(d, EV + TERM + DEF), c + EV + TERM + DEF


CHUVA_RAW = ("chuva_ac_30d", "chuva_ac_60d", "chuva_ac_90d")
V = [
    Variante("base", "controle"),
    Variante("persistencia", "controle: lag1-2", extra=ex_pers),
    Variante("so_persistencia", "controle: so lag1-2", extra=ex_pers, remover="*"),
    Variante("pers_lags4", "lags 1-4", extra=ex_lags4),
    Variante("pers_ano_ant", "persist + anomalia do mesmo slot no ano anterior", extra=ex_ano_ant),
    Variante("pers_ma3", "lag1, lag2, media das 3 ultimas", extra=ex_ma3),
    Variante("pers_clima_anom", "persist + chuva como anomalia (troca valor bruto)", extra=ex_pers_clima_anom, remover=CHUVA_RAW),
    Variante("pers_spi", "persist + chuva z-score do slot (SPI simplificado)", extra=ex_pers_spi, remover=CHUVA_RAW),
    Variante("pers_eventos", "persist + dias desde 5mm, eventos 60d, intensidade", extra=_pers_mais(EV)),
    Variante("pers_termica", "persist + tmin, radiacao, DTR 30d", extra=_pers_mais(TERM)),
    Variante("pers_deficit", "persist + deficit hidrico Hargreaves 30/60d", extra=_pers_mais(DEF)),
    Variante("pers_interacao", "persist + anomalia de chuva x sazonalidade", extra=ex_pers_inter),
    Variante("pers_tudo", "persist + eventos+termica+deficit", extra=ex_pers_tudo),
    Variante("pers_xgb_mono", "persist com XGB monotonico (+) na chuva", extra=ex_pers,
             cfg_patch={"preditivo": {"mono_chuva": True}}),
    Variante("clima_anom", "SEM persist: chuva anomalia", extra=ex_clima_anom, remover=CHUVA_RAW),
    Variante("clima_rico", "SEM persist: base + eventos+termica+deficit", extra=_mk(EV + TERM + DEF)),
]
N = len(V)

# monotonico: wrapper do ajustar_modelo (hiperparametros fixos do config; so adiciona a restricao)
_orig = wf.ajustar_modelo


def _ajustar(nome, X, y, g, cfg_):
    if nome == "xgboost" and cfg_["preditivo"].get("mono_chuva"):
        import copy
        c = copy.deepcopy(cfg_)
        mc = tuple(1 if col.startswith("chuva_ac_") else 0 for col in X.columns)
        c["preditivo"]["xgboost"]["monotone_constraints"] = "(" + ",".join(map(str, mc)) + ")"
        c["preditivo"].pop("mono_chuva")
        return _orig(nome, X, y, g, c)
    return _orig(nome, X, y, g, cfg_)


wf.ajustar_modelo = _ajustar

ANOS = list(range(2010, 2022))
COLS = ["variante", "modelo", "skill_media", "skill_ic_inf_corrigido", "dif_vs_base_media", "dif_vs_base_ic_inf", "frac_anos_positivos"]
if __name__ == "__main__":
    pd.set_option("display.width", 250)
    if len(sys.argv) > 1 and sys.argv[1] == "placebo":
        nomes = ["persistencia"] + sys.argv[2].split(",")
        res = walk_forward(ent, cfg, [v for v in V if v.nome in nomes], ANOS, placebo=True)
        res.to_pickle(OUT / "res_placebo.pkl")
        t = resumir(res, ANOS, [], n_variantes=N, base="persistencia")
        print(t[["variante", "modelo", "skill_media", "skill_ic_inf_corrigido", "frac_anos_positivos"]].round(4).to_string(index=False))
    else:
        res = walk_forward(ent, cfg, V, ANOS)
        res.to_pickle(OUT / "res.pkl")
        for base in ("persistencia", "base"):
            t = resumir(res, ANOS, [], n_variantes=N, base=base)
            t.to_csv(OUT / f"tab_{base}.csv", index=False)
            print("== base:", base, "N =", N)
            print(t[COLS].round(4).to_string(index=False))
