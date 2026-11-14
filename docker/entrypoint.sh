#!/bin/sh
# Escolhe o serviço pelo primeiro argumento: api | app | qualquer outro comando.
set -e
case "$1" in
  api)
    exec uvicorn src.api.main:app --host 0.0.0.0 --port "${API_PORT:-8000}" --no-server-header
    ;;
  app)
    exec streamlit run src/app/app.py \
      --server.address=0.0.0.0 --server.port="${APP_PORT:-8501}" \
      --server.headless=true --browser.gatherUsageStats=false
    ;;
  *)
    exec "$@"
    ;;
esac
