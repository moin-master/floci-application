---
description: Full run - destroy Floci env, rebuild it, check match/delta against the diagram, run e2e, show a readable report
---
Run `scripts/pipeline.sh` from the project root. It takes about 5 to 6 minutes, so run it in the background and wait for it to finish. Do not start a second copy while one is running.

It does 5 steps: destroy the old environment, build a new one, check match and delta against diagram A (`docs/architecture.md`), run the e2e tests, and write a report (sections C Match, D Delta, E Behaviour, then a verdict) to `reports/<timestamp>/summary.md` (`reports/latest` points at the newest).

When it finishes, read `reports/latest/summary.md` and show it in the chat in plain language: the match percentage with any GAP rows (C), the delta table of known differences (D), how many e2e tests passed grouped by question (E), and the verdict. If something failed, say which step and why, using `reports/latest/pipeline.log`. Do not change code unless the user asks.
