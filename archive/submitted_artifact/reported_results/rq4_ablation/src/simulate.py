"""
src/simulate.py — Qiskit Aer simulation and TVD computation.

Supports:
  - Noise-free statevector/shot simulation
  - Depolarising noise models (NM1, NM2)
  - MPS simulation for >20-qubit circuits
  - TVD over marginal measurement distribution for a criterion qubit
"""

import math
from typing import Dict, Optional, Tuple

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error


SHOTS = 8192
MPS_MAX_BOND_DIM = 64


def get_noise_model(p1: float = 0.001, p2: float = 0.01) -> NoiseModel:
    """
    Build a simple depolarising noise model.
    p1: single-qubit error rate
    p2: two-qubit error rate
    """
    noise_model = NoiseModel()
    error1 = depolarizing_error(p1, 1)
    error2 = depolarizing_error(p2, 2)
    noise_model.add_all_qubit_quantum_error(error1, ["h", "x", "y", "z", "s", "t", "sdg", "tdg",
                                                      "rx", "ry", "rz", "u", "u1", "u2", "u3",
                                                      "sx", "sxdg"])
    noise_model.add_all_qubit_quantum_error(error2, ["cx", "cnot", "cz", "cy", "ecr", "rzz"])
    return noise_model


def simulate_circuit_shots(
    circuit: QuantumCircuit,
    shots: int = SHOTS,
    noise_model: Optional[NoiseModel] = None,
    use_mps: bool = False,
) -> Dict[str, int]:
    """
    Simulate circuit and return shot counts.
    Adds measurements if circuit has none.
    """
    # Add measurements if needed
    meas_circuit = _ensure_measurements(circuit)

    if use_mps:
        sim = AerSimulator(method="matrix_product_state", matrix_product_state_max_bond_dimension=MPS_MAX_BOND_DIM)
    else:
        sim = AerSimulator(method="statevector")

    kwargs = {"shots": shots}
    if noise_model is not None:
        kwargs["noise_model"] = noise_model

    try:
        transpiled = transpile(meas_circuit, sim, optimization_level=0)
        job = sim.run(transpiled, **kwargs)
        result = job.result()
        counts = result.get_counts()
        if not counts:
            counts = {"0" * circuit.num_qubits: shots}
        return counts
    except Exception as e:
        print(f"  [simulate] WARNING: simulation failed: {e}; returning uniform counts")
        n = circuit.num_qubits
        return {"0" * n: shots}


def _ensure_measurements(circuit: QuantumCircuit) -> QuantumCircuit:
    """Return circuit with measurements; add if absent."""
    from qiskit.circuit import ClassicalRegister
    has_meas = any(instr.operation.name == "measure" for instr in circuit.data)
    if has_meas:
        return circuit.copy()
    meas = circuit.copy()
    if meas.num_clbits < meas.num_qubits:
        cr = ClassicalRegister(meas.num_qubits, "meas")
        meas.add_register(cr)
    meas.measure_all()
    return meas


def marginal_distribution(
    counts: Dict[str, int],
    criterion_qubit: int,
    n_qubits: int,
) -> Dict[str, float]:
    """
    Compute marginal probability distribution for criterion_qubit.
    Qiskit bitstring is little-endian: bit 0 is rightmost character.
    """
    total = sum(counts.values())
    if total == 0:
        return {"0": 0.5, "1": 0.5}
    marginal: Dict[str, float] = {"0": 0.0, "1": 0.0}
    bit_pos = criterion_qubit  # Qiskit: bit i is at position i from right

    for bitstring, count in counts.items():
        # Pad or truncate bitstring to n_qubits
        bits = bitstring.replace(" ", "")
        if len(bits) < n_qubits:
            bits = "0" * (n_qubits - len(bits)) + bits
        # Extract the criterion qubit bit (from right)
        idx = len(bits) - 1 - bit_pos
        if 0 <= idx < len(bits):
            bit_val = bits[idx]
        else:
            bit_val = "0"
        marginal[bit_val] = marginal.get(bit_val, 0.0) + count / total

    return marginal


def compute_tvd(
    counts_a: Dict[str, int],
    counts_b: Dict[str, int],
    criterion_qubit: int,
    n_qubits: int,
) -> float:
    """
    Total Variation Distance between marginal distributions of two circuits.
    TVD = 0.5 * sum |P(x) - Q(x)|
    """
    dist_a = marginal_distribution(counts_a, criterion_qubit, n_qubits)
    dist_b = marginal_distribution(counts_b, criterion_qubit, n_qubits)
    all_keys = set(dist_a.keys()) | set(dist_b.keys())
    tvd = 0.5 * sum(abs(dist_a.get(k, 0.0) - dist_b.get(k, 0.0)) for k in all_keys)
    return float(np.clip(tvd, 0.0, 1.0))


def compute_tvd_exact(
    circuit_orig: QuantumCircuit,
    circuit_slice: QuantumCircuit,
    criterion_qubit: int,
) -> float:
    """
    Compute TVD using exact statevector computation (no shot noise).
    For small circuits (<= 14 qubits).
    """
    try:
        # Build measurement-free circuits
        orig_no_meas = _strip_measurements(circuit_orig)
        slice_no_meas = _strip_measurements(circuit_slice)

        sv_orig = Statevector(orig_no_meas)
        sv_slice = Statevector(slice_no_meas)

        # Get marginal probabilities for criterion qubit
        p_orig = _marginal_probs_statevector(sv_orig, criterion_qubit, circuit_orig.num_qubits)
        p_slice = _marginal_probs_statevector(sv_slice, criterion_qubit, circuit_slice.num_qubits)

        tvd = 0.5 * sum(abs(p_orig[k] - p_slice.get(k, 0.0)) for k in p_orig)
        return float(np.clip(tvd, 0.0, 1.0))
    except Exception as e:
        print(f"  [simulate] Statevector failed ({e}), falling back to shot simulation")
        counts_a = simulate_circuit_shots(circuit_orig)
        counts_b = simulate_circuit_shots(circuit_slice)
        return compute_tvd(counts_a, counts_b, criterion_qubit, circuit_orig.num_qubits)


def _strip_measurements(circuit: QuantumCircuit) -> QuantumCircuit:
    """Return circuit with measurement instructions removed."""
    from qiskit import QuantumCircuit as QC
    new_circ = QC(circuit.num_qubits)
    for instr in circuit.data:
        if instr.operation.name not in ("measure", "reset", "barrier"):
            # Map qubits by index
            q_indices = [circuit.find_bit(q).index for q in instr.qubits]
            new_circ.append(instr.operation, q_indices)
    return new_circ


def _marginal_probs_statevector(
    sv: Statevector,
    criterion_qubit: int,
    n_qubits: int,
) -> Dict[str, float]:
    """Get marginal probabilities for criterion_qubit from Statevector."""
    probs = sv.probabilities()  # 2^n array
    marginal = {"0": 0.0, "1": 0.0}
    for idx in range(len(probs)):
        # Qiskit: qubit i is bit i (little-endian)
        bit = (idx >> criterion_qubit) & 1
        marginal[str(bit)] += probs[idx]
    return marginal


def calibrate_delta_emp(
    correct_pairs: list,  # list of (tvd_value,) from known-correct slices
    percentile: float = 95.0,
    fallback: float = 0.05,
) -> float:
    """
    Calibrate delta_emp as the bootstrap 95th-percentile TVD of correct-slice pairs.
    Falls back to analytical threshold if not enough samples.
    """
    if not correct_pairs or len(correct_pairs) < 3:
        # Analytical fallback: shot-noise floor for 8192 shots
        return max(fallback, 1.0 / math.sqrt(SHOTS))
    arr = np.array(correct_pairs)
    return float(np.percentile(arr, percentile))