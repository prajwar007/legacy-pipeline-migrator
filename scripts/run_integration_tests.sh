#!/usr/bin/env bash
# Brings up Oracle + SFTP, waits for Oracle to be healthy, runs the real
# integration tests against them, then tears everything down.
#
# Usage:
#   ./scripts/run_integration_tests.sh          # up, test, down
#   ./scripts/run_integration_tests.sh --keep   # up, test, leave containers running
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

export ORACLE_USER="${ORACLE_USER:-migrator}"
export ORACLE_PASSWORD="${ORACLE_PASSWORD:-dev_password}"
export ORACLE_DSN="${ORACLE_DSN:-localhost:1521/${ORACLE_PDB:-FREEPDB1}}"

echo "==> Starting oracle + sftp containers..."
docker compose up -d oracle sftp

echo "==> Waiting for Oracle to report healthy (this can take up to ~60s on first run)..."
until [ "$(docker inspect -f '{{.State.Health.Status}}' legacy-pipeline-oracle 2>/dev/null)" = "healthy" ]; do
    printf '.'
    sleep 5
done
echo " healthy."

echo "==> Running integration tests..."
set +e
pytest -m integration -v
TEST_EXIT_CODE=$?
set -e

if [ "${1:-}" != "--keep" ]; then
    echo "==> Tearing down containers..."
    docker compose down
else
    echo "==> --keep passed, leaving containers running (docker compose down when you're done)."
fi

exit $TEST_EXIT_CODE
