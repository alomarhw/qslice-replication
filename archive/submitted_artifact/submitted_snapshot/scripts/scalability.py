"""Structural scalability of QPDG construction (no simulation), measured on real benchmark circuits.
For each circuit we time the QPDG build and count the ENTANGLEMENT dependencies the QPDG exposes --
the non-local dependencies a classical UED-only (def-use) slicer cannot represent and therefore drops.
Purely structural, so it scales far beyond the exact-simulation ceiling. Writes
results/TAB_scalability.csv and figures/fig_scalability.png.
"""
import csv, os, signal, sys, time
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from qasm_loader import parse_qasm_file
from qdg import build_qdg

HERE = os.path.dirname(__file__); ROOT = os.path.join(HERE, "..")
CORPORA = ["data/qasmbench", "data/QASMBench-master", "data/mqtbench", "data/veriqbench"]
MAX_Q, MAX_OPS, MAX_FILE_KB, PER_CIRCUIT_S = 200, 4000, 800, 8

class _TO(Exception): pass
def _alarm(s, f): raise _TO()
signal.signal(signal.SIGALRM, _alarm)

rows = []; seen = set()
for corp in CORPORA:
    base = Path(os.path.join(ROOT, corp))
    if not base.is_dir(): continue
    for p in sorted(base.rglob("*.qasm")):
        if p.stat().st_size > MAX_FILE_KB * 1024: continue
        signal.alarm(PER_CIRCUIT_S)
        try:
            c = parse_qasm_file(p)
            if c.num_qubits < 2 or not c.ops or c.num_qubits > MAX_Q or len(c.ops) > MAX_OPS:
                signal.alarm(0); continue
            key = (c.name, c.num_qubits, len(c.ops))
            if key in seen: signal.alarm(0); continue
            seen.add(key)
            t0 = time.perf_counter(); q = build_qdg(c); dt = (time.perf_counter() - t0) * 1000.0
            ent = sum(1 for lst in q.edges.values() for (_, typ) in lst if typ == "entanglement")
            rows.append({"circuit": c.name, "n_qubits": c.num_qubits, "n_ops": len(c.ops),
                         "entanglement_deps": ent, "qpdg_build_ms": round(dt, 4)})
        except _TO:
            print(f"  skip (timeout) {p.name}", flush=True)
        except Exception:
            pass
        finally:
            signal.alarm(0)
        if len(rows) % 25 == 0 and rows: print(f"  {len(rows)} circuits...", flush=True)

rows.sort(key=lambda r: (r["n_qubits"], r["n_ops"]))
out = os.path.join(ROOT, "results", "TAB_scalability.csv")
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    xs=[r["n_qubits"] for r in rows]; e=[max(r["entanglement_deps"],0) for r in rows]; t=[max(r["qpdg_build_ms"],1e-3) for r in rows]
    fig, ax1 = plt.subplots(figsize=(7.2,3.8), constrained_layout=True); c1,c2="#1b9e77","#7570b3"
    ax1.scatter(xs,e,s=18,c=c1,alpha=0.7); ax1.set_xlabel("Circuit size (qubits)")
    ax1.set_ylabel("Entanglement dependencies (dropped by classical)",color=c1); ax1.tick_params(axis="y",labelcolor=c1)
    ax1.set_yscale("symlog"); ax1.grid(alpha=0.2)
    ax2=ax1.twinx(); ax2.scatter(xs,t,s=14,c=c2,alpha=0.6,marker="^"); ax2.set_ylabel("QPDG construction time (ms)",color=c2)
    ax2.tick_params(axis="y",labelcolor=c2); ax2.set_yscale("log")
    fig.savefig(os.path.join(ROOT,"figures","fig_scalability.png"),dpi=220)
except Exception as ex: print("  (figure skipped:",ex,")")
n=len(rows); print(f"scalability: {n} circuits, {min(r['n_qubits'] for r in rows)}-{max(r['n_qubits'] for r in rows)} qubits; "
      f"QPDG build <1s on {sum(1 for r in rows if r['qpdg_build_ms']<1000)}/{n} (max {max(r['qpdg_build_ms'] for r in rows):.1f} ms)", flush=True)
