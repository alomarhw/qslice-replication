#!/usr/bin/env bash
# Regenerate every result in this repository and compare it with the shipped copy.
#   bash reproduce.sh          everything: corpora, oracle tests, RQ1-RQ4 (byte for byte),
#                              RQ5 (deterministic columns; long), RQ6 Isabelle, RQ7 hardware table, figures
#   bash reproduce.sh --quick  skip the QASMBench download and RQ5
# Nothing shipped is overwritten: experiments rerun in temporary directories, figures go to figures/out/.
set -euo pipefail
cd "$(dirname "$0")"
QUICK=0; [ "${1:-}" = "--quick" ] && QUICK=1
PY=""
for c in python3.12 python3.11; do command -v "$c" >/dev/null && { PY=$c; break; }; done
[ -n "$PY" ] || { echo "needs Python 3.11 or 3.12"; exit 1; }
[ -x .venv/bin/python ] || { "$PY" -m venv .venv && .venv/bin/pip install -q -r experiments/requirements.lock; }
[ -x .venv-hw/bin/python ] || { "$PY" -m venv .venv-hw && .venv-hw/bin/pip install -q "qiskit-ibm-runtime>=0.40" numpy==1.26.4 matplotlib==3.9.1; }
V="$PWD/.venv/bin/python"; status=0

echo "== corpora"
if [ $QUICK = 1 ]; then "$V" fetch_data.py --verify || status=1; else "$V" fetch_data.py || status=1; fi

echo "== exact oracle checks"
( cd experiments && "$V" tests/test_oracle.py ) || status=1

echo "== experiments (pre-registered): RQ1-RQ3, RQ4$([ $QUICK = 1 ] || echo ', RQ5')"
( cd experiments && if [ $QUICK = 1 ]; then "$V" regenerate.py; else "$V" regenerate.py --with-rq5; fi ) || status=1

echo "== RQ7 hardware table from the captured IBM jobs"
( cd hardware && ../.venv-hw/bin/python regenerate.py ) || status=1

echo "== RQ6 Isabelle"
if command -v isabelle >/dev/null; then
  tmp=$(mktemp -d); cp isabelle/QSliceSoundness.thy isabelle/ROOT "$tmp"/
  ( cd "$tmp" && isabelle build -d . QSliceSoundness ) && echo "isabelle build: exit 0" || status=1
  rm -rf "$tmp"
else
  echo "isabelle not found; skipped"
fi

echo "== figures -> figures/out/"
mkdir -p figures/out
"$V" figures/fig1_qpdg_teleportation.py figures/out || status=1
"$V" figures/fig2_ablation_rerun.py experiments/results/rq4_ablation figures/out/fig2_ablation_rerun.png || status=1
"$V" figures/fig3_scalability.py experiments/results/rq5_scalability figures/out/fig3_scalability.png || status=1
"$V" figures/fig4_isabelle.py figures/out/fig4_isabelle.png || status=1
exit $status
