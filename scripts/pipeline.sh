#!/usr/bin/env bash
# The whole flow in one command:
#   1 destroy old env -> 2 build new env -> 3 match/delta check -> 4 e2e tests -> 5 readable report
# Later steps still run if an earlier check fails, so the report shows everything. Exit code 1 if anything failed.
cd "$(dirname "$0")/.."
# Every run gets its own folder: reports/YYYYMMDD-HHMMSS (reports/latest points at the newest)
export REPORT_DIR="reports/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$REPORT_DIR"; ln -sfn "$(basename "$REPORT_DIR")" reports/latest
exec > >(tee "$REPORT_DIR/pipeline.log") 2>&1   # full log of the run goes into the same folder
echo "Reports for this run: $REPORT_DIR"
fail=0
step() { echo; echo "=================== $1 ==================="; }

step "1/5 Destroy existing environment"
scripts/destroy.sh >/dev/null 2>&1; echo "done"

step "2/5 Build new environment"
scripts/deploy.sh || { echo "BUILD FAILED"; echo "Build failed, see output above" > "$REPORT_DIR/summary.md"; exit 1; }

step "3/5 Check match and delta against the production diagram"
scripts/delta.sh | tee "$REPORT_DIR/delta.txt" || fail=1

step "4/5 Run end-to-end tests"
scripts/e2e.sh >/dev/null 2>&1 || fail=1
echo "done (details in the report)"

step "5/5 Report"
python3 scripts/report.py || fail=1
exit $fail
