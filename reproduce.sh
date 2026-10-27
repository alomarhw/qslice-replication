#!/usr/bin/env bash
# Regenerate the paper's numbers, figures and PDF from the committed results, and run the checks.
#   bash reproduce.sh            corpora check, oracle and tool checks, numbers, figures, paper, Isabelle
#   bash reproduce.sh --earlier  also re-run the earlier run whose protocol PROTOCOL_ICPC.md extends
#                                (experiments/regenerate.py; compares with experiments/results/ byte for byte)
# The full study (hours) is listed in README.md, section "The study".
# Optional corpora, read and never executed: set TEXTBOOK_ROOT (Qiskit textbook) to regenerate Fig. 1, and
# BUGS4Q_ROOT (Bugs4Q at commit 7a71983) to regenerate the facts of the Section II bug.
# The regenerated numbers.tex is compared with the committed copy; a difference fails the run.
set -euo pipefail
cd "$(dirname "$0")"
EARLIER=0; [ "${1:-}" = "--earlier" ] && EARLIER=1
PY=""
for c in python3.12 python3.11; do command -v "$c" >/dev/null && { PY=$c; break; }; done
[ -n "$PY" ] || { echo "needs Python 3.11 or 3.12"; exit 1; }
[ -x .venv/bin/python ] || { "$PY" -m venv .venv && .venv/bin/pip install -q -r experiments/requirements.lock; }
V="$PWD/.venv/bin/python"; status=0

echo "== corpora"
"$V" fetch_data.py --verify || status=1

echo "== oracle checks"
( cd experiments && "$V" tests/test_oracle.py && "$V" tests/test_oracle_icpc.py ) || status=1

echo "== static slicer checks"
"$V" -m tool.tests.dev_summary || status=1
"$V" -m tool.tests.nested_check || status=1

echo "== figures from the study's code"
( cd experiments
  "$V" ../paper/figures/src/make_fig_programs.py
  "$V" ../paper/figures/src/make_fig_pdg.py
  "$V" ../paper/figures/src/make_fig_example.py
  [ -n "${TEXTBOOK_ROOT:-}" ] && "$V" ../paper/figures/src/make_fig_bv.py "$TEXTBOOK_ROOT"
  [ -n "${BUGS4Q_ROOT:-}" ] && "$V" ../paper/figures/src/make_fig_motivating.py "$BUGS4Q_ROOT"
  "$V" icpc/make_result_figs.py ) || status=1
"$V" paper/figures/src/make_fig_tool.py || status=1

echo "== numbers"
( cd experiments && "$V" icpc/make_numbers.py ) || status=1
git diff --quiet -- paper/numbers.tex experiments/results/icpc/numbers.json \
  && echo "numbers.tex: identical to the committed copy" \
  || { echo "numbers.tex differs from the committed copy"; status=1; }

echo "== paper"
( cd paper/figures/src && for f in fig_*.tex; do pdflatex -interaction=nonstopmode "$f" >/dev/null || exit 1; done ) || status=1
for f in fig_bv fig_pdg_ansatz fig_tool fig_size fig_robust fig_cost; do cp "paper/figures/src/$f.pdf" "paper/figures/$f.pdf"; done
( cd paper && latexmk -pdf -interaction=nonstopmode -silent main.tex >/dev/null && echo "main.pdf built" ) || status=1

echo "== Isabelle"
if command -v isabelle >/dev/null; then
  tmp=$(mktemp -d); cp isabelle/QSliceSoundness.thy isabelle/ROOT "$tmp"/
  ( cd "$tmp" && isabelle build -d . QSliceSoundness ) && echo "isabelle build: exit 0" || status=1
  rm -rf "$tmp"
else
  echo "isabelle not found; skipped"
fi

if [ $EARLIER = 1 ]; then
  echo "== earlier run"
  ( cd experiments && "$V" regenerate.py ) || status=1
fi
exit $status
