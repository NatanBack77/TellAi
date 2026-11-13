"""Terreno por ponto a partir do SRTM (tiles HGT de 1 arco-segundo ~30 m, distribuídos em s3://elevation-tiles-prod/skadi, sem login)
-> data/processed/terreno.parquet.

Por ponto: altitude no pixel, altitude média no raio de ~1 km, declive no pixel e declive médio / p90 no raio de ~1 km (%), com vazios
(-32768) como NaN. Declive por diferenças centrais em grade de ~30 m (espaçamento em metros corrigido pela latitude). Cache dos tiles em
data/raw/srtm/ (ignorado pelo git). É terreno do pixel e da vizinhança, não do talhão; declive é indicador de risco de erosão, não modelo de erosão.
"""
from __future__ import annotations

import gzip
import math
import urllib.request

import numpy as np
import pandas as pd

from src.modelos.entrada import RAIZ

N = 3601
RAIO_PX = 33  # ~1 km


def _tile(lat, lon):
    la, lo = math.floor(lat), math.floor(lon)
    return f"{'S' if la < 0 else 'N'}{abs(la):02d}{'W' if lo < 0 else 'E'}{abs(lo):03d}", la, lo


def _carregar(nome, pasta):
    arq = pasta / f"{nome}.hgt"
    if not arq.exists():
        url = f"https://s3.amazonaws.com/elevation-tiles-prod/skadi/{nome[:3]}/{nome}.hgt.gz"
        with urllib.request.urlopen(url, timeout=300) as r:
            arq.write_bytes(gzip.decompress(r.read()))
    a = np.fromfile(arq, dtype=">i2").reshape(N, N).astype(float)
    a[a == -32768] = np.nan
    return a


def coletar():
    pasta = RAIZ / "data/raw/srtm"
    pasta.mkdir(parents=True, exist_ok=True)
    pts = pd.read_csv(RAIZ / "data/processed/pontos.csv")
    pts["_t"] = [_tile(r.lat, r.lon)[0] for r in pts.itertuples()]
    linhas = []
    for nome, grupo in pts.groupby("_t"):                  # um tile por vez na memória
        a = _carregar(nome, pasta)
        print("tile", nome, len(grupo), "pontos", flush=True)
        for r in grupo.itertuples():
            _, la, lo = _tile(r.lat, r.lon)
            i = int(round((la + 1 - r.lat) * (N - 1)))     # linha: do norte (topo) para o sul
            j = int(round((r.lon - lo) * (N - 1)))
            i0, i1 = max(i - RAIO_PX - 1, 0), min(i + RAIO_PX + 2, N)
            j0, j1 = max(j - RAIO_PX - 1, 0), min(j + RAIO_PX + 2, N)
            w = a[i0:i1, j0:j1]
            gy, gx = np.gradient(w, 30.87, 30.87 * math.cos(math.radians(r.lat)))
            decl = np.hypot(gx, gy) * 100.0                 # % (tangente x 100)
            ii, jj = np.mgrid[i0:i1, j0:j1]
            raio = (ii - i) ** 2 + (jj - j) ** 2 <= RAIO_PX ** 2
            linhas.append({"ponto_id": r.ponto_id, "elev_m": float(a[i, j]), "elev_media_1km_m": float(np.nanmean(w[raio])),
                           "declive_pixel_pct": float(decl[i - i0, j - j0]),
                           "declive_medio_1km_pct": float(np.nanmean(decl[raio])),
                           "declive_p90_1km_pct": float(np.nanpercentile(decl[raio], 90))})
    d = pd.DataFrame(linhas)
    d.to_parquet(RAIZ / "data/processed/terreno.parquet", index=False)
    return {"pontos": len(d), "sem_altitude": int(d["elev_m"].isna().sum())}


if __name__ == "__main__":
    print(coletar())
