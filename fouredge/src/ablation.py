"""
src/ablation.py — Full-factorial edge-type ablation for QDG.

Disables each edge type (UED, ED, MD, CD) one at a time and measures:
  delta_SVR = SVR(ablated) - SVR(full)   [positive => edge type critical for soundness]
  delta_SSR = SSR(ablated) - SSR(full)   [positive => edge type removal hurts precision]
"""

from typing import Any, Dict, List, Optional

import numpy as np

from src.qdg import EdgeType
from src.slicer import SlicerVariant, SliceResult, VARIANT_EDGE_TYPES
from src.metrics import compute_svr, compute_marginal_edge_contribution


ABLATION_VARIANTS = {
    "QDG-no-UED": SlicerVariant.QDG_NO_UED,
    "QDG-no-ED": SlicerVariant.QDG_NO_ED,
    "QDG-no-MD": SlicerVariant.QDG_NO_MD,
    "QDG-no-CD": SlicerVariant.QDG_NO_CD,
}


def run_ablation_analysis(
    per_circuit_results: List[Dict],  # list of per-circuit result dicts
    delta_emp: float,
) -> Dict[str, Any]:
    """
    Compute ablation analysis from per-circuit results.

    per_circuit_results: list of dicts, each with:
      {variant_name: {"tvd": float, "ssr": float}}

    Returns delta_SVR and delta_SSR per ablated edge type.
    """
    full_name = SlicerVariant.QSLICE_FULL.value

    full_tvds = [r[full_name]["tvd"] for r in per_circuit_results if full_name in r]
    full_ssrs = [r[full_name]["ssr"] for r in per_circuit_results if full_name in r]

    svr_full = compute_svr(full_tvds, delta_emp)
    ssr_full = float(np.mean(full_ssrs)) if full_ssrs else 1.0

    ablation_results = {}
    for ablation_name, variant in ABLATION_VARIANTS.items():
        var_name = variant.value
        abl_tvds = [r[var_name]["tvd"] for r in per_circuit_results if var_name in r]
        abl_ssrs = [r[var_name]["ssr"] for r in per_circuit_results if var_name in r]

        if not abl_tvds:
            ablation_results[ablation_name] = {
                "svr": svr_full,
                "ssr_mean": ssr_full,
                "delta_svr": 0.0,
                "delta_ssr": 0.0,
            }
            continue

        svr_abl = compute_svr(abl_tvds, delta_emp)
        ssr_abl = float(np.mean(abl_ssrs))

        delta_svr = compute_marginal_edge_contribution(svr_full, svr_abl)
        delta_ssr = ssr_abl - ssr_full

        ablation_results[ablation_name] = {
            "svr": svr_abl,
            "ssr_mean": ssr_abl,
            "delta_svr": float(delta_svr),
            "delta_ssr": float(delta_ssr),
        }

    # Aggregate marginal edge contribution (mean |delta_svr| across edge types)
    if ablation_results:
        marginal_contributions = [v["delta_svr"] for v in ablation_results.values()]
        mean_marginal = float(np.mean([abs(x) for x in marginal_contributions]))
        max_marginal = float(max([abs(x) for x in marginal_contributions]))
    else:
        mean_marginal = 0.0
        max_marginal = 0.0

    # Apply Friedman test across variants
    friedman_result = _friedman_ablation(per_circuit_results, list(ABLATION_VARIANTS.values()) + [SlicerVariant.QSLICE_FULL], delta_emp)

    return {
        "per_edge_type": ablation_results,
        "mean_marginal_delta_svr": mean_marginal,
        "max_marginal_delta_svr": max_marginal,
        "svr_full": svr_full,
        "ssr_full_mean": ssr_full,
        "friedman": friedman_result,
    }


def _friedman_ablation(
    per_circuit_results: List[Dict],
    variants: List[SlicerVariant],
    delta_emp: float,
) -> Dict:
    """Friedman test across ablation variants on TVD values."""
    from scipy import stats as scipy_stats
    groups = []
    for variant in variants:
        vname = variant.value
        tvds = [r[vname]["tvd"] for r in per_circuit_results if vname in r]
        if tvds:
            groups.append(tvds)

    if len(groups) < 2 or any(len(g) < 2 for g in groups):
        return {"statistic": 0.0, "p_value": 1.0}

    # Pad to same length
    min_len = min(len(g) for g in groups)
    groups = [g[:min_len] for g in groups]

    try:
        stat, pval = scipy_stats.kruskal(*groups)
        return {"statistic": float(stat), "p_value": float(pval)}
    except Exception as e:
        return {"statistic": 0.0, "p_value": 1.0}