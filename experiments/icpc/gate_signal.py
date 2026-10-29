"""Deviation I-24: can each standard two-qubit gate signal in each direction? Evidence only, no theorem.

For a gate U on qubits (0, 1) and a direction a -> b, U signals from a to b if b's reduced state after U depends on
a's input. We search seeded random product inputs |psi_a> (x) |psi_b> and a second random |psi_a'>, and record the
largest trace distance between b's two reduced states. A gate whose largest distance stays below 1e-9 in a direction
gives no evidence of signalling in that direction. Parametrised gates take a fixed angle.
Usage (from experiments/): python icpc/gate_signal.py  -> results/icpc/gate_signal/summary.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from qiskit.circuit import library as L
from qiskit.quantum_info import DensityMatrix, Operator, Statevector, partial_trace

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / "results" / "icpc" / "gate_signal"
SEED, TRIALS, EPS, THETA = 20261028, 200, 1e-9, 0.7
GATES = {
    "cx": L.CXGate(), "cy": L.CYGate(), "cz": L.CZGate(), "ch": L.CHGate(), "cs": L.CSGate(), "csx": L.CSXGate(),
    "cp": L.CPhaseGate(THETA), "crx": L.CRXGate(THETA), "cry": L.CRYGate(THETA), "crz": L.CRZGate(THETA),
    "cu": L.CUGate(THETA, THETA, THETA, THETA), "swap": L.SwapGate(), "iswap": L.iSwapGate(), "dcx": L.DCXGate(),
    "ecr": L.ECRGate(), "rxx": L.RXXGate(THETA), "ryy": L.RYYGate(THETA), "rzz": L.RZZGate(THETA),
    "rzx": L.RZXGate(THETA), "xx_plus_yy": L.XXPlusYYGate(THETA), "xx_minus_yy": L.XXMinusYYGate(THETA),
}


# negative controls: product gates, which cannot signal, must stay below EPS in both directions
CONTROLS = {"h(x)i": Operator(L.HGate()).tensor(Operator(L.IGate())),
            "rx(x)ry": Operator(L.RXGate(THETA)).tensor(Operator(L.RYGate(THETA)))}


def _random_qubit(rng):
    v = rng.normal(size=2) + 1j * rng.normal(size=2)
    return v / np.linalg.norm(v)


def max_signal(U: Operator, a: int, rng) -> float:
    """Largest trace distance of qubit b's reduced state over pairs of inputs that differ only on qubit a."""
    b = 1 - a
    best = 0.0
    for _ in range(TRIALS):
        pb, pa, pa2 = _random_qubit(rng), _random_qubit(rng), _random_qubit(rng)
        states = []
        for x in (pa, pa2):
            # Qiskit orders qubit 0 as the least significant tensor factor
            v = np.kron(pb, x) if a == 0 else np.kron(x, pb)
            out = Statevector(v).evolve(U)
            states.append(partial_trace(DensityMatrix(out), [a]).data)
        d = 0.5 * np.abs(np.linalg.eigvalsh(states[0] - states[1])).sum()
        best = max(best, float(d))
    return best


def main() -> int:
    rng = np.random.default_rng(SEED)
    res = {}
    for name, g in GATES.items():
        U = Operator(g)
        res[name] = {"0->1": max_signal(U, 0, rng), "1->0": max_signal(U, 1, rng)}
        res[name]["both"] = int(res[name]["0->1"] > EPS and res[name]["1->0"] > EPS)
    ctrl = {name: {"0->1": max_signal(U, 0, rng), "1->0": max_signal(U, 1, rng)} for name, U in CONTROLS.items()}
    assert all(v < EPS for c in ctrl.values() for v in c.values()), ctrl
    OUT.mkdir(parents=True, exist_ok=True)
    summ = {"seed": SEED, "trials": TRIALS, "eps": EPS, "theta": THETA, "gates": res, "controls": ctrl,
            "n_gates": len(res), "n_both": sum(r["both"] for r in res.values())}
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    for k, r in res.items():
        print(f"{k:12s} 0->1 {r['0->1']:.3f}  1->0 {r['1->0']:.3f}  both={r['both']}")
    print(f"{summ['n_both']}/{summ['n_gates']} gates signal in both directions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
