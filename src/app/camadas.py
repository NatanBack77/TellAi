"""Camadas do mapa (A5): um indicador por ponto (195), com ano opcional. Sem Streamlit; testável.

Tudo vem de arquivo local; ponto sem dado fica CINZA (lacuna), nunca recebe valor inventado:
- solo nu: sem ano = nº de quinzenas em que o campo costuma ficar nu (em pelo menos metade dos anos), lido do diagnóstico;
  com ano = fração das quinzenas daquele ano com NDVI abaixo do percentil 20 do próprio local (mesma regra do diagnóstico;
  data/processed/diagnostico/anomalias.parquet). Exige >= MIN_QUINZENAS_ANO quinzenas com dado no ano.
- declive: declive médio em 1 km (SRTM; data/processed/terreno.parquet). Não muda por ano.
- variabilidade da quadra: sem ano = coeficiente de variação da chuva de fev-mai (desvio/média); com ano = chuva da quadra daquele ano
  em % da média do local (src/app/quadra.py). A chuva vem de células de ~50 km: locais vizinhos repetem o mesmo valor.
- risco de erosão: soma de notas de src/culturas/risco_solo.py (módulo opcional: ImportError => lacuna). Ponto sem os 4 componentes fica cinza.
"""
from __future__ import annotations

import functools
import importlib

import numpy as np
import pandas as pd

from src.app import mvp as M
from src.app import quadra as Q

MIN_QUINZENAS_ANO = 12          # um ano só entra na camada de solo nu se tiver ao menos metade das 24 quinzenas com NDVI
PERCENTIL_SOLO_NU = 20          # igual ao config.yaml (solo_nu.percentil) usado pelo diagnóstico
COR_SEM_DADO = [165, 165, 165, 110]
RAMPA = [(255, 247, 188), (254, 196, 79), (236, 112, 20), (153, 52, 4)]   # amarelo claro -> marrom escuro (ColorBrewer YlOrBr)

CAMADAS = {
    "solo_nu": {"rotulo": "Solo nu (campo sem verdor)", "tem_ano": True},
    "declive": {"rotulo": "Declive do terreno", "tem_ano": False},
    "quadra": {"rotulo": "Variabilidade da chuva da quadra (fev–mai)", "tem_ano": True},
    "erosao": {"rotulo": "Risco de erosão", "tem_ano": False},
}


def _modulo_erosao():
    """Módulo opcional do risco de erosão (src/culturas/risco_solo.py). Ausente = camada vira lacuna."""
    try:
        return importlib.import_module("src.culturas.risco_solo")
    except ImportError:
        return None


def erosao_disponivel() -> bool:
    m = _modulo_erosao()
    return m is not None and callable(getattr(m, "tabela_pontos_cache", None)) and callable(getattr(m, "risco_do_ponto", None))


@functools.lru_cache(maxsize=1)
def _ndvi_quinzenas() -> pd.DataFrame | None:
    arq = M.dir_diagnostico() / "anomalias.parquet"
    if not arq.is_file():
        return None
    a = pd.read_parquet(arq, columns=["ponto_id", "variavel", "ano", "quinzena", "valor"])
    a = a[(a["variavel"] == "ndvi") & a["valor"].notna()].copy()
    lim = a.groupby("ponto_id")["valor"].quantile(PERCENTIL_SOLO_NU / 100)
    a["nu"] = a["valor"] < a["ponto_id"].map(lim)
    return a


@functools.lru_cache(maxsize=1)
def anos_disponiveis() -> list[int]:
    a = _ndvi_quinzenas()
    anos = set() if a is None else set(int(x) for x in a["ano"].unique())
    q = Q._chuva()
    anos |= set(int(x) for x in q["ano"].unique())
    return sorted(anos)


def _frac_solo_nu_ano(ano: int) -> pd.Series:
    a = _ndvi_quinzenas()
    if a is None:
        return pd.Series(dtype=float)
    g = a[a["ano"] == ano].groupby("ponto_id")["nu"].agg(["mean", "count"])
    return g["mean"].where(g["count"] >= MIN_QUINZENAS_ANO)


def _solo_nu(ano: int | None) -> tuple[pd.Series, str, str]:
    if ano is None:
        d = M.carregar_diagnosticos()
        s = pd.Series({k: float(len((r.get("solo_nu") or {}).get("quinzenas_tipicas") or []))
                       for k, r in d.items() if r.get("solo_nu")})
        return s, "quinzenas", ("Número de quinzenas (de 24) em que o campo costuma ficar nu, isto é, com NDVI abaixo do percentil 20 do "
                                "próprio local em pelo menos metade dos anos (diagnóstico). É relativo a cada local.")
    return (_frac_solo_nu_ano(ano) * 100, "%", f"Em {ano}, % das quinzenas com NDVI abaixo do percentil 20 do próprio local "
            f"(só vale se o ano tem {MIN_QUINZENAS_ANO}+ quinzenas com dado). É relativo a cada local, não um valor agronômico.")


def _declive() -> tuple[pd.Series, str, str]:
    arq = M.dir_dados() / "terreno.parquet"
    if not arq.is_file():
        return pd.Series(dtype=float), "%", "arquivo terreno.parquet ausente"
    t = pd.read_parquet(arq).set_index("ponto_id")["declive_medio_1km_pct"]
    return t, "%", ("Declive médio em 1 km em volta do ponto (SRTM, ~30 m). É indicador de terreno, não medida de erosão; "
                    "não muda de ano para ano.")


def _quadra(ano: int | None) -> tuple[pd.Series, str, str]:
    q = Q._chuva()
    if ano is None:
        g = q.groupby("ponto_id")["fma_mm"].agg(["mean", "std", "count"])
        s = (g["std"] / g["mean"]).where(g["count"] >= 10)
        return s, "cv", ("Coeficiente de variação da chuva de fev-mai (desvio ÷ média; maior = quadra mais irregular de um ano para outro). "
                         "Chuva de células de ~50 km: locais vizinhos repetem o valor.")
    x = q[q["ano"] == ano].set_index("ponto_id")["fma_mm"]
    m = q.groupby("ponto_id")["fma_mm"].mean()
    n = q.groupby("ponto_id")["fma_mm"].count()
    s = (100 * x / m.reindex(x.index)).where(n.reindex(x.index) >= 10)
    return s, "% da média", (f"Chuva de fev-mai de {ano} em % da média do próprio local (100 = média; abaixo de 80 = quadra seca pela "
                              "regra do app). Chuva de células de ~50 km.")


def _erosao() -> tuple[pd.Series, str, str]:
    if not erosao_disponivel():
        return pd.Series(dtype=float), "", "módulo de risco de erosão (src/culturas/risco_solo.py) não disponível"
    m = _modulo_erosao()
    tab = m.tabela_pontos_cache()
    ids = list(M.carregar_pontos()["ponto_id"])
    res = {i: m.risco_do_ponto(i, tab) for i in ids}
    # só entra o ponto com os 4 componentes (classe definida); soma parcial não é comparável e fica como lacuna
    s = pd.Series({i: float(r["soma_notas"]) for i, r in res.items() if r.get("classe") is not None})
    aviso = next((r["aviso"] for r in res.values() if r.get("aviso")), "")
    return s, "pontos de 0 a 8", ("Indicador de risco de erosão: soma de 4 notas (declive, textura, carbono orgânico do solo e dias de chuva "
                                  "erosiva; mais alto = mais risco). As notas e cortes são suposições do projeto. " + aviso)


@functools.lru_cache(maxsize=64)
def valores(camada: str, ano: int | None) -> dict:
    """{'serie': Series por ponto_id (NaN = lacuna), 'unidade', 'nota', 'disponivel', 'ano_usado'} para a camada e o ano."""
    if camada not in CAMADAS:
        raise ValueError(f"camada desconhecida: {camada}")
    ano_usado = ano if CAMADAS[camada]["tem_ano"] else None
    try:
        s, unid, nota = {"solo_nu": lambda: _solo_nu(ano_usado), "declive": _declive, "quadra": lambda: _quadra(ano_usado),
                         "erosao": _erosao}[camada]()
    except Exception as e:  # noqa: BLE001 - camada com problema vira lacuna, o mapa não cai
        return {"serie": pd.Series(dtype=float), "unidade": "", "nota": f"camada indisponível ({e.__class__.__name__}: {e})",
                "disponivel": False, "ano_usado": ano_usado}
    s = pd.to_numeric(s, errors="coerce")
    return {"serie": s, "unidade": unid, "nota": nota, "disponivel": bool(s.notna().any()), "ano_usado": ano_usado}


def cores(serie: pd.Series, ids: list[str]) -> tuple[list[list[int]], dict]:
    """Cor RGBA por ponto (rampa clara -> escura; corte nos percentis 5 e 95 para outlier não achatar o mapa). Sem dado = cinza."""
    v = serie.reindex(ids)
    ok = v.dropna()
    if ok.empty:
        return [list(COR_SEM_DADO) for _ in ids], {"min": None, "max": None, "n_sem_dado": len(ids)}
    lo, hi = float(np.percentile(ok, 5)), float(np.percentile(ok, 95))
    out = []
    for x in v:
        if pd.isna(x):
            out.append(list(COR_SEM_DADO))
            continue
        f = 0.5 if hi == lo else min(1.0, max(0.0, (float(x) - lo) / (hi - lo)))
        pos = f * (len(RAMPA) - 1)
        i = min(int(pos), len(RAMPA) - 2)
        t = pos - i
        rgb = [round(a + (b - a) * t) for a, b in zip(RAMPA[i], RAMPA[i + 1])]
        out.append(rgb + [215])
    return out, {"min": float(ok.min()), "max": float(ok.max()), "p5": lo, "p95": hi, "n_sem_dado": int(v.isna().sum())}
