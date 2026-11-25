---
description: Delete old run reports in reports/, keep only the latest 3
---
Run `DRY_RUN=1 scripts/clean-reports.sh` first and show the user which `reports/<timestamp>` folders would be deleted and which 3 are kept. If nothing would be deleted, say so and stop.

Then run `scripts/clean-reports.sh` (default keeps the newest 3; pass a number to change it, e.g. `scripts/clean-reports.sh 5`). Confirm what was deleted and that `reports/latest` still points at the newest run. Only `reports/YYYYMMDD-HHMMSS` folders are touched; never delete anything else.
