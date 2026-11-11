"""Baixa CHIRPS diario (ClimateSERV, datatype 0) por ponto/ano; cache JSON em cache/. Idempotente."""
import json, time, sys, urllib.request, urllib.parse
from pathlib import Path
import pandas as pd
AQUI = Path(__file__).parent; CACHE = AQUI / "cache"; CACHE.mkdir(exist_ok=True)
SCR = AQUI.parent
B = "https://climateserv.servirglobal.net/api/"
def get(ep, **p):
    u = B + ep + "/?" + urllib.parse.urlencode(p)
    for t in range(5):
        try:
            return json.loads(urllib.request.urlopen(u, timeout=90).read())
        except Exception as e:
            err = e; time.sleep(3 * (t + 1))
    raise err
def baixar(pid, lat, lon, ano):
    f = CACHE / f"{pid}_{ano}.json"
    if f.exists(): return
    h = 0.005
    g = {"type": "Polygon", "coordinates": [[[lon-h, lat-h], [lon-h, lat+h], [lon+h, lat+h], [lon+h, lat-h], [lon-h, lat-h]]]}
    jid = get("submitDataRequest", datatype=0, begintime=f"01/01/{ano}", endtime=f"12/31/{ano}",
              intervaltype=0, operationtype=5, geometry=json.dumps(g))[0]
    for _ in range(120):
        p = get("getDataRequestProgress", id=jid)[0]
        if p == 100: break
        if p == -1: raise RuntimeError(f"erro {pid} {ano}")
        time.sleep(2)
    d = get("getDataFromRequest", id=jid)["data"]
    f.write_text(json.dumps(d))
if __name__ == "__main__":
    cl = pd.read_parquet(SCR / "dados13" / "clima_diario.parquet")
    pts = pd.read_csv(Path(__file__).resolve().parents[2] / "data/processed/pontos.csv")
    pts = pts[pts.ponto_id.isin(cl.ponto_id.unique())]
    print(len(pts), "pontos")
    from concurrent.futures import ThreadPoolExecutor
    jobs = [(r.ponto_id, r.lat, r.lon, a) for r in pts.itertuples() for a in range(2001, 2025)]
    def run(j):
        try: baixar(*j); return None
        except Exception as e: return (j, str(e))
    with ThreadPoolExecutor(4) as ex:
        falhas = [x for x in ex.map(run, jobs) if x]
    print("falhas:", falhas)
