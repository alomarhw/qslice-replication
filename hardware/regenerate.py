"""Recompute the RQ7 hardware table from the captured IBM Quantum job results and compare it with the
reported copy. Runs scripts/recompute_hardware_tvd.py (unchanged) in a scratch copy.
Requires qiskit-ibm-runtime (to decode the captured SamplerV2 results); no IBM account is needed.

Usage: python regenerate.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        shutil.copytree(HERE / "scripts", work / "scripts")
        shutil.copytree(HERE / "data", work / "data")
        (work / "results").mkdir()
        (work / "figures").mkdir()
        subprocess.run([sys.executable, "scripts/recompute_hardware_tvd.py"], cwd=work, check=True)
        new = (work / "results" / "TAB_hardware_ibmq.csv").read_bytes()
        old = (HERE / "reported" / "TAB_hardware_ibmq.csv").read_bytes()
        exact = new == old
        # The submitted copy was re-saved with different line endings when the package was assembled;
        # the file as first generated is byte-identical to this recomputation.
        same = exact or new.replace(b"\r\n", b"\n") == old.replace(b"\r\n", b"\n")
        status = "IDENTICAL" if exact else ("IDENTICAL (content; line endings differ)" if same else "DIFFERENT")
        print(f"{status}  TAB_hardware_ibmq.csv")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
