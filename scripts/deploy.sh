#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
dev=false; down=false; logs=false; rebuild=false; envfile=.env.production
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dev) dev=true;;
    --down) down=true;;
    --logs) logs=true;;
    --rebuild) rebuild=true;;
    --env-file) shift; envfile="${1:?Provide env file}";;
    *) echo "Unknown option: $1" >&2; exit 1;;
  esac
  shift
done
docker info --format '{{.ServerVersion}}'
docker compose version
[[ -f "$envfile" ]] || { echo 'Create a private env file from .env.container.example first.' >&2; exit 1; }
compose=(compose --env-file "$envfile" -f docker-compose.yml)
$dev && compose+=(-f docker-compose.dev.yml)
docker "${compose[@]}" config --quiet
if $down; then docker "${compose[@]}" down; exit 0; fi
up=(up -d --wait --wait-timeout 180)
$rebuild && up+=(--build)
docker "${compose[@]}" "${up[@]}"
echo 'Container health checks passed. Verify authenticated browser login before release.'
if $logs; then docker "${compose[@]}" logs -f; fi
