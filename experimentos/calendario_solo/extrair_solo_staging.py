"""Extrai do espelho EcoCrop (OpenCLIM) as colunas de SOLO das 16 culturas -> data/culturas/solo_staging.csv (staging; nada digitado).
Uso: python experimentos/calendario_solo/extrair_solo_staging.py
Entrada: experimentos/calendario_solo/entrada/EcoCrop_DB.csv (commit ea43ecd, sha256 4187e884...d48d106)."""
import csv
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
URL = "https://raw.githubusercontent.com/OpenCLIM/ecocrop/ea43ecd418fd1a1ea08d32c7dce64b7fae02dec4/EcoCrop_DB.csv"
FONTE = "FAO EcoCrop (via espelho OpenCLIM/ecocrop, EcoCrop_DB.csv, commit ea43ecd, sha256 4187e884...d48d106)"
COLS = {"ph_otimo_min": ("PHOPMN", "pH"), "ph_otimo_max": ("PHOPMX", "pH"), "ph_min_abs": ("PHMIN", "pH"), "ph_max_abs": ("PHMAX", "pH"),
        "profundidade_otima": ("DEP", "classe"), "profundidade_faixa": ("DEPR", "classe"),
        "textura_otima": ("TEXT", "classe"), "textura_faixa": ("TEXTR", "classe"),
        "fertilidade_otima": ("FER", "classe"), "fertilidade_faixa": ("FERR", "classe"),
        "salinidade_otima": ("SAL", "classe"), "salinidade_faixa": ("SALR", "classe"),
        "drenagem_otima": ("DRA", "classe"), "drenagem_faixa": ("DRAR", "classe"),
        "toxicidade_otima": ("TOX", "classe"), "toxicidade_faixa": ("TOXR", "classe")}
CULT = [("milho", "2175"), ("feijao_caupi", "2153"), ("feijao_comum", "1668"), ("sorgo", "48747"), ("milheto", "8418"), ("mandioca", "1420"),
        ("algodao", "1160"), ("amendoim", "2199"), ("girassol", "1191"), ("mamona", "1866"), ("gergelim", "1937"), ("guandu", "576"),
        ("palma_forrageira", "8094"), ("crotalaria_juncea", "801"), ("feijao_de_porco", "609"), ("mucuna", "7832")]
e = pd.read_csv(RAIZ / "experimentos/calendario_solo/entrada/EcoCrop_DB.csv", encoding="latin-1", dtype=str).set_index("EcoPortCode")
linhas = []
for cid, code in CULT:
    r = e.loc[code]
    for atr, (col, un) in COLS.items():
        v = r[col]
        ok = isinstance(v, str) and v.strip() not in ("", "NA")
        linhas.append({"cultura_id": cid, "ecoport_code": code, "nome_cientifico": r["ScientificName"], "atributo": atr,
                       "valor": v.strip() if ok else "", "unidade": un, "status": "verificado" if ok else "lacuna", "fonte": FONTE, "url": URL,
                       "coluna": col, "trecho": f"EcoPortCode={code}; {col}={v if ok else 'NA/vazio'}", "data_consulta": "2026-11-14"})
out = RAIZ / "data/culturas/solo_staging.csv"
pd.DataFrame(linhas).to_csv(out, index=False, quoting=csv.QUOTE_MINIMAL)
print(len(linhas), "linhas;", sum(1 for l in linhas if l["status"] == "lacuna"), "lacunas")
