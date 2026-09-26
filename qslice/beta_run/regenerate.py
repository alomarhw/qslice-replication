"""Re-run the beta-manuscript evaluation with the unchanged Jun 28 code in ../ and compare with the
archived results.3suite.json.

Command used by the beta run (reconstructed from its log header "small+medium+mqt+veriq mode,
<= 14 qubits"):  python main.py --medium --mqt --veriq --max-qubits 14 --no-figures
Needs the full QASMBench layout (run the package's fetch_data.py first), MQT Bench and VeriQBench from the
package's data/, and qiskit 2.3.0 / numpy 1.26.4 (../requirements.txt). About 15-20 minutes.

Usage: python regenerate.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE.parent
DATA = CODE.parent / "data"


def diffs(x, y, p=""):
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y)):
            if k not in x or k not in y:
                yield p + "/" + k, "missing", None
            else:
                yield from diffs(x[k], y[k], p + "/" + k)
    elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
        for i, (u, v) in enumerate(zip(x, y)):
            yield from diffs(u, v, f"{p}[{i}]")
    elif x != y:
        num = isinstance(x, (int, float)) and isinstance(y, (int, float))
        yield p, f"{x} vs {y}", abs(x - y) if num else None


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for f in CODE.glob("*.py"):
            shutil.copy2(f, work / f.name)
        (work / "data").mkdir()
        for sub in ("qasmbench", "mqtbench", "veriqbench"):
            os.symlink(DATA / sub, work / "data" / sub)
        (work / "results").mkdir()
        (work / "figures").mkdir()
        subprocess.run([sys.executable, "main.py", "--medium", "--mqt", "--veriq", "--max-qubits", "14",
                        "--no-figures"], cwd=work, check=True)
        new = (work / "results" / "results.json").read_bytes()
    old = (HERE / "results.3suite.json").read_bytes()
    if new == old:
        print("IDENTICAL  results.json vs archived results.3suite.json")
        return 0
    d = list(diffs(json.loads(new), json.loads(old)))
    worst = max((a for _, _, a in d if a is not None), default=0.0)
    structural = [x for x in d if x[2] is None]
    for path, what, _ in d:
        print(f"  differs: {path}: {what}")
    ok = not structural and worst < 1e-9
    print(f"{'NUMERICALLY IDENTICAL (max abs difference %.1e)' % worst if ok else 'DIFFERENT'}  "
          f"results.json vs archived results.3suite.json")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
