"""
src/slicer.py — Unified slicer implementing all 5 variants + 4 ablated QDG variants.

Variants:
  V1: QSlice-full       — all four QDG edge types (UED+ED+MD+CD)
  V2: Classical PDG     — def-use only (UED only, no quantum-specific edges)
  V3: Causal-cone       — bidirectional two-qubit wires (UED+ED, no separability pruning)
  V4: QIRO-based        — SSA def-use without entanglement edges (UED+CD only)
  V5: QDG-no-ED         — ablated: no entanglement edges
  V6: QDG-no-MD         — ablated: no measurement-collapse edges
  V7: QDG-no-CD         — ablated: no classical-feedback edges
  V8: QDG-no-UED        — ablated: no unitary-evolution edges

Exposes slice(circuit, criterion_qubit, variant) -> SliceResult
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from qiskit import QuantumCircuit, transpile
from qiskit.circuit import Qubit

from src.qdg import EdgeType, QDG, qdg_from_circuit, slice_from_qdg


class SlicerVariant(str, Enum):
    QSLICE_FULL = "QSlice-full"
    CLASSICAL_PDG = "Classical PDG"
    CAUSAL_CONE = "Causal-cone"
    QIRO_BASED = "QIRO-based"
    QDG_NO_ED = "QDG-no-ED"
    QDG_NO_MD = "QDG-no-MD"
    QDG_NO_CD = "QDG-no-CD"
    QDG_NO_UED = "QDG-no-UED"


VARIANT_EDGE_TYPES: Dict[SlicerVariant, Set[EdgeType]] = {
    SlicerVariant.QSLICE_FULL:   {EdgeType.UED, EdgeType.ED, EdgeType.MD, EdgeType.CD},
    SlicerVariant.CLASSICAL_PDG: {EdgeType.UED},
    SlicerVariant.CAUSAL_CONE:   {EdgeType.UED, EdgeType.ED},
    SlicerVariant.QIRO_BASED:    {EdgeType.UED, EdgeType.CD},
    SlicerVariant.QDG_NO_ED:     {EdgeType.UED, EdgeType.MD, EdgeType.CD},
    SlicerVariant.QDG_NO_MD:     {EdgeType.UED, EdgeType.ED, EdgeType.CD},
    SlicerVariant.QDG_NO_CD:     {EdgeType.UED, EdgeType.ED, EdgeType.MD},
    SlicerVariant.QDG_NO_UED:    {EdgeType.ED, EdgeType.MD, EdgeType.CD},
}

BASELINE_KEY_MAP = {
    SlicerVariant.CLASSICAL_PDG: (
        "Classical PDG slicer (def-use edges only, no quantum-specific edges) "
        "\u2014 adapted from Ferrante et al. 1984 / Ottenstein & Ottenstein 1984, "
        "implemented in Python/Qiskit; cited as the primary failing baseline across all foundation drafts"
    ),
    SlicerVariant.CAUSAL_CONE: (
        "Sound causal-cone baseline (bidirectional two-qubit gate wires, data+control edges, "
        "no separability pruning) \u2014 the conservative upper bound slicer that is always sound "
        "but maximally imprecise, used in QPDG and QSlice foundation drafts"
    ),
    SlicerVariant.QIRO_BASED: (
        "QIRO-based analysis (ittah2021qiro) \u2014 static single-assignment quantum IR analysis "
        "without entanglement-specific edges; used as a baseline in the Quantum-Aware framework draft"
    ),
    SlicerVariant.QDG_NO_ED: (
        "Ablated QDG variants (full-factorial): QDG-no-ED (no entanglement edges), "
        "QDG-no-MD (no measurement-collapse edges), QDG-no-CD (no classical-feedback edges), "
        "QDG-no-UED (no unitary-evolution edges) \u2014 internal ablation baselines isolating "
        "marginal contribution of each edge type"
    ),
}
# Map all ablated variants to same baseline key
for v in [SlicerVariant.QDG_NO_MD, SlicerVariant.QDG_NO_CD, SlicerVariant.QDG_NO_UED]:
    BASELINE_KEY_MAP[v] = BASELINE_KEY_MAP[SlicerVariant.QDG_NO_ED]

TRANSPILER_KEY = (
    "Qiskit transpiler optimization level 1 \u2014 structural, criterion-unaware circuit reduction; "
    "used as a non-slicing baseline in the Formal Quantum Program Slicing draft to distinguish "
    "criterion-aware from criterion-unaware reduction"
)


@dataclass
class SliceResult:
    variant: SlicerVariant
    circuit_name: str
    criterion_qubit: int
    gate_ids_in_slice: Set[int]
    total_gates: int
    slice_circuit: QuantumCircuit  # sub-circuit with only slice gates
    original_circuit: QuantumCircuit
    ssr: float          # slice size ratio = |slice| / |original|
    drr: float          # depth reduction ratio = slice_depth / original_depth
    cx_original: int    # CX gates in original
    cx_slice: int       # CX gates in slice
    cx_reduction: float # (cx_original - cx_slice) / cx_original
    qdg_construction_time_ms: float = 0.0


def slice_circuit(
    circuit: QuantumCircuit,
    criterion_qubit: int,
    variant: SlicerVariant,
    circuit_name: str = "circuit",
    prebuilt_qdg: Optional[QDG] = None,
) -> SliceResult:
    """
    Slice a circuit using the specified variant.
    Returns SliceResult with metrics.
    """
    # Build or reuse QDG
    if prebuilt_qdg is not None:
        qdg = prebuilt_qdg
    else:
        qdg = qdg_from_circuit(circuit, circuit_name)

    edge_types = VARIANT_EDGE_TYPES[variant]
    gate_ids = slice_from_qdg(qdg, criterion_qubit, edge_types)

    # Build slice circuit
    slice_circ = _build_slice_circuit(circuit, gate_ids, criterion_qubit)

    total_gates = circuit.size()
    slice_gates = slice_circ.size()
    ssr = slice_gates / total_gates if total_gates > 0 else 1.0
    ssr = min(1.0, max(0.0, ssr))

    orig_depth = circuit.depth()
    slice_depth = slice_circ.depth()
    drr = slice_depth / orig_depth if orig_depth > 0 else 1.0
    drr = min(1.0, max(0.0, drr))

    cx_original = _count_cx(circuit)
    cx_slice = _count_cx(slice_circ)
    if cx_original > 0:
        cx_reduction = (cx_original - cx_slice) / cx_original
    else:
        cx_reduction = 0.0

    return SliceResult(
        variant=variant,
        circuit_name=circuit_name,
        criterion_qubit=criterion_qubit,
        gate_ids_in_slice=gate_ids,
        total_gates=total_gates,
        slice_circuit=slice_circ,
        original_circuit=circuit,
        ssr=ssr,
        drr=drr,
        cx_original=cx_original,
        cx_slice=cx_slice,
        cx_reduction=cx_reduction,
        qdg_construction_time_ms=qdg.construction_time_ms,
    )


def _build_slice_circuit(
    circuit: QuantumCircuit,
    gate_ids: Set[int],
    criterion_qubit: int,
) -> QuantumCircuit:
    """Build a new QuantumCircuit containing only the gated in gate_ids."""
    # Create circuit with same registers
    slice_circ = QuantumCircuit(*circuit.qregs, *circuit.cregs)
    for i, instruction in enumerate(circuit.data):
        if i in gate_ids:
            slice_circ.append(instruction)
    return slice_circ


def _count_cx(circuit: QuantumCircuit) -> int:
    count = 0
    for instr in circuit.data:
        if instr.operation.name in ("cx", "cnot", "cz", "ecr", "rzz"):
            count += 1
    return count


def transpiler_baseline_circuit(circuit: QuantumCircuit) -> QuantumCircuit:
    """Qiskit transpiler optimization level 1 as non-slicing baseline."""
    from qiskit_aer import AerSimulator
    backend = AerSimulator()
    try:
        return transpile(circuit, backend=backend, optimization_level=1)
    except Exception:
        return circuit.copy()


def compute_all_variants(
    circuit: QuantumCircuit,
    criterion_qubit: int,
    circuit_name: str = "circuit",
) -> Dict[SlicerVariant, SliceResult]:
    """Run all slicer variants on a single circuit-criterion pair."""
    # Build QDG once, reuse
    qdg = qdg_from_circuit(circuit, circuit_name)
    results = {}
    for variant in SlicerVariant:
        try:
            result = slice_circuit(
                circuit, criterion_qubit, variant, circuit_name, prebuilt_qdg=qdg
            )
            results[variant] = result
        except Exception as e:
            print(f"  WARNING: slice failed for {variant} on {circuit_name}: {e}")
    return results