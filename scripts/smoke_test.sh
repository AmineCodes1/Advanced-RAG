#!/usr/bin/env sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-docker/docker-compose.yml}"
BASE_URL="${BASE_URL:-http://localhost:8000}"

cleanup() {
  docker compose -f "$COMPOSE_FILE" down
}
trap cleanup EXIT

docker compose -f "$COMPOSE_FILE" up -d --build
attempts=0
until curl --fail --silent "$BASE_URL/health" | grep -q '"status":"ok"'; do
  attempts=$((attempts + 1))
  [ "$attempts" -lt 30 ] || { echo "Backend did not become ready" >&2; exit 1; }
  sleep 2
done

curl --fail --silent -N -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"question":"Smoke test: what is in the document?"}' |
  grep -q 'event: done'
echo "GraphRAG smoke test passed."
