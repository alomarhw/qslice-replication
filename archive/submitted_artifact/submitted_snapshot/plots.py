#!/usr/bin/env python3
"""Publication-ready figures for the QPDG controlled experiment.

Reads results/results.json and analysis outputs written by analysis.py, then writes PNG files under
figures/.

Requirements targeted:
- numpy
- pandas
- matplotlib
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import rp_style

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RANDOM_SEED = int(os.environ.get("RP_RANDOM_SEED", 42))
np.random.seed(RANDOM_SEED)

RESULTS_DIR = Path("results")
FIGURES_DIR = Path("figures")
RESULTS_JSON = RESULTS_DIR / "results.json"
OBS_CSV = RESULTS_DIR / "analysis_observations.csv"
SUMMARY_CSV = RESULTS_DIR / "analysis_summary.csv"

METHOD_ORDER = ["QPDG", "Causal classical PDG", "Naive classical PDG"]
METHOD_SHORT = {
    "QPDG": "QPDG",
    "Causal classical PDG": "Causal\nclassical",
    "Naive classical PDG": "Naive\nclassical",
}
METRIC_LABELS = {
    "invalid_slice_rate": "Invalid backward slices (%)",
    "target_state_fidelity": "Target-state fidelity",
    "slice_size_fraction_of_ops": "Slice size (fraction of operations)",
    "mean_slice_size_reduction": "Mean slice-size reduction",
    "forward_influence_completeness": "Forward influence completeness (%)",
    "forward_incomplete_rate": "Incomplete forward slices (%)",
}
RATE_METRICS = {"invalid_slice_rate", "forward_influence_completeness", "forward_incomplete_rate"}


def finite_float(x: Any) -> float | None:
    try:
        v = float(x)
    except Exception:
        return None
    return v if math.isfinite(v) else None


def canonical_metric(metric: Any) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", str(metric).strip().lower()).strip("_")
    aliases = {
        "invalid": "invalid_slice_rate",
        "invalid_rate": "invalid_slice_rate",
        "fidelity": "target_state_fidelity",
        "state_fidelity": "target_state_fidelity",
        "slice_size_fraction": "slice_size_fraction_of_ops",
        "slice_fraction": "slice_size_fraction_of_ops",
        "forward_completeness": "forward_influence_completeness",
        "completeness": "forward_influence_completeness",
        "incomplete_rate": "forward_incomplete_rate",
    }
    return aliases.get(key, key)


def canonical_method(method: Any) -> str:
    if method is None or (isinstance(method, float) and not math.isfinite(method)):
        return "QPDG"
    text = str(method).strip()
    key = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    if "qpdg" in key or key in {"qdg", "full_qdg", "quantum"}:
        return "QPDG"
    if "causal" in key or "light_cone" in key:
        return "Causal classical PDG"
    if "naive" in key or "def_use" in key or key in {"classical", "classical_pdg"}:
        return "Naive classical PDG"
    return text or "QPDG"


def method_color(method: str) -> str:
    method = canonical_method(method)
    if method in METHOD_ORDER:
        return rp_style.PALETTE[METHOD_ORDER.index(method) % len(rp_style.PALETTE)]
    return rp_style.PALETTE[0]


def metric_label(metric: str) -> str:
    return METRIC_LABELS.get(metric, metric.replace("_", " ").capitalize())


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Required input {path} does not exist. Run main.py first.")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not data:
        raise RuntimeError(f"{path} is empty or malformed.")
    return data


def rows_from_results_json(results: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for rq, payload in results.items():
        if not isinstance(payload, dict):
            continue
        for metric, value in (payload.get("metrics") or {}).items():
            v = finite_float(value)
            if v is not None:
                rows.append({"rq": str(rq).upper(), "metric": canonical_metric(metric), "method": "QPDG", "value": v, "pair_id": ""})
        for baseline, metrics in (payload.get("baseline_comparison") or {}).items():
            if not isinstance(metrics, dict):
                continue
            for metric, value in metrics.items():
                v = finite_float(value)
                if v is not None:
                    rows.append(
                        {
                            "rq": str(rq).upper(),
                            "metric": canonical_metric(metric),
                            "method": canonical_method(baseline),
                            "value": v,
                            "pair_id": "",
                        }
                    )
    return pd.DataFrame(rows)


def prepare_inputs() -> tuple[list[str], pd.DataFrame, pd.DataFrame]:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    results = load_json(RESULTS_JSON)
    rqs = [str(k).upper() for k in results.keys()]

    if SUMMARY_CSV.exists():
        summary = pd.read_csv(SUMMARY_CSV)
    else:
        summary = pd.DataFrame(columns=["rq", "metric", "method", "baseline", "mean_method", "mean_baseline", "p_corrected", "estimate", "effect_size"])

    if OBS_CSV.exists():
        obs = pd.read_csv(OBS_CSV)
    else:
        obs = pd.DataFrame()

    fallback = rows_from_results_json(results)
    if obs.empty:
        obs = fallback
    else:
        for col in ["rq", "metric", "method", "value", "pair_id"]:
            if col not in obs.columns:
                obs[col] = ""
        obs = pd.concat([obs, fallback], ignore_index=True)

    if obs.empty:
        raise RuntimeError("No finite observations are available for plotting.")
    obs["rq"] = obs["rq"].astype(str).str.upper()
    obs["metric"] = obs["metric"].apply(canonical_metric)
    obs["method"] = obs["method"].apply(canonical_method)
    obs["value"] = pd.to_numeric(obs["value"], errors="coerce")
    obs = obs[np.isfinite(obs["value"])].copy()

    for col in ["rq", "metric", "method", "baseline"]:
        if col not in summary.columns:
            summary[col] = ""
    summary["rq"] = summary["rq"].astype(str).str.upper()
    summary["metric"] = summary["metric"].apply(canonical_metric)
    summary["method"] = summary["method"].apply(canonical_method)
    summary["baseline"] = summary["baseline"].apply(lambda x: "" if pd.isna(x) or str(x).strip() == "" else canonical_method(x))
    for col in ["mean_method", "mean_baseline", "p_corrected", "estimate", "effect_size", "ci95_low", "ci95_high"]:
        if col in summary.columns:
            summary[col] = pd.to_numeric(summary[col], errors="coerce")

    # Defensive derived rows in case an older analysis.py output lacked them.
    derived: list[dict[str, Any]] = []
    comp = obs[obs["metric"] == "forward_influence_completeness"]
    for _, r in comp.iterrows():
        derived.append({**r.to_dict(), "metric": "forward_incomplete_rate", "value": max(0.0, 1.0 - float(r["value"]))})
    rq2 = obs[(obs["rq"] == "RQ2") & (obs["metric"] == "slice_size_fraction_of_ops")]
    q = rq2[rq2["method"] == "QPDG"]["value"].mean()
    c = rq2[rq2["method"] == "Causal classical PDG"]["value"].mean()
    if math.isfinite(q) and math.isfinite(c):
        derived.append({"rq": "RQ2", "metric": "mean_slice_size_reduction", "method": "QPDG", "value": float(c - q), "pair_id": "aggregate"})
    if derived:
        obs = pd.concat([obs, pd.DataFrame(derived)], ignore_index=True)
        obs["value"] = pd.to_numeric(obs["value"], errors="coerce")
        obs = obs[np.isfinite(obs["value"])].copy()

    missing = [rq for rq in rqs if rq not in set(obs["rq"])]
    if missing:
        raise RuntimeError("Plot observations lack represented RQs: " + ", ".join(missing))
    return rqs, summary, obs


def metric_scale(metric: str, values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if metric in RATE_METRICS and arr.size and float(np.nanmax(np.abs(arr))) <= 1.0:
        return 100.0
    return 1.0


def bootstrap_ci(values: np.ndarray, reps: int = 1000) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return 0.0, 0.0
    if arr.size == 1:
        return float(arr[0]), float(arr[0])
    rng = np.random.default_rng(RANDOM_SEED)
    means = [float(np.mean(arr[rng.integers(0, arr.size, size=arr.size)])) for _ in range(reps)]
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def observations_for(obs: pd.DataFrame, rq: str, metric: str) -> pd.DataFrame:
    sub = obs[(obs["rq"] == rq) & (obs["metric"] == metric)].copy()
    sub = sub[np.isfinite(sub["value"])]
    return sub


def aggregate_stats(df: pd.DataFrame, metric: str) -> tuple[pd.DataFrame, float]:
    if df.empty:
        raise RuntimeError(f"No finite values available for {metric}.")
    scale = metric_scale(metric, df["value"].to_numpy(float))
    rows: list[dict[str, Any]] = []
    for method, g in df.groupby("method", dropna=False):
        vals = g["value"].to_numpy(float) * scale
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            continue
        ci_l, ci_u = bootstrap_ci(vals)
        mean = float(np.mean(vals))
        rows.append(
            {
                "method": canonical_method(method),
                "mean": mean,
                "median": float(np.median(vals)),
                "n": int(vals.size),
                "yerr_low": max(0.0, mean - ci_l),
                "yerr_high": max(0.0, ci_u - mean),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError(f"No finite method statistics available for {metric}.")
    order = [m for m in METHOD_ORDER if m in set(out["method"])] + [m for m in sorted(set(out["method"])) if m not in METHOD_ORDER]
    out["method"] = pd.Categorical(out["method"], categories=order, ordered=True)
    return out.sort_values("method").reset_index(drop=True), scale


def p_marker(p: Any) -> str:
    v = finite_float(p)
    if v is None:
        return ""
    if v < 0.001:
        return "***"
    if v < 0.01:
        return "**"
    if v < 0.05:
        return "*"
    return "n.s."


def add_reference(ax: plt.Axes, metric: str, scale: float) -> None:
    if metric in {"invalid_slice_rate", "forward_incomplete_rate"}:
        ax.axhline(0.0, color="0.35", linestyle="--", linewidth=1.0, zorder=0)
    elif metric == "target_state_fidelity":
        ax.axhline(1.0, color="0.35", linestyle="--", linewidth=1.0, zorder=0)
    elif metric == "forward_influence_completeness" and scale == 100.0:
        ax.axhline(100.0, color="0.35", linestyle="--", linewidth=1.0, zorder=0)


def bar_figure(obs: pd.DataFrame, summary: pd.DataFrame, rq: str, metric: str, filename: str) -> None:
    raw = observations_for(obs, rq, metric)
    if raw.empty:
        raise RuntimeError(f"No finite values available for {rq}/{metric}.")
    stats_df, scale = aggregate_stats(raw, metric)
    x = np.arange(len(stats_df))
    colors = [method_color(str(m)) for m in stats_df["method"]]
    yerr = np.vstack([np.maximum(0.0, stats_df["yerr_low"].to_numpy(float)), np.maximum(0.0, stats_df["yerr_high"].to_numpy(float))])

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    bars = ax.bar(x, stats_df["mean"].to_numpy(float), yerr=yerr, capsize=3, color=colors, edgecolor="white", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([METHOD_SHORT.get(str(m), str(m)) for m in stats_df["method"]])
    ax.set_ylabel(metric_label(metric))
    add_reference(ax, metric, scale)

    ymax = max(float(np.nanmax(stats_df["mean"].to_numpy(float) + stats_df["yerr_high"].to_numpy(float))), 1e-9)
    if metric == "target_state_fidelity":
        ax.set_ylim(max(0.0, min(0.95, float(np.nanmin(stats_df["mean"])) - 0.02)), 1.02)
    else:
        ax.set_ylim(0.0, ymax * 1.25 if ymax > 0 else 1.0)

    for bar in bars:
        h = float(bar.get_height())
        label = f"{h:.1f}" if metric in RATE_METRICS and scale == 100.0 else f"{h:.3g}"
        ax.annotate(label, (bar.get_x() + bar.get_width() / 2.0, h), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8)

    sig = summary[(summary["rq"] == rq) & (summary["metric"] == metric) & (summary["comparison"].astype(str).str.contains("vs", na=False))]
    notes = []
    for _, r in sig.iterrows():
        mark = p_marker(r.get("p_corrected"))
        if mark:
            base = str(r.get("baseline", "")).replace(" classical PDG", "")
            notes.append(f"QPDG vs {base}: {mark}")
    if notes:
        ax.annotate("; ".join(notes[:2]), xy=(0.02, 0.98), xycoords="axes fraction", ha="left", va="top", fontsize=8)

    rp_style.save(FIGURES_DIR / filename)
    plt.close(fig)


def rq2_slice_figure(obs: pd.DataFrame, summary: pd.DataFrame) -> None:
    raw = observations_for(obs, "RQ2", "slice_size_fraction_of_ops")
    if raw.empty:
        red = observations_for(obs, "RQ2", "mean_slice_size_reduction")
        if red.empty:
            raise RuntimeError("No finite RQ2 slice-size or reduction values available for plotting.")
        bar_figure(obs, summary, "RQ2", "mean_slice_size_reduction", "RQ2_slice_size_reduction.png")
        return

    methods = [m for m in ["QPDG", "Causal classical PDG", "Naive classical PDG"] if m in set(raw["method"])]
    raw = raw[raw["method"].isin(methods)].copy()
    if raw.empty:
        raise RuntimeError("No finite RQ2 slice-size values remain after method filtering.")
    stats_df, _scale = aggregate_stats(raw, "slice_size_fraction_of_ops")
    x = np.arange(len(stats_df))
    colors = [method_color(str(m)) for m in stats_df["method"]]
    yerr = np.vstack([np.maximum(0.0, stats_df["yerr_low"].to_numpy(float)), np.maximum(0.0, stats_df["yerr_high"].to_numpy(float))])

    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    bars = ax.bar(x, stats_df["mean"].to_numpy(float), yerr=yerr, capsize=3, color=colors, edgecolor="white", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([METHOD_SHORT.get(str(m), str(m)) for m in stats_df["method"]])
    ax.set_ylabel(metric_label("slice_size_fraction_of_ops"))
    ax.set_ylim(0.0, max(1.0, float(np.nanmax(stats_df["mean"] + stats_df["yerr_high"])) * 1.2))

    for bar in bars:
        h = float(bar.get_height())
        ax.annotate(f"{h:.3g}", (bar.get_x() + bar.get_width() / 2.0, h), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8)

    sr = summary[(summary["rq"] == "RQ2") & (summary["metric"] == "slice_size_fraction_of_ops") & (summary["baseline"] == "Causal classical PDG")]
    if not sr.empty:
        r = sr.iloc[0]
        parts = []
        est = finite_float(r.get("estimate"))
        p = finite_float(r.get("p_corrected"))
        eff = finite_float(r.get("effect_size"))
        if est is not None:
            parts.append(f"Δ={est:.3g}")
        if p is not None:
            parts.append(f"p={p:.3g} {p_marker(p)}")
        if eff is not None:
            parts.append(f"effect={eff:.2g}")
        if parts:
            ax.annotate(", ".join(parts), xy=(0.02, 0.98), xycoords="axes fraction", ha="left", va="top", fontsize=8)

    rp_style.save(FIGURES_DIR / "RQ2_slice_size_distribution.png")
    plt.close(fig)


def effect_heatmap(summary: pd.DataFrame) -> None:
    if summary.empty or "effect_size" not in summary.columns:
        return
    rows = summary[summary["comparison"].astype(str).str.contains("vs", na=False)].copy()
    rows = rows[np.isfinite(pd.to_numeric(rows["effect_size"], errors="coerce"))]
    if rows.empty:
        return
    labels = [f"{r['rq']}\n{str(r['metric']).replace('_', ' ')}\nvs {str(r['baseline']).replace(' classical PDG', '')}" for _, r in rows.iterrows()]
    vals = rows["effect_size"].astype(float).to_numpy()
    vmax = max(0.1, float(np.nanmax(np.abs(vals))))
    fig, ax = plt.subplots(figsize=(max(7.2, 1.15 * len(vals)), 3.2))
    data = vals.reshape(1, -1)
    im = ax.imshow(data, aspect="auto", cmap=rp_style.CMAP, vmin=-vmax, vmax=vmax)
    ax.set_yticks([0])
    ax.set_yticklabels(["Effect"])
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels)
    ax.tick_params(axis="x", rotation=30)
    for label in ax.get_xticklabels():
        label.set_ha("right")
    for j, val in enumerate(vals):
        ax.text(j, 0, f"{val:.2g}", ha="center", va="center", fontsize=8, color="white" if abs(val) > 0.45 * vmax else "black")
    cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.03)
    cbar.set_label("Effect size")
    rp_style.save(FIGURES_DIR / "summary_effect_sizes_heatmap.png")
    plt.close(fig)


def main() -> None:
    rqs, summary, obs = prepare_inputs()
    made: set[str] = set()

    if "RQ1" in rqs:
        bar_figure(obs, summary, "RQ1", "invalid_slice_rate", "RQ1_invalid_slice_rate_by_method.png")
        if not observations_for(obs, "RQ1", "target_state_fidelity").empty:
            bar_figure(obs, summary, "RQ1", "target_state_fidelity", "RQ1_target_state_fidelity_by_method.png")
        made.add("RQ1")

    if "RQ2" in rqs:
        rq2_slice_figure(obs, summary)
        made.add("RQ2")

    if "RQ3" in rqs:
        if not observations_for(obs, "RQ3", "forward_incomplete_rate").empty:
            bar_figure(obs, summary, "RQ3", "forward_incomplete_rate", "RQ3_forward_incomplete_rate_by_method.png")
        elif not observations_for(obs, "RQ3", "forward_influence_completeness").empty:
            bar_figure(obs, summary, "RQ3", "forward_influence_completeness", "RQ3_forward_completeness_by_method.png")
        else:
            raise RuntimeError("No finite RQ3 forward completeness metrics available for plotting.")
        made.add("RQ3")

    for rq in rqs:
        if rq in made:
            continue
        rq_obs = obs[obs["rq"] == rq]
        if rq_obs.empty:
            raise RuntimeError(f"No finite values available to plot {rq}.")
        metric = str(rq_obs["metric"].iloc[0])
        bar_figure(obs, summary, rq, metric, f"{rq}_{metric}_by_method.png")
        made.add(rq)

    effect_heatmap(summary)

    pngs = [p for p in FIGURES_DIR.glob("*.png")]
    rq_with_fig = {p.name.split("_")[0].upper() for p in pngs if p.name.upper().startswith("RQ")}
    missing = [rq for rq in rqs if rq not in rq_with_fig]
    if missing:
        raise RuntimeError("No figure was generated for represented RQs: " + ", ".join(missing))
    if not pngs:
        raise RuntimeError("No figures were generated.")
    print(f"Generated {len(pngs)} publication-ready figure(s) in {FIGURES_DIR}/")


if __name__ == "__main__":
    main()