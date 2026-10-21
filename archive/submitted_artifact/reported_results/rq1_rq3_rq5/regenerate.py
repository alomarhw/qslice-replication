"""Regenerate the reported RQ1-RQ3 and RQ5 result files with the unchanged evaluation code, and compare
them with the reported copies in reported/.

Runs in a scratch copy so nothing in this folder is overwritten:
  main.py                  -> TAB1.csv, TAB_per_corpus.csv, slice_records.csv, forward_records.csv,
                              run_metadata.json   (compared byte for byte)
                           -> results.json (statistical tests; compared byte for byte, and by parsed
                              content, because the submitted copy was re-serialized with a different key
                              order when the artifact was assembled)
  scripts/scalability.py   -> TAB_scalability.csv (structural columns compared exactly; the
                              qpdg_build_ms column is a wall-clock timing and cannot repeat)
The corpus is read from ../../data (the package's data/ folder). RQ5 needs the full QASMBench tree:
run `python fetch_data.py` at the package root first.

Byte identity needs the pinned numpy 1.26.4 (requirements.txt). Under numpy 2.x the simulated
fidelities differ in the 9th decimal place (at most 4.5e-9); every invalid-slice flag and slice size
is unchanged, but TAB1.csv, TAB_per_corpus.csv and slice_records.csv are then not byte-identical.

Usage: python regenerate.py [--skip-scalability]
"""

from __future__ import annotations

import csv
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent.parent / "data"
CODE = ["main.py", "qdg.py", "qasm_loader.py", "rp_data_runtime.py", "figures_qpdg.py", "manifest.json",
        "scripts/scalability.py"]
EXACT = ["TAB1.csv", "TAB_per_corpus.csv", "slice_records.csv", "forward_records.csv", "run_metadata.json"]
STRUCTURAL = ["circuit", "n_qubits", "n_ops", "entanglement_deps"]


def numeric_diff(a: Path, b: Path) -> str:
    """Summarize a CSV mismatch: which columns differ and by how much."""
    ra, rb = list(csv.DictReader(open(a))), list(csv.DictReader(open(b)))
    if len(ra) != len(rb):
        return f"row counts differ: {len(ra)} vs {len(rb)}"
    worst: dict[str, float] = {}
    for x, y in zip(ra, rb):
        for k in x:
            if x[k] == y[k]:
                continue
            try:
                worst[k] = max(worst.get(k, 0.0), abs(float(x[k]) - float(y[k])))
            except ValueError:
                worst[k] = float("inf")
    return "differing columns (max abs difference): " + ", ".join(f"{k} {v:.2e}" for k, v in worst.items())


def run(cmd, cwd):
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> int:
    skip_scal = "--skip-scalability" in sys.argv
    import numpy
    if numpy.__version__ != "1.26.4":
        print(f"warning: numpy {numpy.__version__}; the reported files were produced with numpy 1.26.4")
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for f in CODE:
            (work / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HERE / f, work / f)
        os.symlink(DATA, work / "data")
        (work / "figures").mkdir()
        run([sys.executable, "main.py"], work)
        for f in EXACT:
            same = filecmp.cmp(work / "results" / f, HERE / "reported" / f, shallow=False)
            ok &= same
            print(f"{'IDENTICAL' if same else 'DIFFERENT':9s}  {f}")
            if not same and f.endswith(".csv"):
                print("           " + numeric_diff(work / "results" / f, HERE / "reported" / f))
        new_j, old_j = work / "results" / "results.json", HERE / "reported" / "results.json"
        if filecmp.cmp(new_j, old_j, shallow=False):
            print("IDENTICAL  results.json")
        else:
            same = json.loads(new_j.read_text()) == json.loads(old_j.read_text())
            ok &= same
            print(f"{'IDENTICAL (content; key order differs)' if same else 'DIFFERENT'}  results.json")
        if not skip_scal:
            run([sys.executable, "scripts/scalability.py"], work)
            new = list(csv.DictReader(open(work / "results" / "TAB_scalability.csv")))
            old = list(csv.DictReader(open(HERE / "reported" / "TAB_scalability.csv")))
            key = lambda rows: [tuple(r[c] for c in STRUCTURAL) for r in rows]  # noqa: E731
            same = key(new) == key(old)
            ok &= same
            print(f"{'IDENTICAL' if same else 'DIFFERENT':9s}  TAB_scalability.csv structural columns "
                  f"({len(new)} vs {len(old)} rows; build-time column not comparable)")
            if not same:
                a, b = set(key(new)), set(key(old))
                print(f"           only regenerated: {len(a - b)}   only reported: {len(b - a)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
