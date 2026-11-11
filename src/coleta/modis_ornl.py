"""Coleta MODIS MOD13Q1 v061 por ponto via serviço de subset do ORNL DAAC (público, sem login, sem fila).

Alternativa ao AppEEARS (`modis.py`), que ficou preso na fila. Cada chamada devolve até 10 datas de um pixel;
as respostas ficam em cache em data/raw/modis_ornl/ (retomável, idempotente). O app nunca chama esta API.

Confirmado na API (2026-11-11): `modis_date` AYYYYDDD = início do composto de 16 dias (calendar_date igual ao
início), o que resolve S5; NDVI vem inteiro com fator de escala 0,0001 (aplicamos aqui); preenchimento -3000;
pixel reliability fill = -1. Semântica 0..3 da reliability segue a conferir (config: provisório).
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from src.modelos.entrada import RAIZ, DadosInvalidos, carregar_config

BASE = "https://modis.ornl.gov/rst/api/v1/MOD13Q1"
BANDAS = {"ndvi": "250m_16_days_NDVI", "confiabilidade": "250m_16_days_pixel_reliability"}
ESCALA_NDVI, FILL_NDVI, FILL_REL = 0.0001, -3000, -1
MAX_DATAS = 10


def _get(url: str, tentativas: int = 5):
    erro = None
    for i in range(tentativas):
        try:
            r = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(r, timeout=90) as resp:
                return json.load(resp)
        except Exception as e:
            erro = e
            time.sleep(2 ** i)
    raise DadosInvalidos(f"Falha ao consultar ORNL: {erro}")


def datas_modis(lat: float, lon: float, ini: str, fim: str) -> list[dict]:
    d = _get(f"{BASE}/dates?latitude={lat}&longitude={lon}")["dates"]
    return [x for x in d if ini <= x["calendar_date"] <= fim]


def _baixar_janela(args) -> str:
    pasta, pid, lat, lon, banda, d0, d1 = args
    arq = pasta / f"{pid}__{banda}__{d0}_{d1}.json"
    ok = False
    if arq.exists():
        try:
            ok = "subset" in json.loads(arq.read_text(encoding="utf-8"))   # descarta arquivo truncado
        except Exception:
            ok = False
    if not ok:
        q = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "band": BANDAS[banda], "startDate": d0,
                                    "endDate": d1, "kmAboveBelow": 0, "kmLeftRight": 0})
        arq.write_text(json.dumps(_get(f"{BASE}/subset?{q}")), encoding="utf-8")
    return str(arq)


def coletar(cfg: dict | None = None, trabalhadores: int = 4) -> dict:
    cfg = cfg or carregar_config()
    c = cfg["coleta"]
    p = c["power"]
    ini = f"{str(p['inicio'])[:4]}-{str(p['inicio'])[4:6]}-{str(p['inicio'])[6:]}"
    fim = f"{str(p['fim'])[:4]}-{str(p['fim'])[4:6]}-{str(p['fim'])[6:]}"
    pasta = RAIZ / "data/raw/modis_ornl"
    pasta.mkdir(parents=True, exist_ok=True)
    tarefas = []
    for q in c["pontos"]:
        datas = [x["modis_date"] for x in datas_modis(q["lat"], q["lon"], ini, fim)]
        for i in range(0, len(datas), MAX_DATAS):
            jan = datas[i:i + MAX_DATAS]
            for banda in BANDAS:
                tarefas.append((pasta, q["ponto_id"], q["lat"], q["lon"], banda, jan[0], jan[-1]))
    print(f"{len(tarefas)} janelas", flush=True)
    with ThreadPoolExecutor(trabalhadores) as ex:
        for n, _ in enumerate(ex.map(_baixar_janela, tarefas), 1):
            if n % 100 == 0:
                print(f"{n}/{len(tarefas)}", flush=True)
    linhas = []
    for (_, pid, _, _, banda, d0, d1) in tarefas:
        j = json.loads((pasta / f"{pid}__{banda}__{d0}_{d1}.json").read_text(encoding="utf-8"))
        for s in j["subset"]:
            linhas.append((pid, s["calendar_date"], banda, float(s["data"][0])))
    long = pd.DataFrame(linhas, columns=["ponto_id", "data", "banda", "v"])
    df = long.pivot_table(index=["ponto_id", "data"], columns="banda", values="v", aggfunc="first").reset_index()
    ndvi = df["ndvi"].where(df["ndvi"] != FILL_NDVI) * ESCALA_NDVI
    ndvi = ndvi.where(ndvi.between(-0.2, 1.0))
    out = pd.DataFrame({"ponto_id": df["ponto_id"].astype(str), "data": pd.to_datetime(df["data"]), "ndvi": ndvi,
                        "confiabilidade": df["confiabilidade"].where(df["confiabilidade"] != FILL_REL)})
    out = out.sort_values(["ponto_id", "data"]).reset_index(drop=True)
    saida = RAIZ / cfg["caminhos"]["ndvi"]
    saida.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(saida, index=False)
    return {"arquivo": str(saida), "linhas": int(len(out)), "pontos": int(out["ponto_id"].nunique()),
            "ndvi_ausente": int(out["ndvi"].isna().sum()),
            "valores_confiabilidade": {str(k): int(v) for k, v in out["confiabilidade"].value_counts(dropna=False).items()},
            "datas": [str(out["data"].min().date()), str(out["data"].max().date())]}


def progresso(cfg: dict | None = None) -> dict:
    """Quantas janelas já estão em cache (válidas) versus o total esperado. Faz só 13 chamadas leves de datas."""
    cfg = cfg or carregar_config()
    p = cfg["coleta"]["power"]
    ini = f"{str(p['inicio'])[:4]}-{str(p['inicio'])[4:6]}-{str(p['inicio'])[6:]}"
    fim = f"{str(p['fim'])[:4]}-{str(p['fim'])[4:6]}-{str(p['fim'])[6:]}"
    pasta = RAIZ / "data/raw/modis_ornl"
    total = feitas = 0
    for q in cfg["coleta"]["pontos"]:
        datas = [x["modis_date"] for x in datas_modis(q["lat"], q["lon"], ini, fim)]
        for i in range(0, len(datas), MAX_DATAS):
            jan = datas[i:i + MAX_DATAS]
            for banda in BANDAS:
                total += 1
                arq = pasta / f"{q['ponto_id']}__{banda}__{jan[0]}_{jan[-1]}.json"
                try:
                    feitas += "subset" in json.loads(arq.read_text(encoding="utf-8"))
                except Exception:
                    pass
    return {"janelas_total": total, "janelas_prontas": feitas, "faltam": total - feitas,
            "percentual": round(100 * feitas / total, 1) if total else 0.0}


if __name__ == "__main__":
    import sys

    if "--status" in sys.argv:
        print(json.dumps(progresso(), ensure_ascii=False, indent=2))
    else:
        n = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 4
        print(json.dumps(coletar(trabalhadores=n), ensure_ascii=False, indent=2))
