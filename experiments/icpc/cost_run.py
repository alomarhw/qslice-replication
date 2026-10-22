"""RQ4 cost and graph size (PROTOCOL_ICPC.md section 8): descriptive.

Inputs: F-depth (depth sweep at width 8, families/generate.py) and a width sweep, F-ghz(n, k=n//2)
and F-inv(w, d=10) at widths 4-14 (the k and d of the sweep are fixed here); graph size also on
corpus A. Per circuit, in a fresh process: QDG build time; for every criterion, S-lc time and S-q
time (entanglement_pruned_slice: mutual-information nomination + exact verification); S-q end to end
= build + all S-q calls; peak resident memory; QDG nodes and edges by type (DATA, CONTROL,
ENTANGLEMENT). Limits as PROTOCOL_RQ5.md: 120 s wall time, 4 GiB resident memory, 4 concurrent; a run
over a limit is reported as not completed. The machine is recorded in machine.json. Run it on an
otherwise idle machine: timings are wall-clock.
Outputs (results/icpc/cost/): stages.jsonl, circuits.csv, machine.json.
Usage (from experiments/): python icpc/cost_run.py --data-root ../data --eval-code ../selection
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
OUT = HERE / "results" / "icpc" / "cost"
WALL_S, RSS_GIB, CONCURRENT = 120, 4, 4


def inputs(data_root: str, eval_code: str):
    from families.generate import f_ghz, f_inv, families
    out = [("F-depth", n, None) for f, n, _ in families() if f == "F-depth"]
    out += [("width-F-ghz", f"n{w}_k{w // 2}", None) for w in range(4, 15)]
    out += [("width-F-inv", f"w{w}_d10", None) for w in range(4, 15)]
    from common.corpus import corpus_a
    out += [("corpusA-graph", e.name, e.path) for e in corpus_a(Path(data_root).resolve(), Path(eval_code)) if e.qc is not None]
    return out


def _circuit(kind: str, name: str, rel, data_root: str):
    from families.generate import f_ghz, f_inv, families
    if kind == "F-depth":
        return next(c for f, n, c in families() if f == "F-depth" and n == name)
    if kind == "width-F-ghz":
        n, k = (int(x[1:]) for x in name.split("_"))
        return f_ghz(n, k)
    if kind == "width-F-inv":
        w, d = (int(x[1:]) for x in name.split("_"))
        return f_inv(w, d)
    from common.corpus import load
    return load(Path(data_root) / rel)


def _emit(fh, **rec):
    rec["peak_rss_mib"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, 1)
    fh.write(json.dumps(rec) + "\n")
    fh.flush()


def one(kind, name, rel, data_root, log):
    from slicers.registry import Slicers
    qc = _circuit(kind, name, rel, data_root)
    n = qc.num_qubits
    with open(log, "a") as fh:
        t0 = time.perf_counter()
        s = Slicers(qc, name)
        tb = time.perf_counter() - t0
        g = s.full.graph
        et = {}
        for _, _, d in g.edges(data=True):
            k = str(getattr(d.get("edge_type"), "value", d.get("edge_type")))
            et[k] = et.get(k, 0) + 1
        _emit(fh, kind=kind, name=name, stage="graph", n_qubits=n, n_ops=len(qc.data), depth=qc.depth(),
              build_seconds=round(tb, 4), nodes=g.number_of_nodes(), edges=et)
        if kind == "corpusA-graph":
            _emit(fh, kind=kind, name=name, stage="done")
            return 0
        lc_t, q_t = [], []
        for t in range(n):
            t1 = time.perf_counter()
            s.lc(t)
            lc_t.append(time.perf_counter() - t1)
            t1 = time.perf_counter()
            s.q(t)
            q_t.append(time.perf_counter() - t1)
            _emit(fh, kind=kind, name=name, stage=f"q:{t}", lc_seconds=round(lc_t[-1], 5), q_seconds=round(q_t[-1], 4))
        _emit(fh, kind=kind, name=name, stage="done", lc_total=round(sum(lc_t), 4), q_total=round(sum(q_t), 4),
              q_end_to_end=round(tb + sum(q_t), 4))
    return 0


def _rss_mib(pid):
    o = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return int(o) / 1024 if o else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--eval-code", default="../selection")
    ap.add_argument("--one", nargs=3, default=None)
    ap.add_argument("--log", default=str(OUT / "stages.jsonl"))
    a = ap.parse_args()
    if a.one:
        kind, name, rel = a.one
        return one(kind, name, None if rel == "-" else rel, a.data_root, a.log)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "machine.json").write_text(json.dumps({"platform": platform.platform(), "machine": platform.machine(),
                                                  "processor": platform.processor(), "cpu_count": os.cpu_count(),
                                                  "python": platform.python_version(), "wall_s": WALL_S,
                                                  "rss_gib": RSS_GIB, "concurrent": CONCURRENT}, indent=1))
    todo = inputs(a.data_root, a.eval_code)
    log = Path(a.log)
    running, t0 = {}, time.time()
    while todo or running:
        while todo and len(running) < CONCURRENT:
            kind, name, rel = todo.pop(0)
            p = subprocess.Popen([sys.executable, __file__, "--data-root", a.data_root, "--one", kind, name, rel or "-",
                                  "--log", str(log)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            running[p.pid] = [(kind, name), p, time.time(), 0.0]
        time.sleep(0.2)
        for pid in list(running):
            c, p, start, peak = running[pid]
            rss = _rss_mib(pid)
            running[pid][3] = peak = max(peak, rss)
            over = "wall" if time.time() - start > WALL_S else "memory" if rss > RSS_GIB * 1024 else None
            if p.poll() is not None or over:
                if over:
                    p.kill()
                    p.wait()
                if over or p.returncode != 0:
                    err = "" if over else p.stderr.read().decode(errors="replace")[-300:]
                    with open(log, "a") as fh:
                        fh.write(json.dumps({"kind": c[0], "name": c[1], "stage": "limit" if over else "error",
                                             "limit": over, "seconds": round(time.time() - start, 1),
                                             "peak_rss_mib": round(peak, 1), "stderr": err}) + "\n")
                del running[pid]
    rows = {}
    for r in map(json.loads, log.read_text().splitlines()):
        k = (r["kind"], r["name"])
        row = rows.setdefault(k, {"kind": r["kind"], "name": r["name"], "completed": 0, "limit": ""})
        if r["stage"] == "graph":
            row |= {x: r[x] for x in ("n_qubits", "n_ops", "depth", "build_seconds", "nodes")}
            row |= {f"edges_{t}": v for t, v in r["edges"].items()}
        elif r["stage"] == "done":
            row |= {"completed": 1, "peak_rss_mib": r["peak_rss_mib"]} | {x: r[x] for x in ("lc_total", "q_total", "q_end_to_end") if x in r}
        elif r["stage"] in ("limit", "error"):
            row |= {"limit": r.get("limit") or "error", "peak_rss_mib": r.get("peak_rss_mib")}
    rows = list(rows.values())
    with open(OUT / "circuits.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} circuits; completed {sum(r['completed'] for r in rows)}; {time.time() - t0:.0f}s; wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
