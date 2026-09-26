"""
stats_utils.py
Statistical analysis utilities for the QDG slicing study.

Provides:
  - wilcoxon_test: Wilcoxon signed-rank test with effect size and CI
  - mcnemar_test: McNemar's test for paired proportions
  - rank_biserial_correlation: effect size for Wilcoxon
  - bootstrap_ci: bootstrap confidence interval on a statistic
  - cohens_d: Cohen's d effect size
"""

# Requirements:
#   scipy>=1.11.0
#   numpy==1.26.4

import os
from typing import List, Optional, Tuple

import numpy as np
from scipy import stats
from scipy.stats import wilcoxon, mannwhitneyu

RANDOM_SEED = int(os.environ.get("RP_RANDOM_SEED", 42))


def rank_biserial_correlation(x: np.ndarray, y: Optional[np.ndarray] = None) -> float:
    """
    Compute rank-biserial correlation as effect size for Wilcoxon signed-rank test.
    For paired data (x vs y), computes on differences d = x - y.
    For single array (differences already computed), pass y=None.
    """
    if y is not None:
        d = np.array(x, dtype=float) - np.array(y, dtype=float)
    else:
        d = np.array(x, dtype=float)
    d = d[~np.isnan(d)]
    d = d[d != 0]  # Remove ties
    if len(d) == 0:
        return 0.0
    n = len(d)
    ranks = stats.rankdata(np.abs(d))
    W_plus = np.sum(ranks[d > 0])
    W_minus = np.sum(ranks[d < 0])
    rho = (W_plus - W_minus) / (n * (n + 1) / 2)
    return float(np.clip(rho, -1.0, 1.0))


def bootstrap_ci(data: np.ndarray, statistic=np.mean,
                  n_boot: int = 999, alpha: float = 0.05,
                  seed: int = RANDOM_SEED) -> Tuple[float, float]:
    """Bootstrap percentile confidence interval for a statistic."""
    rng = np.random.default_rng(seed)
    data = np.array(data, dtype=float)
    data = data[np.isfinite(data)]
    if len(data) == 0:
        return (0.0, 0.0)
    boot_stats = np.array([
        statistic(rng.choice(data, size=len(data), replace=True))
        for _ in range(n_boot)
    ])
    low = float(np.percentile(boot_stats, 100 * alpha / 2))
    high = float(np.percentile(boot_stats, 100 * (1 - alpha / 2)))
    return (low, high)


def wilcoxon_test(x: np.ndarray, y: np.ndarray,
                   alternative: str = "two-sided") -> dict:
    """
    Paired Wilcoxon signed-rank test.
    Returns dict with W, p_value, effect_size (rho), confidence_interval.
    """
    x = np.array(x, dtype=float)
    y = np.array(y, dtype=float)
    # Remove pairs with NaN
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    d = x - y

    if len(d) < 2:
        return {"test_used": "Wilcoxon signed-rank",
                "W": 0.0, "p_value": 1.0,
                "effect_size": 0.0,
                "confidence_interval": [0.0, 0.0]}

    # Handle case where all differences are zero
    if np.all(d == 0):
        return {"test_used": "Wilcoxon signed-rank (all ties)",
                "W": 0.0, "p_value": 1.0,
                "effect_size": 0.0,
                "confidence_interval": [0.0, 0.0]}

    try:
        result = wilcoxon(x, y, alternative=alternative, zero_method="wilcox")
        W = float(result.statistic)
        p_val = float(result.pvalue)
    except Exception:
        W, p_val = 0.0, 1.0

    rho = rank_biserial_correlation(x, y)
    ci = bootstrap_ci(d, statistic=rank_biserial_correlation,
                       n_boot=499)

    return {
        "test_used": "Wilcoxon signed-rank",
        "W": W,
        "p_value": float(np.clip(p_val, 1e-15, 1.0)),
        "effect_size": float(rho),
        "confidence_interval": [float(ci[0]), float(ci[1])]
    }


def mcnemar_test(table: np.ndarray) -> dict:
    """
    McNemar's test on 2x2 contingency table.
    table = [[n00, n01], [n10, n11]]
    where n01 = (A=no, B=yes), n10 = (A=yes, B=no)
    """
    table = np.array(table, dtype=float)
    n01 = table[0, 1]
    n10 = table[1, 0]
    n_discordant = n01 + n10

    if n_discordant == 0:
        return {"test_used": "McNemar",
                "chi2": 0.0,
                "p_value": 1.0,
                "effect_size": 0.0,
                "confidence_interval": [0.0, 0.0]}

    # McNemar test statistic (continuity correction for small samples)
    try:
        from scipy.stats import chi2
        chi2_stat = (abs(n01 - n10) - 1) ** 2 / (n01 + n10)
        chi2_stat = max(chi2_stat, 0.0)
        p_val = float(1.0 - chi2.cdf(chi2_stat, df=1))
    except Exception:
        chi2_stat, p_val = 0.0, 1.0

    # Odds ratio as effect size
    odds_ratio = (n01 / n10) if n10 > 0 else float(n01 + 1)
    # CI via log-normal approximation
    if n01 > 0 and n10 > 0:
        log_or = math.log(odds_ratio)
        se = math.sqrt(1 / n01 + 1 / n10)
        ci_low = math.exp(log_or - 1.96 * se)
        ci_high = math.exp(log_or + 1.96 * se)
    else:
        ci_low, ci_high = 0.0, float(odds_ratio * 2)

    return {
        "test_used": "McNemar",
        "chi2": float(chi2_stat),
        "p_value": float(np.clip(p_val, 1e-15, 1.0)),
        "effect_size": float(np.clip(odds_ratio, 0.0, 1e6)),
        "confidence_interval": [float(ci_low), float(ci_high)]
    }


def cohens_d(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Cohen's d between two arrays."""
    x = np.array(x, dtype=float)
    y = np.array(y, dtype=float)
    x = x[np.isfinite(x)]
    y = y[np.isfinite(y)]
    if len(x) < 2 or len(y) < 2:
        return 0.0
    pooled_std = math.sqrt((x.std(ddof=1) ** 2 + y.std(ddof=1) ** 2) / 2)
    if pooled_std < 1e-12:
        return 0.0
    return float((x.mean() - y.mean()) / pooled_std)


def bonferroni_threshold(alpha: float = 0.05, n_tests: int = 12) -> float:
    """Bonferroni-corrected significance threshold."""
    return alpha / n_tests


import math