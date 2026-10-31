"""Rerun after tool-v9 (srcML reads programs as UTF-8): the rows of the programs that tool-v9 reads differently.

experiments/icpc/encoding_check.py lists the programs whose trace, notes or srcSlice profiles change when srcML is told
the source is UTF-8 (results/icpc/encoding/changed.csv); every other program is read byte for byte the same. Their rows
are recomputed with each run's own function, unchanged, and written beside the old results to
results/icpc/<run>__rerun-20261101/, with every other row copied:
  scale          S1 on LintQ's corpus (scale_run.s1_one), and the no-circuit reasons (coverage_reasons.reason). The
                 base is the original S1 with the rows the 2026-10-28 and 2026-10-29 reruns changed, so this run holds
                 every change since.
  qhe            Qiskit HumanEval (qhe_run.one), on the 2026-10-28 rerun, and its summary (qhe_run.summarize)
  tool_coverage  coverage of LintQ's corpus (tool.corpus.coverage.one), as lintq_v9.csv
  unmodelled     the interpretation-only pass (unmodelled_calls.one) and its summary (unmodelled_calls.summarize)
  lintq_compare  the profile predicates at LintQ's warnings (lintq_compare.c1_one), for c1, c1_fp and c1_sarif
  profiles       the qubit profiles of the LintQ sample (tool.corpus.profiles.one)
  srcslice_heldout  srcSlice against the interpreter on the held-out files (srcslice_classical.one)
Files are read, never executed. Usage (workspace root): python experiments/icpc/rerun_encoding_files.py --data-root <data-root>
"""
import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
from tool.corpus.hardlimit import run_all  # noqa: E402

RES = ROOT / "experiments" / "results" / "icpc"
TAG = "__rerun-20261101"


def rows(p):
    return list(csv.DictReader(open(p)))


def write(p, rs, keys=None):
    p.parent.mkdir(parents=True, exist_ok=True)
    keys = keys or list(dict.fromkeys(k for r in rs for k in r))
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    data = Path(a.data_root)
    lq = data / "lintq" / "exp_v08" / "files_selected"
    changed = rows(RES / "encoding" / "changed.csv")
    lintq = {Path(r["file"]).name for r in changed if r["file"].startswith("lintq/")}
    qhe = {Path(r["file"]).name for r in changed if "/qhe/programs/" in r["file"]}
    report = {"changed_lintq": len(lintq), "changed_qhe": len(qhe)}

    # ---- S1, on the original with the 2026-10-28 and 2026-10-29 reruns' rows
    from icpc.scale_run import S1_LIMIT, s1_one
    s1 = rows(RES / "scale" / "s1_lintq.csv")
    for run in ("scale__rerun-20261028", "scale__rerun-20261029"):
        orig = {r["file"]: r for r in rows(RES / "scale" / "s1_lintq.csv")}
        upd = {r["file"]: r for r in rows(RES / run / "s1_lintq.csv") if r != orig.get(r["file"])}
        s1 = [upd.get(r["file"], r) for r in s1]
    jobs = [(lq / r["file"], r["file"]) for r in s1 if r["file"] in lintq]
    new = {r["file"]: r for r in run_all(s1_one, jobs, S1_LIMIT, lambda p, rel: {"file": rel, "error": "timeout"}, a.workers)}
    s1n = [new.get(r["file"], r) for r in s1]
    write(RES / f"scale{TAG}" / "s1_lintq.csv", s1n)
    from icpc.coverage_reasons import reason
    from collections import Counter
    cr = [{"file": r["file"], "reason": reason((lq / r["file"]).read_text(errors="replace"))}
          for r in s1n if r["error"] == "no circuit"]
    write(RES / f"scale{TAG}" / "coverage_reasons.csv", cr, ["file", "reason"])
    (RES / f"scale{TAG}" / "coverage_reasons.json").write_text(
        json.dumps({"no_circuit_files": len(cr), **Counter(r["reason"] for r in cr)}, indent=1) + "\n")
    report["s1_rows_rerun"] = len(new)

    # ---- Qiskit HumanEval, on the 2026-10-28 rerun
    from icpc import qhe_run
    qh = rows(RES / "qhe__rerun-20261028" / "tasks.csv")
    progs = RES / "qhe" / "programs"
    jobs = [(progs / r["file"], r["set"], r["task"], r["difficulty"]) for r in qh if r["file"] in qhe]
    newq = {r["file"]: r for r in run_all(qhe_run.one, jobs, S1_LIMIT, qhe_run.timed_out, a.workers)}
    qhn = [newq.get(r["file"], r) for r in qh]
    write(RES / f"qhe{TAG}" / "tasks.csv", qhn)
    (RES / f"qhe{TAG}" / "summary.json").write_text(json.dumps(qhe_run.summarize(qhn), indent=1) + "\n")
    report["qhe_rows_rerun"] = len(newq)

    # ---- coverage of LintQ's corpus
    from tool.corpus import coverage
    cv = rows(RES / "tool_coverage" / "lintq_v7.csv")
    jobs = [(lq / Path(r["file"]).name, 60) for r in cv if Path(r["file"]).name in lintq]
    newc = {Path(r["file"]).name: r for r in run_all(coverage.one, jobs, 60, coverage.timed_out, a.workers)}
    cvn = [{**newc[Path(r["file"]).name], "file": r["file"]} if Path(r["file"]).name in newc else r for r in cv]
    write(RES / "tool_coverage" / "lintq_v9.csv", cvn)
    report["coverage_rows_rerun"] = len(newc)

    # ---- unmodelled calls
    from icpc import unmodelled_calls as um
    pr = rows(RES / "unmodelled" / "programs.csv")
    def path_of(r):
        return lq / r["file"] if r["corpus"] == "lintq" else progs / r["file"]
    jobs = [(path_of(r), r["corpus"], r["file"]) for r in pr
            if (r["corpus"] == "lintq" and r["file"] in lintq) or (r["corpus"] == "qhe" and r["file"] in qhe)]
    newu = {(r["corpus"], r["file"]): r for r in run_all(um.one, jobs, um.LIMIT, um.timed_out, a.workers)}
    prn = [newu.get((r["corpus"], r["file"]), r) for r in pr]
    out = RES / f"unmodelled{TAG}"
    write(out / "programs.csv", prn, ["corpus", "file", "circuit", "error"] + list(um.PATTERNS))
    (out / "summary.json").write_text(json.dumps(um.summarize(prn), indent=1) + "\n")
    shutil.copy(RES / "unmodelled" / "calls_per_kind.json", out / "calls_per_kind.json")
    report["unmodelled_rows_rerun"] = len(newu)

    # ---- LintQ comparison
    from icpc import lintq_compare as lc
    out = RES / f"lintq_compare{TAG}"
    out.mkdir(parents=True, exist_ok=True)
    keys = ["file", "line", "rule_id", "code_lines", "traced", "exposed", "slice_lines", "warned_line_in_slice", "error"]
    n = 0
    for f in ("c1.csv", "c1_fp.csv", "c1_sarif.csv"):
        base = rows(RES / "lintq_compare" / f)
        by = {}
        for r in base:
            if r["file"] in lintq:
                by.setdefault(r["file"], []).append({"file": r["file"], "line": r["line"], "rule_id": r["rule_id"]})
        got = {}
        for res in run_all(lc.c1_one, [(lq / k, v) for k, v in sorted(by.items())], lc.LIMIT,
                           lambda p, rs: [{**x, "traced": 0, "error": "timeout"} for x in rs], a.workers):
            for r in res:
                got[(r["file"], str(r["line"]), r["rule_id"])] = r
        n += len(got)
        write(out / f, [got.get((r["file"], str(r["line"]), r["rule_id"]), r) for r in base], keys)
    for f in ("c3.json", "summary.json", "summary_fp_sarif.json"):
        shutil.copy(RES / "lintq_compare" / f, out / f)
    report["lintq_compare_rows_rerun"] = n

    # ---- profiles of the LintQ sample
    from tool.corpus import profiles as pf
    out = RES / f"profiles{TAG}"
    shutil.copytree(RES / "profiles", out, dirs_exist_ok=True)
    base = rows(RES / "profiles" / "lintq500.csv")
    hit = sorted({r["file"] for r in base if r["file"] in lintq})
    got = []
    for res in run_all(pf.one, [(lq / f, lq, 60, 64) for f in hit], 60, pf.timed_out, a.workers):
        got.extend(res if isinstance(res, list) else [res])
    write(out / "lintq500.csv", [r for r in base if r["file"] not in hit] + got, list(base[0].keys()))
    report["profile_files_rerun"] = len(hit)

    # ---- srcSlice against the interpreter, held-out files
    from icpc import srcslice_classical as sc
    out = RES / f"srcslice_heldout{TAG}"
    shutil.copytree(RES / "srcslice_heldout", out, dirs_exist_ok=True)
    base = rows(RES / "srcslice_heldout" / "qubits.csv")
    hit = sorted({r["file"] for r in base if r["file"] in lintq})
    got = []
    for res in run_all(sc.one, [("lintq", lq / f, f) for f in hit], sc.TIMEOUT, sc.timed_out, a.workers):
        got.extend(res)
    keys = ["corpus", "file", "qubit", "quantum", "interp", "srcslice", "srcslice_s", "profiles", "error"]
    newrows = [r for r in base if r["file"] not in hit] + got
    write(out / "qubits.csv", newrows, keys)
    report["heldout_files_rerun"] = len(hit)

    (RES / f"scale{TAG}" / "rerun_report.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
