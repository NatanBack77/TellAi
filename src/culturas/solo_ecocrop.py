"""Critério OPCIONAL de SOLO (pH e textura) da viabilidade: `Parametros.solo_modo='ecocrop'` (padrão 'sem' = nada muda).

Faixas: SOMENTE as que o espelho do EcoCrop traz (data/culturas/solo_staging.csv, extraído por
experimentos/calendario_solo/extrair_solo_staging.py): pH (PHMIN, PHOPMN, PHOPMX, PHMAX) e textura (TEXT = ótima, TEXTR = faixa).
Profundidade, fertilidade, salinidade e drenagem existem na base mas o projeto NÃO tem dado do local para compará-las: ficam como LACUNA (não pontuam).
Solo do local: SoilGrids (data/processed/solo.parquet), média 0-30 cm ponderada pela espessura (`risco_solo.solo_de_linha`). É mapa global, NÃO análise.

SUPOSIÇÕES declaradas (sem fonte lida): (1) arenoso (<15% argila) = 'light', médio (15-35%) = 'medium', argiloso (>35%) = 'heavy' (o CSV do EcoCrop
não define light/medium/heavy); (2) textura dentro da faixa absoluta mas fora da ótima = nota 0,5; (3) nota de solo = mínimo(pH, textura), aplicada como TETO
às notas de temperatura e chuva (mesma lógica de fator limitante do motor).
"""
from __future__ import annotations

import functools

import numpy as np
import pandas as pd

from src.modelos.entrada import RAIZ

CAMINHO_STAGING = RAIZ / "data/culturas/solo_staging.csv"
CAMINHO_SOLO = RAIZ / "data/processed/solo.parquet"
AVISO = "solo estimado de mapa global (250 m, mediana de ~2 km), não análise de solo: confirme com o técnico."
CLASSE_TEXTURA = {"arenoso": "light", "médio": "medium", "argiloso": "heavy"}
NOTA_FORA_DA_OTIMA = 0.5       # SUPOSIÇÃO
FATORES_SEM_DADO = ("profundidade", "fertilidade", "salinidade", "drenagem")


@functools.lru_cache(maxsize=1)
def _staging() -> dict:
    if not CAMINHO_STAGING.exists():
        return {}
    d = pd.read_csv(CAMINHO_STAGING, dtype=str, keep_default_na=False)
    d = d[d["status"] == "verificado"]
    out: dict = {}
    for r in d.itertuples():
        out.setdefault(r.cultura_id, {})[r.atributo] = r.valor
    return out


@functools.lru_cache(maxsize=1)
def _solo_df():
    return pd.read_parquet(CAMINHO_SOLO).set_index("ponto_id") if CAMINHO_SOLO.exists() else None


def solo_do_ponto(ponto_id: str) -> dict | None:
    """Solo 0-30 cm do ponto (SoilGrids) ou None (lacuna)."""
    from .risco_solo import solo_de_linha
    d = _solo_df()
    if d is None or ponto_id not in d.index or pd.isna(d.loc[ponto_id].get("clay_0-5cm")):
        return None
    s = solo_de_linha(d.loc[ponto_id])
    a = s["argila_pct"]
    s["textura"] = "arenoso" if a < 15 else ("argiloso" if a > 35 else "médio")
    return s


def _conj(txt: str) -> set:
    return {x.strip() for x in txt.split(",") if x.strip()}


def _trap(x, mn, omn, omx, mx) -> float:
    if x <= mn or x >= mx:
        return 0.0
    if x < omn:
        return (x - mn) / (omn - mn)
    if x > omx:
        return (mx - x) / (mx - omx)
    return 1.0


def nota_solo(cultura_id: str, solo: dict | None) -> dict:
    """{'aplicado', 'nota' (0-1 ou None), 'ph': {...}, 'textura': {...}, 'sem_dado': [...], 'avisos': [...]}. Nunca inventa faixa."""
    st = _staging().get(cultura_id)
    av = [AVISO]
    if solo is None:
        return {"aplicado": False, "nota": None, "motivo": "ponto sem dado de solo (SoilGrids): critério não aplicado", "avisos": av}
    if not st:
        return {"aplicado": False, "nota": None, "motivo": "cultura sem faixa de solo no staging", "avisos": av}
    fr = solo.get("fracao_pixels_validos")
    if fr is not None and fr < 0.5:
        av.append(f"poucos pixels do mapa de solo com dado em volta do ponto ({fr:.0%}): estimativa de baixa confiança")
    elif not solo.get("pixel_central_valido", True):
        av.append("pixel central do mapa de solo sem dado: valor vem dos vizinhos")
    notas, det = [], {}
    try:
        f = [float(st[k]) for k in ("ph_min_abs", "ph_otimo_min", "ph_otimo_max", "ph_max_abs")]
        n = _trap(solo["ph_agua"], *f)
        notas.append(n)
        det["ph"] = {"valor_local": round(solo["ph_agua"], 2), "faixa": f, "nota": n}
    except (KeyError, ValueError):
        det["ph"] = None
    cl = CLASSE_TEXTURA[solo["textura"]]
    if st.get("textura_otima") or st.get("textura_faixa"):
        otima, faixa = _conj(st.get("textura_otima", "")), _conj(st.get("textura_faixa", "")) | _conj(st.get("textura_otima", ""))
        n = 1.0 if cl in otima else (NOTA_FORA_DA_OTIMA if (cl in faixa or "wide" in faixa) else 0.0)
        notas.append(n)
        det["textura"] = {"classe_local": solo["textura"], "classe_ecocrop": cl, "otima": sorted(otima), "faixa": sorted(faixa), "nota": n}
    else:
        det["textura"] = None
    sem = [k for k in FATORES_SEM_DADO] + ([k for k in ("ph", "textura") if det.get(k) is None])
    return {"aplicado": bool(notas), "nota": float(min(notas)) if notas else None, **det, "sem_dado": sem, "avisos": av, "motivo": None}
