"""Every slicer of PROTOCOL_ICPC.md section 1, behind one interface: slice(qc, target) -> positions.

  du          qslice/qdg.py naive_classical_backward_slice (unchanged)
  lc          control-fixed QDG without ENTANGLEMENT edges, backward_slice (unchanged)
  lcq         qiskit.transpiler.passes.LightCone, union over the X, Y, Z observables on the target
  lcq_z       the same, Z observable only (descriptive)
  yz          slicers/yuzhao.py (design log there)
  q           entanglement_pruned_slice on the control-fixed QDG (unchanged; sep_eps = 1e-9)
  4e_unfixed  fouredge QSlice-full, as in the corrected run (seeded at criterion measurements)
  4e_fixed    fouredge QSlice-full seeded at the criterion's last operation of any kind (Deviation I-1)
  qW          set criterion W (section 1, S-qW): see qslice_set()

Slicers return instruction positions of the circuit they are given. They share no code with the oracle.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Sequence, Set

import numpy as np
from qiskit import QuantumCircuit

REPO = Path(__file__).resolve().parents[2]
for p in (REPO / "qslice", REPO / "experiments", REPO / "fouredge"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from qdg import EdgeType  # noqa: E402  (qslice/qdg.py, unchanged)
from method_eval.control_fix import QDGControlFixed  # noqa: E402
from slicers.yuzhao import yuzhao_slice  # noqa: E402

FOUR_EDGE_FULL = None  # resolved lazily (fouredge imports matplotlib-free modules only)


class NotApplicable(Exception):
    """The slicer cannot be applied to this circuit (reported as 'not applicable', not as a result)."""


class Slicers:
    """Builds the per-circuit graphs once, then slices any target."""

    def __init__(self, qc: QuantumCircuit, name: str = "circuit"):
        self.qc = qc
        self.full = QDGControlFixed(qc, name)
        self.full.build(include_entanglement=True, include_control=True)
        self.causal = self.full.remove_edge_type(EdgeType.ENTANGLEMENT)
        self._four = None

    # -- unchanged slicers -------------------------------------------------------------------------
    def du(self, t: int) -> Set[int]:
        return set(self.full.naive_classical_backward_slice(t))

    def lc(self, t: int) -> Set[int]:
        return set(self.causal.backward_slice(t))

    def q(self, t: int) -> Set[int]:
        return set(self.full.entanglement_pruned_slice(t))

    def yz(self, t: int) -> Set[int]:
        return set(self.full.backward_slice(t))  # = yuzhao_slice(qc, t): DATA + CONTROL + ENTANGLEMENT

    # -- Qiskit LightCone --------------------------------------------------------------------------
    def _lightcone(self, t: int, paulis: Iterable[str]) -> Set[int]:
        from qiskit.transpiler import PassManager
        from qiskit.transpiler.passes import LightCone
        labelled = self.qc.copy_empty_like()
        for k, inst in enumerate(self.qc.data):
            op = inst.operation.to_mutable()
            op.label = f"__k{k}"
            labelled.append(op, inst.qubits, inst.clbits)
        keep: Set[int] = set()
        for p in paulis:
            try:
                out = PassManager([LightCone(bit_terms=p, indices=[t])]).run(labelled)
            except Exception as exc:  # e.g. control flow the pass does not support
                raise NotApplicable(f"LightCone({p}): {type(exc).__name__}: {exc}") from exc
            for inst in out.data:
                lab = getattr(inst.operation, "label", None) or ""
                if not lab.startswith("__k"):
                    raise NotApplicable(f"LightCone({p}) returned an unlabelled instruction {inst.operation.name}")
                keep.add(int(lab[3:]))
        return keep

    def lcq(self, t: int) -> Set[int]:
        return self._lightcone(t, ("X", "Y", "Z"))

    def lcq_z(self, t: int) -> Set[int]:
        return self._lightcone(t, ("Z",))

    # -- four-edge slicer --------------------------------------------------------------------------
    def _four_qdg(self):
        if self._four is None:
            from src.qdg import qdg_from_circuit
            self._four = qdg_from_circuit(self.qc, "fourEdge")
        return self._four

    def four_unfixed(self, t: int) -> Set[int]:
        from src.qdg import slice_from_qdg
        from src.slicer import SlicerVariant, VARIANT_EDGE_TYPES
        return set(slice_from_qdg(self._four_qdg(), t, VARIANT_EDGE_TYPES[SlicerVariant.QSLICE_FULL]))

    def four_fixed(self, t: int) -> Set[int]:
        """Same graph and edge types; seeded at the criterion's last operation of any kind."""
        from src.slicer import SlicerVariant, VARIANT_EDGE_TYPES
        g = self._four_qdg()
        enabled = VARIANT_EDGE_TYPES[SlicerVariant.QSLICE_FULL]
        on_t = [gid for gid, node in g.nodes.items() if t in node.qubits]
        if not on_t:
            return set()
        seeds = {max(on_t)}
        preds: Dict[int, list] = {}
        for u, v, data in g.graph.edges(data=True):
            if data.get("types", set()) & enabled:
                preds.setdefault(v, []).append(u)
        seen, stack = set(), list(seeds)
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            stack.extend(preds.get(x, []))
        return seen

    # -- registry ---------------------------------------------------------------------------------
    def get(self, name: str) -> Callable[[int], Set[int]]:
        return {"du": self.du, "lc": self.lc, "lcq": self.lcq, "lcq_z": self.lcq_z, "yz": self.yz,
                "q": self.q, "4e_unfixed": self.four_unfixed, "4e_fixed": self.four_fixed}[name]


def qslice_set(qc: QuantumCircuit, W: Sequence[int], sep_eps: float = 1e-9,
               slicers: Optional[Slicers] = None) -> Set[int]:
    """S-qW: entanglement_pruned_slice generalised to a criterion set W (PROTOCOL_ICPC.md section 1).

    Same steps as qslice/qdg.py entanglement_pruned_slice, with
      - start: the union of the light-cone slices of the qubits of W;
      - candidates: operations in it that touch no qubit of W;
      - nomination: I(W; x) < sep_eps for every qubit x of the operation, in the state after it;
      - verification: trace distance of the joint reduced state rho_W, trial slice vs full, < sep_eps.
    For |W| = 1 this is the same computation as entanglement_pruned_slice (checked on corpus A).
    """
    from qiskit.quantum_info import Statevector, partial_trace
    s = slicers or Slicers(qc)
    W = list(W)
    n = qc.num_qubits
    classical: Set[int] = set()
    for w in W:
        classical |= s.lc(w)
    try:
        full_sv = Statevector(qc)
    except Exception:
        return classical
    trace_out = [x for x in range(n) if x not in W]
    ref = partial_trace(full_sv, trace_out).data

    def _vn(rho) -> float:
        ev = np.linalg.eigvalsh(rho).real
        ev = ev[ev > 1e-12]
        return float(-np.sum(ev * np.log2(ev))) if ev.size else 0.0

    def _mi(sv, x) -> float:
        rho_w = partial_trace(sv, [y for y in range(n) if y not in W]).data
        rho_x = partial_trace(sv, [y for y in range(n) if y != x]).data
        rho_wx = partial_trace(sv, [y for y in range(n) if y not in W and y != x]).data
        return _vn(rho_w) + _vn(rho_x) - _vn(rho_wx)

    nodes = s.full.nodes
    candidates = {p for p in classical if p in nodes and nodes[p].qubits and not (set(nodes[p].qubits) & set(W))}
    qidx = {q: i for i, q in enumerate(qc.qubits)}
    separable: Dict[int, bool] = {}
    sv = Statevector.from_int(0, 2 ** n)
    for k, ci in enumerate(qc.data):
        try:
            sv = sv.evolve(ci.operation, [qidx[q] for q in ci.qubits])
        except Exception:
            return classical
        if k in candidates:
            separable[k] = all(_mi(sv, x) < sep_eps for x in nodes[k].qubits)
    kept = set(classical)
    for pos in sorted(candidates, reverse=True):
        if separable.get(pos):
            trial = kept - {pos}
            try:
                r = partial_trace(Statevector(s.full.extract_slice_circuit(trial)), trace_out).data
            except Exception:
                continue
            if np.linalg.norm(r - ref, ord="nuc") / 2.0 < sep_eps:
                kept = trial
    return kept


__all__ = ["Slicers", "NotApplicable", "qslice_set", "yuzhao_slice"]
