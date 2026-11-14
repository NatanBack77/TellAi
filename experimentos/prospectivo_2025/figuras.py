"""Figuras e CSV do retroteste a partir de previsoes_2025plus.csv e skill_por_ponto.csv (rodar com python que tenha matplotlib)."""
from pathlib import Path
import numpy as np, pandas as pd
OUT = Path(__file__).resolve().parent

def retroteste(te, pt):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # Regra declarada ANTES de ver 2025+: entre os pontos _ce, ordenar por latitude e escolher os de quantil 0, .25, .5, .75, 1 (posicao round(q*(n-1))); + o pior skill_xgb (n>=10).
    cep = pt[pt["ponto_id"].str.endswith("_ce")].sort_values(["lat", "ponto_id"]).reset_index(drop=True)
    idx = [int(round(q * (len(cep) - 1))) for q in (0, .25, .5, .75, 1)]
    esc = cep.loc[idx, "ponto_id"].tolist()
    pior = cep[cep["n"] >= 10].sort_values("skill_xgb").iloc[0]["ponto_id"]
    sel = [(p, "quantil de latitude") for p in esc] + ([(pior, "PIOR skill (n>=10)")] if pior not in esc else [(pior, "quantil de latitude E pior skill")])
    fig, axs = plt.subplots(len(sel), 1, figsize=(11, 3 * len(sel)), sharex=True)
    linhas = []
    for ax, (p, motivo) in zip(axs, sel):
        x = te[te["ponto_id"] == p].sort_values("data")
        ax.fill_between(x["data"], x["p_xgb"] - x["hw80"], x["p_xgb"] + x["hw80"], color="tab:blue", alpha=.15, label="faixa ACI 80%")
        ax.plot(x["data"], x["anomalia_ndvi"], "k.-", label="observada"); ax.plot(x["data"], x["p_xgb"], "o-", color="tab:blue", ms=3, label="prevista (1 composto)")
        ax.axhline(0, color="gray", lw=.5)
        r = pt[pt["ponto_id"] == p].iloc[0]
        ax.set_title(f"{p} (lat {r['lat']:.2f}) [{motivo}]  skill XGB vs clim = {r['skill_xgb']:+.2f}, ingenua = {r['skill_ingenua']:+.2f}, n={int(r['n'])}", fontsize=9)
        ax.set_ylabel("anomalia NDVI")
        linhas.append(x.assign(motivo=motivo))
    axs[0].legend(fontsize=7, ncol=3); fig.tight_layout(); fig.savefig(OUT / "retroteste_5_municipios.png", dpi=110); plt.close(fig)
    pd.concat(linhas)[["ponto_id", "motivo", "data", "anomalia_ndvi", "p_xgb", "p_ridge", "anom_lag1", "hw80", "hw90", "e_xgb"]].rename(
        columns={"anomalia_ndvi": "anomalia_observada", "p_xgb": "anomalia_prevista_xgb", "p_ridge": "anomalia_prevista_ridge",
                 "anom_lag1": "ingenua_ultima_anomalia"}).to_csv(OUT / "retroteste_5_municipios.csv", index=False)
    pd.DataFrame(sel, columns=["ponto_id", "motivo"]).to_csv(OUT / "retroteste_escolhidos.csv", index=False)
    # erro por composto
    pdta = pd.read_csv(OUT / "erro_por_composto.csv", parse_dates=["data"])
    fig, ax = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    ax[0].plot(pdta["data"], pdta["obs"], "k.-", label="anomalia observada (media dos pontos)"); ax[0].plot(pdta["data"], pdta["pred"], "b.-", label="prevista (media)"); ax[0].axhline(0, color="gray", lw=.5); ax[0].legend(fontsize=8)
    ax[1].bar(pdta["data"], pdta["skill_xgb"], width=10, color="tab:blue"); ax[1].axhline(0, color="k", lw=.5); ax[1].set_ylabel("skill XGB vs clim (por composto)")
    fig.tight_layout(); fig.savefig(OUT / "erro_por_composto.png", dpi=110); plt.close(fig)



if __name__ == "__main__":
    te = pd.read_csv(OUT / "previsoes_2025plus.csv", parse_dates=["data"])
    pt = pd.read_csv(OUT / "skill_por_ponto.csv")
    retroteste(te, pt)
