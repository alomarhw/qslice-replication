"""Qiskit source map for the Bugs4Q bugs (PROTOCOL_ICPC.md section 5; Deviation I-11).

Maps every instruction of a prepared buggy Bugs4Q circuit (the one RQ3 slices) to the line of the
ORIGINAL buggy program that created it, then reports RQ3's fault containment and inspection cost in
source lines. No Bugs4Q file is executed: circuits come from the re-typed ports in bugs4q/extract.py.
  1. trace: run the buggy port with QuantumCircuit._append wrapped; each instruction appended to the
     port's circuit gets the innermost "<port>" frame line on the stack.
  2. port line -> original line: the port's "# Lnn" comment if present; otherwise the most similar
     original line (difflib ratio >= 0.6 on stripped text without comments) between the original lines
     of the nearest commented port lines before and after it.
  3. prepared instruction -> traced instruction: difflib alignment of (name, qubits) sequences; inside an
     unequal block of equal length, match by qubits.
Cross-check: the original buggy programs are sent to the authors' Quantum Slicer (qiskit-static mode),
and its per-instruction lines are compared with this map on (name, qubits)-aligned instructions.
Outputs (results/icpc/source_map/): instructions.csv, units.csv, bugs.csv, crosscheck.csv.
Usage (from experiments/): python icpc/qiskit_source_map.py --bugs4q-root BUGS4Q_ROOT [--no-crosscheck]
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "bugs4q"))
OUT = HERE / "results" / "icpc" / "source_map"
SLICER_URL = "http://quantum-slicing.capstone.csi.miamioh.edu/api/analyze"
LCOMMENT = re.compile(r"#\s*L(\d+)\b")


def trace(code: str, var: str):
    """Build the port's circuit; return it and the port line of each of its instructions."""
    import inspect
    from qiskit import QuantumCircuit
    orig = QuantumCircuit._append
    log = []

    def wrapped(self, *a, **k):
        out = orig(self, *a, **k)
        line = next((f.lineno for f in inspect.stack(0)[1:] if f.filename == "<port>"), None)
        log.append((id(self), line))
        return out

    QuantumCircuit._append = wrapped
    try:
        ns = {"__name__": "bugs4q_port"}
        exec(compile(code, "<port>", "exec"), ns)
    finally:
        QuantumCircuit._append = orig
    qc = ns[var]
    lines = [ln for cid, ln in log if cid == id(qc)]
    if len(lines) != len(qc.data):
        raise RuntimeError(f"traced {len(lines)} appends for {len(qc.data)} instructions")
    return qc, lines


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s.split("#", 1)[0])


def port_to_original(code: str, original: list) -> dict:
    """{port line number: original line number or None}."""
    plines = code.split("\n")
    cited = {i + 1: int(m.group(1)) for i, ln in enumerate(plines) if (m := LCOMMENT.search(ln))}
    out = {}
    for i, ln in enumerate(plines, 1):
        if i in cited:
            out[i] = cited[i]
            continue
        if not _norm(ln):
            out[i] = None
            continue
        lo = max([cited[j] for j in cited if j < i], default=1)
        hi = min([cited[j] for j in cited if j > i], default=len(original))
        best, score = None, 0.0
        for k in range(lo, hi + 1):
            r = difflib.SequenceMatcher(None, _norm(ln), _norm(original[k - 1])).ratio()
            if r > score:
                best, score = k, r
        out[i] = best if score >= 0.6 else None
    return out


def _sig(qc, inst):
    return inst.operation.name, tuple(qc.find_bit(q).index for q in inst.qubits)


def align(prepared, built) -> list:
    """For each prepared instruction, the index of its built instruction or None."""
    a = [_sig(prepared, i) for i in prepared.data]
    b = [_sig(built, i) for i in built.data]
    pos = [None] * len(a)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for d in range(i2 - i1):
                if tag == "equal" or a[i1 + d][1] == b[j1 + d][1]:
                    pos[i1 + d] = j1 + d
    return pos


def capstone_lines(source: str, filename: str):
    body = json.dumps({"source": source, "filename": filename, "profile": "baseline",
                       "language": "qiskit-static", "lint_rules": []}).encode()
    req = urllib.request.Request(SLICER_URL, data=body, headers={"Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=120))
    if not d.get("ok"):
        return None, str(d.get("error"))[:200]
    return [(n["name"], tuple(n["qubits"]), n.get("line")) for n in d["nodes"]], ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bugs4q-root", required=True)
    ap.add_argument("--no-crosscheck", action="store_true")
    a = ap.parse_args()
    import extract as ex
    from icpc.rq3_bugs4q import _load
    from slicers.registry import Slicers
    root = Path(a.bugs4q_root)
    OUT.mkdir(parents=True, exist_ok=True)
    units = list(csv.DictReader(open(HERE / "results" / "icpc" / "rq3_bugs4q" / "units.csv")))
    bugs = sorted({u["bug_id"] for u in units})
    irows, urows, brows, xrows = [], [], [], []
    for bug in bugs:
        ex.check_anchors(str(root), bug)
        orig_rel = ex.ANCHORS[bug][0][0]
        original = (root / orig_rel).read_text(encoding="utf-8", errors="replace").split("\n")
        port = ex.PORTS[bug]
        built, plines = trace(port["buggy"], port["var"])
        p2o = port_to_original(port["buggy"], original)
        stem = bug.replace("/", "__")
        prep = _load(stem, "buggy")
        amap = align(prep, built)
        line_of = [p2o.get(plines[j]) if j is not None else None for j in amap]
        for k, inst in enumerate(prep.data):
            irows.append({"bug_id": bug, "position": k, "gate": inst.operation.name, "built_index": amap[k],
                          "port_line": plines[amap[k]] if amap[k] is not None else "", "original_line": line_of[k] or ""})
        code_lines = {i for i, ln in enumerate(original, 1) if _norm(ln)}
        creating = {ln for ln in line_of if ln}
        brows.append({"bug_id": bug, "original_file": orig_rel, "n_instructions": len(prep.data),
                      "n_unmapped": sum(ln is None for ln in line_of), "n_creating_lines": len(creating),
                      "n_code_lines": len(code_lines)})
        s = Slicers(prep, stem)
        for u in (x for x in units if x["bug_id"] == bug):
            t = int(u["target"])
            fault = {int(x) for x in u["fault_site"].split(";") if x}
            fault_lines = {line_of[k] for k in fault if line_of[k]}
            slices = {m: s.get(m)(t) for m in ("du", "lc", "yz", "q")} | {"full": set(range(len(prep.data)))}
            for m, sl in slices.items():
                sl_lines = {line_of[k] for k in sl if line_of[k]}
                urows.append({"bug_id": bug, "target": t, "analysis": u["analysis"], "slicer": m,
                              "n_fault_lines": len(fault_lines), "contained_lines": int(bool(sl_lines & fault_lines)),
                              "slice_lines": len(sl_lines), "slice_lines_fraction": len(sl_lines) / max(len(creating), 1),
                              "unmapped_in_slice": sum(1 for k in sl if not line_of[k])})
        if not a.no_crosscheck:
            nodes, err = capstone_lines("\n".join(original), Path(orig_rel).name)
            if nodes is None:
                xrows.append({"bug_id": bug, "compared": 0, "agree": 0, "note": f"capstone error: {err}"})
            else:
                ours = [(_sig(built, i), p2o.get(plines[j])) for j, i in enumerate(built.data)]
                sm = difflib.SequenceMatcher(None, [o[0] for o in ours], [(n, q) for n, q, _ in nodes], autojunk=False)
                pairs = [(ours[i1 + d][1], nodes[j1 + d][2]) for tag, i1, i2, j1, j2 in sm.get_opcodes()
                         if tag == "equal" for d in range(i2 - i1)]
                xrows.append({"bug_id": bug, "ours_n": len(ours), "capstone_n": len(nodes), "compared": len(pairs),
                              "agree": sum(1 for x, y in pairs if x and y and x == y), "note": ""})
    for name, rows in (("instructions.csv", irows), ("units.csv", urows), ("bugs.csv", brows), ("crosscheck.csv", xrows)):
        if rows:
            with open(OUT / name, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
                w.writeheader()
                w.writerows(rows)
    print(f"bugs {len(brows)}; instructions {len(irows)} ({sum(r['n_unmapped'] for r in brows)} unmapped); "
          f"unit-slicer rows {len(urows)}; cross-check rows {len(xrows)}; wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
