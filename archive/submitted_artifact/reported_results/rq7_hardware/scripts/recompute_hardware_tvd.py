"""Recompute the real IBM-Q (ibm_cleveland) hardware proof-of-concept results (RQ5) from the captured
SamplerV2 job results in data/ibm_cleveland_jobs/. Writes results/TAB_hardware_ibmq.csv and
figures/fig_ibmq_hardware_tvd.png.

Each job ran two pubs: pub0 = FULL circuit (criterion qubit measured among others), pub1 = the QSlice
backward SLICE (criterion qubit measured). We compare the criterion-qubit marginal of slice vs full as
measured on hardware; a slice is "marginal-preserved" if TVD < delta (delta = 0.05). Requires
qiskit-ibm-runtime to deserialize the captured results.
"""
import csv, glob, json, os
from qiskit_ibm_runtime.utils.json import RuntimeDecoder

HERE = os.path.dirname(__file__)
JOBS = os.path.join(HERE, "..", "data", "ibm_cleveland_jobs")
DELTA = 0.05
# Known benchmark labels for the published 6-circuit subset (others reported by job id).
LABELS = {"d8tle4cb": "teleport", "d8tle6dp": "teleport-T", "d8tle2kt": "wstate",
          "d8tje0lp": "wstate-T", "d8tle84b": "qaoa", "d8tlea4t": "qaoa-T"}

def reg_counts(resfile):
    d = json.load(open(resfile), cls=RuntimeDecoder); out = []
    for i in range(len(d)):
        data = d[i].data
        reg = [getattr(data, k) for k in data.__dict__ if hasattr(getattr(data, k), "get_counts")][0]
        out.append((reg.get_counts(), reg.num_bits))
    return out

def marg(counts, bitpos, nbits):
    tot = sum(counts.values())
    return sum(v for bs, v in counts.items() if bs.replace(" ", "").zfill(nbits)[nbits - 1 - bitpos] == "1") / tot

rows = []
for rf in sorted(glob.glob(os.path.join(JOBS, "*-result.json"))):
    jid = os.path.basename(rf).split("-result")[0]; short = jid.replace("job-", "")[:8]
    pubs = reg_counts(rf)
    if len(pubs) < 2: continue
    (full_c, fnb), (slice_c, snb) = pubs[0], pubs[1]
    crit = max(range(snb), key=lambda b: (lambda p: p * (1 - p))(marg(slice_c, b, snb)))
    pf, ps = marg(full_c, crit, fnb), marg(slice_c, crit, snb); tvd = abs(pf - ps)
    rows.append({"circuit": LABELS.get(short, short), "job_id": jid, "criterion_qubit": crit,
                 "P_full_1": round(pf, 4), "P_slice_1": round(ps, 4), "TVD": round(tvd, 4),
                 "marginal_preserved": tvd < DELTA})
rows.sort(key=lambda r: r["TVD"])
npres = sum(r["marginal_preserved"] for r in rows)

out = os.path.join(HERE, "..", "results", "TAB_hardware_ibmq.csv")
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    labels = [r["circuit"] for r in rows]; tvds = [r["TVD"] for r in rows]
    colors = ["#1f77b4" if r["marginal_preserved"] else "#d95f02" for r in rows]
    fig, ax = plt.subplots(figsize=(8.4, 3.8), constrained_layout=True)
    ax.bar(range(len(rows)), tvds, color=colors)
    ax.axhline(DELTA, ls="--", color="black", lw=1)
    ax.text(len(rows) - 0.5, DELTA + 0.01, f"delta = {DELTA}", ha="right", fontsize=9)
    ax.set_xticks(range(len(rows))); ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=7)
    ax.set_ylabel("TVD (slice vs full) on ibm_cleveland"); ax.set_ylim(0, max(0.55, max(tvds) + 0.05))
    ax.grid(axis="y", alpha=0.25)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color="#1f77b4", label=f"marginal preserved (TVD<{DELTA})"),
                       Patch(color="#d95f02", label="soundness violation (TVD>delta)")], frameon=False, fontsize=8)
    fig.savefig(os.path.join(HERE, "..", "figures", "fig_ibmq_hardware_tvd.png"), dpi=220)
except Exception as e:
    print("  (figure skipped:", e, ")")

print(f"ibm_cleveland: {npres}/{len(rows)} circuits marginal-preserved (TVD < {DELTA}); wrote {out} + figure")
