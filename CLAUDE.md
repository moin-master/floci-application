# Project: Stock Price API on Floci

Simple POC: FastAPI (ECS) reads prices from ElastiCache Redis; a Lambda refreshes them hourly. Terraform deploys it all to the Floci AWS emulator (Docker Compose). See README.md.

## Rules
- Keep it simple and beginner friendly. No unit tests (the user does not want them). Verification is end-to-end: `scripts/e2e.sh` (pytest in Docker, needs a deployed stack), plus `scripts/verify.sh` and `scripts/test.sh` as quick checks.
- Terraform runs in a container via `scripts/tf.sh`; do not require a local Terraform install.
- "Deploy" means `scripts/deploy.sh`. "Tear down / reset" means `scripts/destroy.sh`.
- Use `${VAR}:tag` with braces in shell (zsh treats `$VAR:l` as a modifier).

## Gotchas learned
- Floci state lives in Docker volumes (`/app/data` anonymous volume and `floci-aws-ecr-registry-data`); `destroy.sh` removes both. Stale volumes cause "RepositoryAlreadyExists".
- Floci reports ElastiCache as `localhost`; Terraform var `redis_host_override` points containers at `floci`.
- ALB is reachable at `localhost:8080` with `Host: <alb dns>`.
- Floci runs ECS tasks in one AZ even with two subnets; do not claim real multi-AZ was tested.
- Terraform is split by component (`terraform/*.tf`, one folder, one state). A plan on a deployed stack shows 3 harmless in-place changes on security group rules: Floci reads back `referenced_security_group_id` with an account prefix. Not caused by code changes.
