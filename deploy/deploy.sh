#!/usr/bin/env bash
# Build and (re)start LitFinder behind Caddy on the server (see docs/deploy-ec2.md).
#
#   deploy/deploy.sh                  # build and start, or apply an update after `git pull`
#   deploy/deploy.sh logs -f web      # any other docker compose command, with the same files
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f backend/.env ] || { echo "Missing backend/.env: cp backend/.env.example backend/.env and fill it in" >&2; exit 1; }
[ -f deploy/.env ] || { echo "Missing deploy/.env: cp deploy/.env.example deploy/.env and fill it in" >&2; exit 1; }

token=$(sed -n 's/^MCP_TOKEN=//p' deploy/.env | tail -n 1)
if [ "${#token}" -lt 32 ]; then
    echo "MCP_TOKEN in deploy/.env must be at least 32 characters (openssl rand -hex 32)" >&2
    exit 1
fi

compose() {
    docker compose --env-file deploy/.env -f docker-compose.yml -f deploy/docker-compose.prod.yml \
        --profile mcp "$@"
}

if [ "$#" -gt 0 ]; then
    compose "$@"
    exit
fi

compose up -d --build --remove-orphans
docker image prune -f >/dev/null  # Drop the images replaced by this build
compose ps
