---
description: Deploy the stock API to the local Floci AWS emulator with Terraform and smoke-test it
---
Run `scripts/deploy.sh` from the project root. It starts Floci, runs Terraform, pushes the image to the emulated ECR and smoke-tests the API.

If it fails, read the error and `docker logs floci | tail -50`, fix the cause, and re-run (it is safe to re-run). If state looks stale (e.g. RepositoryAlreadyExists), run `scripts/destroy.sh` first.

When it succeeds, report the ALB DNS name and one example `curl -H "Host: <alb>" localhost:8080/stocks/AAPL` result.
