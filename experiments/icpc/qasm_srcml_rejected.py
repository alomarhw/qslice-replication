"""For every file the OpenQASM 2 front end rejects in equiv.csv, whether qiskit.qasm2.load (with Qiskit's legacy
instructions) rejects it too, asked of Qiskit alone.
-> results/icpc/qasm_srcml/rejected.csv (file, front_end_error, qiskit)"""
import csv, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tool.tests.check_qasm_layer import qiskit_ops  # noqa: E402

D = ROOT / "experiments/results/icpc/qasm_srcml"
rows = [r for r in csv.DictReader(open(D / "equiv.csv")) if r["layer_vs_qiskit"] == "False"]
with open(D / "rejected.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["file", "front_end_error", "qiskit"])
    for r in rows:
        try:
            qiskit_ops(r["file"])
            q = "loads"
        except Exception as e:
            q = f"rejects: {type(e).__name__}"
        w.writerow([r["file"], r["note"].split("|")[0].strip()[:200], q])
print(len(rows), "rows ->", D / "rejected.csv")
