"""Confere se o ambiente e os dados estão prontos. Só lê; não baixa nada. Saída: OK / FALTA por item."""
from pathlib import Path
import importlib, sys

RAIZ = Path(__file__).resolve().parents[1]
itens = {
    "clima (195 pontos)": "data/processed/clima_diario.parquet",
    "NDVI (195 pontos)": "data/processed/ndvi_16d.parquet",
    "umidade do solo (SMAP)": "data/processed/umidade_solo.parquet",
    "pontos": "data/processed/pontos.csv",
    "diagnóstico real": "data/processed/diagnostico/diagnostico.json",
    "métricas do preditivo": "data/processed/modelos/metricas.json",
    "tabela de culturas": "data/culturas/tabela_culturas.csv",
    "manifesto do acervo RAG": "docs_rag/manifesto.json",
    "índice do RAG (opcional; rag_docs)": "indice/trechos.jsonl",
    "cache NDVI (ORNL)": "data/raw/modis_ornl",
    "ZARC (opcional)": "data/processed/zarc_ce.parquet",
    ".env (opcional)": ".env",
}
falta = 0
for nome, rel in itens.items():
    ok = (RAIZ / rel).exists()
    print(("OK    " if ok else "FALTA ") + nome + f"  [{rel}]")
    falta += (not ok) and "opcional" not in nome
mods = ["numpy", "pandas", "pyarrow", "sklearn", "xgboost", "streamlit", "yaml", "earthaccess"]
for m in mods:
    try:
        importlib.import_module(m); print("OK    módulo " + m)
    except Exception as e:
        print("FALTA módulo " + m + f" ({e.__class__.__name__})"); falta += 1
for m in ["sentence_transformers", "fastapi", "uvicorn"]:
    try:
        importlib.import_module(m); print("OK    módulo " + m)
    except Exception:
        print("-     módulo " + m + " (opcional; RAG semântico / API)")
print(f"\n{falta} item(ns) obrigatório(s) faltando." if falta else "\nTudo obrigatório presente.")
sys.exit(1 if falta else 0)
