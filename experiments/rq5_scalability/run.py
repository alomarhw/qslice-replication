"""RQ5 scalability of the Sec. III implementation, under the pre-registered protocol (../PROTOCOL.md,
section 5).

Part S (structural, 1,124 circuits): the circuits of the submitted Table VII, selected by the same rules
as the submitted scripts/scalability.py and checked row by row against it. Each circuit is loaded as
written and prepared (common/corpus.py). Measured per circuit, in a fresh process:
  - QDG construction time (method prototype with the control-edge patch: data, control, entanglement);
  - edge counts by type;
  - causal backward slice time from qubit 0;
  - peak resident memory of the process.

Part E (end to end, corpus A, 158 circuits): per circuit, in a fresh process, QDG construction plus
`entanglement_pruned_slice` (causal cone + mutual-information pruning + exact verification) for every
qubit. Measured: total wall time, the slowest single criterion, and peak resident memory.

Limits, fixed in advance: 120 s wall time and 4 GiB resident memory per circuit. A circuit that exceeds
either is killed and recorded as not completed, with the limit it hit. That is a scalability result, not
an exclusion.

Usage: python run.py --data-root DATA --eval-code EVAL_CODE --method-code METHOD_CODE --reference REF_CSV --out OUT
       (internal) python run.py --one PART PATH ...
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

TIME_LIMIT_S, MEM_LIMIT_KB, WORKERS = 120, 4 * 1024 * 1024, 4
S_FIELDS = ["circuit", "path", "n_qubits", "n_ops_submitted", "n_instructions_prepared", "status",
            "build_ms", "edges_data", "edges_control", "edges_entanglement", "causal_slice_ms", "peak_rss_mb"]
E_FIELDS = ["corpus", "circuit", "path", "n_qubits", "n_instructions_prepared", "status", "build_ms",
            "prune_total_ms", "prune_max_ms", "n_criteria", "peak_rss_mb"]


def _peak_rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 2**20 if platform.system() == "Darwin" else r / 1024  # bytes on macOS, KiB on Linux


def select_structural(data_root: Path, eval_code: Path):
    """Same selection as the submitted scripts/scalability.py (corpora order, file-size cap, qubit/op caps,
    8 s parse timeout, de-duplication, final sort), but keeping each circuit's path."""
    sys.path.insert(0, str(eval_code))
    from qasm_loader import parse_qasm_file

    class _TO(Exception):
        pass

    def _alarm(s, f):
        raise _TO()

    signal.signal(signal.SIGALRM, _alarm)
    rows, seen = [], set()
    for corp in ["qasmbench", "QASMBench-master", "mqtbench", "veriqbench"]:
        base = data_root / corp
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.qasm")):
            if p.stat().st_size > 800 * 1024:
                continue
            signal.alarm(8)
            try:
                c = parse_qasm_file(p)
                if c.num_qubits < 2 or not c.ops or c.num_qubits > 200 or len(c.ops) > 4000:
                    continue
                key = (c.name, c.num_qubits, len(c.ops))
                if key in seen:
                    continue
                seen.add(key)
                rows.append({"circuit": c.name, "n_qubits": c.num_qubits, "n_ops": len(c.ops),
                             "path": str(p.relative_to(data_root))})
            except _TO:
                pass
            except Exception:
                pass
            finally:
                signal.alarm(0)
    rows.sort(key=lambda r: (r["n_qubits"], r["n_ops"]))
    return rows


def one(part: str, rel: str, data_root: str, method_code: str) -> dict:
    sys.path.insert(0, method_code)
    from common.corpus import load
    from method_eval.control_fix import QDGControlFixed as QDG
    from qdg import EdgeType

    qc = load(Path(data_root) / rel)
    n = qc.num_qubits
    t0 = time.perf_counter()
    g = QDG(qc, rel)
    g.build(include_entanglement=True, include_control=True)
    build_ms = (time.perf_counter() - t0) * 1000
    if part == "S":
        counts = {t: 0 for t in EdgeType}
        for _, _, d in g.graph.edges(data=True):
            counts[d["edge_type"]] += 1
        t1 = time.perf_counter()
        g.remove_edge_type(EdgeType.ENTANGLEMENT).backward_slice(0)
        return {"n_instructions_prepared": len(qc.data), "status": "completed", "build_ms": round(build_ms, 3),
                "edges_data": counts[EdgeType.DATA], "edges_control": counts[EdgeType.CONTROL],
                "edges_entanglement": counts[EdgeType.ENTANGLEMENT],
                "causal_slice_ms": round((time.perf_counter() - t1) * 1000, 3), "peak_rss_mb": round(_peak_rss_mb(), 1)}
    times = []
    for t in range(n):
        t1 = time.perf_counter()
        g.entanglement_pruned_slice(t)
        times.append((time.perf_counter() - t1) * 1000)
    return {"n_instructions_prepared": len(qc.data), "status": "completed", "build_ms": round(build_ms, 3),
            "prune_total_ms": round(sum(times), 3), "prune_max_ms": round(max(times), 3), "n_criteria": n,
            "peak_rss_mb": round(_peak_rss_mb(), 1)}


def _rss_kb(pid: int) -> int:
    try:
        return int(subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip() or 0)
    except ValueError:
        return 0


def run_many(part, jobs, args):
    """Run each circuit in its own process, at most WORKERS at a time, enforcing the limits."""
    pending, running, results = list(jobs), {}, {}
    while pending or running:
        while pending and len(running) < WORKERS:
            key, rel = pending.pop(0)
            cmd = [sys.executable, __file__, "--one", part, rel, "--data-root", args.data_root,
                   "--method-code", args.method_code]
            running[key] = (subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True),
                            time.time(), 0)
        time.sleep(0.2)
        for key in list(running):
            proc, start, peak = running[key]
            peak = max(peak, _rss_kb(proc.pid))
            running[key] = (proc, start, peak)
            if proc.poll() is not None:
                out = proc.stdout.read().strip().splitlines()
                results[key] = json.loads(out[-1]) if proc.returncode == 0 and out else {"status": f"error (exit {proc.returncode})"}
                del running[key]
            elif time.time() - start > TIME_LIMIT_S or peak > MEM_LIMIT_KB:
                proc.kill()
                proc.wait()
                limit = "time" if time.time() - start > TIME_LIMIT_S else "memory"
                results[key] = {"status": f"not completed ({limit} limit)", "peak_rss_mb": round(peak / 1024, 1)}
                del running[key]
        done = len(results)
        if done and done % 50 == 0 and not getattr(run_many, "_last", None) == (part, done):
            run_many._last = (part, done)
            print(f"  part {part}: {done}/{len(jobs)} circuits", flush=True)
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--one", nargs=2, metavar=("PART", "PATH"))
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--method-code", required=True)
    ap.add_argument("--eval-code")
    ap.add_argument("--reference", help="submitted TAB_scalability.csv, to check the structural selection")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.one:
        print(json.dumps(one(a.one[0], a.one[1], a.data_root, str(Path(a.method_code).resolve()))), flush=True)
        return 0
    from common.corpus import corpus_a
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    root = Path(a.data_root)
    sel = select_structural(root, Path(a.eval_code))
    ref = [(r["circuit"], int(r["n_qubits"]), int(r["n_ops"])) for r in csv.DictReader(open(a.reference))]
    got = [(r["circuit"], r["n_qubits"], r["n_ops"]) for r in sel]
    same = ref == got
    print(f"structural selection: {len(got)} circuits; identical to the submitted Table VII rows: {same}", flush=True)
    if not same:
        raise SystemExit("selection differs from the submitted Table VII; stopping (PROTOCOL 5.1)")
    machine = {"platform": platform.platform(), "python": platform.python_version(), "cpu_count": os.cpu_count(),
               "workers": WORKERS, "time_limit_s": TIME_LIMIT_S, "memory_limit_gib": MEM_LIMIT_KB / 2**20}
    try:
        machine["cpu"] = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
        machine["memory_gib"] = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout) / 2**30
    except Exception:
        pass
    (out / "machine.json").write_text(json.dumps(machine, indent=2))

    t0 = time.time()
    res = run_many("S", [(i, r["path"]) for i, r in enumerate(sel)], a)
    rows = []
    for i, r in enumerate(sel):
        rows.append({"circuit": r["circuit"], "path": r["path"], "n_qubits": r["n_qubits"],
                     "n_ops_submitted": r["n_ops"]} | res[i])
    with open(out / "TAB_scalability_structural.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=S_FIELDS, restval="")
        w.writeheader()
        w.writerows(rows)
    print(f"part S done in {time.time() - t0:.0f}s", flush=True)

    A = [e for e in corpus_a(root, Path(a.eval_code)) if e.qc is not None]
    t0 = time.time()
    res = run_many("E", [(i, e.path) for i, e in enumerate(A)], a)
    rows = [{"corpus": e.corpus, "circuit": e.name, "path": e.path, "n_qubits": e.qc.num_qubits} | res[i]
            for i, e in enumerate(A)]
    with open(out / "TAB_scalability_end_to_end.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=E_FIELDS, restval="")
        w.writeheader()
        w.writerows(rows)
    print(f"part E done in {time.time() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
