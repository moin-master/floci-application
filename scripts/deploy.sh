#!/usr/bin/env bash
# One command: start Floci, run Terraform, push the image, smoke-test the API.
set -euo pipefail
cd "$(dirname "$0")/.."

ECR_URI="000000000000.dkr.ecr.us-east-1.localhost:4566/stock-api"

echo "==> 1/6 Starting Floci"
docker compose up -d floci
until curl -sf localhost:4566/_floci/health >/dev/null; do sleep 1; done

echo "==> 2/6 Packaging the Lambda (code + dependencies)"
rm -rf updater/build && mkdir -p updater/build
docker run --rm -v "$PWD/updater:/u" python:3.12-slim sh -c \
  "pip install -q --disable-pip-version-check --root-user-action=ignore -r /u/requirements.txt -t /u/build && cp /u/handler.py /u/build/"

echo "==> 3/6 Terraform: creating the ECR repository"
scripts/tf.sh init -input=false >/dev/null
scripts/tf.sh apply -auto-approve -input=false -target=aws_ecr_repository.api >/dev/null

echo "==> 4/6 Building and pushing the API image to ECR"
docker build -q -t "${ECR_URI}:latest" api >/dev/null
docker push -q "${ECR_URI}:latest" >/dev/null

echo "==> 5/6 Terraform: creating everything else (VPC, Redis, Lambda, ECS, ALB)"
scripts/tf.sh apply -auto-approve -input=false

echo "==> 6/6 Smoke test"
scripts/test.sh
