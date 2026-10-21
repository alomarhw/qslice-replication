"""Re-run the pre-registered experiments 1 and 2 in a scratch copy and compare every output file with the
shipped results/ byte for byte. About 15 minutes with 4 workers; needs requirements.lock (qiskit 2.3.0).
Experiment 3 (RQ5, results/rq5_scalability) is long and machine-dependent; its deterministic columns are
checked by the RQ5 regeneration in the cleaned-up replication repository.

Usage (from this folder): python regenerate.py
"""

from __future__ import annotations

import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
CODE = ["common", "method_eval", "rq4_ablation_rerun", "run_all.sh"]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        work, data = Path(tmp) / "corrected", Path(tmp) / "data"
        work.mkdir()
        for c in CODE:
            src = HERE / c
            (shutil.copytree if src.is_dir() else shutil.copy2)(src, work / c)
        data.mkdir()
        for sub in ("qasmbench", "mqtbench", "veriqbench"):   # the three corpora the loader reads
            os.symlink(PKG / "data" / sub, data / sub)
        env = dict(os.environ, PYTHON=sys.executable)
        subprocess.run(["bash", "run_all.sh", str(data), str(PKG)], cwd=work, env=env, check=True)
        ok = True
        for f in sorted((HERE / "results").rglob("*")):
            if f.is_file() and "rq5_scalability" not in f.parts:
                rel = f.relative_to(HERE / "results")
                new = work / "results" / rel
                same = new.exists() and filecmp.cmp(new, f, shallow=False)
                ok &= same
                print(f"{'IDENTICAL' if same else 'DIFFERENT':9s}  results/{rel}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
