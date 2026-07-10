#!/bin/sh
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Importing/refreshing master medicine catalogue..."
python manage.py import_medicines || echo "Medicine import skipped/failed (continuing startup)"

echo "Starting server..."
exec gunicorn multirx.wsgi:application --bind 0.0.0.0:${PORT:-8000} --timeout 120
