#!/usr/bin/env bash
# Makes the screenshots and the walkthrough in docs/showcase/ on a fresh
# database: the made-up clinic loaded into HAPI FHIR, its two users, and
# Claude's summaries replayed from the recordings (no key, no cost).
# Needs Postgres, Mailpit and HAPI FHIR (docker compose --profile fhir up -d),
# a built web app and ffmpeg.
set -euo pipefail
cd "$(dirname "$0")/.."

db=record_access_showcase
admin_url="${DATABASE_URL:-postgresql://record_access:record_access@localhost:5432/record_access}"
psql "$admin_url" -q -c "drop database if exists $db with (force)"
psql "$admin_url" -q -c "create database $db"
export DATABASE_URL="${admin_url%/*}/$db"
export PUBLIC_BASE_URL=http://127.0.0.1:8020 BIND_ADDR=127.0.0.1:8020
uv run -q record-access-audit migrate >/dev/null
uv run -q record-access-audit add-user --email privacy@clinic.example.test --name "Alex Example" --role "privacy officer" >/dev/null
uv run -q record-access-audit add-user --email admin@clinic.example.test --name "Example Administrator" --role administrator >/dev/null
uv run -q record-access-audit load-made-up >/dev/null
curl -s -X DELETE http://127.0.0.1:8025/api/v1/messages >/dev/null

OWNER_ANTHROPIC_API_KEY= uv run -q record-access-audit serve --recorded >showcase-server.log 2>&1 &
server=$!
trap 'kill $server' EXIT
for _ in $(seq 1 30); do curl -sf http://127.0.0.1:8020/health >/dev/null && break; sleep 1; done

(cd web && pnpm exec playwright test --config showcase/playwright.config.ts --trace off)
