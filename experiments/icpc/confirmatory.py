"""Confirmatory family H1-H5 and the GO/NO-GO inputs (PROTOCOL_ICPC.md section 9).

Reads only committed result files; computes nothing new about circuits.
  H1  S-q invalid on fewer pairs than S-du (RQ1, 784 pairs at |0...0>): exact McNemar.
  H2  S-q smaller than S-lc (pairs sound under both): mean of size_lc - size_q as fractions of the
      circuit, bootstrap 95% CI (10,000, seed 42), Wilcoxon signed-rank, rank-biserial r.
  H3  pair robustness of S-q under R-haar >= 0.95 (all 784 pairs): Wilson 95% CI; one-sided exact
      binomial test against 0.95.
  H4  containment(S-q) >= containment(S-lc) - 0.05 (RQ3 primary units): exact McNemar on discordant
      units and a paired bootstrap 95% CI of the difference; holds iff the CI's lower bound > -0.05.
  H5  inspection cost of S-q < S-lc on units contained by both: Wilcoxon signed-rank on slice size
      (primary; listed first in section 4.3) and on the in-slice EXAM score (reported alongside).
Holm correction across the five p-values at alpha = 0.05.
Output: results/icpc/confirmatory/summary.json.
Usage (from experiments/): python icpc/confirmatory.py
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from common.evaluate import BOOT_RESAMPLES, SEED, mcnemar_exact, wilcoxon_paired  # noqa: E402

RES = HERE / "results" / "icpc"
OUT = RES / "confirmatory"


def wilson(k: int, n: int, z: float = 1.959964) -> list:
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [float(c - h), float(c + h)]


def holm(ps: dict, alpha: float = 0.05) -> dict:
    order = sorted(ps, key=ps.get)
    out, running = {}, 0.0
    for i, h in enumerate(order):
        adj = min(1.0, (len(order) - i) * ps[h])
        running = max(running, adj)
        out[h] = {"p_holm": running, "reject": running < alpha}
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rq1 = defaultdict(dict)
    for r in csv.DictReader(open(RES / "rq1" / "records.csv")):
        if r["applicable"] == "1":
            rq1[(r["path"], r["target"])][r["slicer"]] = r
    pairs = [v for v in rq1.values() if {"du", "q", "lc"} <= v.keys()]
    res = {"n_pairs_rq1": len(pairs)}

    # H1
    h1 = mcnemar_exact([v["q"]["sound"] != "1" for v in pairs], [v["du"]["sound"] != "1" for v in pairs])
    h1 |= {"invalid_q": sum(v["q"]["sound"] != "1" for v in pairs), "invalid_du": sum(v["du"]["sound"] != "1" for v in pairs)}
    res["H1"] = h1

    # H2
    both = [v for v in pairs if v["q"]["sound"] == "1" and v["lc"]["sound"] == "1"]
    lc = [float(v["lc"]["size_fraction"]) for v in both]
    q = [float(v["q"]["size_fraction"]) for v in both]
    h2 = wilcoxon_paired(lc, q)
    h2 |= {"mean_size_lc": float(np.mean(lc)), "mean_size_q": float(np.mean(q)),
           "relative_reduction": float(1 - np.mean(q) / np.mean(lc)),
           "q_strictly_smaller": sum(int(v["q"]["size"]) < int(v["lc"]["size"]) for v in both)}
    res["H2"] = h2

    # H3
    rob = [r for r in csv.DictReader(open(RES / "rq2_robustness" / "pairs.csv")) if r["slicer"] == "q" and r["regime"] == "R-haar"]
    k, n = sum(r["robust"] == "1" for r in rob), len(rob)
    pk = sum(r["robust"] == "1" for r in rob if r["pruned"] == "1")
    pn = sum(r["pruned"] == "1" for r in rob)
    res["H3"] = {"n": n, "robust": k, "rate": k / n, "wilson95": wilson(k, n),
                 "p_value": float(stats.binomtest(k, n, 0.95, alternative="greater").pvalue),
                 "pruned_pairs": {"n": pn, "robust": pk, "rate": pk / pn, "wilson95": wilson(pk, pn)}}

    # H4, H5
    rec = defaultdict(dict)
    for r in csv.DictReader(open(RES / "rq3" / "records.csv")):
        if r["analysis"] == "primary":
            rec[(r["path"], r["mutant"], r["target"])][r["slicer"]] = r
    units = [v for v in rec.values() if {"q", "lc"} <= v.keys()]
    cq = np.array([float(v["q"]["contained"]) for v in units])
    cl = np.array([float(v["lc"]["contained"]) for v in units])
    d = cq - cl
    rng = np.random.default_rng(SEED)
    boots = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(BOOT_RESAMPLES)])
    ci = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
    h4 = mcnemar_exact(list(cq == 1), list(cl == 1))
    h4 |= {"n_units": len(units), "containment_q": float(cq.mean()), "containment_lc": float(cl.mean()),
           "difference": float(d.mean()), "ci95_difference": ci, "holds": ci[0] > -0.05}
    res["H4"] = h4
    cb = [v for v in units if v["q"]["contained"] == "1" and v["lc"]["contained"] == "1"]
    h5 = wilcoxon_paired([int(v["lc"]["size"]) for v in cb], [int(v["q"]["size"]) for v in cb])
    ex = [(float(v["lc"]["exam_slice"]), float(v["q"]["exam_slice"])) for v in cb if v["lc"]["exam_slice"] and v["q"]["exam_slice"]]
    h5 |= {"measure": "slice size in instructions (lc - q)",
           "exam_slice_alongside": wilcoxon_paired([a for a, _ in ex], [b for _, b in ex])}
    res["H5"] = h5

    res["holm"] = holm({h: res[h]["p_value"] for h in ("H1", "H2", "H3", "H4", "H5")})
    (OUT / "summary.json").write_text(json.dumps(res, indent=2))
    for h in ("H1", "H2", "H3", "H4", "H5"):
        print(h, {k: res[h][k] for k in res[h] if k not in ("exam_slice_alongside", "pruned_pairs")}, res["holm"][h])
    return 0


if __name__ == "__main__":
    sys.exit(main())
