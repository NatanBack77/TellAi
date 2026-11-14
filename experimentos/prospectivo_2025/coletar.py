"""Coleta 2025+ (MODIS ORNL + POWER) para os 195 pontos, em destinos NOVOS. Reutiliza funcoes de src/coleta (sem edita-las).
Nao toca ndvi_16d.parquet, clima_diario.parquet, pontos.csv nem data/raw/modis_ornl|power."""
import sys, json, datetime as dt
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import pandas as pd
from src.coleta import modis_ornl as mo, power as pw
from src.modelos.entrada import carregar_config

cfg = carregar_config()
pontos = cfg["coleta"]["pontos"]
INI = "2025-01-01"
FIM = dt.date.today().isoformat()
W = 10


def modis():
    pasta = RAIZ / "data/raw/modis_ornl_2025plus"
    pasta.mkdir(parents=True, exist_ok=True)
    def datas(q):
        return q["ponto_id"], [x["modis_date"] for x in mo.datas_modis(q["lat"], q["lon"], INI, FIM)]
    with ThreadPoolExecutor(W) as ex:
        dd = dict(ex.map(datas, pontos))
    (pasta / "_datas_listadas.json").write_text(json.dumps(dd))
    tarefas = []
    for q in pontos:
        d = dd[q["ponto_id"]]
        for i in range(0, len(d), mo.MAX_DATAS):
            j = d[i:i + mo.MAX_DATAS]
            for b in mo.BANDAS:
                tarefas.append((pasta, q["ponto_id"], q["lat"], q["lon"], b, j[0], j[-1]))
    print(len(tarefas), "janelas; datas distintas:", sorted({x for v in dd.values() for x in v}), flush=True)
    with ThreadPoolExecutor(W) as ex:
        for n, _ in enumerate(ex.map(mo._baixar_janela, tarefas), 1):
            if n % 100 == 0: print(n, flush=True)
    linhas = []
    for (_, pid, _, _, b, d0, d1) in tarefas:
        j = json.loads((pasta / f"{pid}__{b}__{d0}_{d1}.json").read_text(encoding="utf-8"))
        for s in j["subset"]:
            linhas.append((pid, s["calendar_date"], b, float(s["data"][0])))
    long = pd.DataFrame(linhas, columns=["ponto_id", "data", "banda", "v"])
    df = long.pivot_table(index=["ponto_id", "data"], columns="banda", values="v", aggfunc="first").reset_index()
    ndvi = df["ndvi"].where(df["ndvi"] != mo.FILL_NDVI) * mo.ESCALA_NDVI
    ndvi = ndvi.where(ndvi.between(-0.2, 1.0))
    out = pd.DataFrame({"ponto_id": df["ponto_id"].astype(str), "data": pd.to_datetime(df["data"]), "ndvi": ndvi,
                        "confiabilidade": df["confiabilidade"].where(df["confiabilidade"] != mo.FILL_REL)})
    out = out.sort_values(["ponto_id", "data"]).reset_index(drop=True)
    out.to_parquet(RAIZ / "data/processed/ndvi_2025plus.parquet", index=False)
    print("NDVI", len(out), out["data"].min(), out["data"].max())


def clima():
    bruta = RAIZ / "data/raw/power_2025plus"
    bruta.mkdir(parents=True, exist_ok=True)
    c = json.loads(json.dumps(cfg, default=str))
    c["coleta"]["power"]["inicio"] = 20250101
    c["coleta"]["power"]["fim"] = int(dt.date.today().strftime("%Y%m%d"))
    celulas = {p["ponto_id"]: pw.celula_power(p["lat"], p["lon"], cfg) for p in pontos}
    def um(p):
        arq = bruta / f"{p['ponto_id']}.json"
        if not arq.exists():
            arq.write_text(json.dumps(pw.baixar_ponto(p["lat"], p["lon"], c)), encoding="utf-8")
        return pw.para_dataframe(json.loads(arq.read_text(encoding="utf-8")), p["ponto_id"], celulas[p["ponto_id"]], c)
    with ThreadPoolExecutor(8) as ex:
        partes = list(ex.map(um, pontos))
    df = pd.concat(partes, ignore_index=True)
    df.to_parquet(RAIZ / "data/processed/clima_2025plus.parquet", index=False)
    print("CLIMA", len(df), df["data"].min(), df["data"].max())


if __name__ == "__main__":
    {"modis": modis, "clima": clima}[sys.argv[1]]()
