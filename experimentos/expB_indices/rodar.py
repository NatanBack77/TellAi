import sys, pickle
from pathlib import Path
RAIZ = str(__import__("pathlib").Path(__file__).resolve().parents[2])
sys.path.insert(0, RAIZ)
import os; os.chdir(RAIZ)
import numpy as np, pandas as pd
from src.modelos.entrada import carregar_config, carregar_entradas
from src.modelos.walkforward import walk_forward, resumir, VARIANTES, _ic_inferior
QUI = Path(__file__).parent; SNAP = QUI.parent / "dados13"
ANOS = list(range(2010, 2022))
DATASETS = ["ndvi", "evi", "savi", "ndvi_conf0", "ndvi_viq"]
N = len(DATASETS) * 2   # cada dataset x {base, persistencia}
placebo = "--placebo" in sys.argv
alvo = [a for a in sys.argv[1:] if not a.startswith("--")] or DATASETS
out = QUI / ("res_placebo.pkl" if placebo else "res.pkl")
res = pickle.load(open(out, "rb")) if out.exists() else {}
for ds in alvo:
    cfg = carregar_config()
    cfg["caminhos"].update(clima=str(SNAP / "clima_diario.parquet"), ndvi=str(QUI / "variantes" / f"{ds}.parquet"),
                           umidade_solo=str(SNAP / "umidade_solo_inexistente.parquet"))
    ent = carregar_entradas(cfg)
    r = walk_forward(ent, cfg, [VARIANTES["base"], VARIANTES["persistencia"]], ANOS, placebo=placebo)
    res[ds] = r; pickle.dump(res, open(out, "wb"))
    print(ds, "ok", flush=True)
