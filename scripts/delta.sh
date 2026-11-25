#!/usr/bin/env bash
# Diagram delta: does Floci match the production diagram (docs/architecture.md, diagram B)?
# Read-only. Run scripts/deploy.sh first. Exit code is non-zero if any gap is found.
set -euo pipefail
cd "$(dirname "$0")/.."

NET="$(docker inspect floci --format '{{ index .Config.Labels "com.docker.compose.project" }}')_default"
docker build -q -t floci-e2e tests/e2e >/dev/null
docker run --rm --network "$NET" -v "$PWD/tests/delta:/tests:ro" floci-e2e python /tests/check_delta.py
