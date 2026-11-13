"""TESTE 3: features ERA5-Land (Open-Meteo) sobre pers_lags4. Anomalias com climatologia EXPANDINDO (so anos anteriores ao
ano da linha), logo livre de vazamento em qualquer fold. Nao altera src/modelos/."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
RAIZ = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(RAIZ))
import numpy as np, pandas as pd
from scipy.stats import norm
from src.modelos.walkforward import Variante, extra_persistencia
from src.modelos.features import nomes_features

CACHE = RAIZ / "data/raw/era5land"
MIN_ANOS = 4          # anos anteriores minimos para a climatologia expandindo (1o ano com feature: 2005)
ANO_MIN = 2001 + MIN_ANOS

def carregar_diario(ids):
    """solo: era5_land 0.1 grau (arquivos sem 'chuva'); chuva: era5 0.25 grau (arquivos __chuva__)."""
    out = []
    for pid in ids:
        sl, ch = [], []
        for f in sorted(CACHE.glob(f"{pid}__*.json")):
            j = json.loads(f.read_text()); d = pd.DataFrame(j["daily"]); d["data"] = pd.to_datetime(d.pop("time"))
            if "__chuva__" in f.name: ch.append(d[["data", "precipitation_sum"]])
            else: sl.append(d[["data", "soil_moisture_0_to_7cm_mean", "soil_moisture_7_to_28cm_mean", "soil_moisture_28_to_100cm_mean"]])
        a = pd.concat(sl).drop_duplicates("data"); b = pd.concat(ch).drop_duplicates("data")
        m = a.merge(b, on="data", how="outer"); m["ponto_id"] = pid; out.append(m)
    d = pd.concat(out, ignore_index=True)
    return d.rename(columns={"precipitation_sum": "p", "soil_moisture_0_to_7cm_mean": "s1",
                             "soil_moisture_7_to_28cm_mean": "s2", "soil_moisture_28_to_100cm_mean": "s3"})

def feats_diarias(d):
    """Features no dia t usando so dias <= t-1 (shift 1), igual a src/modelos/features.py."""
    pedacos = []
    for pid, g in d.groupby("ponto_id"):
        g = g.drop_duplicates("data").set_index("data").sort_index().asfreq("D")
        x = pd.DataFrame(index=g.index)
        p = g["p"].shift(1)
        for w in (30, 60, 90): x[f"e_chuva_{w}d"] = p.rolling(w, min_periods=w).sum()
        for k, c in (("s1", "e_sm_0_7"), ("s2", "e_sm_7_28"), ("s3", "e_sm_28_100")):
            x[c] = g[k].shift(1).rolling(15, min_periods=14).mean()
        x["e_sm_0_7_l16"] = x["e_sm_0_7"].shift(16)       # umidade defasada 1 composto (16 d)
        x["e_sm_7_28_l16"] = x["e_sm_7_28"].shift(16)
        x["ponto_id"] = pid; pedacos.append(x.reset_index().rename(columns={"index": "data"}))
    return pd.concat(pedacos, ignore_index=True)

def anomalia_expandindo(df, cols):
    """x - media(mesmo ponto, mesmo slot, anos ANTERIORES); NaN com < MIN_ANOS anos anteriores."""
    df = df.sort_values(["ponto_id", "slot", "ano"]).copy()
    g = df.groupby(["ponto_id", "slot"])
    for c in cols:
        ms = g[c].transform(lambda s: s.shift(1).expanding().mean())
        n = g[c].transform(lambda s: s.shift(1).expanding().count())
        df[c + "_an"] = (df[c] - ms).where(n >= MIN_ANOS)
    return df

def spi_empirico(df, col, nome):
    """percentil da soma de 90 d entre os anos anteriores (mesmo ponto/slot) -> normal. Nao-parametrico, expandindo."""
    df = df.sort_values(["ponto_id", "slot", "ano"]).copy(); df[nome] = np.nan
    for _, idx in df.groupby(["ponto_id", "slot"]).groups.items():
        v = df.loc[idx, col].to_numpy(float); out = np.full(len(v), np.nan)
        for i in range(MIN_ANOS, len(v)):
            ref = v[:i]; ref = ref[~np.isnan(ref)]
            if len(ref) >= MIN_ANOS and not np.isnan(v[i]):
                out[i] = norm.ppf(((ref < v[i]).sum() + 0.5 * (ref == v[i]).sum() + 0.5) / (len(ref) + 1))
        df.loc[idx, nome] = out
    return df

def montar(ids):
    diario = carregar_diario(ids); F = feats_diarias(diario)
    def ex_base(d):
        d, c = extra_persistencia(d)
        g = d.groupby("ponto_id"); gap = g["data"].diff().dt.days
        ok = (gap <= 17) & (gap.shift(1) <= 17) & (gap.shift(2) <= 17) & d["ponto_id"].eq(d["ponto_id"].shift(3))
        d["anom_lag3"] = g["anomalia_ndvi"].shift(3).where(ok)
        ok4 = ok & (gap.shift(3) <= 17) & d["ponto_id"].eq(d["ponto_id"].shift(4))
        d["anom_lag4"] = g["anomalia_ndvi"].shift(4).where(ok4)
        return d, c + ["anom_lag3", "anom_lag4"]
    def com_era(d):
        d, c = ex_base(d)
        d = d.merge(F, on=["ponto_id", "data"], how="left", validate="m:1")
        d = anomalia_expandindo(d, [x for x in F.columns if x.startswith("e_")])
        d = spi_empirico(d, "e_chuva_90d", "e_spi3")
        return d.sort_values(["ponto_id", "data"]).reset_index(drop=True), c
    return ex_base, com_era

def variantes(ids, cfg):
    ex_base, com_era = montar(ids)
    chuva_pw = tuple(f"chuva_ac_{w}d" for w in cfg["preditivo"]["janelas_chuva_dias"])
    def mk(cols_era, remover=(), extra_spi=False):
        def ex(d):
            d, c = com_era(d)
            return d, c + cols_era
        return ex
    def ctrl(d):
        d, c = com_era(d)                                    # controle: mesmas linhas de treino (anomalia ERA valida >= 2005)
        d.loc[d["ano"] < ANO_MIN, "anom_lag1"] = np.nan
        return d, c
    an = lambda *n: [f"{x}_an" for x in n]
    v = [Variante("pers_lags4_c", "controle (treino >= 2005)", extra=ctrl),
         Variante("era_chuva", "pers_lags4 com chuva ERA5-Land (30/60/90 d, anomalia) no lugar da POWER",
                  extra=mk(an("e_chuva_30d", "e_chuva_60d", "e_chuva_90d")), remover=chuva_pw),
         Variante("era_chuva_sm12", "era_chuva + umidade 0-7 e 7-28 cm (15 d e defasada 16 d)",
                  extra=mk(an("e_chuva_30d", "e_chuva_60d", "e_chuva_90d", "e_sm_0_7", "e_sm_7_28", "e_sm_0_7_l16", "e_sm_7_28_l16")), remover=chuva_pw),
         Variante("era_chuva_sm123", "era_chuva_sm12 + umidade 28-100 cm",
                  extra=mk(an("e_chuva_30d", "e_chuva_60d", "e_chuva_90d", "e_sm_0_7", "e_sm_7_28", "e_sm_0_7_l16", "e_sm_7_28_l16", "e_sm_28_100")), remover=chuva_pw),
         Variante("era_spi3", "pers_lags4 (+POWER) + SPI-3 empirico ERA5-Land", extra=mk(["e_spi3"]))]
    return v
