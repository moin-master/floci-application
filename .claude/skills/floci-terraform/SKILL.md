---
name: floci-terraform
description: Run Terraform against the local Floci AWS emulator (init, plan, apply, output, destroy) through scripts/tf.sh, in the right order. Use when the user asks to run, rerun, plan or apply Terraform on Floci, or to check Terraform state or outputs.
---

# Run Terraform on Floci

Terraform runs in a container (`scripts/tf.sh`), never locally. It talks to `http://floci:4566` on the Floci Docker network, so Floci must be running first.

## Full run (normal case)
Use `scripts/deploy.sh`. It does the steps in the only order that works:
1. start Floci (`docker compose up -d floci`) and wait for `/_floci/health`
2. package the Lambda into `updater/build` (the Terraform zips this folder)
3. `terraform init`, then apply only `-target=aws_ecr_repository.api` (the image needs a repo to be pushed to)
4. `docker build` and `docker push` the API image to the emulated ECR
5. full `terraform apply` (VPC, subnets, IGW, NAT, SGs, Redis, Lambda, ECS, ALB)
6. smoke test (`scripts/test.sh`)

It takes several minutes (the ALB alone takes about a minute); run it in the background and wait for completion. Never start a second copy while one is running.

## Single Terraform commands
Only when Floci is up and the image is already pushed:
```bash
scripts/tf.sh plan -input=false
scripts/tf.sh apply -auto-approve -input=false
scripts/tf.sh output
scripts/tf.sh state list
```
Running a bare `apply` on a fresh Floci fails: the Lambda needs `updater/build` and ECS needs the pushed image. Use `scripts/deploy.sh` instead.

## Failure handling
- Read the Terraform error and `docker logs floci | tail -50`.
- `RepositoryAlreadyExists` or other stale-state errors: run the floci-cleanup skill, then deploy again.
- Floci state and Terraform state must go together. After a Floci restart that lost data, delete `terraform/terraform.tfstate*` (floci-cleanup does this).
- Do not edit `terraform.tfstate` by hand.

## After a successful run
1. `scripts/delta.sh` to compare with diagram A (expect 24/24).
2. Report the ALB DNS from `scripts/tf.sh output -raw alb_dns` and one `curl -H "Host: <alb>" localhost:8080/stocks/AAPL` result.
