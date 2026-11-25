#!/usr/bin/env bash
# Run terraform inside a container, on the same Docker network as Floci.
# Usage: scripts/tf.sh <terraform args>
set -euo pipefail
cd "$(dirname "$0")/.."
# The compose network (Floci also joins extra networks it creates for the emulated VPC)
NET="$(docker inspect floci --format '{{ index .Config.Labels "com.docker.compose.project" }}')_default"
docker run --rm --network "$NET" \
  -v "$PWD/terraform:/work/terraform" -v "$PWD/updater:/work/updater" \
  -w /work/terraform hashicorp/terraform:1.9 "$@"
