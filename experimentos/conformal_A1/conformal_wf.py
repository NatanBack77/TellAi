"""A1 (docs/15): cobertura do conformal abaixo da meta. Testa métodos de calibração por walk-forward.

Uso:
  python conformal_wf.py selecao   -> anos 2010-2021 (decide o método)
  python conformal_wf.py confirma  -> UMA vez, 2022-2024, só o método escolhido (argv[2]) e o atual (cell_split)

Para cada ano de teste Y: treino = anos < Y. Métodos:
  cell_split      : método atual (25% das células do treino calibram; modelo ajustado nas demais)
  temp_k3 / k6    : calibra nos K anos mais recentes antes de Y (todas as células); modelo ajustado nos anos anteriores
  temp_k3_estacao : idem, quantil por faixa de estação (Mondrian, 4 faixas de slot)
  temp_k3_ponto   : escore normalizado pelo desvio da anomalia do ponto (anos de modelo): intervalo = q * sigma_ponto
  temp_k3_ponto_estacao : sigma por (ponto, faixa); cai para sigma do ponto se faltar amostra
Métrica: cobertura agregada por ano, gap |cobertura - meta|, largura média, e cobertura condicional (por ponto e por estação).
Sem tuning no teste; N de variantes = 6 (para registro).
"""
import sys
from pathlib import Path
RAIZ = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, RAIZ)
import numpy as np
import pandas as pd
from src.modelos.entrada import carregar_config, carregar_entradas
from src.modelos.features import adicionar_anomalia, construir_dataset, nomes_features
from src.modelos.preditivo import ajustar_modelo, dividir_celulas_calibracao, quantil_conformal
from src.modelos.walkforward import extra_persistencia

OUT = Path(__file__).resolve().parent
cfg = carregar_config()
ALVOS = [0.8, 0.9]
METODOS = ["cell_split", "temp_k3", "temp_k6", "temp_k3_estacao", "temp_k3_ponto", "temp_k3_ponto_estacao"]


def preparar():
    ent = carregar_entradas(cfg)
    ent["umidade_solo"] = None
    df = construir_dataset(ent, cfg)
    cols = nomes_features(cfg, False)
    return df, cols


def tabela_ano(df, cols, Y):
    anos_tr = sorted(a for a in df["ano"].unique() if a < Y)
    d = adicionar_anomalia(df, anos_tr, cfg).sort_values(["ponto_id", "data"]).reset_index(drop=True)
    d, novas = extra_persistencia(d)
    cf = cols + novas
    d["_ok"] = d[cf].notna().all(axis=1) & d["anomalia_ndvi"].notna() & d["completo"]
    d["faixa"] = (d["slot"] // 6).clip(upper=3)
    return d[d["_ok"]].reset_index(drop=True), cf, anos_tr


def faixa_quantis(res_abs, grupos, alvo, minimo=30):
    """Quantil por grupo; grupo pequeno usa o quantil global."""
    glob = quantil_conformal(res_abs, 1 - alvo)
    out = {}
    for g in np.unique(grupos):
        r = res_abs[grupos == g]
        out[g] = quantil_conformal(r, 1 - alvo) if len(r) >= minimo else glob
    return out, glob


def metodo(nome, d, cf, anos_tr, Y):
    te = d[d["ano"] == Y]
    tr = d[d["ano"] < Y]
    y_te = te["anomalia_ndvi"].to_numpy()
    res = {}
    if nome == "cell_split":
        cel_tr, cel_cal = dividir_celulas_calibracao(tr["celula_power"].unique(), 0.25, cfg["semente"])
        prop, cal = tr[tr["celula_power"].isin(cel_tr)], tr[tr["celula_power"].isin(cel_cal)]
    else:
        k = 6 if nome == "temp_k6" else 3
        cut = anos_tr[-k]
        prop, cal = tr[tr["ano"] < cut], tr[tr["ano"] >= cut]
    mod, _ = ajustar_modelo("ridge", prop[cf], prop["anomalia_ndvi"].to_numpy(), prop["celula_power"].to_numpy(), cfg)
    r_cal = np.abs(cal["anomalia_ndvi"].to_numpy() - mod.predict(cal[cf]))
    pred = mod.predict(te[cf])
    err = np.abs(y_te - pred)
    for alvo in ALVOS:
        if nome in ("cell_split", "temp_k3", "temp_k6"):
            q = np.full(len(te), quantil_conformal(r_cal, 1 - alvo))
        elif nome == "temp_k3_estacao":
            qs, glob = faixa_quantis(r_cal, cal["faixa"].to_numpy(), alvo)
            q = te["faixa"].map(lambda f: qs.get(f, glob)).to_numpy()
        else:
            sp = prop.groupby("ponto_id")["anomalia_ndvi"].std()
            sg = float(prop["anomalia_ndvi"].std())
            if nome == "temp_k3_ponto":
                s_cal = cal["ponto_id"].map(sp).fillna(sg).to_numpy()
                s_te = te["ponto_id"].map(sp).fillna(sg).to_numpy()
            else:
                spf = prop.groupby(["ponto_id", "faixa"])["anomalia_ndvi"].agg(["std", "count"])
                spf = spf[spf["count"] >= 30]["std"]

                def sigma(df_):
                    ix = pd.MultiIndex.from_arrays([df_["ponto_id"], df_["faixa"]])
                    v = pd.Series(spf.reindex(ix).to_numpy(), index=df_.index)
                    return v.fillna(df_["ponto_id"].map(sp)).fillna(sg).to_numpy()
                s_cal, s_te = sigma(cal), sigma(te)
            qn = quantil_conformal(r_cal / np.maximum(s_cal, 1e-9), 1 - alvo)
            q = qn * s_te
        res[alvo] = (err <= q, 2 * q)
    return te, res


def rodar(anos, metodos):
    df, cols = preparar()
    linhas, cond = [], []
    for Y in anos:
        d, cf, anos_tr = tabela_ano(df, cols, Y)
        for m in metodos:
            te, res = metodo(m, d, cf, anos_tr, Y)
            for alvo, (cob, larg) in res.items():
                linhas.append({"ano": Y, "metodo": m, "alvo": alvo, "n": len(te), "cobertura": float(cob.mean()),
                               "largura": float(np.mean(larg))})
                t = te[["ponto_id", "faixa"]].assign(cob=cob)
                for chave in ("ponto_id", "faixa"):
                    for g, v in t.groupby(chave)["cob"].mean().items():
                        cond.append({"ano": Y, "metodo": m, "alvo": alvo, "chave": chave, "grupo": g, "cobertura": float(v)})
    return pd.DataFrame(linhas), pd.DataFrame(cond)


def resumo(lin, cond):
    linhas = []
    for (m, alvo), x in lin.groupby(["metodo", "alvo"]):
        linhas.append({"metodo": m, "alvo": alvo, "cobertura_media": np.average(x["cobertura"], weights=x["n"]),
                       "gap_abs_medio": float(np.mean(np.abs(x["cobertura"] - alvo))),
                       "anos_perto_meta": float((x["cobertura"] >= alvo - 0.02).mean()),
                       "largura_media": float(x["largura"].mean())})
    g = pd.DataFrame(linhas)
    for chave, nome in (("ponto_id", "sd_cob_ponto"), ("faixa", "min_cob_estacao")):
        c = cond[cond["chave"] == chave].groupby(["metodo", "alvo", "grupo"])["cobertura"].mean().reset_index()
        f = (c.groupby(["metodo", "alvo"])["cobertura"].std() if chave == "ponto_id"
             else c.groupby(["metodo", "alvo"])["cobertura"].min()).rename(nome).reset_index()
        g = g.merge(f, on=["metodo", "alvo"])
    return g


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "selecao"
    pd.set_option("display.width", 220, "display.max_columns", 30)
    if modo == "selecao":
        lin, cond = rodar(list(range(2010, 2022)), METODOS)
        lin.to_csv(OUT / "selecao_linhas.csv", index=False)
        cond.to_csv(OUT / "selecao_condicional.csv", index=False)
        r = resumo(lin, cond)
        r.to_csv(OUT / "selecao_resumo.csv", index=False)
        print(r.round(4).to_string(index=False))
    else:
        escolhido = sys.argv[2]
        lin, cond = rodar([2022, 2023, 2024], ["cell_split"] + escolhido.split(","))
        r = resumo(lin, cond)
        r.to_csv(OUT / "confirmacao_resumo.csv", index=False)
        print(r.round(4).to_string(index=False))
