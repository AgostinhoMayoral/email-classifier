#!/bin/sh
# Script de startup para Railway (e outros PaaS).
# Cria credentials.json a partir de GOOGLE_CREDENTIALS_JSON se definido.
set -e

if [ -n "$GOOGLE_CREDENTIALS_JSON" ]; then
  printf '%s' "$GOOGLE_CREDENTIALS_JSON" > credentials.json
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
