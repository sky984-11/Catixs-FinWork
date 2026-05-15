#!/bin/sh
set -e

echo "Starting Catixs FinWork"
echo "DB_TYPE=${DB_TYPE:-postgres}"
echo "POSTGRES_HOST=${POSTGRES_HOST:-127.0.0.1}"
echo "POSTGRES_PORT=${POSTGRES_PORT:-5432}"
echo "POSTGRES_DATABASE=${POSTGRES_DATABASE:-finwork}"

exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}"
