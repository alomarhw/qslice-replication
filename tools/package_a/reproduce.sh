#!/usr/bin/env bash
# Regenerate the paper's numbers, Table V and PDF from the committed results, and run the checks.
#   bash reproduce.sh
# A regenerated numbers.tex that differs from the shipped copy fails the run.
set -euo pipefail
cd "$(dirname "$0")"
PY=""
for c in python3.12 python3.11; do command -v "$c" >/dev/null && { PY=$c; break; }; done
[ -n "$PY" ] || { echo "needs Python 3.11 or 3.12"; exit 1; }
[ -x .venv/bin/python ] || { "$PY" -m venv .venv && .venv/bin/pip install -q -r experiments/requirements.lock; }
V="$PWD/.venv/bin/python"; status=0

echo "== corpora"
"$V" fetch_data.py --verify || status=1

echo "== reference simulator checks"
( cd experiments && "$V" tests/test_oracle.py && "$V" tests/test_oracle_icpc.py ) || status=1

echo "== Table V and numbers"
cp paper/numbers.tex /tmp/numbers.shipped.tex
( cd experiments && "$V" icpc/make_result_figs.py >/dev/null && "$V" icpc/make_numbers.py ) || status=1
cmp -s paper/numbers.tex /tmp/numbers.shipped.tex \
  && echo "numbers.tex: identical to the shipped copy" \
  || { echo "numbers.tex differs from the shipped copy"; status=1; }

echo "== paper"
( cd paper/new && pdflatex -interaction=nonstopmode main >/dev/null; bibtex main >/dev/null; \
  pdflatex -interaction=nonstopmode main >/dev/null; pdflatex -interaction=nonstopmode main >/dev/null \
  && echo "paper/new/main.pdf built" ) || status=1

echo "== Isabelle"
if command -v isabelle >/dev/null; then
  tmp=$(mktemp -d); cp isabelle/SliceSoundness.thy isabelle/ROOT "$tmp"/
  ( cd "$tmp" && isabelle build -d . SliceSoundness ) && echo "isabelle build: exit 0" || status=1
  rm -rf "$tmp"
else
  echo "isabelle not found; skipped"
fi
exit $status
