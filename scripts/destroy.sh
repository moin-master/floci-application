#!/usr/bin/env bash
# Tear everything down: Terraform resources first, then Floci itself.
set -uo pipefail
cd "$(dirname "$0")/.."
scripts/tf.sh destroy -auto-approve -input=false || true
# Floci starts real containers (Lambda, Redis, ECS tasks, ECR registry); remove them too
docker ps -aq --filter name=floci-aws | xargs -r docker rm -f >/dev/null
docker compose down -v
docker volume rm floci-aws-ecr-registry-data >/dev/null 2>&1 || true   # the ECR registry's image storage
rm -rf updater/build updater/updater.zip terraform/.terraform terraform/terraform.tfstate*
