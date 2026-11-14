#!/usr/bin/env bash
# Prepara o ambiente do SULCO em outro computador (Linux/Mac; no Windows use Git Bash ou WSL).
# Uso: bash scripts/setup.sh [--rag] [--testes]
#   --rag     reconstrói o índice do RAG (precisa de pdftotext/poppler; baixa o modelo de embeddings na 1ª vez)
#   --testes  roda a suíte (a do RAG leva ~7 min)
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
[ -d .venv ] || "$PY" -m venv .venv
PIP=".venv/bin/python -m pip"
$PIP install --upgrade pip >/dev/null
# Tudo (runtime + RAG + coleta + testes). torch CPU (só o RAG usa); se falhar, o resto segue e a busca cai para BM25
$PIP install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt || {
  echo "AVISO: falha ao instalar tudo; tentando sem torch/sentence-transformers (RAG só BM25)";
  $PIP install -r requirements-runtime.txt -r requirements-coleta.txt -r requirements-dev.txt
}

# Caches pesados versionados como tar.gz (evita baixar de novo)
[ -d data/raw/smap/granulos ] || { [ -f data/raw/smap_cache.tar.gz ] && tar xzf data/raw/smap_cache.tar.gz -C data/raw; }
[ -d data/raw/power ]         || { [ -f data/raw/power_cache.tar.gz ] && tar xzf data/raw/power_cache.tar.gz -C data/raw; }

[ -f .env ] || echo "AVISO: crie .env (nunca commitado) com EARTHDATA_USERNAME / EARTHDATA_PASSWORD e, se for usar, DEEPSEEK_API_KEY. Ver docs/04_RETOMADA.md"

if [[ " $* " == *" --rag "* ]]; then
  command -v pdftotext >/dev/null || echo "AVISO: instale poppler (pdftotext) para reconstruir o índice do RAG"
  .venv/bin/python -m src.rag.rag_docs
fi

.venv/bin/python scripts/verificar_ambiente.py
if [[ " $* " == *" --testes "* ]]; then .venv/bin/python -m pytest -q -W error; fi
