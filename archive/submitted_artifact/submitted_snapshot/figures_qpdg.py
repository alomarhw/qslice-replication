"""Figure generation for QPDG slicing experiments.

Requirements targeted:
- matplotlib==3.10.9
- numpy==1.26.4
- pandas==3.0.3
"""

from __future__ import annotations

import json
import math
import os
import random
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from qdg import backward_slice, build_qdg, make_worked_example

RANDOM_SEED = int(os.environ.get("RP_RANDOM_SEED", 42))
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

PALETTE = {"qpdg": "#1b9e77", "naive": "#d95f02", "causal": "#7570b3"}


def _ensure_dirs() -> None:
    Path("figures").mkdir(parents=True, exist_ok=True)


def _load_results(path: Path = Path("results/results.json")) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def plot_results_summary() -> None:
    _ensure_dirs()
    results = _load_results()
    metrics = ["invalid_slice_rate", "target_state_fidelity", "slice_size_fraction_of_ops", "forward_influence_completeness"]
    methods = ["QPDG", "Naive classical PDG (def-use port)", "Causal classical PDG (data+control light cone)"]
    method_keys = ["qpdg", "naive", "causal"]

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2), constrained_layout=True)
    for ax, rq in zip(axes, ["RQ1", "RQ2", "RQ3"]):
        vals = []
        for method in methods:
            if method == "QPDG":
                vals.append([float(results[rq]["metrics"][m]) for m in metrics])
            else:
                vals.append([float(results[rq]["baseline_comparison"][method][m]) for m in metrics])
        x = np.arange(len(metrics))
        width = 0.25
        for i, (mk, row) in enumerate(zip(method_keys, vals)):
            ax.bar(x + (i - 1) * width, row, width, label=mk.upper(), color=PALETTE[mk])
        ax.set_xticks(x)
        ax.set_xticklabels(["invalid\nrate", "fidelity", "size\nfraction", "forward\ncomplete"], fontsize=8)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("Metric value")
        ax.set_title(rq)
        ax.grid(axis="y", alpha=0.25)
    axes[0].legend(loc="upper center", ncol=3, bbox_to_anchor=(1.7, 1.18), frameon=False)
    fig.savefig("figures/fig_results_summary.png", dpi=220)
    for rq in ["rq1_e1_results", "rq2_e1_results", "rq3_e1_results"]:
        fig.savefig(f"figures/{rq}.png", dpi=220)
    plt.close(fig)


def plot_debug_from_records() -> None:
    _ensure_dirs()
    records_path = Path("results/slice_records.csv")
    if not records_path.exists():
        return
    df = pd.read_csv(records_path)
    for slicer, fname, color in [
        ("naive", "fig_debug_naive.png", PALETTE["naive"]),
        ("qpdg", "fig_debug_qpdg.png", PALETTE["qpdg"]),
    ]:
        sub = df[df["slicer"] == slicer]
        fig, ax = plt.subplots(figsize=(6.4, 4.2), constrained_layout=True)
        ax.scatter(sub["slice_size_fraction"], sub["fidelity"], s=22, alpha=0.75, color=color, edgecolor="black", linewidth=0.25)
        ax.axhline(0.999999, color="black", linestyle="--", linewidth=1.0, label="validity threshold")
        ax.set_xlabel("Slice size / full operations")
        ax.set_ylabel("Target reduced-state fidelity")
        ax.set_ylim(-0.02, 1.02)
        ax.grid(alpha=0.25)
        ax.legend(frameon=False)
        fig.savefig(f"figures/{fname}", dpi=220)
        plt.close(fig)


def draw_worked_graph() -> None:
    _ensure_dirs()
    circuit = make_worked_example()
    qdg = build_qdg(circuit)
    target = 2
    qslice = backward_slice(circuit, target, "qpdg")
    naive = backward_slice(circuit, target, "naive")

    labels = [f"{op.index}: {op.name.upper()} q{','.join(map(str, op.qubits))}" for op in circuit.ops]
    xs = [op.index for op in circuit.ops]
    ys = [2.5 - (sum(op.qubits) / max(len(op.qubits), 1)) for op in circuit.ops]

    fig, ax = plt.subplots(figsize=(10.5, 4.8), constrained_layout=True)
    for op, x, y, label in zip(circuit.ops, xs, ys, labels):
        kept = op.index in qslice
        ax.scatter([x], [y], s=900, color="#a6dba0" if kept else "#e0e0e0", edgecolor="black", zorder=3)
        ax.text(x, y, label, ha="center", va="center", fontsize=8, zorder=4)
    edge_styles = {"state-carry": ("#377eb8", "-"), "entanglement": ("#e41a1c", "--")}
    for dst, preds in qdg.edges.items():
        for src, typ in preds:
            x0, y0 = xs[src], ys[src]
            x1, y1 = xs[dst], ys[dst]
            color, style = edge_styles.get(typ, ("#555555", ":"))
            ax.annotate(
                "",
                xy=(x1 - 0.18, y1),
                xytext=(x0 + 0.18, y0),
                arrowprops={"arrowstyle": "->", "color": color, "linestyle": style, "lw": 1.6, "alpha": 0.85},
            )
    ax.scatter([xs[5]], [ys[5]], s=1200, facecolors="none", edgecolors="#984ea3", linewidths=3, zorder=5)
    ax.text(xs[5], ys[5] - 0.42, "target criterion q2", ha="center", color="#984ea3", fontsize=9)
    handles = [
        plt.Line2D([0], [0], color="#377eb8", lw=2, label="state-carry edge"),
        plt.Line2D([0], [0], color="#e41a1c", lw=2, linestyle="--", label="entanglement edge"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#a6dba0", markeredgecolor="black", markersize=12, label="kept by QPDG slice"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#e0e0e0", markeredgecolor="black", markersize=12, label="removed"),
    ]
    ax.legend(handles=handles, loc="upper center", ncol=4, frameon=False)
    ax.set_yticks([0.5, 1.5, 2.5])
    ax.set_yticklabels(["q2 lane", "q1 lane", "q0 lane"])
    ax.set_xlabel("Program order")
    ax.set_xlim(-0.8, len(circuit.ops) - 0.2)
    ax.set_ylim(0.0, 3.25)
    ax.grid(axis="x", alpha=0.15)
    fig.savefig("figures/fig_qpdg_graph.png", dpi=220)
    fig.savefig("figures/graph_slice_worked_example.png", dpi=220)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.5, 3.2), constrained_layout=True)
    for lane in range(circuit.num_qubits):
        ax.hlines(lane, -0.5, len(circuit.ops) - 0.5, color="#bdbdbd", linewidth=1)
        ax.text(-0.8, lane, f"q{lane}", va="center", ha="right")
    for op in circuit.ops:
        color = "#1b9e77" if op.index in qslice else "#dddddd"
        for q in op.qubits:
            ax.scatter(op.index, q, s=520, color=color, edgecolor="black", zorder=3)
        if len(op.qubits) > 1:
            ax.vlines(op.index, min(op.qubits), max(op.qubits), color="black", linewidth=1.3, zorder=2)
        ax.text(op.index, max(op.qubits) + 0.18, op.name.upper(), ha="center", fontsize=8)
    ax.set_xlim(-1, len(circuit.ops))
    ax.set_ylim(-0.5, circuit.num_qubits - 0.35)
    ax.set_yticks([])
    ax.set_xlabel("Operation index")
    fig.savefig("figures/fig_qpdg_slice.png", dpi=220)
    fig.savefig("figures/fig_slice_circuit_slice.png", dpi=220)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 3.2), constrained_layout=True)
    methods = ["Naive", "QPDG"]
    vals = [len(naive) / len(circuit.ops), len(qslice) / len(circuit.ops)]
    ax.bar(methods, vals, color=[PALETTE["naive"], PALETTE["qpdg"]])
    ax.set_ylim(0, 1)
    ax.set_ylabel("Slice size fraction")
    ax.grid(axis="y", alpha=0.25)
    fig.savefig("figures/fig_qpdg_slice.png", dpi=220)
    plt.close(fig)


def main() -> None:
    draw_worked_graph()
    if Path("results/results.json").exists():
        plot_results_summary()
        plot_debug_from_records()
    print("Generated QPDG figures in figures/")


if __name__ == "__main__":
    main()