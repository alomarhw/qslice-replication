"""QLine against LintQ's own data (Deviation I-22, C1 and C3). LintQ is not run; its files are read as data.

C1  For each of the 216 warnings that LintQ's authors confirmed as true positives on LintQ's corpus
    (data/lintq_artifact/Inspection_LintQ_on_LintQ_dataset.csv), QLine traces the file statically and reports
      traced     the file yields a circuit with an operation or a circuit construction on the warned line;
      exposed    for the five rules about qubits, the profile predicate fixed in I-22 holds at the warned line;
      read       the lines of the backward slices of the qubits acted on at the warned line, against the file's
                 code lines.
C3  LintQ's Figs. 1, 5, 6, 11a, 11b and QChecker's Fig. 5, transcribed as paper/figures/src/programs/lintq_*.py and
    qchecker_fig5.py: every qubit's slice and the predicates.
Usage (workspace root): python experiments/icpc/lintq_compare.py --data-root <data-root>
  -> results/icpc/lintq_compare/{c1.csv, c3.json, summary.json}
"""
import argparse
import csv
import json
import signal
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tool import srcml as X  # noqa: E402
from tool.corpus.hardlimit import run_all  # noqa: E402
from tool.interp import Interpreter  # noqa: E402
from tool.slicer import NOT_SLICED, wire_slice  # noqa: E402

OUT = ROOT / "experiments" / "results" / "icpc" / "lintq_compare"
ART = ROOT / "data" / "lintq_artifact"
LIMIT = 120
RULES = {"ql-operation-after-measurement": "OpAfterMeas", "ql-double-measurement": "DoubleMeas",
         "ql-oversized-circuit": "OversizedCircuit", "ql-conditional-without-measurement": "CondWoMeas",
         "ql-unmeasurable-qubits": "InsuffClasReg"}
EXAMPLES = ["lintq_fig1", "lintq_fig5", "lintq_fig6", "lintq_fig11a", "lintq_fig11b", "qchecker_fig5"]


class Timeout(Exception):
    pass


def _alarm(*_):
    raise Timeout()


def code_lines(path: Path) -> int:
    return sum(1 for ln in path.read_text(errors="replace").splitlines() if ln.strip() and not ln.strip().startswith("#"))


def at(c, L):
    return [k for k, o in enumerate(c.ops) if (o.line == L or L in o.calls) and o.name not in NOT_SLICED]


def qubits_of(o):
    return set().union(*o.qubits) if o.qubits else set()


def predicate(rule: str, c, L: int) -> bool:
    """The I-22 predicate of a rule at line L of circuit c."""
    ks = at(c, L)
    if rule == "OpAfterMeas":
        return any(c.ops[k].name != "measure" and any(c.ops[j].name == "measure" and (qubits_of(c.ops[j]) & qubits_of(c.ops[k]))
                                                         for j in range(k)) for k in ks)
    if rule == "DoubleMeas":
        for k in ks:
            if c.ops[k].name != "measure":
                continue
            for q in qubits_of(c.ops[k]):
                prev = [j for j in range(k) if q in qubits_of(c.ops[j]) and c.ops[j].name not in NOT_SLICED]
                nxt = [j for j in range(k + 1, len(c.ops)) if q in qubits_of(c.ops[j]) and c.ops[j].name not in NOT_SLICED]
                if (prev and c.ops[prev[-1]].name == "measure") or (nxt and c.ops[nxt[0]].name == "measure"):
                    return True
        return False
    if rule == "OversizedCircuit":
        used = set().union(*(qubits_of(o) for o in c.ops if o.name not in NOT_SLICED)) if c.ops else set()
        return any(q not in used for q in range(c.n("q")))
    if rule == "CondWoMeas":
        return any(c.ops[k].cond and not any(c.ops[j].name == "measure" and (set().union(*c.ops[j].clbits) & c.ops[k].cond)
                                             for j in range(k)) for k in ks)
    if rule == "InsuffClasReg":
        return c.n("q") > c.n("c")
    return False


def circuit_for(trace, L: int, rule: str):
    """The circuit the warning is about: one with an operation on line L, or, for the circuit-level rules, one built
    on line L; else the largest."""
    for c in trace.circuits:
        if at(c, L):
            return c
    for c in trace.circuits:
        if c.line == L or L in c.lines:
            return c
    return trace.main_circuit()


def c1_one(path: Path, rows):
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(LIMIT)
    out = []
    try:
        tr = Interpreter(str(path), LIMIT).run(X.parse_file(path))
        cl = code_lines(path)
        for r in rows:
            L = int(float(r["line"]))
            rule = RULES.get(r["rule_id"])
            c = circuit_for(tr, L, rule)
            rec = {"file": r["file"], "line": L, "rule_id": r["rule_id"], "code_lines": cl, "error": ""}
            if c is None or (not c.ops and not (c.line == L or L in c.lines)):
                out.append(rec | {"traced": 0, "error": "no circuit"})
                continue  # a circuit built on the warned line counts even with no operations (an oversized circuit)
            ks = at(c, L)
            rec["traced"] = int(bool(ks) or c.line == L or L in c.lines)
            rec["exposed"] = int(predicate(rule, c, L)) if rule else ""
            qs = set().union(*(qubits_of(c.ops[k]) for k in ks)) if ks else set()
            lines = set()
            for q in sorted(qs)[:64]:
                lines |= wire_slice(c, [q]).lines
            rec["slice_lines"] = len(lines) if qs else ""
            rec["warned_line_in_slice"] = int(L in lines) if qs else ""
            out.append(rec)
        return out
    except Timeout:
        return [{"file": r["file"], "line": r["line"], "rule_id": r["rule_id"], "traced": 0, "error": "timeout"} for r in rows]
    except Exception as exc:  # recorded as a result
        return [{"file": r["file"], "line": r["line"], "rule_id": r["rule_id"], "traced": 0, "error": type(exc).__name__} for r in rows]
    finally:
        signal.alarm(0)


def tp_rows(label="TP"):
    lines = list(csv.reader(open(ART / "Inspection_LintQ_on_LintQ_dataset.csv")))
    hdr = lines[1]
    rs = [dict(zip(hdr, x)) for x in lines[2:] if len(x) >= 6]
    return [r for r in rs if r["label_resolution"] == label]


def sarif_rows():
    """Every SARIF warning of the five qubit rules (Deviation I-23)."""
    d = json.load(open(ART / "data.sarif"))
    out = []
    for r in d["runs"][0]["results"]:
        if r["ruleId"] not in RULES:
            continue
        loc = r["locations"][0]["physicalLocation"]
        out.append({"rule_id": r["ruleId"], "file": loc["artifactLocation"]["uri"],
                    "line": str(loc["region"]["startLine"])})
    return out


def run_set(rows_in, corpus, workers):
    by_file = {}
    for r in rows_in:
        by_file.setdefault(r["file"], []).append(r)
    rows = []
    for res in run_all(c1_one, [(corpus / f, rs) for f, rs in sorted(by_file.items()) if (corpus / f).exists()], LIMIT,
                       lambda p, rs: [{"file": r["file"], "line": r["line"], "rule_id": r["rule_id"], "traced": 0,
                                       "error": "timeout"} for r in rs], workers):
        rows.extend(res)
    return rows


def c3():
    from tool.interp import trace_file
    res = {}
    for name in EXAMPLES:
        p = ROOT / "paper" / "figures" / "src" / "programs" / f"{name}.py"
        tr = trace_file(p)
        c = tr.main_circuit()
        res[name] = {"qubits": c.n("q"), "bits": c.n("c"), "ops": len(c.ops),
                     "slices": {q: {"quantum": sorted(wire_slice(c, [q]).quantum_lines),
                                    "classical": sorted(wire_slice(c, [q]).classical_lines)} for q in range(c.n("q"))},
                     "unused_qubits": [q for q in range(c.n("q")) if not any(q in qubits_of(o) for o in c.ops)],
                     "notes": [f"line {l}: {m}" for l, m in tr.notes]}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--set", choices=["tp", "fp-and-sarif"], default="tp",
                    help="fp-and-sarif (Deviation I-23): the predicates on LintQ's rejected warnings and on all its warnings")
    a = ap.parse_args()
    corpus = Path(a.data_root) / "lintq" / "exp_v08" / "files_selected"
    if a.set == "fp-and-sarif":
        OUT.mkdir(parents=True, exist_ok=True)
        summ = {}
        for name, rs in (("fp", [r for r in tp_rows("FP") if r["rule_id"] in RULES]), ("sarif", sarif_rows())):
            got = run_set(rs, corpus, a.workers)
            keys = ["file", "line", "rule_id", "code_lines", "traced", "exposed", "slice_lines", "warned_line_in_slice", "error"]
            with open(OUT / f"c1_{name}.csv", "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
                w.writeheader()
                w.writerows(got)
            summ[name] = {rule: {"warnings": sum(r["rule_id"] == rule for r in got),
                                 "traced": sum(r["rule_id"] == rule and r.get("traced") == 1 for r in got),
                                 "fires": sum(r["rule_id"] == rule and r.get("exposed") == 1 for r in got)} for rule in RULES}
        (OUT / "summary_fp_sarif.json").write_text(json.dumps(summ, indent=1) + "\n")
        print(json.dumps(summ, indent=1))
        return
    tps = tp_rows()
    assert len(tps) == 216, len(tps)
    by_file = {}
    for r in tps:
        by_file.setdefault(r["file"], []).append(r)
    rows = []
    for res in run_all(c1_one, [(corpus / f, rs) for f, rs in sorted(by_file.items())], LIMIT,
                       lambda p, rs: [{"file": r["file"], "line": r["line"], "rule_id": r["rule_id"], "traced": 0,
                                       "error": "timeout"} for r in rs], a.workers):
        rows.extend(res)
    OUT.mkdir(parents=True, exist_ok=True)
    keys = ["file", "line", "rule_id", "code_lines", "traced", "exposed", "slice_lines", "warned_line_in_slice", "error"]
    with open(OUT / "c1.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["rule_id"], r["file"], int(float(r["line"])))))
    per = {}
    for rule in sorted({r["rule_id"] for r in rows}):
        rs = [r for r in rows if r["rule_id"] == rule]
        per[rule] = {"tp": len(rs), "traced": sum(r.get("traced") == 1 for r in rs),
                     "exposed": sum(r.get("exposed") == 1 for r in rs) if rule in RULES else None}
    (OUT / "c3.json").write_text(json.dumps(c3(), indent=1) + "\n")
    summ = {"tp": len(rows), "files": len(by_file), "per_rule": per,
            "errors": dict(Counter(r["error"] for r in rows if r.get("error")))}
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
