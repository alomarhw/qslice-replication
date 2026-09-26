#!/usr/bin/env bash
# Runs the pre-registered experiments once (PROTOCOL.md, PROTOCOL_RQ5.md).
# Usage: bash run_all.sh DATA_ROOT REPO_ROOT [--with-rq5]
# Paths were updated for this repository's layout after the runs; the drivers and their arguments are
# unchanged (see PROTOCOL_HISTORY.txt for the frozen commits).
set -u
cd "$(dirname "$0")"
D="$1"; R="$2"; PY="${PYTHON:-python}"
SEL="$R/selection"; FOUR="$R/fouredge"; METHOD="$R/qslice"
echo "start $(date)"
"$PY" rq4_ablation_rerun/run.py --data-root "$D" --eval-code "$SEL" --four-edge "$FOUR" --out results/rq4_ablation --workers 4 > logs/rq4.log 2>&1; echo "rq4 rc=$? $(date)"
"$PY" method_eval/run.py --data-root "$D" --eval-code "$SEL" --method-code "$METHOD" --variant control-fixed --out results/method_primary --workers 4 > logs/method_primary.log 2>&1; echo "primary rc=$? $(date)"
"$PY" method_eval/run.py --data-root "$D" --eval-code "$SEL" --method-code "$METHOD" --variant unchanged --out results/method_secondary --workers 4 > logs/method_secondary.log 2>&1; echo "secondary rc=$? $(date)"
if [ "${3:-}" = "--with-rq5" ]; then
  "$PY" rq5_scalability/run.py --data-root "$D" --eval-code "$SEL" --method-code "$METHOD" --reference rq5_scalability/submitted_table_vii_rows.csv --out results/rq5_scalability > logs/rq5.log 2>&1; echo "rq5 rc=$? $(date)"
fi
