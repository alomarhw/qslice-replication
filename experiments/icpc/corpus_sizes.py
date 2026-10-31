"""The same statistics for every subject of the study, for Table IV and the related-work table.

For every subject: the count; the qubits (smallest and largest) and operations (median and largest) of its circuits,
or, for programs, of the circuits that srcSlice-Q traces from them; and, for programs, the median code lines
(non-blank, non-comment lines, scale_run.code_lines). Circuit statistics come from the committed results of the runs
that used each subject; files are read, never executed.
Usage (workspace root): python experiments/icpc/corpus_sizes.py --data-root <data-root>  -> results/icpc/corpus_sizes.json
"""
import argparse
import csv
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
try:  # program statistics need the static slicer (Paper B); Paper A's package has circuits only
    from icpc.scale_run import code_lines  # noqa: E402
    from tool import TOOL_NAME  # noqa: E402
    HAS_TOOL = True
except ImportError:
    HAS_TOOL = False

RES = ROOT / "experiments" / "results" / "icpc"


def rows(p):
    return list(csv.DictReader(open(p)))


def summary(count, qubits, ops, lines=None):
    known = [q for q in qubits if q > 0]  # a traced register of unknown size counts as 0 qubits
    out = {"count": count, "traced": len(ops), "min_qubits": min(known), "max_qubits": max(known),
           "median_ops": st.median(ops), "max_ops": max(ops)}
    if lines is not None:
        lines = sorted(lines)
        out |= {"median_lines": st.median(lines), "max_lines": lines[-1], "total_lines": sum(lines)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    root = Path(ap.parse_args().data_root)
    out = {}

    # ---- circuits (only where the circuit-level results are present; the static slicer's package has none)
    if (RES / "rq1" / "pairs.csv").exists():
        circ = {r["path"]: (r["corpus"], int(r["n_qubits"]), int(r["n_ops"])) for r in rows(RES / "rq1" / "pairs.csv")}
        out["corpus_a"] = summary(len(circ), [q for _, q, _ in circ.values()], [o for _, _, o in circ.values()])
        out["corpus_a"]["by_corpus"] = {c: sum(1 for x, _, _ in circ.values() if x == c) for c in ("MQT Bench", "QASMBench", "VeriQBench")}
        fam = {(r["family"], r["circuit"]): (int(r["n_qubits"]), int(r["n_ops"])) for r in rows(RES / "families" / "rows.csv")}
        out["generated"] = summary(len(fam), [q for q, _ in fam.values()], [o for _, o in fam.values()])
        # the width sweeps of RQ4; its depth sweep is the F-depth family of the generated circuits, counted there
        sw = [r for r in rows(RES / "cost" / "circuits.csv") if r["kind"].startswith("width")]
        out["sweeps"] = summary(len(sw), [int(r["n_qubits"]) for r in sw], [int(r["n_ops"]) for r in sw])
        out["sweeps"]["by_kind"] = {k: sum(r["kind"] == k for r in sw) for k in sorted({r["kind"] for r in sw})}
        cl = rows(RES / "corpus_l" / "circuits.csv")
        out["corpus_l"] = summary(len(cl), [int(r["n_qubits"]) for r in cl], [int(r["n_ops"]) for r in cl])
        out["corpus_l"]["by_corpus"] = {c: sum(r["corpus"] == c for r in cl) for c in ("MQT Bench", "QASMBench", "VeriQBench")}
    if HAS_TOOL:  # QASMBench as read by the slicer, and the programs
        # read through srcML, as RQ3 reports (scale__rerun-20261031b; the original run used the line reader)
        s2 = [r for r in rows(RES / "scale__rerun-20261031b" / "s2_qasmbench.csv") if r["tool"] == TOOL_NAME]
        ok = [r for r in s2 if not r["error"]]
        out["qasmbench"] = summary(len(s2), [int(r["qubits"]) for r in ok], [int(r["ops"]) for r in ok])

        # ---- programs: circuit statistics of what srcSlice-Q traces, and code lines of every program
        def programs(rs, path_of, ok_of):
            traced = [r for r in rs if ok_of(r)]
            return summary(len(rs), [int(r["qubits"]) for r in traced], [int(r["ops"]) for r in traced],
                           [code_lines(path_of(r)) for r in rs])
        dr = lambda r: Path(r["file"].replace("<data-root>", str(root)))  # noqa: E731
        b4 = [r for r in rows(RES / "tool_acceptance" / "tool-v7" / "t3_bugs4q.csv") if r["uses_qiskit"] == "1"]
        out["bugs4q"] = programs(b4, dr, lambda r: int(r["ops"]) > 0)
        tb = [r for r in rows(RES / "tool_coverage" / "textbook_v7.csv") if r["uses_qiskit"] == "1"]
        out["textbook"] = programs(tb, dr, lambda r: int(r["ops"]) > 0)
        lq = rows(RES / "scale__rerun-20261101" / "s1_lintq.csv")
        lqdir = root / "lintq" / "exp_v08" / "files_selected"
        out["lintq"] = programs(lq, lambda r: lqdir / r["file"], lambda r: not r["error"])
        qh = [r for r in rows(RES / "qhe__rerun-20261101" / "tasks.csv") if r["set"] == "hard"]  # the hard set holds the programs without docstrings
        out["qhe"] = programs(qh, lambda r: RES / "qhe" / "programs" / r["file"], lambda r: not r.get("error"))
        s3 = [r for r in rows(RES / "scale" / "s3_parametric.csv") if r["tool"] == TOOL_NAME and not r["error"]]
        out["parametric"] = summary(len({r["program"] for r in s3}), [int(r["qubits"]) for r in s3], [int(r["ops"]) for r in s3],
                                    [int(r["code_lines"]) for r in {r["program"]: r for r in s3}.values()])
        out["parametric"]["traces"] = len(s3)
        from tool import srcml as X  # noqa: PLC0415
        from tool.interp import Interpreter  # noqa: PLC0415
        dev = json.load(open(RES / "tool_acceptance" / "dev_checks.json"))  # our runnable programs (RQ1)
        out["dev"] = summary(len(dev), [r["qubits"] for r in dev], [r["ops"] for r in dev],
                             [code_lines(ROOT / r["program"]) for r in dev])
        cf = sorted((ROOT / "tool" / "tests" / "controlflow").glob("cf*.py"))
        tr = [Interpreter(str(p), 60).run(X.parse_file(p)).main_circuit() for p in cf]
        out["controlflow"] = summary(len(cf), [c.n("q") for c in tr], [len(c.ops) for c in tr], [code_lines(p) for p in cf])

    if HAS_TOOL:  # the OpenQASM data of RQ1, counted by distinct contents as the RQ1 numbers are
        import hashlib
        import re
        from tool import qasm3_layer  # noqa: PLC0415
        digest = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()  # noqa: E731

        def distinct(items):
            seen = {}
            for f, v in items:
                seen.setdefault(digest(f), v)
            return list(seen.values())
        # OpenQASM 2: the files whose trace equals Qiskit's circuit; qubits from their qreg declarations
        eq = [r for r in rows(RES / "qasm_srcml" / "equiv.csv") if "/openqasm3_" not in r["file"]
              and r["layer_vs_qiskit"] in ("True", "False")]
        qregs = lambda f: sum(int(n) for n in re.findall(r"\bqreg\s+\w+\s*\[\s*(\d+)\s*\]", open(f, errors="replace").read()))  # noqa: E731
        same = distinct((r["file"], (qregs(r["file"]), int(r["ops"]))) for r in eq if r["layer_vs_qiskit"] == "True")
        out["oq2"] = summary(len(distinct((r["file"], 0) for r in eq)), [q for q, _ in same], [o for _, o in same])
        # OpenQASM 3: the official examples and VeriQBench's OpenQASM 3 files, traced by the layer
        ex = rows(RES / "qasm3_srcml" / "examples.csv")
        for key, sel in (("oq3_examples", lambda f: f.startswith("openqasm3_examples")), ("oq3_veriq", lambda f: not f.startswith("openqasm3_examples"))):
            fs = [r for r in ex if sel(r["file"])]
            tr = [qasm3_layer.read(ROOT / "data" / r["file"]).main_circuit() if (ROOT / "data" / r["file"]).exists()
                  else qasm3_layer.read(root.parent / "qslice-icpc" / "data" / r["file"]).main_circuit()
                  for r in fs if r["outcome"] == "trace"]
            out[key] = summary(len(fs), [c.n("q") for c in tr], [len(c.ops) for c in tr])
        # OpenQASM 3 written by Qiskit's exporter from our programs and from the corpus files, with their answers
        rt = ROOT / "data" / "openqasm3_roundtrip"
        files = sorted((rt / "ours").glob("*.qasm")) + [rt / "corpus" / r["file"] for r in rows(RES / "qasm3_srcml" / "roundtrip_corpus.csv")]
        qdecl = lambda t: sum(int(n) if n else 1 for n in re.findall(r"^\s*qubit(?:\[(\d+)\])?\s+\w+\s*;", t, re.M))  # noqa: E731
        ex3 = distinct((f, (qdecl(f.read_text()), len(json.load(open(f.with_suffix(".json")))["flat"]))) for f in files)
        out["oq3_export"] = summary(len(ex3), [q for q, _ in ex3], [o for _, o in ex3])

    (RES / "corpus_sizes.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
