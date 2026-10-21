"""
main.py — Quantum Program Dependence Graph (QPDG) slicing study.

Thesis: classical dependence analysis is NECESSARY but NOT SUFFICIENT for quantum program slicing.
A faithful port of classical slicing (def-use, where a controlled gate reads its control and writes
its target) ignores entanglement and therefore produces semantically INVALID slices. A quantum-aware
QPDG that adds entanglement edges (a) restores soundness and (b) via flow-sensitive separability,
yields more precise (smaller) sound slices than even a sound causal classical baseline.

Three slicers are compared on REAL benchmark circuits (QASMBench), for BOTH backward and forward
slicing:
  - naive_classical : classical def-use port (unsound — the realistic baseline)
  - causal_classical: data+control light cone (sound but imprecise)
  - qpdg            : entanglement-aware (sound + precise)

RQ1 (soundness, backward): how often does naive classical slicing produce semantically invalid
     slices, and does QPDG eliminate them?  (criterion = target reduced density matrix)
RQ2 (precision, backward): does QPDG produce smaller SOUND slices than the sound causal baseline?
RQ3 (soundness, forward):  does the naive classical FORWARD slice miss entanglement-influenced
     operations, and does QPDG cover them?  (criterion = influence completeness under perturbation)

Run:  python main.py          # smoke: a subset of circuits, fast
      python main.py --full   # all loadable QASMBench small circuits
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import DensityMatrix, Statevector, partial_trace, state_fidelity

from qasm_loader import load_qasmbench_corpus, load_combined
from qdg import QDG, EdgeType
from stats_utils import bootstrap_ci, mcnemar_test, wilcoxon_test

RESULTS_DIR = Path("results")
FIG_DIR = Path("figures")
FIDELITY_EPS = 1e-6          # a slice is semantically valid iff fidelity >= 1 - eps
SMOKE_CIRCUITS = 12          # circuits used in the default (smoke) run
SMOKE_MAX_QUBITS = 8
FULL_MAX_QUBITS = 11
# Exact statevector slicing is O(ops) per prefix and 2^q per state; cap gate count so a few huge
# QASMBench circuits (e.g. basis_trotter ~1500 ops) don't dominate. Documented as a coverage bound.
SMOKE_MAX_OPS = 120
FULL_MAX_OPS = 300
# Medium circuits: exact statevector is 2**q, so cap qubits for tractability; gate cap keeps the
# per-prune verification cost bounded. Circuits above these stay available as data (structural use).
MEDIUM_MAX_QUBITS = 20
MEDIUM_MAX_OPS = 200
# Exact eval cost is O(targets) per circuit, and forward influence is O(n) partial traces at 2**n per
# target; on wide circuits we sample a spread of target qubits rather than all n (we aggregate over
# slices, so a representative sample is sufficient and keeps the exact run tractable).
TARGET_SAMPLE_CAP = 8
# Exact analysis evolves a statevector gate-by-gate. A k-qubit gate forces a 2^k x 2^k operator in
# Statevector.evolve, so a single wide *composite* gate (e.g. an MQT/VeriQBench Deutsch-Jozsa or
# Grover "Oracle" spanning all qubits, or a quantum_volume block) materialises a 2^n x 2^n matrix and
# OOMs (a 14-qubit oracle = 4.3 GB). We decompose only gates wider than this into elementary gates
# before building the QDG, so (a) evolve stays cheap and (b) the dependence graph is over realistic
# elementary gates — a monolithic n-qubit black box couples every qubit and is not a meaningful
# slicing unit anyway. Set above any normal gate's arity so this is a no-op on typical circuits.
FLATTEN_ARITY = 8            # decompose composite gates with > this many qubits
HARD_ARITY_CAP = 12          # if a gate still exceeds this after flattening, the circuit is skipped


# ──────────────────────────────────────────────────────────────────────────────
# Circuit normalisation for exact analysis
# ──────────────────────────────────────────────────────────────────────────────

def _flatten_wide_gates(qc: QuantumCircuit, max_arity: int = FLATTEN_ARITY,
                        max_reps: int = 16, op_ceiling: int = 50_000) -> QuantumCircuit:
    """Recursively decompose only composite gates wider than ``max_arity`` into their definitions,
    leaving normal (<= max_arity-qubit) gates untouched. Returns the circuit unchanged when it has no
    wide gates (the common case), so existing results are unaffected. Bails out early once the
    decomposition exceeds ``op_ceiling`` gates — such a circuit far exceeds any exact gate budget and
    will be dropped anyway, so there is no point materialising a 100k+ gate object."""
    cur = qc
    for _ in range(max_reps):
        wide = sorted({ci.operation.name for ci in cur.data
                       if ci.operation.num_qubits > max_arity})
        if not wide:
            return cur
        try:
            cur = cur.decompose(gates_to_decompose=wide)
        except Exception:
            return cur
        if len(cur.data) > op_ceiling:
            return cur  # too big for exact analysis; caller's gate-cap filter drops it
    return cur


def _max_arity(qc: QuantumCircuit) -> int:
    return max((ci.operation.num_qubits for ci in qc.data), default=0)


# ──────────────────────────────────────────────────────────────────────────────
# Semantic primitives
# ──────────────────────────────────────────────────────────────────────────────

def _reduced(qc: QuantumCircuit, keep: List[int]) -> np.ndarray:
    n = qc.num_qubits
    return partial_trace(Statevector(qc), [q for q in range(n) if q not in keep]).data


def _fidelity_target(full: QuantumCircuit, sliced: QuantumCircuit, target: int) -> float:
    """State fidelity of the target's reduced density matrix: slice vs full circuit."""
    try:
        ref = _reduced(full, [target])
        got = _reduced(sliced, [target])
        return float(state_fidelity(DensityMatrix(ref), DensityMatrix(got), validate=False))
    except Exception:
        return 0.0


def _affected_qubits(qc: QuantumCircuit, target: int) -> set:
    """Qubits whose reduced state CHANGES when the target is perturbed at the input — the ground-truth
    forward influence set of ``target`` (used to judge forward-slice completeness)."""
    n = qc.num_qubits
    pert = QuantumCircuit(n)
    pert.x(target)
    pert.compose(qc, inplace=True)
    try:
        base = Statevector(qc)
        per = Statevector(pert)
    except Exception:
        return set()
    affected = set()
    for q in range(n):
        rb = partial_trace(base, [x for x in range(n) if x != q]).data
        rp = partial_trace(per, [x for x in range(n) if x != q]).data
        if np.linalg.norm(rb - rp, ord="nuc") / 2.0 > 1e-9:
            affected.add(q)
    return affected


def _sample_targets(nq: int, cap: int = TARGET_SAMPLE_CAP) -> List[int]:
    """All qubits if ``nq <= cap``, else an evenly-spaced spread of ``cap`` target qubits (deterministic)."""
    if nq <= cap:
        return list(range(nq))
    return sorted({int(round(i * (nq - 1) / (cap - 1))) for i in range(cap)})


def _slice_qubits(qdg: QDG, nodes) -> set:
    out = set()
    for p in nodes:
        node = qdg.nodes.get(p)
        if node:
            out.update(node.qubits)
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Per-circuit evaluation
# ──────────────────────────────────────────────────────────────────────────────

def eval_backward(qc: QuantumCircuit) -> List[Dict]:
    """Backward slicing: size + semantic validity (target reduced state) for each slicer × target."""
    full = QDG(qc); full.build(include_entanglement=True, include_control=True)
    causal = full.remove_edge_type(EdgeType.ENTANGLEMENT)
    nops = max(len(qc.data), 1)
    recs = []
    for t in _sample_targets(qc.num_qubits):
        slices = {
            "naive": full.naive_classical_backward_slice(t),
            "causal": causal.backward_slice(t),
            "qpdg": full.entanglement_pruned_slice(t),
        }
        rec = {"target": t}
        for name, s in slices.items():
            fid = _fidelity_target(qc, full.extract_slice_circuit(set(s)), t)
            rec[name] = {"size": len(s) / nops, "fidelity": fid, "valid": fid >= 1 - FIDELITY_EPS}
        recs.append(rec)
    return recs


def eval_forward(qc: QuantumCircuit) -> List[Dict]:
    """Forward slicing: does the slice COVER every qubit the target actually influences?"""
    full = QDG(qc); full.build(include_entanglement=True, include_control=True)
    causal = full.remove_edge_type(EdgeType.ENTANGLEMENT)
    recs = []
    for t in _sample_targets(qc.num_qubits):
        truth = _affected_qubits(qc, t)
        slices = {
            "naive": full.naive_classical_forward_slice(t),
            "causal": causal.forward_slice(t),
            "qpdg": full.forward_slice(t),
        }
        rec = {"target": t, "n_affected": len(truth)}
        for name, s in slices.items():
            covered = _slice_qubits(full, s) | {t}
            complete = truth.issubset(covered)
            missed = len(truth - covered)
            rec[name] = {"complete": complete, "missed": missed}
        recs.append(rec)
    return recs


# ──────────────────────────────────────────────────────────────────────────────
# Aggregation into RQ metrics
# ──────────────────────────────────────────────────────────────────────────────

def _rate(flags) -> float:
    return float(np.mean(flags)) if flags else 0.0


def aggregate(corpus, back, fwd) -> Dict:
    methods = ["naive", "causal", "qpdg"]
    # Flatten per-slice records.
    b = {m: {"size": [], "fid": [], "valid": []} for m in methods}
    for recs in back:
        for r in recs:
            for m in methods:
                b[m]["size"].append(r[m]["size"])
                b[m]["fid"].append(r[m]["fidelity"])
                b[m]["valid"].append(bool(r[m]["valid"]))
    f = {m: {"complete": [], "missed": []} for m in methods}
    for recs in fwd:
        for r in recs:
            for m in methods:
                f[m]["complete"].append(bool(r[m]["complete"]))
                f[m]["missed"].append(r[m]["missed"])

    n_back = len(b["naive"]["valid"])
    n_fwd = len(f["naive"]["complete"])
    invalid = {m: 1 - _rate(b[m]["valid"]) for m in methods}

    # RQ1 — soundness (backward): naive invalid vs qpdg via McNemar on the paired valid/invalid flags.
    nv = np.array(b["naive"]["valid"]); qv = np.array(b["qpdg"]["valid"])
    n00 = int(np.sum(~nv & ~qv)); n01 = int(np.sum(~nv & qv))
    n10 = int(np.sum(nv & ~qv)); n11 = int(np.sum(nv & qv))
    rq1_stats = mcnemar_test([[n00, n01], [n10, n11]])

    # RQ2 — precision (backward): QPDG vs causal slice size, paired Wilcoxon (sound slices only).
    sound_pairs = [(r["causal"]["size"], r["qpdg"]["size"])
                   for recs in back for r in recs
                   if r["causal"]["valid"] and r["qpdg"]["valid"]]
    causal_sz = np.array([c for c, _ in sound_pairs]) if sound_pairs else np.array([0.0])
    qpdg_sz = np.array([q for _, q in sound_pairs]) if sound_pairs else np.array([0.0])
    rq2_stats = wilcoxon_test(causal_sz, qpdg_sz)
    reduction = causal_sz - qpdg_sz

    # RQ3 — soundness (forward): naive incomplete vs qpdg via McNemar on completeness flags.
    nc = np.array(f["naive"]["complete"]); qc_ = np.array(f["qpdg"]["complete"])
    m00 = int(np.sum(~nc & ~qc_)); m01 = int(np.sum(~nc & qc_))
    m10 = int(np.sum(nc & ~qc_)); m11 = int(np.sum(nc & qc_))
    rq3_stats = mcnemar_test([[m00, m01], [m10, m11]])

    def _ci(arr):
        a = np.array(arr, dtype=float)
        if a.size < 2:
            return [float(a.mean()) if a.size else 0.0] * 2
        lo, hi = bootstrap_ci(a, statistic=np.mean, n_boot=499)
        return [float(lo), float(hi)]

    results = {
        "RQ1": {
            "_question": "Does a faithful classical (def-use) PDG slicer produce semantically invalid "
                         "backward slices on real quantum circuits, and does QPDG eliminate them?",
            "metrics": {
                "n_slices": float(n_back),
                "qpdg_invalid_rate": invalid["qpdg"],
                "qpdg_mean_fidelity": float(np.mean(b["qpdg"]["fid"])),
                "naive_classical_invalid_rate": invalid["naive"],
                "naive_classical_mean_fidelity": float(np.mean(b["naive"]["fid"])),
                "qpdg_slices_repaired_over_naive": float(n01),  # naive invalid & qpdg valid (the wins)
            },
            "baseline_comparison": {
                "naive_classical_pdg": {"invalid_rate": invalid["naive"],
                                        "mean_fidelity": float(np.mean(b["naive"]["fid"]))},
                "causal_classical_pdg": {"invalid_rate": invalid["causal"],
                                         "mean_fidelity": float(np.mean(b["causal"]["fid"]))},
            },
            "statistical_tests": rq1_stats,
        },
        "RQ2": {
            "_question": "Does QPDG produce smaller SOUND backward slices than the sound causal "
                         "classical baseline (precision win at equal soundness)?",
            "metrics": {
                "n_sound_pairs": float(len(sound_pairs)),
                "qpdg_mean_slice_size": float(qpdg_sz.mean()),
                "mean_slice_size_reduction": float(reduction.mean()),
                "max_slice_size_reduction": float(reduction.max()) if reduction.size else 0.0,
                "fraction_slices_improved": float(np.mean(reduction > 1e-9)) if reduction.size else 0.0,
                "qpdg_invalid_rate": invalid["qpdg"],
                "reduction_ci_low": _ci(reduction)[0],
                "reduction_ci_high": _ci(reduction)[1],
            },
            "baseline_comparison": {
                "causal_classical_pdg": {"mean_slice_size": float(causal_sz.mean())},
            },
            "statistical_tests": rq2_stats,
        },
        "RQ3": {
            "_question": "Does the naive classical FORWARD slice miss entanglement-influenced "
                         "operations (incomplete influence), and does QPDG cover them?",
            "metrics": {
                "n_slices": float(n_fwd),
                "qpdg_incomplete_rate": 1 - _rate(f["qpdg"]["complete"]),
                "qpdg_mean_qubits_missed": float(np.mean(f["qpdg"]["missed"])),
                "naive_classical_incomplete_rate": 1 - _rate(f["naive"]["complete"]),
                "naive_classical_mean_qubits_missed": float(np.mean(f["naive"]["missed"])),
            },
            "baseline_comparison": {
                "naive_classical_pdg": {"incomplete_rate": 1 - _rate(f["naive"]["complete"]),
                                        "mean_qubits_missed": float(np.mean(f["naive"]["missed"]))},
                "causal_classical_pdg": {"incomplete_rate": 1 - _rate(f["causal"]["complete"]),
                                         "mean_qubits_missed": float(np.mean(f["causal"]["missed"]))},
            },
            "statistical_tests": rq3_stats,
        },
    }
    # carry aggregates for figures
    results["_agg"] = {"backward": b, "forward": f, "invalid": invalid}
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Motivating debugging case study
# ──────────────────────────────────────────────────────────────────────────────

def debugging_case_study() -> Dict:
    """A concrete debugging scenario: a 3-qubit circuit is supposed to leave q0 in a known state, but
    a planted faulty gate (an extra RZ on q2, entangled with q0) corrupts q0's measurement. We slice
    backward from q0 with each slicer and ask: does the slice CONTAIN the faulty gate (so a developer
    inspecting the slice would find it)?  Naive classical slicing drops it (q2 looks independent of
    q0 because the entangling CX 'writes' only its target); QPDG keeps it."""
    qc = QuantumCircuit(3)
    qc.h(0)
    qc.cx(0, 1)          # entangle q0,q1
    qc.cx(1, 2)          # entangle q1,q2  -> q0,q1,q2 jointly entangled
    qc.h(2)
    FAULTY = len(qc.data)
    qc.rz(0.9, 2)        # <-- PLANTED BUG: spurious rotation on q2; via entanglement it shifts q0
    qc.cx(1, 2)
    qc.cx(0, 1)          # disentangle path back toward q0

    full = QDG(qc); full.build(include_entanglement=True, include_control=True)
    causal = full.remove_edge_type(EdgeType.ENTANGLEMENT)
    slices = {
        "naive": full.naive_classical_backward_slice(0),
        "causal": causal.backward_slice(0),
        "qpdg": full.entanglement_pruned_slice(0),
    }
    contains = {m: (FAULTY in s) for m, s in slices.items()}
    sizes = {m: len(s) for m, s in slices.items()}
    return {"circuit": qc, "qdg": full, "faulty_pos": FAULTY,
            "slices": slices, "contains_bug": contains, "sizes": sizes}


# ──────────────────────────────────────────────────────────────────────────────
# Figures
# ──────────────────────────────────────────────────────────────────────────────

def _teleportation_circuit():
    """Quantum teleportation — the textbook circuit exercising ALL THREE dependence edge types:
    data (gates along a wire), entanglement (the Bell pair), and control (corrections classically
    conditioned on measurement outcomes)."""
    from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
    qr = QuantumRegister(3, "q"); cr = ClassicalRegister(2, "c")
    qc = QuantumCircuit(qr, cr)
    qc.h(1); qc.cx(1, 2)                    # entanglement: Bell pair (q1,q2)
    qc.cx(0, 1); qc.h(0)                    # entangle the message qubit q0 with q1
    qc.measure(0, 0); qc.measure(1, 1)
    with qc.if_test((cr[1], 1)): qc.x(2)    # control: X correction conditioned on q1's outcome
    with qc.if_test((cr[0], 1)): qc.z(2)    # control: Z correction conditioned on q0's outcome
    return qc


def make_figures(corpus, results, case):
    import figures_qpdg as F
    FIG_DIR.mkdir(exist_ok=True)

    # 0. Concept figure: teleportation QPDG — shows DATA, CONTROL, and ENTANGLEMENT edges together
    #    (control edges only exist when a measurement classically conditions a later gate).
    tele = _teleportation_circuit()
    teleq = QDG(tele); teleq.build(include_entanglement=True, include_control=True)
    F.draw_qpdg_graph(teleq, str(FIG_DIR / "fig_qpdg_concept.png"),
                      title="QPDG of quantum teleportation — data, control, and entanglement edges")

    # 1. QPDG graph of a representative, NON-TRIVIAL circuit (enough structure to show real edges and a
    #    slice that is a proper subset). Prefer a recognisable algorithm of moderate size with several
    #    two-qubit gates; pick the target qubit whose QPDG slice is a strict subset so the slice is visible.
    def _twoq(e):
        return sum(1 for ci in e["qc"].data if len(ci.qubits) >= 2)
    prefer = ["qft_n4", "adder_n4", "fredkin_n3", "variational_n4", "linearsolver_n3", "vqe_n4"]
    cands = [e for e in corpus if 8 <= e["n_ops"] <= 22 and 3 <= e["n_qubits"] <= 5 and _twoq(e) >= 2]
    rep = next((e for e in corpus if e["id"] in prefer and e in cands),
               max(cands or corpus, key=lambda e: (_twoq(e), -abs(e["n_ops"] - 14))))
    repq = QDG(rep["qc"]); repq.build(include_entanglement=True, include_control=True)
    F.draw_qpdg_graph(repq, str(FIG_DIR / "fig_qpdg_graph.png"),
                      title=f"QPDG of {rep['id']} — data, control, and entanglement edges")

    # 2. Slice visualisation: choose the target qubit whose QPDG slice is a STRICT subset (most illustrative).
    best_t, sl = 0, repq.entanglement_pruned_slice(0)
    for t in range(rep["n_qubits"]):
        s = repq.entanglement_pruned_slice(t)
        if 0 < len(s) < len(rep["qc"].data):
            best_t, sl = t, s
            break
    F.draw_qpdg_graph(repq, str(FIG_DIR / "fig_qpdg_slice.png"), slice_nodes=sl,
                      title=f"QPDG backward slice on q{best_t} of {rep['id']} "
                            f"({len(sl)}/{len(rep['qc'].data)} gates)")
    F.draw_slice_panels(rep["qc"], repq, sl, str(FIG_DIR / "fig_slice_circuit.png"), target=best_t)

    # 3. Results bars (RQ1 soundness + RQ2 precision summary).
    inv = results["_agg"]["invalid"]
    b = results["_agg"]["backward"]
    per_method = {
        "naive classical": {"size": float(np.mean(b["naive"]["size"])), "invalid": inv["naive"],
                            "fidelity": float(np.mean(b["naive"]["fid"]))},
        "causal classical": {"size": float(np.mean(b["causal"]["size"])), "invalid": inv["causal"],
                             "fidelity": float(np.mean(b["causal"]["fid"]))},
        "QPDG": {"size": float(np.mean(b["qpdg"]["size"])), "invalid": inv["qpdg"],
                 "fidelity": float(np.mean(b["qpdg"]["fid"]))},
    }
    F.draw_results_bars(per_method, str(FIG_DIR / "fig_results_summary.png"),
                        title="QPDG vs classical slicing on QASMBench (backward)")

    # 4. Debugging case study: contrast the NAIVE slice (drops the faulty gate -> bug invisible) with
    #    the QPDG slice (keeps it -> bug found). Two graphs side-by-side tell the motivating story.
    fp = case["faulty_pos"]
    F.draw_qpdg_graph(case["qdg"], str(FIG_DIR / "fig_debug_naive.png"),
                      slice_nodes=case["slices"]["naive"],
                      title="Naive classical slice on q0 — faulty gate #%d is MISSED (not in slice)" % fp)
    F.draw_qpdg_graph(case["qdg"], str(FIG_DIR / "fig_debug_qpdg.png"),
                      slice_nodes=case["slices"]["qpdg"],
                      title="QPDG slice on q0 — faulty gate #%d is CAPTURED (in slice)" % fp)
    F.draw_slice_panels(case["circuit"], case["qdg"], case["slices"]["qpdg"],
                        str(FIG_DIR / "fig_debug_slice.png"), target=0, method="QPDG")


# ──────────────────────────────────────────────────────────────────────────────
# Structural scalability pass (NO simulation) — runs on LARGE circuits
# ──────────────────────────────────────────────────────────────────────────────

def run_structural_scale(categories=("small", "medium", "large"), max_qubits=1024,
                         max_ops=50000, n_targets=8, suites=("qasmbench", "mqt")) -> List[Dict]:
    """Structural slice analysis that needs NO statevector simulation, so it scales to hundreds of
    qubits. For each circuit we slice from sampled target qubits with the naive classical (def-use)
    and the sound causal classical slicers, both O(ops).

    The unsoundness signature is computable structurally: a two-qubit gate is a dependence on BOTH
    wires, so the sound causal slice keeps it, but the naive def-use slice drops it when slicing from
    the control qubit. ``dropped_2q`` = two-qubit (entangling) gates in ``causal \\ naive`` = exactly
    the entanglement-mediated dependencies the naive slicer omits — the mechanism we verified by
    fidelity on the simulable circuits, now measured at scale.
    """
    import time
    corpus = [e for e in load_combined(max_qubits=max_qubits, categories=categories,
                                       max_ops=max_ops, require_unitary=False, suites=suites)
              if e["n_ops"] <= max_ops]
    rng = np.random.default_rng(0)
    rows: List[Dict] = []
    for e in corpus:
        qc = e["qc"]; nq = qc.num_qubits; nops = max(len(qc.data), 1)
        t0 = time.perf_counter()
        qdg = QDG(qc); qdg.build(include_entanglement=False, include_control=True)  # O(ops); no O(n^2) closure
        build_s = time.perf_counter() - t0
        targets = (list(range(nq)) if nq <= n_targets
                   else sorted(int(x) for x in rng.choice(nq, n_targets, replace=False)))
        per = []
        for t in targets:
            naive = qdg.naive_classical_backward_slice(t)
            causal = qdg.backward_slice(t)
            dropped = causal - naive
            dropped_2q = sum(1 for p in dropped if p in qdg.nodes and len(qdg.nodes[p].qubits) >= 2)
            per.append((len(naive) / nops, len(causal) / nops, len(dropped), dropped_2q,
                        1.0 if dropped_2q > 0 else 0.0))
        a = np.array(per)
        rows.append({"id": e["id"], "source": e.get("source", "QASMBench"),
                     "category": e["category"], "n_qubits": nq, "n_ops": len(qc.data),
                     "naive_size": float(a[:, 0].mean()), "causal_size": float(a[:, 1].mean()),
                     "mean_dropped": float(a[:, 2].mean()), "mean_dropped_2q": float(a[:, 3].mean()),
                     "frac_slices_unsound_signature": float(a[:, 4].mean()), "build_s": build_s})
    return rows


def scale_main(categories, max_qubits, max_ops, suites=("qasmbench", "mqt")):
    rows = run_structural_scale(categories=categories, max_qubits=max_qubits, max_ops=max_ops, suites=suites)
    if not rows:
        raise RuntimeError("No circuits loaded for the structural scale run")
    rows.sort(key=lambda r: r["n_qubits"])
    print(f"Structural scale run: {len(rows)} circuits (no simulation)\n")
    print(f"  {'circuit':24s} {'cat':6s} {'q':>5s} {'ops':>7s} {'naive%':>7s} {'causal%':>8s} "
          f"{'drop2q':>7s} {'unsound%':>8s} {'build_s':>8s}")
    for r in rows:
        print(f"  {r['id'][:24]:24s} {r['category']:6s} {r['n_qubits']:5d} {r['n_ops']:7d} "
              f"{r['naive_size']:6.0%} {r['causal_size']:7.0%} {r['mean_dropped_2q']:7.1f} "
              f"{r['frac_slices_unsound_signature']:7.0%} {r['build_s']:8.3f}")
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    print("\n  per category (mean):")
    for cat, rs in by_cat.items():
        mq = np.mean([r["n_qubits"] for r in rs]); d2 = np.mean([r["mean_dropped_2q"] for r in rs])
        us = np.mean([r["frac_slices_unsound_signature"] for r in rs])
        print(f"    {cat:6s}: {len(rs):3d} circuits, mean {mq:5.0f} qubits | "
              f"naive drops {d2:5.1f} entangling deps/slice | {us:.0%} of slices show the unsound signature")
    RESULTS_DIR.mkdir(exist_ok=True)
    with open(RESULTS_DIR / "results_scale.json", "w") as fh:
        json.dump({"circuits": rows}, fh, indent=2, default=float)
    print(f"\nWrote {RESULTS_DIR/'results_scale.json'}")
    try:
        import figures_qpdg as F
        FIG_DIR.mkdir(exist_ok=True)
        F.draw_scale_figure(rows, str(FIG_DIR / "fig_scale.png"))
        print(f"Wrote {FIG_DIR/'fig_scale.png'}")
    except Exception as exc:
        print(f"(figure skipped: {exc})")


# ──────────────────────────────────────────────────────────────────────────────
# Driver
# ──────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="QPDG slicing study — smoke run by default")
    ap.add_argument("--full", action="store_true", help="Use all loadable QASMBench small circuits")
    ap.add_argument("--medium", action="store_true",
                    help="Also include MEDIUM circuits within the exact-simulation cap "
                         f"(<= {MEDIUM_MAX_QUBITS} qubits, <= {MEDIUM_MAX_OPS} gates)")
    ap.add_argument("--max-qubits", type=int, default=None, help="Override the qubit cap (exact sim is 2**q)")
    ap.add_argument("--scale", action="store_true",
                    help="Structural scalability run (NO simulation) over small+medium+LARGE circuits")
    ap.add_argument("--mqt", action="store_true",
                    help="Also include the MQT Bench suite (cross-benchmark replication)")
    ap.add_argument("--veriq", action="store_true",
                    help="Also include the VeriQBench suite (verification-oriented cross-benchmark)")
    ap.add_argument("--no-figures", action="store_true", help="Skip figure generation")
    args = ap.parse_args()

    suites = ["qasmbench"]
    if args.mqt:
        suites.append("mqt")
    if args.veriq:
        suites.append("veriqbench")
    suites = tuple(suites)
    if args.scale:
        scale_main(categories=("small", "medium", "large"),
                   max_qubits=args.max_qubits or 1024, max_ops=50000, suites=suites)
        return

    cats = ("small", "medium") if args.medium else ("small",)
    if args.medium:
        max_q = args.max_qubits or MEDIUM_MAX_QUBITS
        max_ops = MEDIUM_MAX_OPS
        mode = "small+medium"
    else:
        max_q = args.max_qubits or (FULL_MAX_QUBITS if args.full else SMOKE_MAX_QUBITS)
        max_ops = FULL_MAX_OPS if args.full else SMOKE_MAX_OPS
        mode = "full" if args.full else "smoke"
    raw_corpus = load_combined(max_qubits=max_q, categories=cats, max_ops=max_ops, suites=suites)
    # Flatten wide composite gates (e.g. n-qubit oracles) to elementary gates BEFORE filtering on
    # gate count — flattening can grow the op count, and a circuit that fits the exact budget only as
    # a black box must be judged at the elementary-gate level it will actually be sliced at.
    corpus = []
    dropped = {"ops": [], "arity": []}
    for e in raw_corpus:
        flat = _flatten_wide_gates(e["qc"])
        if _max_arity(flat) > HARD_ARITY_CAP:
            dropped["arity"].append(e["id"]); continue
        n_ops = len(flat.data)
        if n_ops > max_ops:
            dropped["ops"].append((e["id"], n_ops)); continue
        e = {**e, "qc": flat, "n_ops": n_ops, "n_ops_raw": e["n_ops"]}
        corpus.append(e)
    if mode == "smoke":
        corpus = corpus[:SMOKE_CIRCUITS]
    if args.mqt:
        mode += "+mqt"
    if args.veriq:
        mode += "+veriq"
    if not corpus:
        raise RuntimeError("No circuits loaded — run fetch_data.py / unzip data/QASMBench-master.zip")
    from collections import Counter as _Counter
    by_src = dict(_Counter(e["source"] for e in corpus))
    print(f"Loaded {len(corpus)} REAL circuits {by_src} "
          f"({mode} mode, <= {max_q} qubits, <= {max_ops} gates after flattening)")
    if dropped["ops"] or dropped["arity"]:
        print(f"  [coverage] dropped {len(dropped['ops'])} over gate-cap after flattening "
              f"(e.g. {dropped['ops'][:3]}), {len(dropped['arity'])} with irreducible >{HARD_ARITY_CAP}-qubit gates "
              f"(e.g. {dropped['arity'][:3]}); these remain in the structural (no-simulation) pass.")
    for e in corpus:
        print(f"  [{e.get('source','?'):9s} {e.get('category','small'):6s}] {e['id']:30s} q={e['n_qubits']:2d} ops={e['n_ops']}")

    print("\nEvaluating backward + forward slices (naive / causal / QPDG) ...")
    back = [eval_backward(e["qc"]) for e in corpus]
    fwd = [eval_forward(e["qc"]) for e in corpus]
    results = aggregate(corpus, back, fwd)

    case = debugging_case_study()
    results["_case_study"] = {
        "description": "3-qubit circuit with a planted faulty RZ on q2; slicing backward from q0.",
        "faulty_gate_position": case["faulty_pos"],
        "slice_contains_faulty_gate": case["contains_bug"],
        "slice_sizes": case["sizes"],
    }

    # Report
    print("\n=== RQ1 (backward soundness) ===")
    print(f"  naive classical invalid slices: {results['RQ1']['metrics']['naive_classical_invalid_rate']:.1%} "
          f"(fidelity {results['RQ1']['metrics']['naive_classical_mean_fidelity']:.3f})")
    print(f"  QPDG invalid slices:            {results['RQ1']['metrics']['qpdg_invalid_rate']:.1%} "
          f"(fidelity {results['RQ1']['metrics']['qpdg_mean_fidelity']:.3f})")
    print(f"  McNemar p={results['RQ1']['statistical_tests']['p_value']:.2e}")
    print("=== RQ2 (backward precision) ===")
    print(f"  mean slice-size reduction vs causal classical: "
          f"{results['RQ2']['metrics']['mean_slice_size_reduction']:.1%} "
          f"(max {results['RQ2']['metrics']['max_slice_size_reduction']:.1%}); Wilcoxon "
          f"p={results['RQ2']['statistical_tests']['p_value']:.2e}")
    print("=== RQ3 (forward soundness) ===")
    print(f"  naive classical incomplete: {results['RQ3']['metrics']['naive_classical_incomplete_rate']:.1%} "
          f"| QPDG incomplete: {results['RQ3']['metrics']['qpdg_incomplete_rate']:.1%}")
    print("=== Debugging case study ===")
    print(f"  faulty gate in slice?  {results['_case_study']['slice_contains_faulty_gate']}")

    # Persist results.json (strip private aggregates / non-serialisable case objects).
    RESULTS_DIR.mkdir(exist_ok=True)
    public = {k: v for k, v in results.items() if not k.startswith("_agg")}
    public.pop("_case_study", None)
    public["RQ_case_study"] = results["_case_study"]
    with open(RESULTS_DIR / "results.json", "w") as fh:
        json.dump({k: v for k, v in public.items()}, fh, indent=2, default=float)
    print(f"\nWrote {RESULTS_DIR/'results.json'}")

    if not args.no_figures:
        print("Generating figures ...")
        make_figures(corpus, results, case)
        print(f"Figures in {FIG_DIR}/")


if __name__ == "__main__":
    main()
