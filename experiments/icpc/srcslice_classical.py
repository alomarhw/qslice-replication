"""Deviation I-20: QSlice's classical lines from srcSlice, against the interpreter's provenance lines.

Per qubit of each file's largest circuit (at most 64 qubits): the quantum lines of its QDG slice (tool.slicer), the
interpreter's classical lines (I-15) and srcSlice's (tool.srcslice), with srcSlice's time for the file. Files are
read and never executed. The file lists are those of the I-17 profile runs (results/icpc/profiles/), so the LintQ
files are the same 500-file sample.
Usage (workspace root):
  python experiments/icpc/srcslice_classical.py --data-root <data-root>  -> results/icpc/srcslice/qubits.csv, summary.json
"""
import argparse
import csv
import json
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tool import srcml as X  # noqa: E402
from tool import srcslice as S  # noqa: E402
from tool.corpus.hardlimit import run_all  # noqa: E402
from tool.interp import Interpreter  # noqa: E402
from tool.slicer import wire_slice  # noqa: E402

RES = ROOT / "experiments" / "results" / "icpc"
OUT = RES / "srcslice"
TIMEOUT = 60
MAX_QUBITS = 64
DEV = sorted((ROOT / "tool/tests/big").glob("*.py")) + sorted((ROOT / "tool/tests/programs").glob("t0*.py")) + \
    sorted(p for p in (ROOT / "paper/figures/src/programs").glob("*.py") if p.name != "bv.py")
CORPORA = {"bugs4q": ("bugs4q/Bugs4Q-7a719839662f94614872d65f9e9fbcd07408437c", "bugs4q.csv"),
           "textbook": ("textbook_py", "textbook.csv"),
           "lintq": ("lintq/exp_v08/files_selected", "lintq500.csv")}


class Timeout(Exception):
    pass


def _alarm(*_):
    raise Timeout()


def one(corpus: str, path: Path, rel: str):
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(TIMEOUT)
    try:
        root = X.parse_file(path)
        c = Interpreter(str(path), TIMEOUT).run(root).main_circuit()
        if c is None or not c.ops:
            return [{"corpus": corpus, "file": rel, "qubit": -1, "error": "no circuit"}]
        prof, took = S.profiles(path)
        rows = []
        for q in range(min(c.n("q"), MAX_QUBITS)):
            s = wire_slice(c, [q])
            if not s.ops:
                continue
            ss = S.classical_lines(path, s.quantum_lines, prof, root)
            rows.append({"corpus": corpus, "file": rel, "qubit": q, "quantum": ";".join(map(str, sorted(s.quantum_lines))),
                         "interp": ";".join(map(str, sorted(s.classical_lines))), "srcslice": ";".join(map(str, sorted(ss))),
                         "srcslice_s": round(took, 4), "profiles": len(prof), "error": ""})
        return rows or [{"corpus": corpus, "file": rel, "qubit": -1, "error": "no qubit acted on"}]
    except Timeout:
        return [{"corpus": corpus, "file": rel, "qubit": -1, "error": "timeout"}]
    except Exception as exc:  # recorded as a result
        return [{"corpus": corpus, "file": rel, "qubit": -1, "error": type(exc).__name__}]
    finally:
        signal.alarm(0)


def timed_out(corpus, path, rel):
    return [{"corpus": corpus, "file": rel, "qubit": -1, "error": "timeout"}]


def lines(s):
    return {int(x) for x in s.split(";") if x}


def summarize(rows):
    out = {}
    for corpus in ["dev", "bugs4q", "textbook", "lintq"]:
        ok = [r for r in rows if r["corpus"] == corpus and not r["error"]]
        if not ok:
            continue
        contain = sum(lines(r["interp"]) <= lines(r["srcslice"]) for r in ok)
        equal = sum(lines(r["interp"]) == lines(r["srcslice"]) for r in ok)
        ref = sum(len(lines(r["interp"])) for r in ok)
        got = sum(len(lines(r["srcslice"])) for r in ok)
        hit = sum(len(lines(r["interp"]) & lines(r["srcslice"])) for r in ok)
        times = sorted({(r["file"], r["srcslice_s"]) for r in ok})
        med = sorted(t for _, t in times)[len(times) // 2]
        out[corpus] = {"files": len({r["file"] for r in ok}), "qubits": len(ok), "contain": contain, "equal": equal,
                       "recall": round(hit / ref, 4) if ref else 1.0, "precision": round(hit / got, 4) if got else 1.0,
                       "median_srcslice_ms": round(1000 * med, 1),
                       "errors": sum(1 for r in rows if r["corpus"] == corpus and r["error"] not in ("", "no circuit", "no qubit acted on"))}
    dv = [r for r in rows if r["corpus"] in ("dev", "bugs4q") and not r["error"]] or \
        [r for r in rows if not r["error"]]  # held-out run: LintQ files only
    share = sum(lines(r["interp"]) <= lines(r["srcslice"]) for r in dv) / len(dv)
    out["decision"] = {"dev_bugs4q_contain_share": round(share, 4), "threshold": 0.95,
                       "adopt_srcslice_lines": share >= 0.95}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--heldout", type=int, default=0,
                    help="Deviation I-23: N LintQ-corpus files with a circuit (S1), outside the I-17 sample, instead")
    ap.add_argument("--seed", type=int, default=20261028)
    a = ap.parse_args()
    global OUT
    data = Path(a.data_root)
    if a.heldout:
        import random
        OUT = RES / "srcslice_heldout"
        used = {r["file"] for r in csv.DictReader(open(RES / "profiles" / "lintq500.csv"))}
        pool = sorted({r["file"] for r in csv.DictReader(open(RES / "scale" / "s1_lintq.csv"))
                       if not r["error"] and r["file"] not in used})
        pick = sorted(random.Random(a.seed).sample(pool, a.heldout))
        jobs = [("lintq", data / CORPORA["lintq"][0] / f, f) for f in pick]
    else:
        jobs = [("dev", p, str(p.relative_to(ROOT))) for p in DEV]
        for corpus, (sub, lst) in CORPORA.items():
            with open(RES / "profiles" / lst) as fh:
                files = sorted({r["file"] for r in csv.DictReader(fh) if not r["error"]})
            jobs += [(corpus, data / sub / f, f) for f in files]
    t0 = time.time()
    rows = []
    for r in run_all(one, jobs, TIMEOUT, timed_out, a.workers):
        rows.extend(r)
    OUT.mkdir(parents=True, exist_ok=True)
    keys = ["corpus", "file", "qubit", "quantum", "interp", "srcslice", "srcslice_s", "profiles", "error"]
    with open(OUT / "qubits.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    summ = summarize(rows)
    summ["srcslice_version"] = "upstream ce86ef8 + tools/srcslice/srcslice-python.diff"
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps(summ, indent=1), f"\n{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
