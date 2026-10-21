"""D1 check: does the corrected corpus loader keep every operation of the raw OpenQASM?

For every corpus-A circuit, count the operations written in the raw .qasm file with a small parser that
shares no code with qiskit (register broadcast expanded, gate-definition bodies, declarations and
barriers skipped) and compare with:
  - qiskit.qasm2.load, as experiments/common/corpus.py loads it (before preparation), and
  - the submitted evaluation loader (archive/.../qasm_loader.py, parse_qasm_file), which D1 says
    dropped unsupported gates, measure, reset and if.

Usage: python d1_instruction_counts.py REPO_ROOT OUT.csv
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

DECL = {"OPENQASM", "include", "qreg", "creg", "barrier", "opaque"}


def raw_operation_count(text: str) -> tuple[int, dict]:
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"gate\s+[^{]*\{[^}]*\}", "", text)  # definitions are not operations
    regs = {m.group(1): int(m.group(2)) for m in re.finditer(r"\bqreg\s+(\w+)\s*\[\s*(\d+)\s*\]", text)}
    cregs = {m.group(1): int(m.group(2)) for m in re.finditer(r"\bcreg\s+(\w+)\s*\[\s*(\d+)\s*\]", text)}
    count, names = 0, {}
    for stmt in text.split(";"):
        stmt = stmt.strip()
        if not stmt:
            continue
        m = re.match(r"if\s*\(([^)]*)\)\s*(.*)", stmt, re.S)
        body = m.group(2).strip() if m else stmt
        word = re.match(r"[A-Za-z_]\w*", body)
        if not word or word.group(0) in DECL:
            continue
        name = word.group(0)
        if name == "measure":
            args = [body[len("measure"):].split("->")[0].strip()]
        else:
            rest = re.sub(r"^\w+\s*(\([^)]*\))?", "", body).strip()
            args = [a.strip() for a in rest.split(",") if a.strip()]
        width = 1
        for a in args:
            if "[" not in a and a in regs:
                width = max(width, regs[a])
        key = f"if:{name}" if m else name
        names[key] = names.get(key, 0) + width
        count += width
    return count, names


def main() -> int:
    repo, out = Path(sys.argv[1]), Path(sys.argv[2])
    sys.path.insert(0, str(repo / "experiments"))
    from qiskit import qasm2
    from common.corpus import corpus_a

    sys.path.insert(0, str(repo / "archive" / "submitted_artifact" / "reported_results" / "rq1_rq3_rq5"))
    try:
        import qasm_loader as submitted  # the ICSE evaluation loader (selection/qasm_loader.py is byte-identical)
    except Exception as exc:  # report, do not fail the check
        submitted, why = None, f"{type(exc).__name__}: {exc}"

    data = repo / "data"
    rows = []
    for e in corpus_a(data, repo / "selection"):
        text = (data / e.path).read_text()
        raw, names = raw_operation_count(text)
        try:
            qc = qasm2.load(str(data / e.path), custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
            loaded = sum(1 for i in qc.data if i.operation.name != "barrier")
        except Exception as exc:
            loaded = f"error: {type(exc).__name__}"
        old = ""
        if submitted is not None:
            try:
                old = len(submitted.parse_qasm_file(data / e.path).ops)
            except Exception as exc:
                old = f"error: {type(exc).__name__}"
        rows.append({"corpus": e.corpus, "path": e.path, "raw_operations": raw, "qasm2_load": loaded,
                     "submitted_loader": old, "match": int(loaded == raw),
                     "dynamic_ops_raw": sum(v for k, v in names.items() if k == "measure" or k == "reset" or k.startswith("if:"))})
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    ok = [r for r in rows if r["match"]]
    lost = [r for r in rows if isinstance(r["submitted_loader"], int) and r["submitted_loader"] < r["raw_operations"]]
    print(f"circuits: {len(rows)}; qasm2.load count == raw count: {len(ok)}")
    for r in rows:
        if not r["match"]:
            print(f"  mismatch {r['path']}: raw {r['raw_operations']} qasm2 {r['qasm2_load']}")
    errors = [r for r in rows if isinstance(r["submitted_loader"], str) and r["submitted_loader"]]
    if errors:
        print(f"submitted loader raised on {len(errors)} circuits: {errors[0]['submitted_loader']}")
    if submitted is None:
        print(f"submitted loader not importable: {why}")
    else:
        print(f"submitted loader kept fewer operations than the raw file on {len(lost)} circuits "
              f"({sum(r['raw_operations'] - r['submitted_loader'] for r in lost)} operations dropped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
