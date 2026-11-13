"""Solo por ponto via SoilGrids v2.0 (ISRIC; API pública, sem login, limite ~5 chamadas/min) -> data/processed/solo.parquet.

Propriedades (média, 0-5, 5-15 e 15-30 cm): areia, silte, argila, carbono orgânico (soc), pH em água (phh2o). Unidades do SoilGrids:
areia/silte/argila em g/kg (÷10 = %), soc em dg/kg (÷10 = g/kg), pH×10. Ponto sem valor (célula urbana/mascarada) tenta 4 deslocamentos de 0,01°
(~1 km) e registra o deslocamento usado; sem valor em todos fica NaN (lacuna). Cache JSON por ponto em data/raw/soilgrids/ (retomável).
Resolução 250 m: representa o pixel, não o talhão.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

import pandas as pd

from src.modelos.entrada import RAIZ

BASE = "https://rest.isric.org/soilgrids/v2.0/properties/query"
PROPS = ["sand", "silt", "clay", "soc", "phh2o"]
DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]
OFFS = [(0.0, 0.0), (0.01, 0.0), (-0.01, 0.0), (0.0, 0.01), (0.0, -0.01)]
PAUSA_S = 13


def _consultar(lat, lon, tentativas=5):
    q = [("lon", lon), ("lat", lat), ("value", "mean")] + [("property", p) for p in PROPS] + [("depth", d) for d in DEPTHS]
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(f"{BASE}?{urllib.parse.urlencode(q)}", timeout=120) as r:
                return json.load(r)
        except Exception:
            time.sleep(PAUSA_S * (i + 1))
    return None


def _valores(d):
    out = {}
    for camada in d["properties"]["layers"]:
        for x in camada["depths"]:
            out[f"{camada['name']}_{x['label']}"] = x["values"]["mean"]
    return out


def coletar():
    pasta = RAIZ / "data/raw/soilgrids"
    pasta.mkdir(parents=True, exist_ok=True)
    pts = pd.read_csv(RAIZ / "data/processed/pontos.csv")
    linhas = []
    for n, r in enumerate(pts.itertuples(), 1):
        arq = pasta / f"{r.ponto_id}.json"
        if arq.exists():
            reg = json.loads(arq.read_text(encoding="utf-8"))
        else:
            reg = {"ponto_id": r.ponto_id, "deslocamento": None, "valores": None, "falhou": True}
            for dlat, dlon in OFFS:
                d = _consultar(r.lat + dlat, r.lon + dlon)
                time.sleep(PAUSA_S)
                if d is None:
                    continue
                v = _valores(d)
                reg["falhou"] = False
                if v.get("clay_0-5cm") is not None:
                    reg.update(deslocamento=[dlat, dlon], valores=v)
                    break
            if not reg["falhou"]:             # só grava se o servidor respondeu (timeout não vira "sem dado")
                arq.write_text(json.dumps(reg), encoding="utf-8")
        if reg.get("valores"):
            linhas.append({"ponto_id": r.ponto_id, "deslocamento_graus": str(reg["deslocamento"]), **reg["valores"]})
        else:
            linhas.append({"ponto_id": r.ponto_id, "deslocamento_graus": None})
        if n % 10 == 0:
            print(f"{n}/{len(pts)}", flush=True)
    d = pd.DataFrame(linhas)
    d.to_parquet(RAIZ / "data/processed/solo.parquet", index=False)
    return {"pontos": len(d), "com_dado": int(d["clay_0-5cm"].notna().sum())}


if __name__ == "__main__":
    print(coletar())
