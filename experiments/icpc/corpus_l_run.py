"""Corpus L run (PROTOCOL_ICPC.md section 3.5): soundness, size and cost beyond the corpus-A caps.

For each circuit of results/icpc/corpus_l/corpus_l.json, a worker process (`--one PATH`) slices every
qubit with S-du, S-lc, S-lcq, S-yz and S-q, then checks each slice with the oracle (qubit limit 20,
branch limit 64 above 16 qubits). The parent runs at most 2 workers at a time and stops a worker
that exceeds 600 s wall time or 8 GiB resident memory (polled with `ps`); the stage that was running
is reported as not completed, with the limit it hit. The worker logs one JSON line per finished
stage, so stages completed before the limit are kept.
Fallback (section 3.1): S-q returns the light cone unpruned when Statevector(circuit) fails
(measurement, reset, feedback); recorded per circuit as qslice/qdg.py decides it.
Outputs (results/icpc/corpus_l/): stages.jsonl (raw), circuits.csv, slices.csv.
Usage (from experiments/): python icpc/corpus_l_run.py --data-root ../data
"""

from __future__ import annotations

import argparse
import csv
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
OUT = HERE / "results" / "icpc" / "corpus_l"
SLICERS = ["du", "lc", "lcq", "yz", "q"]
WALL_S, RSS_GIB, CONCURRENT = 600, 8, 2


def _emit(fh, **rec):
    rec["peak_rss_mib"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, 1)  # macOS: bytes
    fh.write(json.dumps(rec) + "\n")
    fh.flush()


def one(path: str, data_root: str, log: str) -> int:
    from common.corpus import load
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from qiskit.quantum_info import Statevector
    from slicers.registry import NotApplicable, Slicers

    with open(log, "a") as fh:
        t0 = time.time()
        qc = load(Path(data_root) / path)
        n = qc.num_qubits
        try:
            Statevector(qc)
            fallback = 0
        except Exception:  # noqa: BLE001 - qslice/qdg.py's own condition for the unpruned light cone
            fallback = 1
        s = Slicers(qc, Path(path).stem)
        _emit(fh, path=path, stage="graph", seconds=round(time.time() - t0, 3), n_qubits=n, n_ops=len(qc.data),
              fallback=fallback)
        slices = {}
        for m in SLICERS:
            t1 = time.time()
            try:
                slices[m] = {t: sorted(s.get(m)(t)) for t in range(n)}
                _emit(fh, path=path, stage=f"slice:{m}", seconds=round(time.time() - t1, 3), slices=slices[m])
            except NotApplicable as exc:
                _emit(fh, path=path, stage=f"slice:{m}", seconds=round(time.time() - t1, 3), not_applicable=str(exc)[:200])
        t1 = time.time()
        base = oi.reduced_states(qc, range(n), max_qubits=20)
        cache, sound = {}, {}
        for m, per in slices.items():
            sound[m] = {}
            for t, sl in per.items():
                key = frozenset(sl)
                if key not in cache:
                    cache[key] = oi.reduced_states(materialise(qc, key), range(n), max_qubits=20)
                sound[m][t] = oi.uhlmann_fidelity(base[t], cache[key][t]) >= 1 - oi.FIDELITY_EPS
        _emit(fh, path=path, stage="oracle", seconds=round(time.time() - t1, 3), sound={m: {str(t): int(v) for t, v in d.items()}
                                                                                        for m, d in sound.items()})
        _emit(fh, path=path, stage="done", seconds=round(time.time() - t0, 3))
    return 0


def _rss_mib(pid: int) -> float:
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return int(out) / 1024 if out else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--one", default=None)
    ap.add_argument("--log", default=str(OUT / "stages.jsonl"))
    a = ap.parse_args()
    if a.one:
        return one(a.one, a.data_root, a.log)
    sel = json.loads((OUT / "corpus_l.json").read_text())["selected"]
    log = Path(a.log)
    done = set()
    if log.exists():
        done = {r["path"] for r in map(json.loads, log.read_text().splitlines()) if r.get("stage") in ("done", "limit", "error")}
    todo = [c for c in sel if c["path"] not in done]
    print(f"{len(done)} circuits already finished, {len(todo)} to run", flush=True)
    running = {}  # pid -> (circuit, Popen, start, peak_rss)
    t0 = time.time()
    while todo or running:
        while todo and len(running) < CONCURRENT:
            c = todo.pop(0)
            p = subprocess.Popen([sys.executable, __file__, "--data-root", a.data_root, "--one", c["path"], "--log", str(log)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            running[p.pid] = [c, p, time.time(), 0.0]
        time.sleep(0.5)
        for pid in list(running):
            c, p, start, peak = running[pid]
            rss = _rss_mib(pid)
            running[pid][3] = peak = max(peak, rss)
            over = "wall" if time.time() - start > WALL_S else "memory" if rss > RSS_GIB * 1024 else None
            if p.poll() is not None or over:
                if over:
                    p.kill()
                    p.wait()
                err = p.stderr.read().decode(errors="replace")[-400:] if p.stderr else ""
                if over or p.returncode != 0:
                    with open(log, "a") as fh:
                        fh.write(json.dumps({"path": c["path"], "stage": "limit" if over else "error", "limit": over,
                                             "seconds": round(time.time() - start, 1), "peak_rss_mib": round(peak, 1),
                                             "stderr": "" if over else err}) + "\n")
                del running[pid]
                print(f"  {c['path']}: {'LIMIT ' + over if over else ('ok' if p.returncode == 0 else 'error')} "
                      f"({time.time() - start:.0f}s, {peak:.0f} MiB); {time.time() - t0:.0f}s total", flush=True)
    summarize(log, sel)
    return 0


def summarize(log: Path, sel) -> None:
    """circuits.csv: one row per circuit (stages completed, limit hit, S-q time and peak memory, fallback);
    slices.csv: one row per (circuit, qubit, slicer) with size, size relative to S-lc, and soundness."""
    recs = {}
    for r in map(json.loads, log.read_text().splitlines()):
        recs.setdefault(r["path"], []).append(r)
    crow, srow = [], []
    for c in sel:
        rs = recs.get(c["path"], [])
        st = {r["stage"]: r for r in rs}
        g = st.get("graph", {})
        lim = next((r for r in rs if r["stage"] in ("limit", "error")), None)
        stages = [r["stage"] for r in rs if r["stage"] not in ("limit", "error")]
        nxt = ["graph"] + [f"slice:{m}" for m in SLICERS] + ["oracle", "done"]
        stopped_at = next((x for x in nxt if x not in stages), "") if lim else ""
        crow.append({**{k: c[k] for k in ("corpus", "name", "path", "n_qubits", "n_ops")},
                     "completed": int("done" in st),
                     "limit": (lim or {}).get("limit") or (("oracle branch limit" if "measurement branches" in (lim or {}).get("stderr", "")
                                                          else "error") if lim else ""),
                     "stopped_at": stopped_at, "fallback": g.get("fallback", ""),
                     "q_seconds": st.get("slice:q", {}).get("seconds", ""),
                     "q_peak_rss_mib": st.get("slice:q", {}).get("peak_rss_mib", ""),
                     "total_seconds": st.get("done", {}).get("seconds", "")})
        sound = st.get("oracle", {}).get("sound", {})
        lc = st.get("slice:lc", {}).get("slices", {})
        for m in SLICERS:
            r = st.get(f"slice:{m}")
            if not r:
                continue
            if "not_applicable" in r:
                srow.append({"path": c["path"], "slicer": m, "target": "", "applicable": 0, "note": r["not_applicable"]})
                continue
            for t, sl in r["slices"].items():
                base = len(lc.get(t, [])) if lc else None
                srow.append({"path": c["path"], "corpus": c["corpus"], "slicer": m, "target": t, "applicable": 1,
                             "size": len(sl), "size_rel_lc": (len(sl) / base) if base else "",
                             "sound": sound.get(m, {}).get(str(t), "")})
    for name, rows in (("circuits.csv", crow), ("slices.csv", srow)):
        with open(OUT / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
            w.writeheader()
            w.writerows(rows)
    print(f"completed {sum(r['completed'] for r in crow)}/{len(crow)} circuits; wrote circuits.csv, slices.csv")


if __name__ == "__main__":
    sys.exit(main())
