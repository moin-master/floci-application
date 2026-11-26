---
name: architecture-comparison-report
description: Write docs/architecture-comparison-report.md comparing the production AWS diagram (A) with what is actually running in Floci (B), with match and delta tables backed by a fresh run of scripts/delta.sh. Use when the user asks for the architecture comparison, match/delta report, or a diagram gap report.
---

# Architecture comparison report

Produce `docs/architecture-comparison-report.md`. Sections C (Match) and D (Delta) are the same ones `scripts/report.py` puts in every pipeline report (`reports/latest/summary.md`); reuse them, built from the fresh `delta.sh` output and section D of `docs/match-delta.md`, instead of writing them from memory. Every claim in it must come from a run you did now, not from memory or from the old doc.

## Steps

1. Confirm the stack is deployed: `docker ps --format '{{.Names}}' | grep -x floci`. If not, ask the user whether to run `scripts/deploy.sh` first. Do not report on a stack that is not running.
2. Collect evidence (keep the raw output):
   - `scripts/delta.sh` for the PASS/GAP list and the percentage.
   - `scripts/verify.sh` for the quick infrastructure and API checks.
   - `scripts/e2e.sh` for the test count (skip only if the user asks for a quick report, and say so in the report).
3. Read diagram A and the built layout from `docs/architecture.md` and the `terraform/*.tf` files, so the report compares the current design and the current code.
4. Write the report in this order, plain language, no unexplained jargon:

```markdown
# Architecture comparison report: AWS vs Floci
Date, Floci image/version if shown by `curl localhost:4566/_floci/health`, and the commands run.

## Summary
One short paragraph: match percentage (N of M checks), number of gaps, verdict (does Floci represent the production design?).

## A. AWS (production target)
Diagram A copied from docs/architecture.md.

## B. Floci (as built)
Diagram B copied from docs/architecture.md, plus the resource counts from Terraform.

## C. Match
Table: element in A | what Floci reports | result. One row per delta.sh check.

## D. Delta
Table: topic | AWS | Floci | why | risk if moved to real AWS.
Include every GAP from delta.sh and every known emulator limit (Redis host override, ALB via localhost:8080, Lambda VPC not enforced, NAT/IGW carry no traffic, one service per subnet).

## E. Evidence
The raw delta.sh summary line, verify.sh result, e2e result (passed/failed counts).

## F. Conclusion and next steps
What was missed, what to change in A or in Terraform, and what Floci cannot prove.
```

5. Rules:
   - A GAP in delta.sh must appear in D. Never turn a failure into a PASS, and never round up the percentage.
   - A PASS means Floci reports the resource as configured, not that traffic flows. Say this in the report.
   - If A and the Terraform disagree (the diagram changed but the code did not), list that as a delta too.
   - Do not claim real multi-AZ behaviour was tested (project rule in CLAUDE.md).
6. Tell the user the file path and the headline result (match percentage, number of gaps). Do not paste the whole report.
