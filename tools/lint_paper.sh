#!/bin/sh
# Writing checks for the rewrite (paper/new, the paper only; story.tex is a planning note). "Static" is defined once, in the sentence marked
# % static-definition; elsewhere the text says "static", never "without running" or "without executing".
set -eu
cd "$(dirname "$0")/../paper/new"
fail=0
hits=$(grep -rniE "without (running|executing)" --include='*.tex' sections main.tex | grep -v "static-definition" || true)
[ -n "$hits" ] && { echo "FAIL: say 'static' (defined once):"; echo "$hits"; fail=1; }
n=$(grep -rc "static-definition" --include='*.tex' sections main.tex | awk -F: '{s+=$2} END {print s+0}')
[ "$n" -le 1 ] || { echo "FAIL: static is defined $n times"; fail=1; }
hits=$(grep -rnE "\((Fig|Figs|Table|Tables|Section|Sec)\.?~?\\\\ref" --include='*.tex' sections main.tex || true)
[ -n "$hits" ] && { echo "FAIL: parenthetical reference; say 'see Table I' or 'Fig. 2 shows':"; echo "$hits"; fail=1; }
[ $fail -eq 0 ] && echo "lint ok"
exit $fail
