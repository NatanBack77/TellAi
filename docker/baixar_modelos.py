"""Baixa os dois modelos do Hugging Face para o cache (HF_HOME) durante o BUILD, para o contêiner rodar sem internet.
Os nomes são lidos de src/rag/busca.py (MODELO_EMB e MODELO_CROSS) para não haver cópia que possa divergir."""
import ast
import sys
from pathlib import Path

arvore = ast.parse(Path(sys.argv[1]).read_text(encoding="utf-8"))
nomes = {}
for no in arvore.body:
    if isinstance(no, ast.Assign) and len(no.targets) == 1 and getattr(no.targets[0], "id", "") in ("MODELO_EMB", "MODELO_CROSS"):
        nomes[no.targets[0].id] = ast.literal_eval(no.value)
faltam = {"MODELO_EMB", "MODELO_CROSS"} - set(nomes)
if faltam:
    sys.exit(f"não achei {sorted(faltam)} em {sys.argv[1]}")

from sentence_transformers import CrossEncoder, SentenceTransformer  # noqa: E402

SentenceTransformer(nomes["MODELO_EMB"], device="cpu")
CrossEncoder(nomes["MODELO_CROSS"], device="cpu")
print("modelos no cache:", nomes)
