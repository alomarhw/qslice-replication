"""srcSlice-Q on the Bugs4Q bugs, against the circuit each buggy program builds (data/bugs4q_ported, read as data).

T1  srcSlice-Q reads each original buggy program without running it; its trace is compared with the ported circuit,
    position by position, as (gate, qubits, original line). Terminal measurements are left out (preparation drops
    them), conditional blocks are flattened, and gate names are normalized for Qiskit's API renamings.
T2  For every unit (bug, criterion qubit), the original lines of srcSlice-Q's slice are compared with the original
    lines of the circuit's light cone (experiments/icpc/b_reference.py).
Fault lines: for each primary unit whose faulty instructions map to lines, whether the light cone's lines keep one.
No Bugs4Q file is executed. A tool error is recorded as a result.
Outputs (results/icpc/tool_acceptance/<tag>/): t1.csv, t2.csv, summary.json, fault_lines.csv
Usage (from experiments/): python icpc/b_bugs4q.py --bugs4q-root BUGS4Q_ROOT [--tag tool-v7]
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
DATA = HERE.parent / "data" / "bugs4q_ported"
OUT = HERE / "results" / "icpc" / "tool_acceptance"
RENAME = {"u1": "p", "cu1": "cp", "cnot": "cx", "toffoli": "ccx", "u3": "u", "iden": "id", "fredkin": "cswap"}


def load(stem: str):
    from qiskit import qasm2, qpy
    from icpc.b_reference import prepare
    q = DATA / "circuits" / f"{stem}.buggy.qasm"
    if q.exists():
        return prepare(qasm2.load(str(q), custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS))
    with open(DATA / "circuits" / f"{stem}.buggy.qpy", "rb") as fh:
        return prepare(qpy.load(fh)[0])


def prepared_ops(prep, line_of):
    """(gate, qubits, original line) per operation of the prepared circuit, with if_else blocks flattened."""
    out = []

    def walk(data, qmap, line):
        for inst in data:
            qs = tuple(qmap[q] for q in inst.qubits)
            if inst.operation.name == "if_else":
                body = inst.operation.blocks[0]
                walk(body.data, {bq: oq for bq, oq in zip(body.qubits, qs)}, line)
            else:
                out.append((inst.operation.name, qs, line))
    for k, inst in enumerate(prep.data):
        qs = tuple(prep.find_bit(q).index for q in inst.qubits)
        if inst.operation.name == "if_else":
            body = inst.operation.blocks[0]
            walk(body.data, {bq: oq for bq, oq in zip(body.qubits, qs)}, line_of[k])
        else:
            out.append((inst.operation.name, qs, line_of[k]))
    return out


def tool_ops(circ):
    from tool.slicer import terminal
    term = terminal(circ)
    return [(RENAME.get(o.name, o.name), tuple(next(iter(s)) if len(s) == 1 else None for s in o.qubits), o.line)
            for k, o in enumerate(circ.ops) if k not in term]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bugs4q-root", required=True)
    ap.add_argument("--tag", default="tool-v7", help="tool version label for the output folder")
    a = ap.parse_args()
    from icpc.b_reference import light_cone
    from tool.interp import trace_file
    from tool.slicer import wire_slice
    root = Path(a.bugs4q_root)
    out = OUT / a.tag
    out.mkdir(parents=True, exist_ok=True)
    bugs = list(csv.DictReader(open(DATA / "bugs.csv")))
    ins = list(csv.DictReader(open(DATA / "instructions.csv")))
    units = list(csv.DictReader(open(DATA / "units.csv")))
    t1, t2, fl = [], [], []
    for b in bugs:
        bug = b["bug_id"]
        stem = bug.replace("/", "__")
        prep = load(stem)
        rows = sorted((r for r in ins if r["bug_id"] == bug), key=lambda r: int(r["position"]))
        line_of = [int(r["original_line"]) if r["original_line"] else None for r in rows]
        ref = prepared_ops(prep, line_of)
        for u in (x for x in units if x["bug_id"] == bug and x["analysis"] == "primary"):
            fault = {line_of[k] for k in (int(x) for x in u["fault_site"].split(";") if x) if line_of[k]}
            cone = {line_of[k] for k in light_cone(prep, int(u["target"])) if line_of[k]}
            fl.append({"bug_id": bug, "target": u["target"], "fault_lines": len(fault), "cone_lines": len(cone),
                       "contained": int(bool(cone & fault))})
        try:
            tr = trace_file(root / b["original_file"])
        except Exception as exc:  # a tool error is a result: recorded, never hidden
            t1.append({"bug_id": bug, "prepared_ops": len(ref), "tool_ops": 0, "exact": 0, "matched": 0,
                       "circuit_index": -1, "circuits": 0, "notes": 0,
                       "first_difference": f"tool error: {type(exc).__name__}: {exc}"[:200], "tool_notes": ""})
            for u in (x for x in units if x["bug_id"] == bug):
                t2.append({"bug_id": bug, "target": int(u["target"]), "analysis": u["analysis"], "study_lines": "",
                           "tool_lines": "", "equal": 0, "note": f"tool error: {type(exc).__name__}"})
            continue
        # the tool's circuit that matches the prepared one best (programs may build several)
        cands = [(difflib.SequenceMatcher(None, [x[:2] for x in tool_ops(c)], [x[:2] for x in ref], autojunk=False).ratio(), i, c)
                 for i, c in enumerate(tr.circuits)]
        ratio, ci, circ = max(cands, key=lambda x: (x[0], -x[1])) if cands else (0.0, -1, None)
        mine = tool_ops(circ) if circ is not None else []
        exact = mine == ref
        sm = difflib.SequenceMatcher(None, mine, ref, autojunk=False)
        matched = sum(bl.size for bl in sm.get_matching_blocks())
        first = next(((i, mine[i] if i < len(mine) else None, ref[i] if i < len(ref) else None)
                      for i in range(max(len(mine), len(ref))) if (mine[i] if i < len(mine) else None) != (ref[i] if i < len(ref) else None)), None)
        t1.append({"bug_id": bug, "prepared_ops": len(ref), "tool_ops": len(mine), "exact": int(exact),
                   "matched": matched, "circuit_index": ci, "circuits": len(tr.circuits), "notes": len(tr.notes),
                   "first_difference": "" if exact else str(first)[:200],
                   "tool_notes": "; ".join(f"L{l}: {m}" for l, m in tr.notes)[:300]})
        for u in (x for x in units if x["bug_id"] == bug):
            t = int(u["target"])
            study = {line_of[k] for k in light_cone(prep, t) if line_of[k]}
            row = {"bug_id": bug, "target": t, "analysis": u["analysis"], "study_lines": ";".join(map(str, sorted(study)))}
            if circ is None or t >= circ.n("q"):
                t2.append(row | {"tool_lines": "", "equal": 0, "note": "no matching circuit or qubit"})
                continue
            sl = wire_slice(circ, [t])
            tool = {circ.ops[k].line for k in sl.ops}
            row |= {"tool_lines": ";".join(map(str, sorted(tool))), "equal": int(tool == study),
                    "tool_only": ";".join(map(str, sorted(tool - study))), "study_only": ";".join(map(str, sorted(study - tool))),
                    "tool_classical_lines": ";".join(map(str, sorted(sl.classical_lines))), "may_ops": sl.may,
                    "note": "" if not any(None in x[1] for x in mine) else "unresolved qubits in trace"}
            t2.append(row)
    for name, rows in (("t1.csv", t1), ("t2.csv", t2), ("fault_lines.csv", fl)):
        with open(out / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
            w.writeheader()
            w.writerows(rows)
    summ = {"t1_bugs": len(t1), "t1_exact": sum(r["exact"] for r in t1),
            "t1_ops_prepared": sum(r["prepared_ops"] for r in t1), "t1_ops_matched": sum(r["matched"] for r in t1),
            "t2_units": len(t2), "t2_equal": sum(r["equal"] for r in t2),
            "t2_units_mapped": sum(1 for r in t2 if r["study_lines"]),
            "t2_equal_mapped": sum(r["equal"] for r in t2 if r["study_lines"])}
    summ["tool_version"] = a.tag
    (out / "summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
