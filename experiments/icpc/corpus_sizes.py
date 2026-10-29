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
from icpc.scale_run import code_lines  # noqa: E402
from tool import TOOL_NAME  # noqa: E402

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

    # ---- circuits
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
    s2 = [r for r in rows(RES / "scale" / "s2_qasmbench.csv") if r["tool"] == TOOL_NAME]
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
    lq = rows(RES / "scale" / "s1_lintq.csv")
    lqdir = root / "lintq" / "exp_v08" / "files_selected"
    out["lintq"] = programs(lq, lambda r: lqdir / r["file"], lambda r: not r["error"])
    qh = [r for r in rows(RES / "qhe" / "tasks.csv") if r["set"] == "hard"]  # the hard set holds the programs without docstrings
    out["qhe"] = programs(qh, lambda r: RES / "qhe" / "programs" / r["file"], lambda r: not r.get("error"))
    s3 = [r for r in rows(RES / "scale" / "s3_parametric.csv") if r["tool"] == TOOL_NAME and not r["error"]]
    out["parametric"] = summary(len({r["program"] for r in s3}), [int(r["qubits"]) for r in s3], [int(r["ops"]) for r in s3],
                                [int(r["code_lines"]) for r in {r["program"]: r for r in s3}.values()])
    out["parametric"]["traces"] = len(s3)
    from tool import srcml as X  # noqa: PLC0415
    from tool.interp import Interpreter  # noqa: PLC0415
    cf = sorted((ROOT / "tool" / "tests" / "controlflow").glob("cf*.py"))
    tr = [Interpreter(str(p), 60).run(X.parse_file(p)).main_circuit() for p in cf]
    out["controlflow"] = summary(len(cf), [c.n("q") for c in tr], [len(c.ops) for c in tr], [code_lines(p) for p in cf])

    (RES / "corpus_sizes.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
