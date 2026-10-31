"""Workspace check (not shipped): make_numbers_b.py, run into a temporary file, must give every macro Paper B uses the
value it has in paper/numbers.tex. Usage (workspace root): python tools/b_package/check_numbers.py [NUMBERS_B.tex]"""
import re, subprocess, sys, tempfile
from pathlib import Path

def macros_used():
    tex = "".join(p.read_text() for p in [Path("paper/b/main.tex"), *Path("paper/b/sections").glob("*.tex")])
    return set(re.findall(r"\\num[A-Za-z]+", tex))

def load(p):
    return {m.group(1): m.group(2) for l in open(p) if (m := re.match(r"\\newcommand\{(\\num\w+)\}\{(.*)\}  % ", l))}

def main():
    if len(sys.argv) > 1:
        new = load(sys.argv[1])
    else:
        with tempfile.TemporaryDirectory() as d:
            src = Path("experiments/icpc/make_numbers_b.py").read_text()
            src = src.replace('TEX = HERE.parent / "paper" / "numbers.tex"', f'TEX = Path("{d}/n.tex")')
            src = src.replace('(ICPC / "numbers_b.json")', f'(Path("{d}/n.json"))')
            Path("experiments/icpc/_mnb_check.py").write_text(src)
            try:
                subprocess.run([sys.executable, "icpc/_mnb_check.py"], cwd="experiments", check=True, capture_output=True)
            finally:
                Path("experiments/icpc/_mnb_check.py").unlink()
            new = load(f"{d}/n.tex")
    old, used = load("paper/numbers.tex"), macros_used()
    missing = sorted(m for m in used if m not in new)
    diff = sorted(m for m in used if m in new and new[m] != old.get(m))
    print(f"{len(used)} macros used; missing {missing}; different {[(m, old.get(m), new[m]) for m in diff]}")
    sys.exit(1 if missing or diff else 0)

if __name__ == "__main__":
    main()
