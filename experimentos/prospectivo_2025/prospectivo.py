"""Teste prospectivo 2025+ do modelo congelado (treino/climatologia <= 2024). NAO altera src/. Nada e ajustado com 2025+.
Uso: python prospectivo.py            (roda tudo; grava CSV/PNG/json nesta pasta)
     python prospectivo.py sanidade   (reproduz walk_forward de 2024 com o mesmo pipeline)"""
import sys, json
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import numpy as np, pandas as pd
from src.modelos.entrada import carregar_config, carregar_entradas
from src.modelos.features import construir_dataset, adicionar_anomalia, adicionar_persistencia, nomes_features
from src.modelos.preditivo import ajustar_modelo
from src.modelos.conformal_aci import aci_walk_forward, _tabela_ano, q_nivel, atualizar_alpha, N_FAIXAS

OUT = Path(__file__).resolve().parent
CORTE = 2024            # ultimo ano de treino/climatologia
cfg = carregar_config()
PERS = cfg["preditivo"].get("persistencia_max_gap_dias", 17)


def carregar():
    ent = carregar_entradas(cfg)
    ent["umidade_solo"] = None
    cl = pd.read_parquet(RAIZ / "data/processed/clima_2025plus.parquet")
    nd = pd.read_parquet(RAIZ / "data/processed/ndvi_2025plus.parquet")
    ent["clima"] = pd.concat([ent["clima"], cl], ignore_index=True)
    ent["ndvi"] = pd.concat([ent["ndvi"], nd], ignore_index=True)
    return ent


def skill(r, r0): return float(1 - r / r0)
def rmse(e): return float(np.sqrt(np.mean(np.square(e))))


def preparar(ds, Y0):
    """Anomalia com climatologia dos anos < Y0 + persistencia. Devolve tabela com linhas validas e colunas de features."""
    anos_tr = sorted(int(a) for a in ds["ano"].unique() if a < Y0)
    d = adicionar_anomalia(ds, anos_tr, cfg)
    d, novas = adicionar_persistencia(d, PERS)
    cols = nomes_features(cfg, False) + novas
    d["_ok"] = d["completo"] & d["anomalia_ndvi"].notna() & d[cols].notna().all(axis=1)
    return d, cols


def ajustar(d, cols, Y0):
    tr = d[(d["ano"] < Y0) & d["_ok"]]
    out = {}
    for n in ("ridge", "xgboost"):
        out[n], _ = ajustar_modelo(n, tr[cols], tr["anomalia_ndvi"].to_numpy(), tr["celula_power"].to_numpy(), cfg)
    return out, tr


def sanidade(ds):
    from src.modelos.walkforward import walk_forward, VARIANTES
    ent = carregar_entradas(cfg); ent["umidade_solo"] = None
    wf = walk_forward(ent, cfg, [VARIANTES["persistencia"]], [2024])
    d, cols = preparar(ds[ds["ano"] <= 2024], 2024)
    mods, tr = ajustar(d, cols, 2024)
    te = d[(d["ano"] == 2024) & d["_ok"]]
    y = te["anomalia_ndvi"].to_numpy(); r0 = rmse(y)
    print(wf[["variante", "modelo", "n", "rmse", "skill"]].round(5).to_string())
    for n, m in mods.items():
        print("meu", n, len(te), round(rmse(y - m.predict(te[cols])), 5), round(skill(rmse(y - m.predict(te[cols])), r0), 5))
    print("meu ingenua", round(skill(rmse(y - te["anom_lag1"].to_numpy()), r0), 5))


# ----------------------------------------------------------------------------- bootstrap por cluster
def boot_skill(df, col_err, col_cl, cluster, n_boot=5000, seed=7, ref_err=None):
    """Skill agregado = 1 - sqrt(sum e2/n)/sqrt(sum y2/n); reamostra clusters (datas ou pontos) com reposicao."""
    g = df.assign(e2=df[col_err] ** 2, y2=df[col_cl] ** 2, one=1.0)
    cols = ["e2", "y2", "one"] + ([] if ref_err is None else ["r2"])
    if ref_err is not None: g["r2"] = df[ref_err] ** 2
    s = g.groupby(cluster)[cols].sum()
    rng = np.random.default_rng(seed)
    k = len(s)
    w = rng.multinomial(k, np.ones(k) / k, size=n_boot).astype(float)
    tot = w @ s.to_numpy()
    sk = 1 - np.sqrt(tot[:, 0] / tot[:, 1])
    pt = 1 - np.sqrt(s["e2"].sum() / s["y2"].sum())
    out = {"ponto": float(pt), "ic95": [float(np.percentile(sk, 2.5)), float(np.percentile(sk, 97.5))], "n_clusters": int(k)}
    if ref_err is not None:   # dif de skill modelo - referencia
        sk2 = 1 - np.sqrt(tot[:, 3] / tot[:, 1])
        dif = sk - sk2
        out["dif_ref"] = {"ponto": float(pt - (1 - np.sqrt(s["r2"].sum() / s["y2"].sum()))), "ic95": [float(np.percentile(dif, 2.5)), float(np.percentile(dif, 97.5))]}
    return out


def tab_skill(te, grupo):
    linhas = []
    for k, x in te.groupby(grupo):
        r0 = rmse(x["anomalia_ndvi"])
        linhas.append({grupo: k, "n": len(x), "rmse_clim": r0, "skill_xgb": skill(rmse(x["e_xgb"]), r0),
                       "skill_ridge": skill(rmse(x["e_ridge"]), r0), "skill_ingenua": skill(rmse(x["e_ing"]), r0),
                       "vies_xgb": float(x["e_xgb"].mean()), "obs_media": float(x["anomalia_ndvi"].mean())})
    return pd.DataFrame(linhas)


# ----------------------------------------------------------------------------- horizonte
def horizonte(d, cols, h, Y0):
    """Alvo = anomalia do composto t; origem = linha do composto t-h+1 (features e anom_lag1/2 dela: so o que se sabia ali);
    + sin/cos sazonais do composto-alvo. Exige h compostos consecutivos (gaps <= 17 d) entre a origem e o alvo."""
    d = d.sort_values(["ponto_id", "data"]).reset_index(drop=True)
    g = d.groupby("ponto_id")
    ok = pd.Series(True, index=d.index)
    gap = g["data"].diff().dt.days
    for s in range(0, h - 1):                       # gaps entre linhas t-h+1 .. t
        ok &= (gap.shift(s) <= PERS) & d["ponto_id"].eq(d["ponto_id"].shift(s + 1))
    X = pd.DataFrame(index=d.index)
    for c in cols:
        X[c] = d[c].shift(h - 1) if h > 1 else d[c]
    q = d["quinzena"].to_numpy()
    X["alvo_sin"] = np.sin(2 * np.pi * q / 24); X["alvo_cos"] = np.cos(2 * np.pi * q / 24)
    ok &= d["ponto_id"].eq(d["ponto_id"].shift(h - 1)) & d["anomalia_ndvi"].notna() & X.notna().all(axis=1)
    # origem precisa ser linha valida (completo) -> feature notna ja garante clima completo
    t = pd.concat([d[["ponto_id", "data", "ano", "slot", "celula_power", "anomalia_ndvi"]], X], axis=1)[ok]
    t["lag_ult"] = X["anom_lag1"][ok]
    feats = list(X.columns)
    tr, te = t[t["ano"] < Y0], t[t["ano"] >= Y0]
    res = {}
    y = te["anomalia_ndvi"].to_numpy(); r0 = rmse(y)
    row = {"h": h, "n_teste": len(te), "n_treino": len(tr), "rmse_clim": r0, "skill_ingenua": skill(rmse(y - te["lag_ult"].to_numpy()), r0)}
    preds = {}
    for n in ("ridge", "xgboost"):
        m, _ = ajustar_modelo(n, tr[feats], tr["anomalia_ndvi"].to_numpy(), tr["celula_power"].to_numpy(), cfg)
        preds[n] = m.predict(te[feats]); row[f"skill_{n}"] = skill(rmse(y - preds[n]), r0)
    te = te.assign(e_xgb=y - preds["xgboost"], e_ridge=y - preds["ridge"], e_ing=y - te["lag_ult"].to_numpy())
    for n, c in (("xgb", "e_xgb"), ("ridge", "e_ridge"), ("ing", "e_ing")):
        b = boot_skill(te, c, "anomalia_ndvi", "data", n_boot=3000)
        row[f"ic_{n}"] = b["ic95"]
    return row


def main():
    ent = carregar()
    ds = construir_dataset(ent, cfg)
    if "sanidade" in sys.argv:
        return sanidade(ds)
    Y0 = CORTE + 1
    d, cols = preparar(ds, Y0)
    mods, tr = ajustar(d, cols, Y0)
    te = d[(d["ano"] >= Y0) & d["_ok"]].copy()
    te["faixa"] = (te["slot"] // 6).clip(upper=N_FAIXAS - 1)
    te["mes"] = te["data"].dt.month
    y = te["anomalia_ndvi"].to_numpy()
    te["p_xgb"] = mods["xgboost"].predict(te[cols]); te["p_ridge"] = mods["ridge"].predict(te[cols])
    te["e_xgb"] = y - te["p_xgb"]; te["e_ridge"] = y - te["p_ridge"]; te["e_ing"] = y - te["anom_lag1"].to_numpy()

    # ---- cobertura/diagnostico dos dados 2025+
    novo = ds[ds["ano"] >= Y0]
    cob = {"linhas_ndvi_valido_2025plus": int(len(novo)), "linhas_testaveis": int(len(te)), "pontos_testaveis": int(te["ponto_id"].nunique()),
           "datas_testaveis": [str(x.date()) for x in sorted(te["data"].unique())],
           "linhas_sem_clima_completo": int((~novo["completo"]).sum()),
           "linhas_sem_lags": int((novo["completo"] & ~novo["_ok"] if "_ok" in novo else 0).sum()) if False else None}

    # ---- ACI: estado ao fim de 2024 (aquecimento+2022-24 como na producao), depois online em 2025+
    aq = list(range(2009, 2022)); at = [2022, 2023, 2024]
    dsa = ds[ds["ano"] <= CORTE]
    r = aci_walk_forward(dsa, cfg, aq, at, True, retornar_faixas=True)
    estado0 = {(float(a) / 100, int(f)): v for a, fs in r["faixas_finais"]["alpha_final"].items() for f, v in fs.items()}
    da, cfa, anos_tr = _tabela_ano(ds, cfg, Y0, True)           # clim <= 2024
    trA = da[da["ano"] < Y0]; teA = da[da["ano"] >= Y0].copy()
    corte = anos_tr[-3]
    prop, cal = trA[trA["ano"] < corte], trA[trA["ano"] >= corte]
    modA, _ = ajustar_modelo("ridge", prop[cfa], prop["anomalia_ndvi"].to_numpy(), prop["celula_power"].to_numpy(), cfg)
    rcal = np.abs(cal["anomalia_ndvi"].to_numpy() - modA.predict(cal[cfa]))
    rf = {f: np.sort(rcal[(cal["faixa"] == f).to_numpy()]) for f in range(N_FAIXAS)}
    teA["err"] = np.abs(teA["anomalia_ndvi"].to_numpy() - modA.predict(teA[cfa]))
    chaves = ["ponto_id", "data"]
    teA["hw80"] = np.nan; teA["hw90"] = np.nan; teA["hw80_est"] = np.nan; teA["hw90_est"] = np.nan
    estado = dict(estado0)
    for dt_, ix in teA.groupby("data").groups.items():
        sub = teA.loc[ix]
        for f, jx in sub.groupby("faixa").groups.items():
            for alvo in (0.8, 0.9):
                a0 = 1 - alvo; al = estado.get((alvo, int(f)), a0)
                hw = q_nivel(rf[int(f)], al)
                teA.loc[jx, f"hw{int(alvo*100)}"] = hw
                teA.loc[jx, f"hw{int(alvo*100)}_est"] = q_nivel(rf[int(f)], estado0.get((alvo, int(f)), a0))
                c = teA.loc[jx, "err"].to_numpy() <= hw
                estado[(alvo, int(f))] = atualizar_alpha(al, a0, 1 - float(c.mean()), float(r["gamma"]))
    te = te.merge(teA[chaves + ["hw80", "hw90", "hw80_est", "hw90_est", "err"]].rename(columns={"err": "err_ridgeACI"}), on=chaves, how="left")
    for m_, nome in (("xgb", "e_xgb"), ("aci", "err_ridgeACI")):
        for a in (80, 90):
            te[f"cob_{m_}_{a}"] = (te[nome].abs() <= te[f"hw{a}"]).astype(float)
            te[f"cob_{m_}_{a}_est"] = (te[nome].abs() <= te[f"hw{a}_est"]).astype(float)

    # ---- metricas
    r0 = rmse(y)
    G = {"n_linhas": int(len(te)), "n_pontos": int(te["ponto_id"].nunique()), "n_datas": int(te["data"].nunique()),
         "rmse_clim": r0, "rmse_xgb": rmse(te["e_xgb"]), "rmse_ridge": rmse(te["e_ridge"]), "rmse_ingenua": rmse(te["e_ing"]),
         "skill_xgb": skill(rmse(te["e_xgb"]), r0), "skill_ridge": skill(rmse(te["e_ridge"]), r0), "skill_ingenua": skill(rmse(te["e_ing"]), r0),
         "vies_medio_xgb": float(te["e_xgb"].mean()), "anomalia_obs_media": float(y.mean()), "anomalia_pred_media_xgb": float(te["p_xgb"].mean())}
    B = {}
    for n, c in (("xgb", "e_xgb"), ("ridge", "e_ridge"), ("ingenua", "e_ing")):
        B[n] = {"por_composto": boot_skill(te, c, "anomalia_ndvi", "data"), "por_ponto": boot_skill(te, c, "anomalia_ndvi", "ponto_id")}
    B["xgb_menos_ingenua"] = {"por_composto": boot_skill(te, "e_xgb", "anomalia_ndvi", "data", ref_err="e_ing")["dif_ref"],
                              "por_ponto": boot_skill(te, "e_xgb", "anomalia_ndvi", "ponto_id", ref_err="e_ing")["dif_ref"]}
    B["xgb_menos_ridge"] = {"por_composto": boot_skill(te, "e_xgb", "anomalia_ndvi", "data", ref_err="e_ridge")["dif_ref"]}
    # vies medio com IC por composto
    por_data = te.groupby("data").agg(n=("e_xgb", "size"), obs=("anomalia_ndvi", "mean"), pred=("p_xgb", "mean"), vies=("e_xgb", "mean"),
                                      rmse_xgb=("e_xgb", rmse), rmse_clim=("anomalia_ndvi", lambda s: rmse(s)),
                                      rmse_ing=("e_ing", rmse)).reset_index()
    por_data["skill_xgb"] = 1 - por_data["rmse_xgb"] / por_data["rmse_clim"]
    rng = np.random.default_rng(11)
    mv = [rng.choice(por_data["vies"].to_numpy(), len(por_data)).mean() for _ in range(5000)]
    G["vies_por_composto_media"] = float(por_data["vies"].mean()); G["vies_ic95_composto"] = [float(np.percentile(mv, 2.5)), float(np.percentile(mv, 97.5))]
    por_data.to_csv(OUT / "erro_por_composto.csv", index=False)
    por_ano = {int(a): {"n": int(len(x)), "skill_xgb": skill(rmse(x["e_xgb"]), rmse(x["anomalia_ndvi"])), "skill_ridge": skill(rmse(x["e_ridge"]), rmse(x["anomalia_ndvi"])),
                        "skill_ingenua": skill(rmse(x["e_ing"]), rmse(x["anomalia_ndvi"])), "vies_xgb": float(x["e_xgb"].mean())} for a, x in te.groupby("ano")}
    est = tab_skill(te, "faixa"); mes = tab_skill(te, "mes")
    est.to_csv(OUT / "skill_por_estacao.csv", index=False); mes.to_csv(OUT / "skill_por_mes.csv", index=False)
    pt = tab_skill(te, "ponto_id")
    lat = pd.read_csv(RAIZ / "data/processed/pontos.csv")[["ponto_id", "lat", "lon"]]
    pt = pt.merge(lat, on="ponto_id")
    pt.to_csv(OUT / "skill_por_ponto.csv", index=False)
    pt_ok = pt[pt["n"] >= 10]
    P = {"n_pontos_n>=10": int(len(pt_ok)), "pct_xgb_vence_clim": float((pt_ok["skill_xgb"] > 0).mean() * 100),
         "pct_xgb_vence_ingenua": float((pt_ok["skill_xgb"] > pt_ok["skill_ingenua"]).mean() * 100),
         "pct_ridge_vence_clim": float((pt_ok["skill_ridge"] > 0).mean() * 100),
         "skill_ponto_quantis": {str(q): float(pt_ok["skill_xgb"].quantile(q)) for q in (0, .1, .25, .5, .75, .9, 1)}}
    # regiao: tercis de latitude (proxy; nao e classificacao litoral/sertao). Subconjunto Ceara.
    ce = te.merge(lat, on="ponto_id"); ce = ce[ce["ponto_id"].str.endswith("_ce")].copy()
    ptlat = ce.drop_duplicates("ponto_id")["lat"]; qs = ptlat.quantile([1 / 3, 2 / 3]).to_numpy()
    ce["terc_lat"] = pd.cut(ce["lat"], [-99, qs[0], qs[1], 99], labels=["sul (lat baixa)", "meio", "norte (lat alta)"])
    reg = tab_skill(ce, "terc_lat"); reg.to_csv(OUT / "skill_por_regiao_lat.csv", index=False)
    R = {"cortes_lat": [float(q) for q in qs]}
    # cobertura
    C = {}
    for m_ in ("xgb", "aci"):
        for a in (80, 90):
            c = f"cob_{m_}_{a}"
            C[f"{m_}_{a}"] = {"global": float(te[c].mean()), "por_estacao": {int(k): float(v) for k, v in te.groupby("faixa")[c].mean().items()},
                              "por_mes": {int(k): float(v) for k, v in te.groupby("mes")[c].mean().items()},
                              "pior_composto": float(te.groupby("data")[c].mean().min()),
                              "ic95_composto": boot_mean(te, c, "data"), "ic95_ponto": boot_mean(te, c, "ponto_id"),
                              "estatico_global": float(te[f"{c}_est"].mean())}
    C["largura_media_meia_80"] = float(te["hw80"].mean()); C["largura_media_meia_90"] = float(te["hw90"].mean())
    C["alpha_inicial_2025"] = {f"{k[0]}_{k[1]}": v for k, v in estado0.items()}
    # horizonte
    H = [horizonte(d, cols, h, Y0) for h in (2, 3, 4)]
    h1 = {"h": 1, "n_teste": int(len(te)), "skill_xgboost": G["skill_xgb"], "skill_ridge": G["skill_ridge"], "skill_ingenua": G["skill_ingenua"],
          "ic_xgb": B["xgb"]["por_composto"]["ic95"], "ic_ridge": B["ridge"]["por_composto"]["ic95"], "ic_ing": B["ingenua"]["por_composto"]["ic95"]}
    res = {"cobertura_dados": cob, "global": G, "bootstrap_skill": B, "por_ano": por_ano, "pontos": P, "regiao": R, "faixa_aci": C, "horizonte": [h1] + H,
           "n_treino": int(len(tr)), "anos_treino": [int(tr["ano"].min()), int(tr["ano"].max())], "cols": cols}
    (OUT / "resultados.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))
    te[["ponto_id", "data", "slot", "faixa", "mes", "anomalia_ndvi", "p_xgb", "p_ridge", "anom_lag1", "e_xgb", "e_ridge", "e_ing", "hw80", "hw90",
        "cob_xgb_80", "cob_xgb_90"]].to_csv(OUT / "previsoes_2025plus.csv", index=False)
    print(json.dumps(res, ensure_ascii=False, indent=1, default=float))
    print(est.round(3).to_string()); print(mes.round(3).to_string()); print(reg.round(3).to_string())
    print('figuras: rodar figuras.py (matplotlib fora do .venv)')


def boot_mean(df, col, cluster, n_boot=5000, seed=5):
    s = df.groupby(cluster)[col].agg(["sum", "count"])
    rng = np.random.default_rng(seed); k = len(s)
    w = rng.multinomial(k, np.ones(k) / k, size=n_boot).astype(float)
    t = w @ s.to_numpy(); m = t[:, 0] / t[:, 1]
    return [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


if __name__ == "__main__":
    main()
