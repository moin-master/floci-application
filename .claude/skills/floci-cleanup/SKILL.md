---
name: floci-cleanup
description: Fully clean up the Floci environment (Terraform resources, Floci containers, Docker volumes and networks, local state files) and verify nothing is left. Use when the user says clean up, reset, wipe or start from scratch for Floci, or when a deploy fails with stale state such as RepositoryAlreadyExists.
---

# Floci cleanup

Goal: leave no Floci state behind, then prove it.

## Steps

1. Do not run this while `scripts/deploy.sh`, `scripts/e2e.sh` or `scripts/delta.sh` is running (check with `pgrep -fl "scripts/"`). Wait or ask.
2. Run `scripts/destroy.sh` from the project root. It runs `terraform destroy`, removes every `floci-aws*` container, runs `docker compose down -v`, removes the `floci-aws-ecr-registry-data` volume, and deletes `updater/build`, `updater/updater.zip`, `terraform/.terraform` and `terraform/terraform.tfstate*`.
3. Verify nothing is left (all of these should print nothing):

```bash
docker ps -a --format '{{.Names}}' | grep -i floci
docker volume ls --format '{{.Name}}' | grep -i floci
docker network ls --format '{{.Name}}' | grep -i floci
ls terraform/.terraform terraform/terraform.tfstate* updater/build updater/updater.zip 2>/dev/null
```

4. If something remains, remove only that leftover, by exact name: `docker rm -f <name>`, `docker volume rm <name>`, `docker network rm <name>`. Never use `docker system prune` or touch containers and volumes that are not Floci's.
5. Report what was removed and what, if anything, you had to remove by hand. A Docker image cache (`floci-e2e`, `hashicorp/terraform`, Floci's own image) is kept on purpose; mention it, and remove it only if the user asks.

## Notes
- This deletes all Floci data. It is a local emulator, but if the user only said "stop", use `docker compose stop` instead.
- Afterwards, `scripts/deploy.sh` rebuilds from scratch.
