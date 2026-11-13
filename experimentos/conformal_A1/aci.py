"""Conformal adaptativo (ACI, Gibbs e Candès 2021, NeurIPS; arXiv 2106.00170) contra o deslocamento por ano da cobertura.

A atualização é online: alpha_{t+1} = alpha_t + gamma * (alpha - err_t), com err_t = fração de pontos NÃO cobertos no composto t.
Isso ajusta o nível usado quando um ano inteiro (seco/úmido) desloca os resíduos de todos os pontos juntos.
Calibração: resíduos dos 3 anos anteriores (modelo ajustado antes disso), como `temp_k3` de conformal_wf.py. Gamma FIXO a priori.

Uso:  python aci.py selecao   |   python aci.py confirma   (UMA vez; 2022-2024, o alpha continua do fim de 2021)
Métodos (N=6 incluindo as referências): temp_k3, temp_k3_estacao, aci_g01, aci_g05, aci_estacao_g01, aci_estacao_g05.
"""
import sys
from pathlib import Path
RAIZ = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, RAIZ)
import numpy as np
import pandas as pd
import conformal_wf as cw
from src.modelos.preditivo import ajustar_modelo, quantil_conformal

OUT = Path(__file__).resolve().parent
cfg = cw.cfg
ALVOS = (0.8, 0.9)
GAMMAS = {"g01": 0.01, "g05": 0.05}


def q_nivel(r_sorted, alpha):
    """Quantil empírico de nível 1-alpha com correção de amostra finita; alpha<=0 => cobre tudo; alpha>=1 => 0."""
    n = len(r_sorted)
    if alpha <= 0:
        return np.inf
    if alpha >= 1:
        return 0.0
    k = int(np.ceil((n + 1) * (1 - alpha)))
    return np.inf if k > n else float(r_sorted[k - 1])


def rodar(anos, estado):
    df, cols = cw.preparar()
    linhas = []
    for Y in anos:
        d, cf, anos_tr = cw.tabela_ano(df, cols, Y)
        tr, te = d[d["ano"] < Y], d[d["ano"] == Y].copy()
        cut = anos_tr[-3]
        prop, cal = tr[tr["ano"] < cut], tr[tr["ano"] >= cut]
        mod, _ = ajustar_modelo("ridge", prop[cf], prop["anomalia_ndvi"].to_numpy(), prop["celula_power"].to_numpy(), cfg)
        r_cal = np.abs(cal["anomalia_ndvi"].to_numpy() - mod.predict(cal[cf]))
        r_cal_s = np.sort(r_cal)
        r_por_faixa = {f: np.sort(r_cal[(cal["faixa"] == f).to_numpy()]) for f in range(4)}
        te["err"] = np.abs(te["anomalia_ndvi"].to_numpy() - mod.predict(te[cf]))
        for alvo in ALVOS:
            a0 = 1 - alvo
            # referências sem adaptação
            q = quantil_conformal(r_cal, a0)
            te["c_temp_k3"] = te["err"] <= q
            qf = {f: quantil_conformal(r_por_faixa[f], a0) for f in range(4)}
            te["c_temp_k3_estacao"] = te["err"] <= te["faixa"].map(qf)
            # ACI: percorre os compostos em ordem de data; alpha (global ou por faixa) segue entre anos
            for gnome, g in GAMMAS.items():
                cg, ce = np.zeros(len(te), bool), np.zeros(len(te), bool)
                for t, ix in te.groupby("data").indices.items():
                    sub = te.iloc[ix]
                    st = estado.setdefault((alvo, gnome, "g"), a0)
                    cov = sub["err"].to_numpy() <= q_nivel(r_cal_s, st)
                    cg[ix] = cov
                    estado[(alvo, gnome, "g")] = st + g * (a0 - (1 - cov.mean()))
                    covs = np.zeros(len(sub), bool)
                    for f, jx in sub.groupby("faixa").indices.items():
                        key = (alvo, gnome, f"f{f}")
                        sf = estado.setdefault(key, a0)
                        c = sub["err"].to_numpy()[jx] <= q_nivel(r_por_faixa[f], sf)
                        covs[jx] = c
                        estado[key] = sf + g * (a0 - (1 - c.mean()))
                    ce[ix] = covs
                te[f"c_aci_{gnome}"], te[f"c_aci_estacao_{gnome}"] = cg, ce
            for m in [c for c in te.columns if c.startswith("c_")]:
                for f, x in te.groupby("faixa"):
                    linhas.append({"ano": Y, "alvo": alvo, "metodo": m[2:], "faixa": f, "n": len(x), "cob": float(x[m].mean())})
        print("ano", Y, flush=True)
    return pd.DataFrame(linhas)


def resumo(l):
    a = l.groupby(["metodo", "alvo", "ano"]).apply(lambda x: pd.Series({"cob": np.average(x["cob"], weights=x["n"])}), include_groups=False).reset_index()
    out = []
    for (m, alvo), x in a.groupby(["metodo", "alvo"]):
        pf = l[(l["metodo"] == m) & (l["alvo"] == alvo)].groupby("faixa").apply(lambda z: np.average(z["cob"], weights=z["n"]), include_groups=False)
        out.append({"metodo": m, "alvo": alvo, "cob_media": x["cob"].mean(), "gap_abs": float(np.mean(np.abs(x["cob"] - alvo))),
                    "pior_ano": x["cob"].min(), "pior_estacao": pf.min()})
    return pd.DataFrame(out)


if __name__ == "__main__":
    pd.set_option("display.width", 200, "display.max_columns", 20)
    if sys.argv[1] == "selecao":
        l = rodar(range(2010, 2022), {})
        l.to_csv(OUT / "aci_selecao_linhas.csv", index=False)
        r = resumo(l); r.to_csv(OUT / "aci_selecao_resumo.csv", index=False)
    else:
        estado = {}
        rodar(range(2010, 2022), estado)           # só para levar o alpha até o fim de 2021 (não é avaliação)
        l = rodar([2022, 2023, 2024], estado)
        l.to_csv(OUT / "aci_confirmacao_linhas.csv", index=False)
        r = resumo(l); r.to_csv(OUT / "aci_confirmacao_resumo.csv", index=False)
    print(r.round(4).sort_values(["alvo", "gap_abs"]).to_string(index=False))
