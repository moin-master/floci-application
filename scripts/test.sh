#!/usr/bin/env bash
# Smoke test: run the Lambda once, then read a price through the load balancer.
set -euo pipefail
cd "$(dirname "$0")/.."

ALB=$(scripts/tf.sh output -raw alb_dns)
AUTH='Authorization: AWS4-HMAC-SHA256 Credential=test/20260101/us-east-1/lambda/aws4_request'

echo "- invoking the updater Lambda"
curl -sf -X POST -H "$AUTH" -d '{}' localhost:4566/2015-03-31/functions/stock-updater/invocations; echo

echo "- calling the API through the ALB (waiting for ECS tasks to become healthy)"
for i in $(seq 1 40); do
  if out=$(curl -sf -m 5 -H "Host: $ALB" localhost:8080/stocks/AAPL); then
    echo "$out"; echo "OK: API served a price from ElastiCache"; exit 0
  fi
  sleep 3
done
echo "FAILED: API did not answer. Check: docker logs floci | tail -50" >&2
exit 1
