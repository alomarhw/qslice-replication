"""figures_qpdg.py — publication-quality figures for the QPDG slicing study.

Three kinds of figure:
  1. QPDG graphs  — NetworkX + Graphviz (dot layout, transitive-reduced for legibility) showing the
     three dependence edge types (data / control / ENTANGLEMENT) and, optionally, a highlighted slice.
  2. Quantum circuits — qiskit's matplotlib drawer, full circuit and the extracted slice side by side.
  3. Results charts — slice size, semantic validity, and fidelity per slicer (Okabe–Ito palette).

Graph rendering uses pydot -> Graphviz `dot`. Circuit/results use matplotlib via the project house
style (rp_style). Every figure is written as PNG (300 dpi) and PDF (vector) for the paper.
"""

from __future__ import annotations

import os
from typing import Dict, Iterable, List, Optional, Sequence

import networkx as nx

from qdg import EdgeType

# Okabe–Ito colorblind-safe edge styling, one per dependence type.
EDGE_STYLE = {
    "data":         {"color": "#555555", "style": "solid",  "penwidth": "1.3"},
    "control":      {"color": "#0072B2", "style": "dashed", "penwidth": "1.8"},
    "entanglement": {"color": "#D55E00", "style": "bold",    "penwidth": "2.4"},
}
_GATE_FILL = "#F4F6F8"
_SLICE_FILL = "#FFE3BF"
_SLICE_EDGE = "#D55E00"


_C_DATA = "#5A6066"
_C_CTRL = "#0072B2"
_C_ENT = "#D55E00"


def _edge_key(data) -> str:
    et = data.get("edge_type", EdgeType.DATA)
    return et.value if isinstance(et, EdgeType) else str(et)


def _asap_layers(qdg) -> Dict[int, int]:
    """ASAP scheduling layer (x-coordinate) for each gate over data+control edges, so independent
    gates share a column and the graph reads left-to-right like a scheduled circuit."""
    g = qdg.graph
    layer: Dict[int, int] = {}
    for pos in sorted(qdg.nodes):
        preds = [u for u in g.predecessors(pos)
                 if _edge_key(g.get_edge_data(u, pos) or {}) in ("data", "control")]
        layer[pos] = 1 + max((layer[u] for u in preds), default=-1)
    return layer


def _node_label(qdg, pos) -> str:
    node = qdg.nodes[pos]
    qs = ",".join(f"q{q}" for q in node.qubits)
    name = node.gate_name
    if name == "if_else":  # classically-conditioned op — show the inner gate it applies
        try:
            inner = qdg.qc.data[pos].operation.blocks[0].data[0].operation.name.upper()
            return f"{inner} (if)\n[{qs}]"
        except Exception:
            return f"IF\n[{qs}]"
    if name == "measure":
        return f"MEAS\n[{qs}]"
    return f"{name.upper()}\n[{qs}]"


def draw_qpdg_graph(qdg, out_path: str, *, slice_nodes: Optional[Iterable[int]] = None,
                    title: Optional[str] = None, max_nodes: int = 44) -> str:
    """Render the QPDG as a 2-D dependence graph: x = circuit time (ASAP layer), y = qubit lane.

    Data edges run along a wire, control edges are dashed, entanglement edges arc across qubit lanes
    (transitive-reduced so the figure shows the dependence structure, not the closure's hairball).
    ``slice_nodes`` are highlighted. This reads as a real graph, not a vertical list.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch
    from matplotlib.lines import Line2D

    slice_nodes = set(slice_nodes or [])
    positions = sorted(qdg.nodes)[:max_nodes]
    g = qdg.graph
    layer = _asap_layers(qdg)
    nq = qdg.qc.num_qubits

    xy: Dict[int, tuple] = {}
    for p in positions:
        node = qdg.nodes[p]
        y = nq - 1 - (sum(node.qubits) / len(node.qubits))  # q0 at the top
        xy[p] = (layer[p], y)
    nlayers = max((layer[p] for p in positions), default=0) + 1

    fig, ax = plt.subplots(figsize=(max(6.5, 1.45 * nlayers + 2.0), max(3.2, 1.15 * nq + 1.6)))

    # qubit lanes
    for q in range(nq):
        yy = nq - 1 - q
        ax.axhline(yy, color="#E3E7EB", lw=10, alpha=0.55, zorder=0)
        ax.text(-1.0, yy, f"q{q}", ha="right", va="center", fontsize=11, fontweight="bold", color="#444")
    # two-qubit gates: faint vertical span across the wires they couple
    for p in positions:
        node = qdg.nodes[p]
        if len(node.qubits) >= 2:
            ys = [nq - 1 - q for q in node.qubits]
            ax.plot([layer[p], layer[p]], [min(ys), max(ys)], color="#C7CDD3", lw=1.0, ls=":", zorder=1)

    # edges (entanglement transitive-reduced; data/control kept)
    ent = nx.DiGraph(); ent.add_nodes_from(positions)
    other = []
    for u, v, d in g.edges(data=True):
        if u not in xy or v not in xy:
            continue
        k = _edge_key(d)
        if k == "entanglement":
            ent.add_edge(u, v)
        else:
            other.append((u, v, k))
    try:
        ent_red = nx.transitive_reduction(ent)
    except Exception:
        ent_red = ent
    edges = other + [(u, v, "entanglement") for u, v in ent_red.edges() if u in xy and v in xy]
    style = {"data": (_C_DATA, "-", 0.0, 1.4, 0.9),
             "control": (_C_CTRL, (0, (4, 3)), 0.06, 1.7, 0.9),
             "entanglement": (_C_ENT, "-", 0.22, 2.2, 0.85)}
    for u, v, k in edges:
        c, ls, rad, lw, al = style[k]
        ax.add_patch(FancyArrowPatch(xy[u], xy[v], connectionstyle=f"arc3,rad={rad}",
                     arrowstyle="-|>", mutation_scale=11, color=c, lw=lw, linestyle=ls,
                     alpha=al, zorder=2, shrinkA=10, shrinkB=10))

    # nodes
    for p in positions:
        x, y = xy[p]
        in_slice = p in slice_nodes
        ax.text(x, y, _node_label(qdg, p), ha="center", va="center",
                fontsize=8.5, fontweight="bold", zorder=3,
                bbox=dict(boxstyle="round,pad=0.32",
                          fc=_SLICE_FILL if in_slice else _GATE_FILL,
                          ec=_SLICE_EDGE if in_slice else "#33373B",
                          lw=2.2 if in_slice else 1.1))

    handles = [Line2D([0], [0], color=_C_DATA, lw=2, label="data"),
               Line2D([0], [0], color=_C_CTRL, lw=2, ls="--", label="control"),
               Line2D([0], [0], color=_C_ENT, lw=2.6, label="entanglement")]
    if slice_nodes:
        handles.append(Line2D([0], [0], marker="s", linestyle="none", markerfacecolor=_SLICE_FILL,
                              markeredgecolor=_SLICE_EDGE, markersize=12, label="in slice"))
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.0),
              ncol=len(handles), frameon=False, fontsize=10)

    ax.set_xlim(-1.6, nlayers - 0.4)
    ax.set_ylim(-0.7, nq - 0.3)
    ax.set_xlabel("circuit time  (ASAP layer)", fontsize=10)
    ax.set_yticks([])
    ax.set_xticks(range(nlayers))
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    if title:
        ax.set_title(title, fontsize=12, fontweight="bold", pad=26)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    try:
        fig.savefig(out_path.rsplit(".", 1)[0] + ".pdf", bbox_inches="tight")
    except Exception:
        pass
    plt.close(fig)
    return out_path


def draw_circuit(qc, out_path: str, *, title: Optional[str] = None,
                 highlight=None, fold: int = 26) -> str:
    """Draw a quantum circuit with qiskit's matplotlib drawer (house-styled, 300 dpi PNG + PDF)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = qc.draw(output="mpl", fold=fold, style={"name": "clifford"})
    if title:
        fig.suptitle(title, fontsize=13, fontweight="bold")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    try:
        fig.savefig(out_path.rsplit(".", 1)[0] + ".pdf", bbox_inches="tight")
    except Exception:
        pass
    plt.close(fig)
    return out_path


def draw_slice_panels(qc, qdg, slice_nodes, out_path: str, *, target: int,
                      method: str = "QPDG") -> str:
    """Two-panel figure: the full circuit (top) and the extracted slice sub-circuit (bottom)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sliced = qdg.extract_slice_circuit(set(slice_nodes))
    full_fig = qc.draw(output="mpl", fold=24, style={"name": "clifford"})
    slice_fig = sliced.draw(output="mpl", fold=24, style={"name": "clifford"})

    full_fig.suptitle(f"Full circuit  (n={qc.num_qubits}, {len(qc.data)} ops)",
                      fontsize=12, fontweight="bold")
    slice_fig.suptitle(f"{method} backward slice on q{target}  "
                       f"({len(slice_nodes)}/{len(qc.data)} ops)",
                       fontsize=12, fontweight="bold")
    base = out_path.rsplit(".", 1)[0]
    full_fig.savefig(base + "_full.png", dpi=300, bbox_inches="tight")
    slice_fig.savefig(base + "_slice.png", dpi=300, bbox_inches="tight")
    plt.close(full_fig)
    plt.close(slice_fig)
    return base + "_slice.png"


def draw_scale_figure(rows, out_path: str, *, title: Optional[str] = None) -> str:
    """Structural scalability: entanglement dependencies the naive slicer drops, and analysis runtime,
    vs circuit size (qubits). ``rows`` is the list from main.run_structural_scale."""
    import rp_style  # noqa: F401
    import matplotlib.pyplot as plt
    import numpy as np

    from matplotlib.lines import Line2D
    cat_color = {"small": "#0072B2", "medium": "#E69F00", "large": "#D55E00"}
    src_marker = {"QASMBench": "o", "MQT": "^"}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4))

    for ax, ykey, ylab, ttl, ylog in [
        (ax1, "mean_dropped_2q", "Entangling deps dropped by\nnaive classical slicer (per slice)",
         "Naive-classical unsoundness vs scale", True),
        (ax2, "build_s", "QPDG build + slice time (s)", "Analysis runtime vs scale", False)]:
        for cat in ("small", "medium", "large"):
            for src, mk in src_marker.items():
                rs = [r for r in rows if r["category"] == cat and r.get("source", "QASMBench") == src]
                if not rs:
                    continue
                ax.scatter([r["n_qubits"] for r in rs], [r[ykey] for r in rs], s=44, marker=mk,
                           color=cat_color[cat], edgecolor="#222", linewidth=0.6, alpha=0.85, zorder=3)
        ax.set_xscale("log"); ax.set_xlabel("circuit size (qubits, log scale)")
        if ylog:  # deps span 0 to ~24k -> symlog keeps small + huge legible
            ax.set_yscale("symlog", linthresh=1)
        else:     # runtime is all sub-second -> linear from 0
            ax.set_ylim(bottom=0)
        ax.set_ylabel(ylab); ax.set_title(ttl, fontsize=11)
        ax.grid(True, which="both", alpha=0.25)

    # legends: color = size category, marker = benchmark suite
    cat_handles = [Line2D([0], [0], marker="s", linestyle="none", markerfacecolor=c,
                          markeredgecolor="#222", markersize=10, label=k) for k, c in cat_color.items()]
    src_handles = [Line2D([0], [0], marker=m, linestyle="none", markerfacecolor="#999",
                          markeredgecolor="#222", markersize=10, label=k) for k, m in src_marker.items()]
    leg1 = ax1.legend(handles=cat_handles, frameon=False, fontsize=9, title="size", loc="upper left")
    ax1.add_artist(leg1)
    ax1.legend(handles=src_handles, frameon=False, fontsize=9, title="benchmark", loc="lower right")
    if title:
        fig.suptitle(title, fontsize=13, fontweight="bold")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    try:
        fig.savefig(out_path.rsplit(".", 1)[0] + ".pdf", bbox_inches="tight")
    except Exception:
        pass
    plt.close(fig)
    return out_path


def draw_results_bars(per_method: Dict[str, Dict[str, float]], out_path: str, *,
                      title: Optional[str] = None) -> str:
    """Grouped bars: mean slice size, invalid-slice %, and mean fidelity per slicer.

    ``per_method[name] = {"size": float(0..1), "invalid": float(0..1), "fidelity": float(0..1)}``.
    """
    import rp_style  # noqa: F401  (applies house style)
    import matplotlib.pyplot as plt
    import numpy as np

    methods = list(per_method)
    pal = ["#D55E00", "#56B4E9", "#009E73"]  # naive / causal / qpdg-ish
    metrics = [("size", "Mean slice size\n(fraction of ops)"),
               ("invalid", "Invalid slices\n(% semantically wrong)"),
               ("fidelity", "Mean fidelity\n(target reduced state)")]
    fig, axes = plt.subplots(1, 3, figsize=(11, 4))
    for ax, (key, lab) in zip(axes, metrics):
        vals = [per_method[m].get(key, 0.0) for m in methods]
        colors = [pal[i % len(pal)] for i in range(len(methods))]
        bars = ax.bar(methods, vals, color=colors, edgecolor="#222", linewidth=0.8)
        ax.set_title(lab, fontsize=11)
        ax.set_ylim(0, 1.05)
        ax.tick_params(axis="x", rotation=20)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.0%}" if key != "fidelity" else f"{v:.3f}",
                    ha="center", va="bottom", fontsize=10, fontweight="bold")
    if title:
        fig.suptitle(title, fontsize=13, fontweight="bold")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    try:
        fig.savefig(out_path.rsplit(".", 1)[0] + ".pdf", bbox_inches="tight")
    except Exception:
        pass
    plt.close(fig)
    return out_path
