import sys, json, time, urllib.request, urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
RAIZ = Path(__file__).resolve().parents[2]
QUI = Path(__file__).parent
CACHE = QUI / "cache"
BASE = "https://modis.ornl.gov/rst/api/v1/MOD13Q1"
BANDAS = {"evi": "250m_16_days_EVI", "red": "250m_16_days_red_reflectance",
          "nir": "250m_16_days_NIR_reflectance", "viq": "250m_16_days_VI_Quality"}
ids = pd.read_parquet(QUI.parent / "dados13/ndvi_16d.parquet")["ponto_id"].unique()
pts = pd.read_csv(RAIZ / "data/processed/pontos.csv").set_index("ponto_id").loc[list(ids)]

def get(url, n=6):
    e = None
    for i in range(n):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=90) as r:
                return json.load(r)
        except Exception as ex:
            e = ex; time.sleep(2 ** i)
    raise RuntimeError(e)

def janela(a):
    pid, lat, lon, b, d0, d1 = a
    f = CACHE / f"{pid}__{b}__{d0}_{d1}.json"
    if f.exists():
        try:
            if "subset" in json.loads(f.read_text()): return
        except Exception: pass
    q = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "band": BANDAS[b], "startDate": d0, "endDate": d1, "kmAboveBelow": 0, "kmLeftRight": 0})
    f.write_text(json.dumps(get(f"{BASE}/subset?{q}")))

tar = []
for pid, r in pts.iterrows():
    ds = [x["modis_date"] for x in get(f"{BASE}/dates?latitude={r.lat}&longitude={r.lon}")["dates"] if "2001-01-01" <= x["calendar_date"] <= "2024-12-31"]
    for i in range(0, len(ds), 10):
        for b in BANDAS: tar.append((pid, r.lat, r.lon, b, ds[i], ds[min(i + 9, len(ds) - 1)]))
print(len(tar), "janelas", flush=True)
json.dump(tar, open(QUI / "tarefas.json", "w"))
with ThreadPoolExecutor(16) as ex:
    for n, _ in enumerate(ex.map(janela, tar), 1):
        if n % 200 == 0: print(n, flush=True)
print("FIM")
