"""Indicador da chuva da quadra chuvosa (fevereiro a maio) e sua relação com o rendimento municipal (IBGE/PAM). Sem Streamlit; testável.

Por quê: nos dados do Ceará (experimentos/novas_fontes/RESULTADO.md) a chuva de fev-mai explica mais da variação do rendimento do que o NDVI
(milho: R² 0,31 contra 0,10). Este módulo mostra, para o local, quão variável é a quadra e o que isso significou para o rendimento nos dados do IBGE.
É ASSOCIAÇÃO histórica (não causa) e não é previsão da próxima quadra: a previsão sazonal oficial é da FUNCEME.
O rendimento do PAM é estimado por agentes do IBGE (não é medido por parcela) e há no máximo 9 anos por município (2015-2023).
"""
from __future__ import annotations

import functools

import numpy as np
import pandas as pd

from src.modelos.entrada import RAIZ

PROD = {"milho": "Milho (em grão)", "feijao": "Feijão (em grão)", "mandioca": "Mandioca"}
LIMIAR_SECO = 0.8          # quadra abaixo de 80% da média do próprio local = "quadra seca"
LIMIAR_UMIDO = 1.2


@functools.lru_cache(maxsize=1)
def _chuva() -> pd.DataFrame:
    c = pd.read_parquet(RAIZ / "data/processed/clima_diario.parquet", columns=["ponto_id", "data", "chuva_mm"])
    c["ano"], c["mes"] = c["data"].dt.year, c["data"].dt.month
    q = c[c["mes"].between(2, 5)].groupby(["ponto_id", "ano"])["chuva_mm"].agg(["sum", "count"]).reset_index()
    q = q[q["count"] >= 100]                                 # quadra com dados em quase todos os dias (fev-mai = 120 dias)
    return q.rename(columns={"sum": "fma_mm"}).drop(columns="count")


def serie_quadra(ponto_id: str) -> pd.DataFrame:
    return _chuva()[_chuva()["ponto_id"] == ponto_id][["ano", "fma_mm"]].reset_index(drop=True)


def indicador_quadra(ponto_id: str) -> dict:
    s = serie_quadra(ponto_id)
    if len(s) < 10:
        return {"lacuna": f"menos de 10 quadras completas com dado para {ponto_id}; indicador não calculado."}
    m = float(s["fma_mm"].mean())
    secos = s[s["fma_mm"] < LIMIAR_SECO * m]
    umidos = s[s["fma_mm"] > LIMIAR_UMIDO * m]
    return {"n_anos": int(len(s)), "anos": [int(s["ano"].min()), int(s["ano"].max())], "media_mm": m, "desvio_mm": float(s["fma_mm"].std()),
            "cv": float(s["fma_mm"].std() / m), "n_secos": int(len(secos)), "anos_secos": [int(a) for a in secos["ano"]],
            "n_umidos": int(len(umidos)), "pior_ano": int(s.loc[s["fma_mm"].idxmin(), "ano"]), "pior_mm": float(s["fma_mm"].min()),
            "melhor_ano": int(s.loc[s["fma_mm"].idxmax(), "ano"]), "melhor_mm": float(s["fma_mm"].max()),
            "limiar_seco_mm": LIMIAR_SECO * m, "serie": s}


@functools.lru_cache(maxsize=1)
def efeito_rendimento() -> dict:
    """Por cultura, no conjunto dos municípios do CE com PAM e clima: variação do rendimento (%) em anos secos e úmidos."""
    arq = RAIZ / "data/processed/pam_ce.parquet"
    if not arq.exists():
        return {}
    pam = pd.read_parquet(arq)
    pts = pd.read_csv(RAIZ / "data/processed/pontos.csv").dropna(subset=["ibge"])
    pts["ibge"] = pts["ibge"].astype(int)
    q = _chuva().merge(pts[["ponto_id", "ibge"]], on="ponto_id")
    rend = pam[(pam["variavel"] == "rendimento_medio") & (pam["valor"] > 0)]
    out = {}
    for k, prod in PROD.items():
        x = rend[rend["produto"] == prod].merge(q, on=["ibge", "ano"])
        x = x[x.groupby("ibge")["valor"].transform("count") >= 5].copy()
        if x["ibge"].nunique() < 30:
            continue
        mfma = x.groupby("ibge")["fma_mm"].transform("mean")
        x["rend_anom"] = 100 * (x["valor"] / x.groupby("ibge")["valor"].transform("mean") - 1)
        seco, umido = x[x["fma_mm"] < LIMIAR_SECO * mfma], x[x["fma_mm"] > LIMIAR_UMIDO * mfma]
        r = float(np.corrcoef(x["fma_mm"] - mfma, x["rend_anom"])[0, 1])
        out[k] = {"produto": prod, "n_obs": int(len(x)), "n_municipios": int(x["ibge"].nunique()), "anos": [int(x["ano"].min()), int(x["ano"].max())],
                  "rend_ano_seco_pct": float(seco["rend_anom"].mean()), "n_secos": int(len(seco)),
                  "rend_ano_umido_pct": float(umido["rend_anom"].mean()), "n_umidos": int(len(umido)), "correlacao": r, "r2": r * r}
    return out
