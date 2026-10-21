#!/usr/bin/env bash
# Runs the three pre-registered experiments once (PROTOCOL.md). Usage: bash run_all.sh DATA_ROOT PACKAGE_ROOT
set -u
cd "$(dirname "$0")"
D="$1"; P="$2"; PY="${PYTHON:-python}"
echo "commit $(git rev-parse HEAD 2>/dev/null) start $(date)"
"$PY" rq4_ablation_rerun/run.py --data-root "$D" --eval-code "$P/reported_results/rq1_rq3_rq5" --four-edge "$P/reported_results/rq4_ablation" --out results/rq4_ablation --workers 4 > results_rq4.log 2>&1; echo "rq4 rc=$? $(date)"
"$PY" method_eval/run.py --data-root "$D" --eval-code "$P/reported_results/rq1_rq3_rq5" --method-code "$P/described_method" --variant control-fixed --out results/method_primary --workers 4 > results_m1.log 2>&1; echo "primary rc=$? $(date)"
"$PY" method_eval/run.py --data-root "$D" --eval-code "$P/reported_results/rq1_rq3_rq5" --method-code "$P/described_method" --variant unchanged --out results/method_secondary --workers 4 > results_m2.log 2>&1; echo "secondary rc=$? $(date)"
