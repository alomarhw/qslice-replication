"""The study's rules on the examples of Yu and Zhao's QPDG paper [yu2025qpdg], and the slice its Fig. 1 implies.

Listings 1-5 of the paper are transcribed by hand as circuits (only the circuit-building statements; Listing 4's
time.sleep is not part of the circuit). For every qubit this records the dependence set and the slices of
def-use, the classical PDG, the QDG, the QPDG and its read-only reading, with fidelities at |0...0>.

Fig. 1 of the paper draws the QPDG of Listing 1. Its edges are transcribed below as drawn (the node drawn as
"qc.cx(1)" is qc.x(1) in the listing). Backward reachability from qc.measure(1,1) over these edges is the slice
the paper's definition gives. The script compares the probability that q1 measures 1 in the program and in
that slice.
Output: results/icpc/yz_listings/listings.json, fig1.json.
Usage (from experiments/): python icpc/yz_listings.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.quantum_info import Statevector

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
OUT = HERE / "results" / "icpc" / "yz_listings"


def listing1():
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.delay(100)
    qc.x(1)
    qc.cx(0, 1)
    qc.measure(0, 0)
    qc.measure(1, 1)
    return qc


def listing2():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure_all()
    return qc


def listing3():
    qc = QuantumCircuit(2)
    qc.x(0)
    qc.cx(0, 1)
    qc.measure_all()
    return qc


def listing4():
    qc = QuantumCircuit(1)
    qc.h(0)
    qc.x(0)
    qc.measure_all()
    return qc


def listing5():
    qreg, creg = QuantumRegister(1), ClassicalRegister(1)
    qc = QuantumCircuit(qreg, creg)
    qc.h(qreg[0])
    qc.measure(qreg[0], creg[0])
    with qc.if_test((creg, 1)):
        qc.x(qreg[0])
    return qc


# Fig. 1 nodes in listing order, and its edges as drawn (control, entanglement, no-cloning, temporal, measurement)
FIG1_NODES = ["h(0)", "cx(0,1)", "delay(100)", "x(1)", "cx(0,1)", "measure(0,0)", "measure(1,1)"]
FIG1_EDGES = [(0, 1), (1, 6), (1, 4), (2, 3), (1, 5), (5, 6)]


def listing_facts(qc0):
    from common.corpus import prepare
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from icpc.cpdg import cpdg_slice
    from icpc.influence import influence, influence_sets
    from icpc.qpdg_ro import yzro_slice
    from slicers.registry import Slicers
    qc = prepare(qc0)
    n = qc.num_qubits
    s = Slicers(qc, "yz_listing")
    base = oi.reduced_states(qc, range(n))
    dep = influence_sets(influence(qc), n)
    out = {"ops": [f"{i.operation.name}{[qc.find_bit(x).index for x in i.qubits]}" for i in qc.data]}
    for t in range(n):
        sl = {"du": s.du(t), "cpdg": cpdg_slice(qc, t), "lc": s.lc(t), "yz": s.yz(t), "yzro": yzro_slice(qc, t)}
        out[f"q{t}"] = {"dep": sorted(dep[t])}
        for m, v in sl.items():
            f = oi.uhlmann_fidelity(base[t], oi.reduced_states(materialise(qc, set(v)), range(n))[t])
            out[f"q{t}"][m] = {"slice": sorted(v), "fidelity": round(float(f), 6)}
    return out


def fig1_facts():
    pred = {}
    for i, j in FIG1_EDGES:
        pred.setdefault(j, set()).add(i)
    seen, st = set(), [6]
    while st:
        x = st.pop()
        if x not in seen:
            seen.add(x)
            st.extend(pred.get(x, ()))
    full = listing1().remove_final_measurements(inplace=False)
    # Fig. 1 has one node per statement, and qc.delay(100) appends one instruction per qubit
    node_of, k = [], 0
    for inst in full.data:
        if inst.operation.name == "delay" and node_of and full.data[len(node_of) - 1].operation.name == "delay":
            node_of.append(node_of[-1])
        else:
            node_of.append(k)
            k += 1
    assert [FIG1_NODES[k].split("(")[0] for k in node_of] == [i.operation.name for i in full.data]
    kept = QuantumCircuit(2)
    for k, inst in zip(node_of, full.data):
        if k in seen:
            kept.append(inst)
    p = {name: float(Statevector(c).probabilities([1])[1]) for name, c in [("program", full), ("slice", kept)]}
    return {"slice": [FIG1_NODES[k] for k in sorted(seen)],
            "missing": [FIG1_NODES[k] for k in range(5) if k not in seen and FIG1_NODES[k] != "delay(100)"],
            "p_q1_one": {k: round(v, 6) for k, v in p.items()}}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    L = {f"listing{k}": listing_facts(f()) for k, f in enumerate([listing1, listing2, listing3, listing4, listing5], 1)}
    (OUT / "listings.json").write_text(json.dumps(L, indent=1))
    F = fig1_facts()
    (OUT / "fig1.json").write_text(json.dumps(F, indent=1))
    same = all(v[q]["yz"]["slice"] == v[q]["lc"]["slice"] for v in L.values() for q in v if q.startswith("q"))
    print("QPDG == QDG on every listing:", same)
    print("Fig. 1:", F)


if __name__ == "__main__":
    main()
