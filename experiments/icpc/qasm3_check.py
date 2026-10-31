"""Validation of the OpenQASM 3 front end (tool/qasm3_srcml.py) and the quantum layer over it (tool/qasm3_layer.py).

  lossless    every OpenQASM 3 file (official examples, round-trip corpus, VeriQBench) marked up gives back the file
              byte for byte, or is rejected as not valid OpenQASM 3;
  grammar     the official grammar suite: reference cases matched statement for statement, invalid statements rejected
              (tool.tests.test_qasm3_grammar);
  roundtrip   the round-trip corpus (tool.tests.check_qasm3_roundtrip): our programs against the Qiskit front end,
              the re-exported corpus against the circuits Qiskit loaded;
  examples    the official examples and VeriQBench's OpenQASM 3 files: a trace, a rejection, or a reported error,
              never a crash, with the constructs outside the subset each file uses.
-> results/icpc/qasm3_srcml/summary.json, examples.csv
"""
import csv
import glob
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tool import qasm3_layer  # noqa: E402
from tool.qasm3_srcml import to_srcml  # noqa: E402
from tool.qasm_srcml import QasmSyntaxError  # noqa: E402
from tool.tests import check_qasm3_roundtrip as RT, test_qasm3_grammar as G  # noqa: E402

OUT = ROOT / "experiments" / "results" / "icpc" / "qasm3_srcml"


def oq3_files():
    ex = sorted(glob.glob(str(ROOT / "data" / "openqasm3_examples" / "*.qasm")))
    vq = sorted({os.path.realpath(f) for f in glob.glob(str(ROOT / "../qslice-icpc/data") + "/**/*.qasm", recursive=True)
                 + glob.glob(str(ROOT / "data") + "/**/*.qasm", recursive=True)
                 if os.path.isfile(f) and "openqasm3_" not in f
                 and re.search(r"OPENQASM\s+3", open(f, errors="replace").read(300))})
    return ex, vq


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ex, vq = oq3_files()
    rt = {k: sorted(glob.glob(str(ROOT / "data" / "openqasm3_roundtrip" / k / "*.qasm"))) for k in ("ours", "corpus")}
    summ = {}
    # lossless
    ll = {}
    for name, fs in (("examples", ex), ("ours", rt["ours"]), ("corpus", rt["corpus"]), ("veriqbench", vq)):
        n = ok = rej = 0
        for f in fs:
            t = open(f, newline="", errors="replace").read()
            n += 1
            try:
                ok += "".join(ET.fromstring(to_srcml(t).encode()).itertext()) == t
            except QasmSyntaxError:
                rej += 1
        ll[name] = {"files": n, "lossless": ok, "rejected": rej}
    summ["lossless"] = ll
    # official grammar suite
    buf = io.StringIO()
    with redirect_stdout(buf):
        G.main()
    m1 = re.search(r"reference: (\d+) of (\d+)", buf.getvalue())
    m2 = re.search(r"invalid: (\d+) rejected, (\d+) kept whole as unsupported, (\d+) accepted", buf.getvalue())
    summ["grammar"] = {"reference_match": int(m1.group(1)), "reference_cases": int(m1.group(2)),
                       "invalid_rejected": int(m2.group(1)), "invalid_unsupported": int(m2.group(2)),
                       "invalid_accepted": int(m2.group(3))}
    # round trip
    for k in ("ours", "corpus"):
        sys.argv = ["x", k]
        with redirect_stdout(io.StringIO()):
            RT.main()
        rows = list(csv.DictReader(open(OUT / f"roundtrip_{k}.csv")))
        summ[f"roundtrip_{k}"] = {"files": len(rows), "equal": sum(r["equal"] == "True" for r in rows)}
    # examples and VeriQBench
    rows = []
    for f in ex + vq:
        rel = f.split("/data/")[-1]
        try:
            to_srcml(open(f, newline="", errors="replace").read())   # the whole file's syntax first
            t = qasm3_layer.read(f)
            outside = sorted({m.split(":")[0] for _, m in t.notes if "outside" in m})
            rows.append([rel, "trace", len(t.main_circuit().ops), ";".join(outside), ""])
        except QasmSyntaxError as e:
            rows.append([rel, "rejected: not valid OpenQASM 3", "", "", str(e)[:120]])
        except qasm3_layer.Qasm3Error as e:
            rows.append([rel, "reported", "", "", str(e).split(": ", 2)[-1][:120]])
        except Exception as e:  # a crash would be a bug, recorded as such
            rows.append([rel, "crash", "", "", f"{type(e).__name__}: {str(e)[:100]}"])
    with open(OUT / "examples.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "outcome", "ops", "outside_subset", "message"])
        w.writerows(rows)
    for k, sel in (("examples", [r for r in rows if "openqasm3_examples" in r[0]]),
                   ("veriqbench", [r for r in rows if "openqasm3_examples" not in r[0]])):
        summ[k] = {"files": len(sel), "trace": sum(r[1] == "trace" for r in sel),
                   "trace_with_outside_constructs": sum(r[1] == "trace" and bool(r[3]) for r in sel),
                   "rejected": sum(r[1].startswith("rejected") for r in sel),
                   "reported": sum(r[1] == "reported" for r in sel), "crash": sum(r[1] == "crash" for r in sel)}
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
