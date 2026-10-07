#!/usr/bin/env bash
# Выкладка полного стенда fsp-talent на сервер: свежий main → сборка фронта (реальный API) → пересборка бэкенда → Caddy.
# Запуск на сервере: /opt/fsp-talent/app/infra/stand/deploy.sh  (рядом должен лежать .env, см. .env.example)
set -euo pipefail
APP=/opt/fsp-talent/app
STAND="$APP/infra/stand"
cd "$APP"
git fetch -q origin main && git reset -q --hard origin/main
echo "версия: $(git log --oneline -1)"

# фронт: режим реального API, сборка в одноразовом контейнере node
docker run --rm -v "$APP":/app -w /app/frontend -e VITE_USE_MOCKS=false node:22-alpine \
  sh -c "npm ci --no-audit --no-fund --loglevel=error && npx vite build --logLevel error"
mkdir -p "$STAND/site"
# копируем содержимое на место: Caddy держит примонтированную папку, подменять её нельзя
find "$STAND/site" -mindepth 1 -delete
cp -r "$APP/frontend/dist/." "$STAND/site/"

cd "$STAND"
docker compose --env-file .env up -d --build --remove-orphans
docker compose --env-file .env exec -T backend python -m app.testing.sync_bank | tail -1
echo "стенд обновлён: https://$(grep ^STAND_HOST= .env | cut -d= -f2)"
