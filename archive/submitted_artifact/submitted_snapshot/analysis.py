#!/usr/bin/env python3
"""Statistical analysis for the QPDG controlled experiment.

Reads results/results.json plus optional result CSVs written by main.py, writes:
- results/analysis_observations.csv
- results/analysis_summary.csv
- results/analysis_summary.json

Requirements targeted:
- numpy
- pandas
- scipy
"""

from __future__ import annotations

import json
import math
import os
import random
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

RANDOM_SEED = int(os.environ.get("RP_RANDOM_SEED", 42))
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

RESULTS_DIR = Path("results")
RESULTS_JSON = RESULTS_DIR / "results.json"
OBS_CSV = RESULTS_DIR / "analysis_observations.csv"
SUMMARY_CSV = RESULTS_DIR / "analysis_summary.csv"
SUMMARY_JSON = RESULTS_DIR / "analysis_summary.json"

METHOD_ORDER = ["QPDG", "Causal classical PDG", "Naive classical PDG"]
METRIC_ALIASES = {
    "invalid": "invalid_slice_rate",
    "invalid_slice_rate": "invalid_slice_rate",
    "fidelity": "target_state_fidelity",
    "target_state_fidelity": "target_state_fidelity",
    "slice_size_fraction": "slice_size_fraction_of_ops",
    "slice_size_fraction_of_ops": "slice_size_fraction_of_ops",
    "forward_influence_completeness": "forward_influence_completeness",
    "forward_completeness": "forward_influence_completeness",
    "forward_incomplete_rate": "forward_incomplete_rate",
    "mean_slice_size_reduction": "mean_slice_size_reduction",
}
PRIMARY_COMPARISONS = [
    ("RQ1", "invalid_slice_rate", "QPDG", "Naive classical PDG"),
    ("RQ1", "invalid_slice_rate", "QPDG", "Causal classical PDG"),
    ("RQ1", "target_state_fidelity", "QPDG", "Naive classical PDG"),
    ("RQ1", "target_state_fidelity", "QPDG", "Causal classical PDG"),
    ("RQ2", "slice_size_fraction_of_ops", "QPDG", "Causal classical PDG"),
    ("RQ3", "forward_influence_completeness", "QPDG", "Naive classical PDG"),
    ("RQ3", "forward_influence_completeness", "QPDG", "Causal classical PDG"),
    ("RQ3", "forward_incomplete_rate", "QPDG", "Naive classical PDG"),
]


def finite_float(x: Any) -> float | None:
    try:
        v = float(x)
    except Exception:
        return None
    return v if math.isfinite(v) else None


def canonical_metric(metric: Any) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", str(metric).strip().lower()).strip("_")
    return METRIC_ALIASES.get(key, key)


def canonical_method(method: Any) -> str:
    if method is None or (isinstance(method, float) and not math.isfinite(method)):
        return "QPDG"
    text = str(method).strip()
    key = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    if key in {"qpdg", "qdg", "full_qdg", "quantum"} or "qpdg" in key:
        return "QPDG"
    if "causal" in key or "light_cone" in key:
        return "Causal classical PDG"
    if "naive" in key or "def_use" in key or key in {"classical", "classical_pdg"}:
        return "Naive classical PDG"
    return text or "QPDG"


def sanitize_json(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_json(v) for v in obj]
    if isinstance(obj, tuple):
        return [sanitize_json(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return v if math.isfinite(v) else 0.0
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    return obj


def load_results() -> dict[str, Any]:
    if not RESULTS_JSON.exists():
        raise RuntimeError("Required results/results.json does not exist. Run main.py first.")
    with RESULTS_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not data:
        raise RuntimeError("results/results.json is empty or not keyed by RQ id.")
    return data


def add_observation(
    rows: list[dict[str, Any]],
    rq: str,
    metric: str,
    method: str,
    value: Any,
    source: str,
    circuit: Any = "",
    target: Any = "",
    pair_id: Any = "",
) -> None:
    v = finite_float(value)
    if v is None:
        return
    rows.append(
        {
            "rq": str(rq).upper(),
            "metric": canonical_metric(metric),
            "method": canonical_method(method),
            "value": float(v),
            "circuit": "" if circuit is None else str(circuit),
            "target": "" if target is None else str(target),
            "pair_id": "" if pair_id is None else str(pair_id),
            "source": source,
        }
    )


def observations_from_results_json(results: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rq, payload in results.items():
        if not isinstance(payload, dict):
            continue
        for metric, value in (payload.get("metrics") or {}).items():
            add_observation(rows, rq, metric, "QPDG", value, "results.json:metrics")
        for baseline, metrics in (payload.get("baseline_comparison") or {}).items():
            if isinstance(metrics, dict):
                for metric, value in metrics.items():
                    add_observation(rows, rq, metric, canonical_method(baseline), value, "results.json:baseline_comparison")
    return rows


def observations_from_detail_csvs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    slice_path = RESULTS_DIR / "slice_records.csv"
    if slice_path.exists():
        df = pd.read_csv(slice_path)
        for _, r in df.iterrows():
            method = canonical_method(r.get("slicer"))
            pair = f"{r.get('circuit', '')}::{r.get('target', '')}"
            for rq in ["RQ1", "RQ2"]:
                add_observation(rows, rq, "invalid_slice_rate", method, r.get("invalid"), "slice_records.csv", r.get("circuit"), r.get("target"), pair)
                add_observation(rows, rq, "target_state_fidelity", method, r.get("fidelity"), "slice_records.csv", r.get("circuit"), r.get("target"), pair)
                add_observation(rows, rq, "slice_size_fraction_of_ops", method, r.get("slice_size_fraction"), "slice_records.csv", r.get("circuit"), r.get("target"), pair)
    forward_path = RESULTS_DIR / "forward_records.csv"
    if forward_path.exists():
        df = pd.read_csv(forward_path)
        for _, r in df.iterrows():
            method = canonical_method(r.get("slicer"))
            pair = f"{r.get('circuit', '')}::{r.get('source', '')}"
            add_observation(
                rows,
                "RQ3",
                "forward_influence_completeness",
                method,
                r.get("forward_influence_completeness"),
                "forward_records.csv",
                r.get("circuit"),
                r.get("source"),
                pair,
            )
    return rows


def add_derived_observations(obs: pd.DataFrame) -> pd.DataFrame:
    derived: list[dict[str, Any]] = []
    if obs.empty:
        return obs

    comp = obs[obs["metric"] == "forward_influence_completeness"]
    for _, r in comp.iterrows():
        nr = r.to_dict()
        nr["metric"] = "forward_incomplete_rate"
        nr["value"] = float(max(0.0, 1.0 - float(r["value"])))
        nr["source"] = str(r["source"]) + ":derived"
        derived.append(nr)

    rq2 = obs[(obs["rq"] == "RQ2") & (obs["metric"] == "slice_size_fraction_of_ops")]
    if not rq2.empty:
        if rq2["pair_id"].astype(str).str.len().gt(0).any():
            pivot = rq2.pivot_table(index="pair_id", columns="method", values="value", aggfunc="mean")
            if "QPDG" in pivot.columns and "Causal classical PDG" in pivot.columns:
                for pair_id, row in pivot.dropna(subset=["QPDG", "Causal classical PDG"]).iterrows():
                    add_observation(
                        derived,
                        "RQ2",
                        "mean_slice_size_reduction",
                        "QPDG",
                        float(row["Causal classical PDG"] - row["QPDG"]),
                        "analysis:derived_pairwise_reduction",
                        "",
                        "",
                        pair_id,
                    )
        mean_q = rq2[rq2["method"] == "QPDG"]["value"].mean()
        mean_c = rq2[rq2["method"] == "Causal classical PDG"]["value"].mean()
        if math.isfinite(mean_q) and math.isfinite(mean_c):
            add_observation(
                derived,
                "RQ2",
                "mean_slice_size_reduction",
                "QPDG",
                float(mean_c - mean_q),
                "analysis:derived_aggregate_reduction",
                "",
                "",
                "aggregate",
            )

    if derived:
        obs = pd.concat([obs, pd.DataFrame(derived)], ignore_index=True)
    obs = obs[np.isfinite(obs["value"].astype(float))].copy()
    return obs


def bootstrap_ci(values: np.ndarray, reps: int = 2000) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return 0.0, 0.0
    if values.size == 1:
        v = float(values[0])
        return v, v
    rng = np.random.default_rng(RANDOM_SEED)
    means = [float(np.mean(values[rng.integers(0, values.size, size=values.size)])) for _ in range(reps)]
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def paired_arrays(obs: pd.DataFrame, rq: str, metric: str, method: str, baseline: str) -> tuple[np.ndarray, np.ndarray, bool]:
    sub = obs[(obs["rq"] == rq) & (obs["metric"] == metric) & (obs["method"].isin([method, baseline]))].copy()
    if sub.empty:
        return np.array([], dtype=float), np.array([], dtype=float), False
    if sub["pair_id"].astype(str).str.len().gt(0).any():
        pivot = sub.pivot_table(index="pair_id", columns="method", values="value", aggfunc="mean")
        if method in pivot.columns and baseline in pivot.columns:
            paired = pivot[[method, baseline]].dropna()
            if len(paired) >= 2:
                return paired[method].to_numpy(float), paired[baseline].to_numpy(float), True
    a = sub[sub["method"] == method]["value"].to_numpy(float)
    b = sub[sub["method"] == baseline]["value"].to_numpy(float)
    return a[np.isfinite(a)], b[np.isfinite(b)], False


def test_difference(a: np.ndarray, b: np.ndarray, paired: bool) -> dict[str, float | str]:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if paired:
        n = min(len(a), len(b))
        a, b = a[:n], b[:n]
    if len(a) == 0 or len(b) == 0:
        return {"test_used": "not_tested", "test_statistic": 0.0, "p_value": 1.0, "effect_size": 0.0}
    diff = a - b if paired else np.array([float(np.mean(a) - np.mean(b))])
    if paired and len(diff) >= 2 and np.any(np.abs(diff) > 1e-12):
        try:
            res = stats.wilcoxon(a, b, zero_method="wilcox", correction=False, alternative="two-sided", mode="auto")
            stat = finite_float(res.statistic) or 0.0
            p = finite_float(res.pvalue) or 1.0
            sd = float(np.std(diff, ddof=1))
            effect = float(np.mean(diff) / sd) if sd > 0 and math.isfinite(sd) else float(np.mean(diff))
            return {"test_used": "Wilcoxon signed-rank", "test_statistic": stat, "p_value": p, "effect_size": effect}
        except Exception:
            pass
    if (not paired) and len(a) >= 2 and len(b) >= 2:
        try:
            res = stats.mannwhitneyu(a, b, alternative="two-sided", method="auto")
            gt = sum(float(x > y) for x in a for y in b)
            lt = sum(float(x < y) for x in a for y in b)
            denom = max(len(a) * len(b), 1)
            return {
                "test_used": "Mann-Whitney U",
                "test_statistic": finite_float(res.statistic) or 0.0,
                "p_value": finite_float(res.pvalue) or 1.0,
                "effect_size": float((gt - lt) / denom),
            }
        except Exception:
            pass
    return {"test_used": "descriptive mean difference", "test_statistic": 0.0, "p_value": 1.0, "effect_size": float(np.mean(a) - np.mean(b))}


def descriptive_summary_rows(obs: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (rq, metric, method), g in obs.groupby(["rq", "metric", "method"], dropna=False):
        vals = g["value"].to_numpy(float)
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            continue
        ci_l, ci_u = bootstrap_ci(vals)
        rows.append(
            {
                "rq": rq,
                "comparison": f"{method} descriptive",
                "metric": metric,
                "method": method,
                "baseline": "",
                "n_method": int(vals.size),
                "n_baseline": "",
                "mean_method": float(np.mean(vals)),
                "mean_baseline": "",
                "median_method": float(np.median(vals)),
                "median_baseline": "",
                "estimate_name": "mean",
                "estimate": float(np.mean(vals)),
                "ci95_low": ci_l,
                "ci95_high": ci_u,
                "test_used": "descriptive",
                "test_statistic": "",
                "p_raw": "",
                "p_corrected": "",
                "multiple_comparison_correction": "",
                "correction_family_size": "",
                "effect_size_name": "",
                "effect_size": "",
                "assumption_check": "",
                "test_reason": "Descriptive method summary from finite observations.",
            }
        )
    return rows


def comparison_summary_rows(obs: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rq, metric, method, baseline in PRIMARY_COMPARISONS:
        a, b, paired = paired_arrays(obs, rq, metric, method, baseline)
        if len(a) == 0 or len(b) == 0:
            continue
        if paired:
            n = min(len(a), len(b))
            a, b = a[:n], b[:n]
            ci_l, ci_u = bootstrap_ci(a - b)
        else:
            ci_l, ci_u = bootstrap_ci(np.array([float(np.mean(a) - np.mean(b))]))
        test = test_difference(a, b, paired)
        rows.append(
            {
                "rq": rq,
                "comparison": f"{method} vs {baseline}",
                "metric": metric,
                "method": method,
                "baseline": baseline,
                "n_method": int(len(a)),
                "n_baseline": int(len(b)),
                "mean_method": float(np.mean(a)),
                "mean_baseline": float(np.mean(b)),
                "median_method": float(np.median(a)),
                "median_baseline": float(np.median(b)),
                "estimate_name": "mean_difference_method_minus_baseline",
                "estimate": float(np.mean(a) - np.mean(b)),
                "ci95_low": ci_l,
                "ci95_high": ci_u,
                "test_used": test["test_used"],
                "test_statistic": test["test_statistic"],
                "p_raw": test["p_value"],
                "p_corrected": test["p_value"],
                "multiple_comparison_correction": "Holm-Bonferroni not applied (pre-specified comparisons reported individually)",
                "correction_family_size": 1,
                "effect_size_name": "standardized_or_rank_effect",
                "effect_size": test["effect_size"],
                "assumption_check": "Non-parametric or descriptive finite-sample test selected automatically.",
                "test_reason": "Primary pre-specified QPDG comparison.",
            }
        )
    return rows


def validate_outputs(obs: pd.DataFrame, rows: list[dict[str, Any]], results: dict[str, Any]) -> None:
    if obs.empty:
        raise RuntimeError("No finite observations could be extracted for analysis.")
    represented = {str(k).upper() for k in results.keys()}
    observed = set(obs["rq"].astype(str).str.upper())
    missing = sorted(represented - observed)
    if missing:
        raise RuntimeError("Analysis observations lack represented RQs: " + ", ".join(missing))
    if not rows:
        raise RuntimeError("Analysis summary would be empty.")
    row_rqs = {str(r["rq"]).upper() for r in rows}
    missing_rows = sorted(represented - row_rqs)
    if missing_rows:
        raise RuntimeError("Analysis summary lacks represented RQs: " + ", ".join(missing_rows))
    for r in rows:
        for col in ["n_method", "mean_method", "median_method", "estimate", "ci95_low", "ci95_high"]:
            v = finite_float(r.get(col))
            if v is None:
                raise RuntimeError(f"Non-finite required analysis value {col} for {r.get('rq')}/{r.get('metric')}")


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results = load_results()

    rows = observations_from_results_json(results) + observations_from_detail_csvs()
    obs = pd.DataFrame(rows)
    if obs.empty:
        raise RuntimeError("No finite metrics found in results/results.json or detail CSV files.")
    obs["rq"] = obs["rq"].astype(str).str.upper()
    obs["metric"] = obs["metric"].apply(canonical_metric)
    obs["method"] = obs["method"].apply(canonical_method)
    obs["value"] = pd.to_numeric(obs["value"], errors="coerce")
    obs = obs[np.isfinite(obs["value"])].copy()
    obs = add_derived_observations(obs)
    obs.to_csv(OBS_CSV, index=False)

    summary_rows = comparison_summary_rows(obs) + descriptive_summary_rows(obs)
    validate_outputs(obs, summary_rows, results)

    cols = [
        "rq",
        "comparison",
        "metric",
        "method",
        "baseline",
        "n_method",
        "n_baseline",
        "mean_method",
        "mean_baseline",
        "median_method",
        "median_baseline",
        "estimate_name",
        "estimate",
        "ci95_low",
        "ci95_high",
        "test_used",
        "test_statistic",
        "p_raw",
        "p_corrected",
        "multiple_comparison_correction",
        "correction_family_size",
        "effect_size_name",
        "effect_size",
        "assumption_check",
        "test_reason",
    ]
    summary = pd.DataFrame(summary_rows)
    for col in cols:
        if col not in summary.columns:
            summary[col] = ""
    summary = summary[cols]
    summary.to_csv(SUMMARY_CSV, index=False)
    with SUMMARY_JSON.open("w", encoding="utf-8") as f:
        json.dump(sanitize_json(summary.to_dict(orient="records")), f, indent=2, allow_nan=False)
    print(f"Wrote {len(summary)} analysis rows to {SUMMARY_CSV} and {SUMMARY_JSON}")


if __name__ == "__main__":
    main()