#!/usr/bin/env bash
# Delete old run reports, keep the newest N (default 3). Only touches reports/YYYYMMDD-HHMMSS folders.
# Usage: scripts/clean-reports.sh [keep]      (set DRY_RUN=1 to only list what would be deleted)
set -euo pipefail
cd "$(dirname "$0")/.."
KEEP="${1:-3}"
DIR="${REPORTS_DIR:-reports}"
[ -d "$DIR" ] || { echo "No $DIR folder, nothing to clean."; exit 0; }

# timestamp folder names sort oldest -> newest
runs=$(ls -1 "$DIR" | grep -E '^[0-9]{8}-[0-9]{6}$' || true)
total=$(printf '%s\n' "$runs" | grep -c . || true)
if [ "$total" -le "$KEEP" ]; then echo "$total run folder(s), keeping all (limit $KEEP)."; exit 0; fi

old=$(printf '%s\n' "$runs" | head -n $((total - KEEP)))
for d in $old; do
  if [ "${DRY_RUN:-0}" = 1 ]; then echo "would delete $DIR/$d"; else rm -rf "${DIR:?}/$d" && echo "deleted $DIR/$d"; fi
done
# keep the 'latest' link pointing at the newest remaining run
newest=$(printf '%s\n' "$runs" | tail -n 1)
[ "${DRY_RUN:-0}" = 1 ] || ln -sfn "$newest" "$DIR/latest"
echo "Kept the newest $KEEP: $(printf '%s\n' "$runs" | tail -n "$KEEP" | tr '\n' ' ')"
