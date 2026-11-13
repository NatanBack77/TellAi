"""Solo por ponto lido DIRETO dos mapas do SoilGrids v2.0 (ISRIC, 250 m, licença CC BY 4.0) -> data/processed/solo.parquet.

A API REST (rest.isric.org) ficou fora do ar em 2026-11-13; os mapas (files.isric.org, VRT/COG em projeção Homolosine) respondem e são lidos
por leitura parcial (GDAL /vsicurl via rasterio), sem baixar os arquivos inteiros. Requer `rasterio` (requirements.txt).

Propriedades (média da camada; profundidades 0-5, 5-15 e 15-30 cm): areia, silte, argila (g/kg; /10 = %), carbono orgânico do solo `soc`
(dg/kg; /10 = g/kg) e pH em água (pH x 10). Por ponto: mediana dos pixels VÁLIDOS numa janela de 9x9 pixels (~2 km) centrada no ponto, porque o
pixel do centro pode estar mascarado (área urbana, água). Guarda a fração de pixels válidos e se o pixel central era válido. Sem pixel válido:
NaN (lacuna). Representa ~2 km, NÃO o talhão; é modelagem global (incerteza grande em escala local), não análise de solo.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform
from rasterio.windows import Window

from src.modelos.entrada import RAIZ

BASE = "/vsicurl/https://files.isric.org/soilgrids/latest/data"
PROPS = ["sand", "silt", "clay", "soc", "phh2o"]
DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]
RAIO_PX = 4          # janela de 9x9 pixels (250 m cada)
ESCALA = {"sand": 0.1, "silt": 0.1, "clay": 0.1, "soc": 0.1, "phh2o": 0.1}   # g/kg->%, dg/kg->g/kg, pH*10->pH


def _camada(prop: str, depth: str, pts: pd.DataFrame, tentativas: int = 4) -> dict:
    url = f"{BASE}/{prop}/{prop}_{depth}_mean.vrt"
    erro = None
    for i in range(tentativas):
        try:
            with rasterio.Env(GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="3", GDAL_HTTP_TIMEOUT="120",
                              CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".vrt,.tif", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
                with rasterio.open(url) as ds:
                    xs, ys = transform("EPSG:4326", ds.crs, pts["lon"].tolist(), pts["lat"].tolist())
                    nod = ds.nodata
                    out = {}
                    for pid, x, y in zip(pts["ponto_id"], xs, ys):
                        r, c = ds.index(x, y)
                        a = ds.read(1, window=Window(c - RAIO_PX, r - RAIO_PX, 2 * RAIO_PX + 1, 2 * RAIO_PX + 1), boundless=True,
                                    fill_value=nod).astype(float)
                        ok = a != nod
                        centro = bool(ok[RAIO_PX, RAIO_PX])
                        out[pid] = (float(np.median(a[ok]) * ESCALA[prop]) if ok.any() else np.nan, float(ok.mean()), centro)
                    return out
        except Exception as e:                         # rede/GDAL: espera e tenta de novo
            erro = e
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"SoilGrids {prop} {depth}: {erro}")


def coletar(trabalhadores: int = 5) -> dict:
    pasta = RAIZ / "data/raw/soilgrids"
    pasta.mkdir(parents=True, exist_ok=True)
    pts = pd.read_csv(RAIZ / "data/processed/pontos.csv")[["ponto_id", "lat", "lon"]]
    tarefas = [(p, d) for p in PROPS for d in DEPTHS]

    def rodar(t):
        p, d = t
        arq = pasta / f"{p}_{d}.json"
        if arq.exists():
            return t, json.loads(arq.read_text(encoding="utf-8"))
        r = _camada(p, d, pts)
        arq.write_text(json.dumps(r), encoding="utf-8")
        print("camada", p, d, flush=True)
        return t, r

    with ThreadPoolExecutor(trabalhadores) as ex:
        res = dict(ex.map(rodar, tarefas))
    linhas = []
    for pid in pts["ponto_id"]:
        l = {"ponto_id": pid}
        for (p, d), r in res.items():
            v = r[pid]
            l[f"{p}_{d}"] = None if v[0] is None or (isinstance(v[0], float) and np.isnan(v[0])) else v[0]
        v0 = res[("clay", "0-5cm")][pid]
        l["fracao_pixels_validos"], l["pixel_central_valido"] = v0[1], bool(v0[2])
        linhas.append(l)
    d = pd.DataFrame(linhas)
    d.to_parquet(RAIZ / "data/processed/solo.parquet", index=False)
    return {"pontos": len(d), "com_argila_0_5": int(d["clay_0-5cm"].notna().sum()), "pixel_central_valido": int(d["pixel_central_valido"].sum())}


if __name__ == "__main__":
    print(coletar())
