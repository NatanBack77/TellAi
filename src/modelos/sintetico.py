"""Gerador de dados SINTÉTICOS aleatórios, só para testar formato e fluxo.

Arquivos levam 'SINTETICO' no nome. Métricas obtidas com eles NUNCA são resultado do projeto.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def gerar_sinteticos(
    destino: str | Path,
    n_celulas: int = 6,
    pontos_por_celula: int = 2,
    ano_ini: int = 2010,
    ano_fim: int = 2023,
    semente: int = 42,
    com_umidade: bool = True,
) -> dict[str, Path]:
    rng = np.random.default_rng(semente)
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)

    dias = pd.date_range(f"{ano_ini}-01-01", f"{ano_fim}-12-31", freq="D")
    doy = dias.day_of_year.to_numpy()
    sazonal = np.sin(2 * np.pi * (doy - 30) / 365.25)  # pico chuvoso no início do ano

    clima, ndvi, umid = [], [], []
    ponto = 0
    for c in range(n_celulas):
        # clima compartilhado por célula (como o POWER ~50 km)
        prob = np.clip(0.25 + 0.2 * sazonal, 0.02, 0.9)
        chuva = np.where(rng.random(len(dias)) < prob, rng.gamma(1.2, 8.0, len(dias)), 0.0)
        tmax = 31 + 3 * np.cos(2 * np.pi * (doy - 300) / 365.25) + rng.normal(0, 1, len(dias))
        tmin = tmax - 9 + rng.normal(0, 0.8, len(dias))
        rad = 20 + 4 * np.cos(2 * np.pi * (doy - 340) / 365.25) + rng.normal(0, 1, len(dias))
        for _ in range(pontos_por_celula):
            pid = f"P{ponto:03d}"
            ponto += 1
            clima.append(pd.DataFrame({
                "ponto_id": pid, "celula_power": f"C{c:02d}", "data": dias,
                "chuva_mm": chuva, "tmax_c": tmax, "tmin_c": tmin, "radiacao": rad,
            }))
            # NDVI a cada 16 dias, responde à chuva acumulada de 60 d + ruído
            # grade MODIS: DOY 1, 17, ..., 353 em cada ano (23 por ano)
            datas16 = pd.DatetimeIndex([
                pd.Timestamp(a, 1, 1) + pd.Timedelta(days=16 * k)
                for a in range(ano_ini, ano_fim + 1) for k in range(23)
            ])
            serie = pd.Series(chuva, index=dias)
            ac60 = serie.rolling(60, min_periods=1).sum().reindex(datas16).to_numpy()
            nd = 0.2 + 0.5 * (1 - np.exp(-ac60 / 150)) + rng.normal(0, 0.03, len(datas16))
            conf = rng.choice([0, 1, 2], size=len(datas16), p=[0.8, 0.15, 0.05])
            nd = np.where(rng.random(len(datas16)) < 0.04, np.nan, nd)  # falhas
            ndvi.append(pd.DataFrame({
                "ponto_id": pid, "data": datas16, "ndvi": np.clip(nd, -0.1, 0.95),
                "confiabilidade": conf,
            }))
            if com_umidade:
                sm = serie.rolling(30, min_periods=1).sum().to_numpy()
                umid.append(pd.DataFrame({
                    "ponto_id": pid, "data": dias,
                    "sm_superficie": np.clip(0.05 + sm / 800 + rng.normal(0, 0.01, len(dias)), 0, 0.5),
                    "sm_raiz": np.clip(0.08 + sm / 1000 + rng.normal(0, 0.01, len(dias)), 0, 0.5),
                }))

    saidas = {
        "clima": destino / "SINTETICO_clima_diario.parquet",
        "ndvi": destino / "SINTETICO_ndvi_16d.parquet",
    }
    pd.concat(clima).to_parquet(saidas["clima"], index=False)
    pd.concat(ndvi).to_parquet(saidas["ndvi"], index=False)
    if com_umidade:
        saidas["umidade_solo"] = destino / "SINTETICO_umidade_solo.parquet"
        pd.concat(umid).to_parquet(saidas["umidade_solo"], index=False)
    return saidas


if __name__ == "__main__":
    from .entrada import RAIZ
    for k, v in gerar_sinteticos(RAIZ / "data" / "processed" / "sintetico").items():
        print(k, v)
