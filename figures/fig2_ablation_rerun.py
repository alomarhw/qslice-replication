"""Fig. 2: edge-type ablation from the pre-registered run (experiments/results/rq4_ablation).

Bars: delta-SVR per removed edge type over all (circuit, criterion) pairs of corpora A+B (the primary
metric), with the dynamic-circuit subset alongside. Values are printed on the bars. The full slicer's own
SVR is stated in the caption line, since it is not 0.

Usage: python fig2_ablation_rerun.py [results_dir] [out_png]
"""

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
res = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "experiments" / "results" / "rq4_ablation"
out = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "fig2_ablation_rerun.png"
rows = list(csv.DictReader(open(res / "TAB_ablation_rerun.csv")))
ORDER = ["QDG-no-ED", "QDG-no-MD", "QDG-no-UED", "QDG-no-CD"]
LAB = {"QDG-no-ED": "ED", "QDG-no-MD": "MD", "QDG-no-UED": "UED", "QDG-no-CD": "CD"}
SCOPES = [("A+B", "all pairs (A+B)", "#1F4E79"), ("dynamic circuits in A+B", "dynamic-circuit pairs", "#9DB9D5")]


def get(scope, variant, key):
    for r in rows:
        if r["scope"] == scope and r["unit"] == "pair" and r["variant"] == variant:
            return r[key]
    raise KeyError((scope, variant))


fig, ax = plt.subplots(figsize=(7.2, 3.9))
w = 0.38
for j, (scope, label, colour) in enumerate(SCOPES):
    xs = [i + (j - 0.5) * w for i in range(len(ORDER))]
    ys = [float(get(scope, v, "delta_svr")) for v in ORDER]
    n = get(scope, "QSlice-full", "n")
    bars = ax.bar(xs, ys, w - 0.04, color=colour, label=f"{label} (n={n})", zorder=2)
    for b, y in zip(bars, ys):
        ax.text(b.get_x() + b.get_width() / 2, y + 0.012, f"{y:.3f}", ha="center", va="bottom", fontsize=8.5)
ax.set_xticks(range(len(ORDER)), [f"{LAB[v]} removed" for v in ORDER])
ax.set_ylabel("ΔSVR vs. full slicer")
ax.set_ylim(0, 0.62)
ax.grid(axis="y", alpha=0.3, zorder=0)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(frameon=False, fontsize=9, loc="upper right")
full_all = float(get("A+B", "QSlice-full", "svr"))
full_dyn = float(get("dynamic circuits in A+B", "QSlice-full", "svr"))
ax.set_title(f"Full four-edge slicer SVR: {full_all:.4f} (all pairs), {full_dyn:.4f} (dynamic)", fontsize=9.5)
fig.tight_layout()
fig.savefig(out, dpi=220)
print(f"wrote {out}")
