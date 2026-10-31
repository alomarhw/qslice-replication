"""Which programs srcSlice-Q reads differently when srcML is told the source is UTF-8 (tool-v9; RERUNS.md 2026-11-01).

srcML read Python files in its default encoding before tool-v9, so a program with non-ASCII characters (a name such as
Υ_hat, a string such as 'θ') was marked up with mis-decoded text. For every Python file of the corpora with a non-ASCII
byte, the trace, the interpreter's notes and srcSlice's profiles are computed with srcML reading the file in its default
encoding and as UTF-8, and the files where any of them differ are listed. Files are read, never executed.
Usage (workspace root): python experiments/icpc/encoding_check.py --data-root <data-root>  -> results/icpc/encoding/changed.csv
"""
import argparse
import csv
import glob
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "experiments" / "results" / "icpc" / "encoding"


def parse(path, utf8):
    cmd = ["srcml", "--position", "-l", "Python"] + (["--src-encoding=UTF-8"] if utf8 else []) + [path]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout


def one(path):
    from tool.interp import Interpreter
    out = {}
    for utf8 in (False, True):
        try:
            raw = parse(path, utf8)
            tr = Interpreter(path, 60).run(ET.fromstring(raw))
            ops = [(c.uid, [(o.name, [sorted(s) for s in o.qubits], [sorted(s) for s in o.clbits], sorted(o.cond), o.line,
                             list(o.iters), o.may) for o in c.ops]) for c in tr.circuits]
            with tempfile.TemporaryDirectory() as d:
                x = os.path.join(d, "a.xml")
                open(x, "w").write(raw)
                prof = subprocess.run(["srcslice", x], capture_output=True, text=True, timeout=120).stdout
            out[utf8] = (json.dumps(ops), json.dumps(sorted(m for _, m in tr.notes)), prof)
        except Exception as e:  # recorded as a difference to inspect
            out[utf8] = ("error " + type(e).__name__, "", "")
    a, b = out[False], out[True]
    return path, a[0] == b[0], a[1] == b[1], a[2] == b[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--workers", type=int, default=6)
    root = Path(ap.parse_args().data_root)
    roots = [root / "lintq" / "exp_v08" / "files_selected", root / "bugs4q", root / "textbook_py",
             ROOT / "experiments" / "results" / "icpc" / "qhe" / "programs", ROOT / "tool" / "tests",
             ROOT / "paper" / "figures" / "src" / "programs"]
    files = sorted({f for r in roots for f in glob.glob(str(r) + "/**/*.py", recursive=True)
                    if any(b > 127 for b in open(f, "rb").read())})
    rows = []
    with ProcessPoolExecutor(ap.parse_args().workers) as ex:
        for path, same_ops, same_notes, same_prof in ex.map(one, files, chunksize=4):
            if not (same_ops and same_notes and same_prof):
                rows.append({"file": os.path.relpath(path, root) if path.startswith(str(root)) else os.path.relpath(path, ROOT),
                             "trace_differs": int(not same_ops), "notes_differ": int(not same_notes),
                             "profiles_differ": int(not same_prof)})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "changed.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, ["file", "trace_differs", "notes_differ", "profiles_differ"])
        w.writeheader()
        w.writerows(rows)
    (OUT / "summary.json").write_text(json.dumps({"files_with_non_ascii": len(files), "differ": len(rows)}, indent=1) + "\n")
    print(len(files), "files with non-ASCII bytes;", len(rows), "read differently")


if __name__ == "__main__":
    main()
