# syntax=docker/dockerfile:1.7
# SULCO: imagem de produção em vários estágios (multi-stage).
#
#   base    -> Python slim + libgomp (XGBoost) + variáveis comuns
#   deps    -> venv com as dependências de EXECUÇÃO (e o RAG semântico, se WITH_RAG=1)
#   modelos -> baixa os 2 modelos do Hugging Face para /opt/hf (o contêiner roda sem internet)
#   indice  -> poppler-utils + PDFs: constrói indice/ (RAG). Nada disso vai para a imagem final
#   cache   -> treina e grava o cache do modelo de previsão da API (evita ~20 s na 1ª chamada)
#   runtime -> imagem final enxuta, usuário não-root  (alvo padrão)
#   test    -> (opcional) runtime + dependências de teste, para CI:  docker build --target test .
#
# Uso:   docker build -t sulco .                        # completa (RAG semântico)
#        docker build --build-arg WITH_RAG=0 -t sulco:bm25 .   # sem torch: RAG só BM25, imagem bem menor
#        docker run -p 8000:8000 sulco api    |    docker run -p 8501:8501 sulco app
ARG PYTHON_VERSION=3.14
ARG WITH_RAG=1

# ---------------------------------------------------------------- base
FROM python:${PYTHON_VERSION}-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app
# libgomp1: biblioteca de OpenMP exigida pelo XGBoost em imagens slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# ---------------------------------------------------------------- deps
FROM base AS deps
ARG WITH_RAG
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
COPY requirements-runtime.txt requirements-rag.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-runtime.txt
# torch CPU (a roda padrão do PyPI traz CUDA e passa de 2 GB)
RUN --mount=type=cache,target=/root/.cache/pip \
    if [ "${WITH_RAG}" = "1" ]; then \
      pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-rag.txt; \
    fi

# ---------------------------------------------------------------- modelos (Hugging Face)
FROM deps AS modelos
ARG WITH_RAG
ENV HF_HOME=/opt/hf
COPY docker/baixar_modelos.py /tmp/baixar_modelos.py
COPY src/rag/busca.py /tmp/busca.py
RUN mkdir -p /opt/hf \
 && if [ "${WITH_RAG}" = "1" ]; then python /tmp/baixar_modelos.py /tmp/busca.py; fi

# ---------------------------------------------------------------- indice do RAG
FROM deps AS indice
ARG WITH_RAG
RUN apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils \
 && rm -rf /var/lib/apt/lists/*
COPY --from=modelos /opt/hf /opt/hf
ENV HF_HOME=/opt/hf HF_HUB_OFFLINE=1
COPY config.yaml ./
COPY src ./src
COPY docs_rag ./docs_rag
# sem o modelo de embeddings (WITH_RAG=0) o indice sai só com BM25 (rag_docs trata a exceção)
RUN python -m src.rag.rag_docs

# ---------------------------------------------------------------- cache do modelo de previsão
FROM deps AS cache
COPY config.yaml ./
COPY src ./src
COPY data/processed ./data/processed
COPY data/culturas ./data/culturas
RUN python -c "from src.modelos.previsao import carregar_ou_treinar; c = carregar_ou_treinar(True); print('cache de previsão:', c.get('origem'), c.get('segundos'))"

# ---------------------------------------------------------------- runtime (final)
FROM base AS runtime
ARG WITH_RAG
ENV PATH="/opt/venv/bin:${PATH}" \
    HF_HOME=/opt/hf \
    HF_HUB_OFFLINE=1 \
    SULCO_LLM_MODO=template \
    SULCO_ABERTURA_ZOOM=0 \
    API_PORT=8000 \
    APP_PORT=8501
RUN groupadd --system --gid 10001 sulco \
 && useradd --system --uid 10001 --gid sulco --home-dir /app --shell /usr/sbin/nologin sulco
COPY --from=deps /opt/venv /opt/venv
COPY --from=modelos --chown=sulco:sulco /opt/hf /opt/hf
COPY --chown=sulco:sulco config.yaml ./
COPY --chown=sulco:sulco src ./src
COPY --chown=sulco:sulco data/processed ./data/processed
COPY --chown=sulco:sulco data/culturas ./data/culturas
COPY --chown=sulco:sulco docs_rag/manifesto.json ./docs_rag/manifesto.json
# arquivos de texto que o app lê em execução (página 'Limites dos dados'): src/app/mvp.py
COPY --chown=sulco:sulco experimentos/avaliacao_195/RESULTADO.md ./experimentos/avaliacao_195/RESULTADO.md
COPY --chown=sulco:sulco docs/04_RETOMADA.md ./docs/04_RETOMADA.md
COPY --from=indice --chown=sulco:sulco /app/indice ./indice
COPY --from=cache --chown=sulco:sulco /app/data/processed/modelos/cache_api_previsao.joblib ./data/processed/modelos/cache_api_previsao.joblib
COPY --chown=root:root docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh \
 && mkdir -p /app/data/processed/llm_cache \
 && chown -R sulco:sulco /app/data/processed/llm_cache /app/data/processed/modelos
USER sulco
EXPOSE 8000 8501
# Sem HEALTHCHECK aqui: a imagem serve dois processos. Os healthchecks ficam no docker-compose.yml
# (API: GET /saude; app: GET /_stcore/health).
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["api"]

# ---------------------------------------------------------------- test (CI)
FROM runtime AS test
USER root
COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt
COPY --chown=sulco:sulco tests ./tests
USER sulco
ENTRYPOINT []
CMD ["python", "-m", "pytest", "-q", "-W", "error", "--ignore=tests/test_rag.py"]

# O alvo final é o ÚLTIMO estágio do arquivo quando nenhum --target é dado. Para que `docker build .` produza a imagem
# de produção (e não a de teste), o estágio de produção é reapontado aqui:
FROM runtime AS final
