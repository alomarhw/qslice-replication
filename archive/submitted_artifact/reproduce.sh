#!/usr/bin/env bash
# Regenerate everything in this package that can be regenerated, and compare with the reported files.
# Nothing in the package is overwritten; every run happens in a temporary directory.
#   bash reproduce.sh           full: fetch QASMBench (~165 MB), RQ1-RQ3, RQ5, RQ7, Isabelle
#   bash reproduce.sh --quick   skip the QASMBench download and the RQ5 scalability scan
# Not regenerated, because the producing code or inputs do not exist: Table VI / Fig. 2 (see
# PROVENANCE.md, D2). Figs. 1 and 4 are redrawn by new scripts (redrawn_figures/).
set -euo pipefail
cd "$(dirname "$0")"
QUICK=0; CORR=0
for a in "$@"; do case "$a" in --quick) QUICK=1;; --corrected) CORR=1;; esac; done

PY=""
for c in python3.12 python3.11; do command -v "$c" >/dev/null && { PY=$c; break; }; done
[ -n "$PY" ] || { echo "needs Python 3.11 or 3.12 (numpy 1.26.4 has no wheels for newer versions)"; exit 1; }

if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv
  # The pinned numerical stack from reported_results/rq1_rq3_rq5/requirements.txt (byte identity
  # depends on numpy 1.26.4), plus qiskit-ibm-runtime to decode the captured hardware jobs.
  .venv/bin/pip install -q numpy==1.26.4 scipy==1.13.1 pandas==2.2.2 matplotlib==3.9.1
  .venv/bin/pip install -q "qiskit-ibm-runtime>=0.40" networkx==3.4.2 "numpy==1.26.4"
fi
P="$PWD/.venv/bin/python"
status=0

echo "== corpora"
if [ $QUICK = 1 ]; then "$P" fetch_data.py --verify || status=1
else "$P" fetch_data.py || status=1; fi

echo "== RQ1-RQ3 (Tables III-V) and RQ5 (Table VII, Fig. 3)"
( cd reported_results/rq1_rq3_rq5
  if [ $QUICK = 1 ]; then "$P" regenerate.py --skip-scalability; else "$P" regenerate.py; fi ) || status=1

echo "== RQ7 (Table IX, Fig. 5) from the captured IBM jobs"
( cd reported_results/rq7_hardware && "$P" regenerate.py ) || status=1

echo "== RQ6 Isabelle build (Table VIII); see PROVENANCE.md D3: building does not validate the claim"
if command -v isabelle >/dev/null; then
  tmp=$(mktemp -d); cp reported_results/rq6_isabelle/ROOT reported_results/rq6_isabelle/*.thy "$tmp"/
  ( cd "$tmp" && isabelle build -d . QSlicePreserv ) && echo "isabelle build: exit 0" || status=1
  rm -rf "$tmp"
else
  echo "isabelle not found; skipped"
fi

echo "== Figs. 1 and 4 redrawn from their sources (original drawing scripts not saved) -> redrawn_figures/out/"
( cd redrawn_figures && "$P" fig1_qpdg_teleportation.py out && "$P" fig4_proof_obligations.py out ) || status=1

if [ $CORR = 1 ]; then
  echo "== corrected experiments (corrected_results/, pre-registered): rerun and compare byte for byte"
  [ -x .venv-corrected/bin/python ] || { "$PY" -m venv .venv-corrected && .venv-corrected/bin/pip install -q -r corrected_results/requirements.lock; }
  ( cd corrected_results && ../.venv-corrected/bin/python tests/test_oracle.py && ../.venv-corrected/bin/python regenerate.py ) || status=1
fi

echo "== Table VI / Fig. 2 (submitted): not reproducible (no driver or circuit list was saved); see reported_results/rq4_ablation/README.md; replaced by corrected_results/"
exit $status
