"""
src/circuit_loader.py — Load and stratify benchmark circuits.

Loads .qasm files from:
  - data/repos/pnnl_qasmbench/  (QASMBench)
  - data/repos/openqasm3/       (OpenQASM 3 dynamic circuits)
  - data/mqtbench/              (MQT Bench, if downloaded)

Stratifies into:
  S1a: <= 10 qubits, no mid-circuit measurement
  S1b: 11-20 qubits, no mid-circuit measurement
  S1c: dynamic circuits with mid-circuit measurement
  S2:  15-50 qubits (for noise experiment)
  S3:  3-10 qubits, <= 50 gates (for hardware proof-of-concept)
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from qiskit import QuantumCircuit, qasm2


@dataclass
class CircuitInfo:
    name: str
    path: str
    n_qubits: int
    n_gates: int
    n_cx: int
    stratum: str  # S1a, S1b, S1c, S2, S3
    has_mid_meas: bool
    circuit: Optional[QuantumCircuit] = None
    source: str = "unknown"  # qasmbench, openqasm3, mqtbench, synthetic


def _count_cx(circuit: QuantumCircuit) -> int:
    return sum(
        1 for instr in circuit.data
        if instr.operation.name in ("cx", "cnot", "cz", "ecr")
    )


def _has_mid_circuit_measurement(circuit: QuantumCircuit) -> bool:
    """True if there is a measurement followed by a gate on any qubit."""
    meas_qubits = set()
    for instr in circuit.data:
        if instr.operation.name == "measure":
            for q in instr.qubits:
                meas_qubits.add(id(q))
        elif instr.operation.name not in ("barrier",):
            for q in instr.qubits:
                if id(q) in meas_qubits:
                    return True
    return False


def _assign_stratum(info: CircuitInfo) -> str:
    n = info.n_qubits
    g = info.n_gates
    if info.has_mid_meas:
        return "S1c"
    if n <= 10 and g <= 50:
        return "S3"
    if n <= 10:
        return "S1a"
    if n <= 20:
        return "S1b"
    if n <= 50:
        return "S2"
    return "S2"  # large circuits also go to S2


def load_qasm_file(path: Path) -> Optional[QuantumCircuit]:
    """Load a QASM file, trying QASM 2 first, then raw."""
    try:
        qc = qasm2.load(str(path), custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
        return qc
    except Exception:
        pass
    try:
        with open(path, "r", errors="ignore") as f:
            content = f.read()
        # Try to parse as qasm2 from string
        qc = qasm2.loads(content, custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
        return qc
    except Exception:
        pass
    return None


def load_corpus(
    qasmbench_dir: Optional[Path] = None,
    openqasm3_dir: Optional[Path] = None,
    mqtbench_dir: Optional[Path] = None,
    max_circuits: Optional[int] = None,
    max_qubits: int = 50,
    min_qubits: int = 2,
) -> List[CircuitInfo]:
    """
    Load all circuits from benchmark corpus directories.
    Returns list of CircuitInfo with parsed circuits.
    """
    circuits: List[CircuitInfo] = []
    sources = []
    if qasmbench_dir and qasmbench_dir.exists():
        sources.append((qasmbench_dir, "qasmbench"))
    if openqasm3_dir and openqasm3_dir.exists():
        sources.append((openqasm3_dir, "openqasm3"))
    if mqtbench_dir and mqtbench_dir.exists():
        sources.append((mqtbench_dir, "mqtbench"))

    seen_names = set()
    for base_dir, source_name in sources:
        qasm_files = sorted(base_dir.rglob("*.qasm"))
        print(f"  [loader] {source_name}: found {len(qasm_files)} .qasm files in {base_dir}")
        for qasm_path in qasm_files:
            if max_circuits and len(circuits) >= max_circuits:
                break
            name = qasm_path.stem
            if name in seen_names:
                continue
            seen_names.add(name)

            qc = load_qasm_file(qasm_path)
            if qc is None:
                continue
            if qc.num_qubits < min_qubits or qc.num_qubits > max_qubits:
                continue
            if qc.num_qubits == 0 or qc.size() == 0:
                continue

            has_mid = _has_mid_circuit_measurement(qc)
            n_cx = _count_cx(qc)

            info = CircuitInfo(
                name=name,
                path=str(qasm_path),
                n_qubits=qc.num_qubits,
                n_gates=qc.size(),
                n_cx=n_cx,
                stratum="",
                has_mid_meas=has_mid,
                circuit=qc,
                source=source_name,
            )
            info.stratum = _assign_stratum(info)
            circuits.append(info)

    print(f"  [loader] Total circuits loaded: {len(circuits)}")
    return circuits


def make_synthetic_corpus(n_circuits: int = 6, seed: int = 42) -> List[CircuitInfo]:
    """
    Generate a small synthetic benchmark corpus for smoke testing.
    Creates circuits of varying sizes to cover multiple strata.
    """
    import numpy as np
    rng = np.random.default_rng(seed)
    circuits = []

    configs = [
        ("ghz_4", 4, "ghz"),
        ("bell_2", 2, "bell"),
        ("qft_5", 5, "qft"),
        ("grover_4", 4, "grover"),
        ("teleport_3", 3, "teleport"),
        ("vqe_4", 4, "vqe"),
    ]

    for name, n_qubits, circuit_type in configs[:n_circuits]:
        qc = _make_synthetic_circuit(name, n_qubits, circuit_type, rng)
        has_mid = _has_mid_circuit_measurement(qc)
        n_cx = _count_cx(qc)
        info = CircuitInfo(
            name=name,
            path=f"synthetic/{name}",
            n_qubits=n_qubits,
            n_gates=qc.size(),
            n_cx=n_cx,
            stratum="",
            has_mid_meas=has_mid,
            circuit=qc,
            source="synthetic",
        )
        info.stratum = _assign_stratum(info)
        circuits.append(info)

    return circuits


def _make_synthetic_circuit(
    name: str,
    n_qubits: int,
    circuit_type: str,
    rng: "np.random.Generator",
) -> QuantumCircuit:
    """Create a synthetic circuit of specified type."""
    from qiskit.circuit.library import QFT
    import numpy as np

    qc = QuantumCircuit(n_qubits, n_qubits)

    if circuit_type == "ghz":
        qc.h(0)
        for i in range(n_qubits - 1):
            qc.cx(i, i + 1)
        qc.measure_all()

    elif circuit_type == "bell":
        qc.h(0)
        qc.cx(0, 1)
        qc.measure_all()

    elif circuit_type == "qft":
        for i in range(n_qubits):
            qc.h(i)
            for j in range(i + 1, n_qubits):
                qc.cp(np.pi / (2 ** (j - i)), i, j)
        qc.measure_all()

    elif circuit_type == "grover":
        # Simple 2-qubit Grover
        qc.h(range(n_qubits))
        qc.cz(0, 1) if n_qubits >= 2 else None
        qc.h(range(n_qubits))
        qc.x(range(n_qubits))
        if n_qubits >= 2:
            qc.cz(0, 1)
        qc.x(range(n_qubits))
        qc.h(range(n_qubits))
        qc.measure_all()

    elif circuit_type == "teleport":
        # 3-qubit teleportation circuit
        qc.h(1)
        qc.cx(1, 2)
        qc.cx(0, 1)
        qc.h(0)
        qc.measure([0, 1], [0, 1])
        # Classically conditioned corrections
        with qc.if_test((qc.clbits[1], 1)):
            qc.x(2)
        with qc.if_test((qc.clbits[0], 1)):
            qc.z(2)
        qc.measure(2, 2)

    elif circuit_type == "vqe":
        # Simple VQE-like circuit
        angles = rng.uniform(0, 2 * np.pi, n_qubits)
        for i in range(n_qubits):
            qc.ry(float(angles[i]), i)
        for i in range(n_qubits - 1):
            qc.cx(i, i + 1)
        angles2 = rng.uniform(0, 2 * np.pi, n_qubits)
        for i in range(n_qubits):
            qc.ry(float(angles2[i]), i)
        qc.measure_all()

    return qc


def write_corpus_manifest(
    circuits: List[CircuitInfo],
    output_path: Path,
):
    """Write data/corpus_manifest.json with per-circuit metadata."""
    manifest = []
    for info in circuits:
        manifest.append({
            "name": info.name,
            "path": info.path,
            "n_qubits": info.n_qubits,
            "n_gates": info.n_gates,
            "n_cx": info.n_cx,
            "stratum": info.stratum,
            "has_mid_meas": info.has_mid_meas,
            "source": info.source,
        })
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  [loader] Corpus manifest written: {output_path} ({len(manifest)} circuits)")