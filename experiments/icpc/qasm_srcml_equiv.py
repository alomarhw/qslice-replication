"""Step 2 of the OpenQASM 2 front-end validation over the corpora: for every OpenQASM 2 file, the trace the quantum
layer reads from the file's srcML is compared with the circuit qiskit.qasm2.load builds (tool.tests.check_qasm_layer),
and the old line reader's trace with the layer's.
-> results/icpc/qasm_srcml/equiv.csv (file, ops, layer_vs_qiskit, layer_vs_reader, note)"""
import csv, glob, os, re, signal, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tool import qasm, qasm_layer  # noqa: E402
from tool.tests.check_qasm_layer import compare, layer_ops  # noqa: E402

MAX_BYTES = 5_000_000      # larger files are compared in the scale run, not here
LIMIT = 300


class _T(Exception):
    pass


def _alarm(*_):
    raise _T()


signal.signal(signal.SIGALRM, _alarm)
files = sorted({os.path.realpath(f) for d in ("../qslice-icpc/data", "data") for f in glob.glob(str(ROOT / d) + "/**/*.qasm", recursive=True)})
out = ROOT / "experiments/results/icpc/qasm_srcml/equiv.csv"
with open(out, "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["file", "bytes", "ops", "layer_vs_qiskit", "layer_vs_reader", "note"])
    for f in files:
        t = open(f, errors="replace").read()
        m = re.search(r"OPENQASM\s+([\d.]+)", t)
        if m and m.group(1).startswith("3"):
            continue
        if len(t) > MAX_BYTES:
            w.writerow([f, len(t), "", "", "", "large, in the scale run"]); continue
        signal.alarm(LIMIT)
        try:
            mine = layer_ops(f)
            try:
                ok, note = compare(f)
            except Exception as e:
                ok, note = "", f"qiskit: {type(e).__name__}: {str(e)[:150]}"
            try:
                old = [(qasm_layer.BUILTIN.get(n, (n,))[0], tuple(q), mb, tuple(sorted(c))) for n, q, mb, c, _, _ in qasm._Reader(Path(f)).run()]
                rd = old == mine
            except Exception as e:
                rd = f"reader: {type(e).__name__}"
            w.writerow([f, len(t), len(mine), ok, rd, note])
        except _T:
            w.writerow([f, len(t), "", "", "", "timeout"])
        except Exception as e:
            try:
                compare(f); qn = "qiskit loads it"
            except Exception as e2:
                qn = f"qiskit also rejects: {type(e2).__name__}"
            w.writerow([f, len(t), "", False, "", f"layer: {type(e).__name__}: {str(e)[:150]} | {qn}"])
        finally:
            signal.alarm(0)
        fh.flush()
print("done", out)
