"""Redraw Fig. 1 (typed QPDG of quantum teleportation) from the four-edge implementation.

The original drawing script was not saved. This script builds the teleportation circuit, runs the
unchanged four-edge implementation (reported_results/rq4_ablation/src/qdg.py, qdg_from_circuit) on it,
and draws every node and edge that code produces. It also checks the built edge set against the 17
edges read off the submitted Fig. 1 and prints the result.

Layout: x = ASAP layer over qubits (classical bits ignored), y = qubit lane (multi-qubit gates sit
between their lanes). Edge styles follow the submitted figure; CD edges are dashed.

Usage: python fig1_qpdg_teleportation.py [out_dir]     (default: ./out)
Needs qiskit>=2.3, networkx, matplotlib (the four-edge implementation's environment).
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from qiskit import QuantumCircuit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "reported_results" / "rq4_ablation"))
from src.qdg import qdg_from_circuit  # noqa: E402  (unchanged four-edge implementation)

# Edges (src gate id, dst gate id, type) as drawn in the submitted Fig. 1, gate ids in circuit order:
# 0 H[q1], 1 CX[q1,q2], 2 CX[q0,q1], 3 H[q0], 4 MEAS[q0], 5 MEAS[q1], 6 X(if)[q2], 7 Z(if)[q2].
SUBMITTED_FIG1_EDGES = {
    (2, 3, "UED"),
    (0, 1, "ED"), (0, 6, "ED"), (0, 7, "ED"), (1, 2, "ED"), (1, 7, "ED"), (2, 6, "ED"), (2, 7, "ED"),
    (3, 5, "ED"), (4, 5, "ED"), (5, 7, "ED"),
    (2, 5, "MD"), (3, 4, "MD"),
    (1, 6, "CD"), (4, 7, "CD"), (5, 6, "CD"), (6, 7, "CD"),
}
STYLE = {  # colour, linestyle, legend label
    "UED": ("#6B7280", "-", "UED · unitary evolution"),
    "ED": ("#D97706", "-", "ED · entanglement"),
    "MD": ("#15803D", "-", "MD · measurement collapse"),
    "CD": ("#2563EB", "--", "CD · classical feedback"),
}


def teleportation() -> QuantumCircuit:
    qc = QuantumCircuit(3, 2)
    qc.h(1)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.h(0)
    qc.measure(0, 0)
    qc.measure(1, 1)
    with qc.if_test((qc.clbits[1], 1)):
        qc.x(2)
    with qc.if_test((qc.clbits[0], 1)):
        qc.z(2)
    return qc


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out"
    out.mkdir(parents=True, exist_ok=True)
    qdg = qdg_from_circuit(teleportation())
    built = {(s, d, t) for t in STYLE for (s, d) in qdg.edges_of_type(t)}
    same = built == SUBMITTED_FIG1_EDGES
    print(f"four-edge QPDG of teleportation: {len(built)} edges; "
          f"{'IDENTICAL to' if same else 'DIFFERENT from'} the edge set of the submitted Fig. 1")
    if not same:
        print("  only built:", sorted(built - SUBMITTED_FIG1_EDGES))
        print("  only in submitted figure:", sorted(SUBMITTED_FIG1_EDGES - built))

    # ASAP layer over qubits; y = mean lane (q0 on top).
    layer_of_qubit: dict[int, int] = {}
    pos = {}
    nq = 3
    for gid in sorted(qdg.nodes):
        n = qdg.nodes[gid]
        layer = max((layer_of_qubit.get(q, -1) for q in n.qubits), default=-1) + 1
        for q in n.qubits:
            layer_of_qubit[q] = layer
        pos[gid] = (layer, sum(nq - 1 - q for q in n.qubits) / len(n.qubits))

    fig, ax = plt.subplots(figsize=(13, 5.2))
    for q in range(nq):
        y = nq - 1 - q
        ax.axhspan(y - 0.22, y + 0.22, color="#EEF2F7", zorder=0)
        ax.text(-0.7, y, f"q{q}", ha="center", va="center", fontsize=13, fontweight="bold")
    for s, d, t in sorted(built):
        colour, ls, _ = STYLE[t]
        bend = 0.18 if abs(pos[s][1] - pos[d][1]) > 0.6 or pos[d][0] - pos[s][0] > 1 else 0.08
        ax.annotate("", xy=pos[d], xytext=pos[s], zorder=1,
                    arrowprops=dict(arrowstyle="-|>", color=colour, lw=2.2, linestyle=ls,
                                    shrinkA=17, shrinkB=17, mutation_scale=14,
                                    connectionstyle=f"arc3,rad={bend}"))
    for gid, n in qdg.nodes.items():
        if n.is_measurement:
            face, name = "#DBEAFE", "MEAS"
        elif n.is_conditioned:
            face, name = "#E5E7EB", "X/Z(if)"
        else:
            face, name = "#FEF3C7", n.name.upper()
        ax.scatter(*pos[gid], s=1500, color=face, edgecolor="#1F2937", linewidth=1.5, zorder=2)
        ax.text(*pos[gid], f"{name}\n[{','.join(f'q{q}' for q in n.qubits)}]",
                ha="center", va="center", fontsize=8.5, zorder=3)
    ax.set_xlim(-1.1, max(p[0] for p in pos.values()) + 0.6)
    ax.set_ylim(-0.6, nq - 0.4)
    ax.set_yticks([])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.set_xticks(range(0, max(p[0] for p in pos.values()) + 1))
    ax.set_xlabel("circuit time (ASAP layer)")
    ax.legend(handles=[Line2D([], [], color=c, ls=ls, lw=2.2, label=lab) for c, ls, lab in STYLE.values()],
              loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=4, frameon=False)
    fig.tight_layout()
    fig.savefig(out / "fig1_qpdg_teleportation_redrawn.png", dpi=220)
    print(f"wrote {out / 'fig1_qpdg_teleportation_redrawn.png'}")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
