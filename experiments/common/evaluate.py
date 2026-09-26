"""Shared slice materialisation, statistics and parallel driver helpers (fixed in PROTOCOL.md)."""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence

import numpy as np
from qiskit import QuantumCircuit
from scipy import stats

FIDELITY_EPS = 1e-6      # a slice is sound iff fidelity(criterion reduced state) >= 1 - FIDELITY_EPS
BOOT_RESAMPLES, SEED = 10_000, 42


def materialise(qc: QuantumCircuit, positions: Iterable[int]) -> QuantumCircuit:
    """The slice as a circuit: the original instructions at `positions`, in order, on the original
    registers. Every slicer's output is materialised the same way before the oracle judges it."""
    keep = set(positions)
    out = qc.copy_empty_like()
    for k, inst in enumerate(qc.data):
        if k in keep:
            out.append(inst)
    return out


def mcnemar_exact(a: Sequence[bool], b: Sequence[bool]) -> dict:
    """Exact two-sided McNemar test on paired binary outcomes (binomial on discordant pairs)."""
    n01 = sum(1 for x, y in zip(a, b) if not x and y)
    n10 = sum(1 for x, y in zip(a, b) if x and not y)
    n = n01 + n10
    p = 1.0 if n == 0 else float(stats.binomtest(min(n01, n10), n, 0.5).pvalue)
    return {"test": "exact McNemar", "a_only": n10, "b_only": n01, "p_value": p}


def wilcoxon_paired(x: Sequence[float], y: Sequence[float]) -> dict:
    """Two-sided Wilcoxon signed-rank on x - y, with mean difference and bootstrap 95% CI."""
    d = np.asarray(x, float) - np.asarray(y, float)
    if len(d) == 0:
        return {"test": "Wilcoxon signed-rank", "n": 0}
    if np.all(d == 0):
        p, stat = 1.0, 0.0
    else:
        r = stats.wilcoxon(x, y, zero_method="wilcox", alternative="two-sided")
        p, stat = float(r.pvalue), float(r.statistic)
    nz = d[d != 0]
    ranks = stats.rankdata(np.abs(nz))
    rbc = float((ranks[nz > 0].sum() - ranks[nz < 0].sum()) / ranks.sum()) if len(nz) else 0.0
    rng = np.random.default_rng(SEED)
    boots = rng.choice(d, size=(BOOT_RESAMPLES, len(d)), replace=True).mean(axis=1)
    return {"test": "Wilcoxon signed-rank", "n": int(len(d)), "statistic": stat, "p_value": p,
            "mean_difference": float(d.mean()),
            "ci95_mean_difference": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "rank_biserial": rbc}


def rate(flags: Sequence[bool]) -> float:
    return float(np.mean(flags)) if len(flags) else math.nan
