#!/bin/bash
set -e

echo "Running database migrations..."
alembic -c services/ledger/alembic.ini upgrade head

echo "Starting application..."
exec "$@"