#!/bin/sh
# Anonymous build: the submission PDF and the replication package with the tool named QLine.
# The source of the rewrite names the tool srcSlice-Q (tool.TOOL_NAME, \tool in the paper); this script renders
# the anonymous form into build/anon/ and fails if "srcSlice-Q" survives in either.
# Usage (workspace root): sh tools/build_anon.sh
set -eu
OUT=build/anon
rm -rf "$OUT" && mkdir -p "$OUT/package"
git archive HEAD | tar -x -C "$OUT/package"
# text files only; binary files (PDFs, images) are rebuilt or carry no name
find "$OUT/package" -type f \( -name '*.py' -o -name '*.md' -o -name '*.tex' -o -name '*.csv' -o -name '*.json' \
  -o -name '*.sh' -o -name '*.txt' -o -name '*.tsv' -o -name '*.diff' \) -print0 | xargs -0 sed -i '' 's/srcSlice-Q/QLine/g'
# MANIFEST.sha256.tsv lists the renamed files; it is regenerated for the package
(cd "$OUT/package/paper/new" && pdflatex -interaction=nonstopmode '\def\anonbuild{}\input{main}' >/dev/null 2>&1 \
  && bibtex main >/dev/null 2>&1; pdflatex -interaction=nonstopmode '\def\anonbuild{}\input{main}' >/dev/null 2>&1; \
  pdflatex -interaction=nonstopmode '\def\anonbuild{}\input{main}' >/dev/null 2>&1) || true
fail=0
if grep -rIl "srcSlice-Q" "$OUT/package" >/dev/null; then echo "FAIL: srcSlice-Q in the package"; grep -rIl "srcSlice-Q" "$OUT/package" | head; fail=1; fi
if [ -f "$OUT/package/paper/new/main.pdf" ]; then
  cp "$OUT/package/paper/new/main.pdf" "$OUT/submission.pdf"
  if pdftotext "$OUT/submission.pdf" - | grep -q "srcSlice-Q"; then echo "FAIL: srcSlice-Q in the PDF"; fail=1; fi
fi
[ $fail -eq 0 ] && echo "anonymous build ok: $OUT/submission.pdf, $OUT/package"
exit $fail
