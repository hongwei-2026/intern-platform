#!/usr/bin/env bash
set -euo pipefail

TS="$(date +%Y%m%d%H%M%S)"
ZIP="/opt/intern-platform-deploy-new.zip"
TARGET="/opt/intern-platform"
PREV="/opt/intern-platform.prev"
NEW="/opt/intern-platform.new"

# Prefer current .env; fall back to previous tree if last deploy left a flat broken tree.
ENV_SRC=""
if [[ -f "${TARGET}/.env" ]]; then
  ENV_SRC="${TARGET}/.env"
elif [[ -f "${PREV}/.env" ]]; then
  ENV_SRC="${PREV}/.env"
else
  ENV_SRC="$(ls -1t /opt/intern-platform.env.bak.* 2>/dev/null | head -n1 || true)"
fi
test -n "$ENV_SRC"
test -f "$ZIP"

ENV_BAK="/opt/intern-platform.env.bak.${TS}"
cp -a "$ENV_SRC" "$ENV_BAK"

rm -rf "$NEW"
mkdir -p "$NEW"
python3 - <<'PY'
import zipfile
from pathlib import Path
zf = zipfile.ZipFile("/opt/intern-platform-deploy-new.zip")
zf.extractall("/opt/intern-platform.new")
root = Path("/opt/intern-platform.new")
assert (root / "src" / "intern_platform" / "__init__.py").is_file(), "bad zip layout: missing src/"
assert (root / "apps" / "web" / "package.json").is_file(), "bad zip layout: missing apps/web"
assert (root / "Dockerfile.api").is_file()
print("extracted", len(zf.namelist()), "files")
print("layout_ok")
PY

cp -a "$ENV_BAK" "${NEW}/.env"
chmod +x "${NEW}/docker/api-entrypoint.sh" || true

# Preserve TLS certs across deploys (not in zip)
CERT_SRC=""
if [[ -d "${TARGET}/certs" ]]; then
  CERT_SRC="${TARGET}/certs"
elif [[ -d "${PREV}/certs" ]]; then
  CERT_SRC="${PREV}/certs"
elif [[ -d "${PREV}.old/certs" ]]; then
  CERT_SRC="${PREV}.old/certs"
fi
if [[ -n "$CERT_SRC" ]]; then
  mkdir -p "${NEW}/certs"
  cp -a "${CERT_SRC}/." "${NEW}/certs/"
fi

# Keep previous good tree if current is broken flat export
if [[ ! -d "${TARGET}/src" && -d "${PREV}/src" ]]; then
  rm -rf "$TARGET"
elif [[ -d "$TARGET" ]]; then
  rm -rf "${PREV}.old"
  mv "$PREV" "${PREV}.old" 2>/dev/null || true
  mv "$TARGET" "$PREV"
fi

mv "$NEW" "$TARGET"
cd "$TARGET"
ls -la
test -d src
test -d apps
test -f docker-compose.yml
test -f .env

docker compose build --pull --no-cache
docker compose up -d --force-recreate
docker compose ps

WEB_PORT="$(grep -E '^WEB_PORT=' .env | cut -d= -f2 | tr -d '\r' || true)"
WEB_PORT="${WEB_PORT:-8080}"
BASE="http://127.0.0.1:${WEB_PORT}"

echo "health:"
curl -sS "${BASE}/api/v1/health"
echo
echo -n "web:"
curl -sS -o /dev/null -w "%{http_code}\n" "${BASE}/"
echo "alembic:"
docker exec intern-platform-api-1 python -c "from sqlalchemy import create_engine,text; import os; e=create_engine(os.environ['DATABASE_URL']); print(list(e.connect().execute(text('select * from alembic_version'))))"
echo "deploy_ok env_bak=$ENV_BAK web_port=$WEB_PORT"
