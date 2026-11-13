"""TESTE 3: baixa dados ERA5 via Open-Meteo Historical API (sem chave). Cache idempotente em data/raw/era5land/.
 - tipo 'solo'  : models=era5_land, umidade do solo 0-7, 7-28, 28-100 cm (media diaria, m3/m3), 0.1 grau.
 - tipo 'chuva' : models=era5, precipitation_sum (mm/dia), 0.25 grau. (Doc Open-Meteo: ERA5-Land NAO fornece precipitacao; a
   precipitacao do ERA5-Land e o proprio forcante ERA5.)
Limites do plano gratuito (doc /pricing): 600/min, 5.000/h, 10.000/dia, 300.000/mes. Custo = n_vars/10 * dias/14.
Este script usa um livro-caixa (t3_ledger.jsonl) e se limita a 4.000 unidades/h e --orcamento por dia; <=4 threads."""
import argparse, json, sys, time, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd, requests
RAIZ = Path(__file__).resolve().parents[2]
CACHE = RAIZ / "data/raw/era5land"; CACHE.mkdir(parents=True, exist_ok=True)
LEDGER = Path(__file__).parent / "t3_ledger.jsonl"
URL = "https://archive-api.open-meteo.com/v1/archive"
SOLO = ["soil_moisture_0_to_7cm_mean", "soil_moisture_7_to_28cm_mean", "soil_moisture_28_to_100cm_mean"]
CHUNKS = [(f"{a}-01-01", f"{min(a+2, 2021)}-12-31") for a in range(2001, 2022, 3)]
lock = threading.Lock()

def ledger():
    return [json.loads(l) for l in LEDGER.read_text().splitlines()] if LEDGER.exists() else []

def registrar(c):
    with lock:
        with open(LEDGER, "a") as f: f.write(json.dumps({"ts": time.time(), "c": c}) + "\n")

def gasto(janela):
    t = time.time(); return sum(x["c"] for x in ledger() if t - x["ts"] < janela)

def escolher(n):
    p = pd.read_csv(RAIZ / "data/processed/pontos.csv")
    p["cl"] = p.lat.round(1).astype(str) + "_" + p.lon.round(1).astype(str)
    p = p.drop_duplicates("cl").sort_values(["lat", "lon"]).reset_index(drop=True)
    idx = np.unique(np.round(np.linspace(0, len(p) - 1, n)).astype(int))
    return p.iloc[idx], len(p)

def um(args):
    tipo, pid, lat, lon, ini, fim, orc = args
    f = CACHE / (f"{pid}__{ini}_{fim}.json" if tipo == "solo" else f"{pid}__chuva__{ini}_{fim}.json")
    if f.exists(): return "cache"
    custo_est = (3 if tipo == "solo" else 1) / 10 * 1096 / 14
    par = dict(latitude=lat, longitude=lon, start_date=ini, end_date=fim, timezone="UTC")
    par.update(daily=",".join(SOLO), models="era5_land") if tipo == "solo" else par.update(daily="precipitation_sum", models="era5")
    for tent in range(8):
        while True:
            with lock: pass
            if gasto(86400) + custo_est > orc: return "orcamento_dia"
            if gasto(3600) + custo_est > 4000 or gasto(60) + custo_est > 500:
                time.sleep(15); continue
            break
        r = requests.get(URL, params=par, timeout=120)
        if r.status_code == 200:
            registrar(float(r.headers.get("X-RateLimit-Cost", custo_est))); f.write_text(r.text); return "ok"
        if r.status_code == 429 or "limit" in r.text[:200].lower():
            registrar(0.0); time.sleep(60); continue
        time.sleep(5)
    return "falha"

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=40); ap.add_argument("--orcamento", type=float, default=9000)
    ap.add_argument("--primeiros", type=int, default=None, help="usar so os k primeiros pontos do subconjunto")
    ap.add_argument("--tipos", default="solo,chuva")
    a = ap.parse_args()
    sel, ncel = escolher(a.n)
    if a.primeiros: sel = sel.iloc[:a.primeiros]
    print("pontos:", len(sel), "de", ncel, "celulas ERA5-Land distintas (0.1 grau)", flush=True)
    tarefas = [(t, r.ponto_id, r.lat, r.lon, i, f, a.orcamento) for t in a.tipos.split(",") for r in sel.itertuples() for i, f in CHUNKS]
    cont = {}
    with ThreadPoolExecutor(4) as ex:
        for st in ex.map(um, tarefas): cont[st] = cont.get(st, 0) + 1
    print(cont, "gasto 24h (unidades):", round(gasto(86400), 1))
