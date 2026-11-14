"""Núcleo do experimento SoilGrids: variantes de solo sobre a persistência, walk-forward guardando as PREVISÕES por linha.

Hiperparâmetros FIXOS a priori (os da produção via ajustar_modelo; v4 usa Ridge alpha=1,0 fixo). Nada ajustado olhando o teste.
Variantes (N próprias = 5 variantes x 2 modelos = 10 comparações; ver RESULTADO.md para o N total no Bonferroni):
  base      = persistência (modelo de produção; referência)
  v1_solo   = + areia, argila, carbono orgânico, pH (média 0-30 cm ponderada pela espessura 5/10/15 cm), padronizados entre os 195 pontos
  v2_ad     = + água disponível 0-30 cm (mm) por Saxton & Rawls (2006) (equações lidas em Blake & Assi 2019, Trans. ASABE 62(2):289-301,
              https://doi.org/10.13031/trans.13073, eqs. 2-5; ver agua_disponivel())
  v3_inter  = v1 + interações: chuva_ac_{30,60,90}d x argila; dias_secos x areia; chuva_ac_{30,60,90}d x carbono
  v4_solo   = base + correção do viés por ponto PREVISTO PELO SOLO (Ridge alpha=1 do viés médio por ponto no treino ~ 4 propriedades)
  v4_ref    = base + viés médio por ponto observado no treino (controle: sem solo; mede se existe efeito de ponto)
Placebo: o mapa ponto -> solo é permutado entre os 195 pontos (semente fixa); a skill contra a base deve ficar <= 0.
"""
import sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from src.modelos.entrada import carregar_config, carregar_entradas
from src.modelos.features import adicionar_anomalia, adicionar_persistencia, construir_dataset, nomes_features
from src.modelos.preditivo import ajustar_modelo

cfg = carregar_config()
MODELOS = ("ridge", "xgboost")
VARS = ["base", "v1_solo", "v2_ad", "v3_inter", "v4_solo", "v4_ref"]
D = ["0-5cm", "5-15cm", "15-30cm"]
ESP = np.array([50, 100, 150.0])           # mm
SOLO4 = ["sand", "clay", "soc", "phh2o"]


def agua_disponivel(areia_pct, argila_pct, soc_g_kg):
    """Saxton & Rawls (2006), eqs. 2-5 como reproduzidas em Blake & Assi (2019). S e C em FRAÇÃO (0-1), OM em % de massa.
    OM = SOC(g/kg)/10 x 1,724 (fator de van Bemmelen: SUPOSIÇÃO, sem fonte lida neste projeto). Devolve (CC33, PMP1500) em m3/m3."""
    S, C, OM = areia_pct / 100, argila_pct / 100, soc_g_kg / 10 * 1.724
    t33 = -0.251 * S + 0.195 * C + 0.011 * OM + 0.006 * S * OM - 0.027 * C * OM + 0.452 * S * C + 0.299
    cc = t33 + (1.283 * t33 ** 2 - 0.374 * t33 - 0.015)
    t15 = -0.024 * S + 0.487 * C + 0.006 * OM + 0.005 * S * OM - 0.013 * C * OM + 0.068 * S * C + 0.031
    pmp = t15 + (0.14 * t15 - 0.02)
    return cc, pmp


def tabela_solo() -> pd.DataFrame:
    s = pd.read_parquet(RAIZ / "data/processed/solo.parquet").set_index("ponto_id")
    w = ESP / ESP.sum()
    o = pd.DataFrame(index=s.index)
    for p in SOLO4:
        o[p] = np.column_stack([s[f"{p}_{d}"] for d in D]) @ w
    ad = 0.0
    for i, d in enumerate(D):
        cc, pmp = agua_disponivel(s[f"sand_{d}"], s[f"clay_{d}"], s[f"soc_{d}"])
        ad = ad + (cc - pmp) * ESP[i]
    o["ad_mm"] = ad
    return o


SOLO = tabela_solo()


def mapa_solo(semente_placebo=None) -> pd.DataFrame:
    """Padroniza (z) entre pontos; placebo permuta as LINHAS (ponto -> solo de outro ponto)."""
    z = (SOLO - SOLO.mean()) / SOLO.std(ddof=0)
    if semente_placebo is not None:
        perm = np.random.default_rng(semente_placebo).permutation(len(z))
        z = pd.DataFrame(z.to_numpy()[perm], index=z.index, columns=z.columns)
    return z


def colunas_solo(d: pd.DataFrame, Z: pd.DataFrame, var: str) -> tuple[pd.DataFrame, list[str]]:
    d = d.copy()
    m = d["ponto_id"].map
    for p in SOLO4 + ["ad_mm"]:
        d[f"z_{p}"] = m(Z[p])
    v1 = [f"z_{p}" for p in SOLO4]
    if var == "v1_solo":
        return d, v1
    if var == "v2_ad":
        return d, ["z_ad_mm"]
    if var == "v3_inter":
        nov = []
        for w in (30, 60, 90):
            d[f"x_chuva{w}_argila"] = d[f"chuva_ac_{w}d"] * d["z_clay"]; nov.append(f"x_chuva{w}_argila")
            d[f"x_chuva{w}_soc"] = d[f"chuva_ac_{w}d"] * d["z_soc"]; nov.append(f"x_chuva{w}_soc")
        d["x_secos_areia"] = d["dias_secos_consecutivos"] * d["z_sand"]; nov.append("x_secos_areia")
        return d, v1 + nov
    return d, []


def preparar_fold(df, cols, anos_tr):
    d = adicionar_anomalia(df, anos_tr, cfg).sort_values(["ponto_id", "data"]).reset_index(drop=True)
    d, nov = adicionar_persistencia(d)
    cf = list(cols) + nov
    d["_ok"] = d[cf].notna().all(axis=1) & d["anomalia_ndvi"].notna() & d["completo"]
    d["faixa"] = (d["slot"] // 6).clip(upper=3)
    return d, cf


def vies_ponto(tr, pred_tr, Z, ponto_te):
    """Viés médio por ponto no treino (y - pred); devolve (correção por ponto via solo [v4_solo], via observado [v4_ref])."""
    b = (tr["anomalia_ndvi"].to_numpy() - pred_tr)
    b = pd.Series(b, index=tr.index).groupby(tr["ponto_id"]).mean()
    X = Z.loc[b.index, [f"{p}" for p in SOLO4]].to_numpy()
    r = Ridge(alpha=1.0).fit(X, b.to_numpy())
    pontos = pd.Index(ponto_te.unique())
    via_solo = pd.Series(r.predict(Z.loc[pontos, SOLO4].to_numpy()), index=pontos)
    return via_solo, b


def rodar(df, anos_teste, placebo_semente=None, variantes=VARS) -> pd.DataFrame:
    Z = mapa_solo(placebo_semente)
    cols = nomes_features(cfg, False)
    anos_todos = sorted(df["ano"].unique())
    saida = []
    for Y in anos_teste:
        anos_tr = [a for a in anos_todos if a < Y]
        d0, cf0 = preparar_fold(df, cols, anos_tr)
        tr0 = d0[(d0["ano"] < Y) & d0["_ok"]]
        te0 = d0[(d0["ano"] == Y) & d0["_ok"]]
        base = te0[["ponto_id", "celula_power", "ano", "slot", "faixa", "data", "anomalia_ndvi"]].copy()
        base["anom_lag1"] = te0["anom_lag1"].to_numpy()
        preds = {}
        for nome in MODELOS:
            cache = {}
            for v in variantes:
                if v in ("v4_solo", "v4_ref"):
                    continue
                dd, extra = colunas_solo(d0, Z, v)
                cf = cf0 + extra
                tr, te = dd[(dd["ano"] < Y) & dd["_ok"]], dd[(dd["ano"] == Y) & dd["_ok"]]
                mod, _ = ajustar_modelo(nome, tr[cf], tr["anomalia_ndvi"].to_numpy(), tr["celula_power"].to_numpy(), cfg)
                preds[(v, nome)] = mod.predict(te[cf])
                if v == "base":
                    cache = (mod, tr)
            if "v4_solo" in variantes or "v4_ref" in variantes:
                mod, tr = cache
                via_solo, b = vies_ponto(tr, mod.predict(tr[cf0]), Z, te0["ponto_id"])
                p0 = preds[("base", nome)]
                preds[("v4_solo", nome)] = p0 + te0["ponto_id"].map(via_solo).to_numpy()
                preds[("v4_ref", nome)] = p0 + te0["ponto_id"].map(b).fillna(0).to_numpy()
        for (v, nome), p in preds.items():
            x = base.copy(); x["variante"] = v; x["modelo"] = nome; x["pred"] = p
            saida.append(x)
        print("ano", Y, "linhas", len(te0), flush=True)
    return pd.concat(saida, ignore_index=True)


def carregar_df():
    ent = carregar_entradas(cfg); ent["umidade_solo"] = None
    return construir_dataset(ent, cfg)
