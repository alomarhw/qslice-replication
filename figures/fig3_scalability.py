"""Fig. 3: scalability of the Sec. III implementation (experiments/results/rq5_scalability).

(a) structural: QDG construction time per circuit vs qubits, for the 1,124 circuits of Table VII;
    circuits that hit the 120 s / 4 GiB limit are drawn at the top edge with an x; circuits that
    qiskit.qasm2 cannot parse are counted in the title (causes in error_diagnosis.csv).
(b) end to end: total time of entanglement-pruned slicing over all criteria per circuit vs qubits,
    for the 158 circuits of corpus A.
Also prints the summary statistics pre-registered in PROTOCOL_RQ5.md 5.3.

Usage: python fig3_scalability.py [results_dir] [out_png]
"""

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
RES = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "experiments" / "results" / "rq5_scalability"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "fig3_scalability.png"
S = list(csv.DictReader(open(RES / "TAB_scalability_structural.csv")))
E = list(csv.DictReader(open(RES / "TAB_scalability_end_to_end.csv")))


def summary(rows, col, label):
    done = [r for r in rows if r["status"] == "completed"]
    v = np.array([float(r[col]) for r in done])
    print(f"{label}: completed {len(done)}/{len(rows)}; median {np.median(v):.1f} ms, "
          f"p95 {np.percentile(v, 95):.1f} ms, max {v.max():.1f} ms; "
          f"peak memory max {max(float(r['peak_rss_mb'] or 0) for r in rows):.0f} MB")
    for s in sorted({r['status'] for r in rows} - {"completed"}):
        print(f"  {s}: {sum(1 for r in rows if r['status'] == s)}")
    return done


sd = summary(S, "build_ms", "structural build")
epi = [(int(r["edges_data"]) + int(r["edges_control"]) + int(r["edges_entanglement"])) /
       max(int(r["n_instructions_prepared"]), 1) for r in sd]
print(f"  edges per instruction: median {np.median(epi):.1f}, max {max(epi):.1f}")
ed = summary(E, "prune_total_ms", "end-to-end pruned slicing (all criteria)")

fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.8))
cap = 120_000
xs = [int(r["n_qubits"]) for r in sd]
a.scatter(xs, [max(float(r["build_ms"]), 1e-2) for r in sd], s=10, color="#1F4E79", alpha=0.6, label="completed")
nd = [r for r in S if r["status"].startswith("not completed")]
perr = sum(1 for r in S if r["status"].startswith("error"))
if nd:
    a.scatter([int(r["n_qubits"]) for r in nd], [cap] * len(nd), s=22, marker="x", color="#B91C1C",
              label=f"limit reached ({len(nd)})")
a.set_yscale("log")
a.set_xlabel("qubits")
a.set_ylabel("QDG construction time (ms)")
a.set_title(f"(a) structural: {len(sd)} of {len(S)} completed ({perr} not parsable by qiskit.qasm2)", fontsize=9.5)
a.legend(frameon=False, fontsize=8)
b.scatter([int(r["n_qubits"]) for r in ed], [float(r["prune_total_ms"]) for r in ed], s=12, color="#1F4E79", alpha=0.7)
ne = [r for r in E if r["status"].startswith("not completed")]
if ne:
    b.scatter([int(r["n_qubits"]) for r in ne], [cap] * len(ne), s=22, marker="x", color="#B91C1C",
              label=f"limit reached ({len(ne)})")
    b.legend(frameon=False, fontsize=8)
b.set_yscale("log")
b.set_xlabel("qubits")
b.set_ylabel("pruned slicing, all criteria (ms)")
b.set_title(f"(b) end to end: {len(ed)} of {len(E)} completed", fontsize=9.5)
for ax in (a, b):
    ax.grid(alpha=0.3)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(OUT, dpi=220)
print(f"wrote {OUT}")
