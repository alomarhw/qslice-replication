"""Re-run the pre-registered experiments in a scratch copy and compare with the shipped results/.

RQ1-RQ4 outputs are compared byte for byte. RQ5 (--with-rq5, needs the full QASMBench from
../fetch_data.py) is compared on its deterministic columns only: the circuit, its sizes and edge counts
for every circuit that completed in both runs. Wall-clock times, memory and limit outcomes depend on
the machine.

Usage (from this folder): python regenerate.py [--with-rq5]
"""

from __future__ import annotations

import csv
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CODE = ["common", "method_eval", "rq4_ablation_rerun", "rq5_scalability", "run_all.sh"]
RQ5_KEYS = {"TAB_scalability_structural.csv": ["circuit", "path", "n_qubits", "n_ops_submitted",
                                               "n_instructions_prepared", "edges_data", "edges_control",
                                               "edges_entanglement"],
            "TAB_scalability_end_to_end.csv": ["corpus", "circuit", "path", "n_qubits",
                                               "n_instructions_prepared", "n_criteria"]}


def rq5_compare(new: Path, old: Path, keys) -> bool:
    a = {r["path"]: r for r in csv.DictReader(open(new))}
    b = {r["path"]: r for r in csv.DictReader(open(old))}
    if list(a) != list(b):
        return False
    both = [p for p in a if a[p]["status"] == b[p]["status"] == "completed"]
    return all(a[p][k] == b[p][k] for p in both for k in keys)


def main() -> int:
    with_rq5 = "--with-rq5" in sys.argv
    with tempfile.TemporaryDirectory() as tmp:
        work, data = Path(tmp) / "experiments", Path(tmp) / "data"
        work.mkdir()
        (work / "logs").mkdir()
        for c in CODE:
            src = HERE / c
            (shutil.copytree if src.is_dir() else shutil.copy2)(src, work / c)
        data.mkdir()
        subs = ["qasmbench", "mqtbench", "veriqbench"] + (["QASMBench-master"] if with_rq5 else [])
        for sub in subs:
            os.symlink(REPO / "data" / sub, data / sub)
        env = dict(os.environ, PYTHON=sys.executable)
        cmd = ["bash", "run_all.sh", str(data), str(REPO)] + (["--with-rq5"] if with_rq5 else [])
        subprocess.run(cmd, cwd=work, env=env, check=True)
        ok = True
        for f in sorted((HERE / "results").rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(HERE / "results")
            if rel.parts[0] == "rq5_scalability":
                if not with_rq5 or f.name not in RQ5_KEYS:
                    continue
                same = rq5_compare(work / "results" / rel, f, RQ5_KEYS[f.name])
                label = "IDENTICAL (deterministic columns)" if same else "DIFFERENT"
            else:
                new = work / "results" / rel
                same = new.exists() and filecmp.cmp(new, f, shallow=False)
                label = "IDENTICAL" if same else "DIFFERENT"
            ok &= same
            print(f"{label:34s} results/{rel}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
