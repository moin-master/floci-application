#!/usr/bin/env bash
# End-to-end tests against the deployed stack. Run scripts/deploy.sh first.
set -euo pipefail
cd "$(dirname "$0")/.."

NET="$(docker inspect floci --format '{{ index .Config.Labels "com.docker.compose.project" }}')_default"
ALB_DNS=$(scripts/tf.sh output -raw alb_dns)

REPORT_DIR="${REPORT_DIR:-reports/latest}"; mkdir -p "$REPORT_DIR"
docker build -q -t floci-e2e tests/e2e >/dev/null
docker run --rm --network "$NET" -v "$PWD/tests/e2e:/tests:ro" -v "$PWD/$REPORT_DIR:/report" -e ALB_DNS="$ALB_DNS" "$@" floci-e2e
