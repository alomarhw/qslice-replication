#!/bin/sh
# Paper A's anonymous replication package: the study, its results, the proof and the paper, without the static
# slicer for source code (Paper B) and without names that identify the authors or link the two submissions.
# Usage (workspace root): sh tools/build_package_a.sh   -> build/package-a/ and build/package-a.zip
set -eu
OUT=build/package-a
rm -rf "$OUT" build/package-a.zip && mkdir -p "$OUT"
git archive HEAD | tar -x -C "$OUT"
cd "$OUT"

# ---- what belongs to Paper B or to planning, not to Paper A
rm -rf tool tools paper/b paper/sections paper/main.tex paper/abstract.tex paper/abstract_plain.txt paper/title.txt \
  paper/new/story.tex paper/new/cuts data/lintq_artifact
for f in calls_per_kind coverage_reasons lintq_compare qhe_run rerun_controlflow_files rerun_gate_table scale_run \
  srcslice_classical tool_acceptance unmodelled_calls; do rm -f "experiments/icpc/$f.py"; done
for d in lintq_compare profiles qasm_frontend qhe qhe__rerun-20261028 scale scale__rerun-20261028 scale__rerun-20261029 \
  srcslice srcslice_heldout srcslice_i20 tool_acceptance tool_coverage unmodelled controlflow; do
  rm -rf "experiments/results/icpc/$d"; done
( cd paper/figures && for f in fig_cost fig_llm fig_overview fig_robust fig_scale fig_size fig_tool; do rm -f "$f.pdf"; done
  cd src && rm -f make_fig_tool.py make_fig_overview.py make_fig_bv.py make_fig_pdg.py fig_tool.* fig_overview.* \
    fig_scale.* fig_programs.* fig_example.* fig_motivating.* fig_pdg_teleport.* fig_cost.* fig_llm.* fig_robust.* \
    fig_size.* make_fig_programs.py make_fig_example.py make_fig_motivating.py
  rm -f programs/lintq_fig*.py programs/qchecker_fig5.py )

# ---- names: no tool name, no earlier working title, no author path
git mv -k qslice qdg 2>/dev/null || mv qslice qdg
mv isabelle/QSliceSoundness.thy isabelle/SliceSoundness.thy
find . -type f \( -name '*.py' -o -name '*.md' -o -name '*.tex' -o -name '*.csv' -o -name '*.json' -o -name '*.jsonl' \
  -o -name '*.sh' -o -name '*.txt' -o -name '*.tsv' -o -name '*.thy' -o -name 'ROOT' -o -name '*.diff' -o -name '*.log' \) \
  -print0 | xargs -0 sed -i '' \
    -e 's/QSliceSoundness/SliceSoundness/g' -e 's/srcSlice-Q/the static slicer/g' -e 's/QLine/the static slicer/g' \
    -e 's/QSlice_/Qdg_/g' -e 's/\([^A-Za-z]\)QSlice/\1the slicer/g' -e 's/^QSlice/the slicer/' -e 's/QSlice/Qdg/g' -e 's/from qslice/from qdg/g' -e 's/import qslice/import qdg/g' -e 's/qslice\./qdg./g' \
    -e 's/QSLICE/QDG/g' -e 's/qslice/qdg/g' \
    -e 's#/Users/[A-Za-z0-9_]*/#/home/anon/#g'

# ---- the package's own README and reproduce script; numbers and Table V regenerated without the slicer
cp ../../tools/package_a/README.md README.md
cp ../../tools/package_a/reproduce.sh reproduce.sh
PYV="$(cd ../.. && pwd)/.venv/bin/python"
( cd experiments && "$PYV" icpc/make_result_figs.py >/dev/null && "$PYV" icpc/make_numbers.py >/dev/null )
( cd paper/new && pdflatex -interaction=nonstopmode main >/dev/null 2>&1; bibtex main >/dev/null 2>&1; \
  pdflatex -interaction=nonstopmode main >/dev/null 2>&1; pdflatex -interaction=nonstopmode main >/dev/null 2>&1 ) || true
# the bibliography keeps only the entries the paper cites
"$PYV" - <<'PYEOF'
import re
keys = set()
for m in re.finditer(r'\\citation\{([^}]*)\}', open('paper/new/main.aux').read()):
    keys |= {k.strip() for k in m.group(1).split(',')}
bib = open('paper/references.bib').read()
entries = re.split(r'\n(?=@)', bib)
kept = [e for e in entries if (m := re.match(r'@\w+\{([^,]+),', e.strip())) and m.group(1).strip() in keys]
open('paper/references.bib', 'w').write('\n'.join(e.strip() for e in kept) + '\n')
print(f"bibliography: {len(kept)} cited entries kept")
PYEOF
( cd paper/new && bibtex main >/dev/null 2>&1; pdflatex -interaction=nonstopmode main >/dev/null 2>&1; \
  pdflatex -interaction=nonstopmode main >/dev/null 2>&1 ) || true
find . -type f ! -name MANIFEST.sha256.tsv ! -path './paper/new/main.*' -print0 | sort -z \
  | xargs -0 shasum -a 256 | awk '{print $2"\t"$1}' > MANIFEST.sha256.tsv
cd ..
zip -qr package-a.zip package-a
echo "built build/package-a ($(du -sh package-a | cut -f1)) and build/package-a.zip"
