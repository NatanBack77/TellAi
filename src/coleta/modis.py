"""Coleta MODIS MOD13Q1 v061 (NDVI 250 m, 16 dias) por ponto -> data/processed/ndvi_16d.parquet.

Usa a API AppEEARS (NASA, mesmo login Earthdata): amostra o pixel de cada ponto, sem baixar tiles inteiros.
Credenciais vêm de `.env` (EARTHDATA_USERNAME / EARTHDATA_PASSWORD); nunca são impressas nem commitadas.
Retomável: o id da tarefa fica em data/raw/modis/tarefa.json. O app nunca chama esta API.

Confirmado na API (/api/product/MOD13Q1.061, 2026-11-11): NDVI já vem com fator de escala aplicado
(0,0001; faixa válida -0,2..1,0; preenchimento -3000); pixel reliability 0..3 (preenchimento -1).
Semântica 0..3 (0 bom, 1 marginal, 2 neve/gelo, 3 nuvem) é do guia do usuário MOD13 e AINDA PRECISA ser
conferida (config: ndvi.confiabilidade_aceita é provisório).
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

import numpy as np
import pandas as pd

from src.modelos.entrada import RAIZ, DadosInvalidos, carregar_config

API = "https://appeears.earthdatacloud.nasa.gov/api"
PRODUTO = "MOD13Q1.061"
L_NDVI, L_REL = "_250m_16_days_NDVI", "_250m_16_days_pixel_reliability"
FILL_NDVI = -3000


def _env() -> tuple[str, str]:
    arq = RAIZ / ".env"
    if arq.exists():
        for lin in arq.read_text(encoding="utf-8").splitlines():
            if "=" in lin and not lin.lstrip().startswith("#"):
                k, v = lin.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    u, s = os.environ.get("EARTHDATA_USERNAME"), os.environ.get("EARTHDATA_PASSWORD")
    if not u or not s:
        raise DadosInvalidos("Defina EARTHDATA_USERNAME e EARTHDATA_PASSWORD no .env.")
    return u, s


def _req(url, token=None, dados=None, basic=None, metodo=None):
    h = {}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if basic:
        import base64
        h["Authorization"] = "Basic " + base64.b64encode(f"{basic[0]}:{basic[1]}".encode()).decode()
    corpo = None
    if dados is not None:
        corpo = json.dumps(dados).encode()
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=corpo, headers=h, method=metodo or ("POST" if (corpo or basic) else "GET"))
    with urllib.request.urlopen(r, timeout=180) as resp:
        return resp.read()


def login() -> str:
    return json.loads(_req(f"{API}/login", basic=_env(), metodo="POST"))["token"]


def enviar_tarefa(token: str, cfg: dict) -> str:
    c = cfg["coleta"]
    p = c["power"]
    ini, fim = str(p["inicio"]), str(p["fim"])
    corpo = {"task_type": "point", "task_name": "sulco_mod13q1",
             "params": {"dates": [{"startDate": f"{ini[4:6]}-{ini[6:]}-{ini[:4]}", "endDate": f"{fim[4:6]}-{fim[6:]}-{fim[:4]}"}],
                        "layers": [{"product": PRODUTO, "layer": L_NDVI}, {"product": PRODUTO, "layer": L_REL}],
                        "coordinates": [{"id": q["ponto_id"], "category": "ponto", "latitude": q["lat"], "longitude": q["lon"]}
                                        for q in c["pontos"]]}}
    return json.loads(_req(f"{API}/task", token=token, dados=corpo))["task_id"]


def esperar(token: str, tarefa: str, limite_s: int) -> bool:
    t0 = time.time()
    while time.time() - t0 < limite_s:
        st = json.loads(_req(f"{API}/task/{tarefa}", token=token)).get("status")
        print("status AppEEARS:", st, flush=True)
        if st == "done":
            return True
        if st in ("error", "expired"):
            raise DadosInvalidos(f"Tarefa AppEEARS terminou com status '{st}'.")
        time.sleep(30)
    return False


def baixar_csv(token: str, tarefa: str, pasta) -> str:
    arqs = json.loads(_req(f"{API}/bundle/{tarefa}", token=token))["files"]
    alvo = next((a for a in arqs if a["file_name"].endswith(".csv") and "MOD13Q1" in a["file_name"]), None)
    if alvo is None:
        raise DadosInvalidos("CSV de resultados não encontrado no bundle AppEEARS.")
    dest = pasta / "resultados.csv"
    dest.write_bytes(_req(f"{API}/bundle/{tarefa}/{alvo['file_id']}", token=token))
    return str(dest)


def converter(csv: str) -> pd.DataFrame:
    d = pd.read_csv(csv)
    cn = next(c for c in d.columns if c.endswith(L_NDVI))
    cr = next(c for c in d.columns if c.endswith(L_REL))
    ndvi = d[cn].astype(float)
    ndvi = ndvi.where((ndvi != FILL_NDVI) & ndvi.between(-0.2, 1.0))      # preenchimento/fora da faixa => NaN
    rel = d[cr].astype(float).where(lambda s: s >= 0)                     # -1 = preenchimento => NaN
    out = pd.DataFrame({"ponto_id": d["ID"].astype(str), "data": pd.to_datetime(d["Date"]),
                        "ndvi": ndvi, "confiabilidade": rel})
    return out.sort_values(["ponto_id", "data"]).reset_index(drop=True)


def coletar(cfg: dict | None = None, espera_s: int = 540) -> dict:
    cfg = cfg or carregar_config()
    pasta = RAIZ / "data/raw/modis"
    pasta.mkdir(parents=True, exist_ok=True)
    marca = pasta / "tarefa.json"
    token = login()
    if marca.exists():
        tarefa = json.loads(marca.read_text())["task_id"]
        print("retomando tarefa", tarefa)
    else:
        tarefa = enviar_tarefa(token, cfg)
        marca.write_text(json.dumps({"task_id": tarefa}))
        print("tarefa enviada", tarefa)
    if not esperar(token, tarefa, espera_s):
        return {"status": "em andamento", "task_id": tarefa, "nota": "rode de novo para retomar"}
    df = converter(baixar_csv(token, tarefa, pasta))
    saida = RAIZ / cfg["caminhos"]["ndvi"]
    saida.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(saida, index=False)
    return {"status": "ok", "arquivo": str(saida), "linhas": int(len(df)), "pontos": int(df["ponto_id"].nunique()),
            "ndvi_ausente": int(df["ndvi"].isna().sum()),
            "valores_confiabilidade": {str(k): int(v) for k, v in df["confiabilidade"].value_counts(dropna=False).items()},
            "datas": [str(df["data"].min().date()), str(df["data"].max().date())]}


if __name__ == "__main__":
    print(json.dumps(coletar(), ensure_ascii=False, indent=2))
