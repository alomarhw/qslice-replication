#!/usr/bin/env bash
# Run the tool's tests, regenerate the paper's numbers and scale figure from the committed results, and build the paper.
#   bash reproduce.sh
# A regenerated numbers.tex or fig_scale.tex that differs from the shipped copy fails the run.
set -euo pipefail
cd "$(dirname "$0")"
PY=""
for c in python3.12 python3.11; do command -v "$c" >/dev/null && { PY=$c; break; }; done
[ -n "$PY" ] || { echo "needs Python 3.11 or 3.12"; exit 1; }
[ -x .venv/bin/python ] || { "$PY" -m venv .venv && .venv/bin/pip install -q -r experiments/requirements.lock; }
V="$PWD/.venv/bin/python"; status=0
tmp=$(mktemp -d)

echo "== data"
"$V" fetch_data.py --verify || echo "(QASMBench is fetched by: python fetch_data.py; needed only for the runs)"

echo "== tool tests"
command -v srcml >/dev/null || { echo "srcml 1.1.0 not on the PATH"; status=1; }
"$V" -m srcslice_q.tests.test_qasm_srcml | tail -1 || status=1
"$V" -m srcslice_q.tests.test_qasm3_grammar | tail -2 || status=1
"$V" -m srcslice_q.tests.check_trace srcslice_q/tests/programs/*.py srcslice_q/tests/big/*.py >/dev/null && echo "traces: ok" || status=1

echo "== numbers and the scale figure"
cp paper/numbers.tex "$tmp/numbers.tex"; cp paper/figures/src/fig_scale.tex "$tmp/fig_scale.tex"
( cd experiments && "$V" icpc/make_numbers_b.py && "$V" icpc/make_fig_scale.py >/dev/null ) || status=1
cmp -s paper/numbers.tex "$tmp/numbers.tex" && echo "numbers.tex: identical to the shipped copy" \
  || { echo "numbers.tex differs from the shipped copy"; status=1; }
cmp -s paper/figures/src/fig_scale.tex "$tmp/fig_scale.tex" && echo "fig_scale.tex: identical to the shipped copy" \
  || { echo "fig_scale.tex differs from the shipped copy"; status=1; }

echo "== paper"
( cd paper && pdflatex -interaction=nonstopmode main >/dev/null; bibtex main >/dev/null; \
  pdflatex -interaction=nonstopmode main >/dev/null; pdflatex -interaction=nonstopmode main >/dev/null \
  && echo "paper/main.pdf built" ) || status=1
rm -rf "$tmp"
exit $status
