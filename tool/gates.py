"""Which arguments of a QuantumCircuit method are qubits, classical bits and angles.

Derived from the signatures of Qiskit's QuantumCircuit methods, plus the methods older Qiskit versions had
(Bugs4Q programs use them). A method's qubit arguments are listed in order; the leading ones named
"control..." are controls. The slicer does not need to know which qubit is a control (the wire rule
reads and writes every qubit of a gate); controls are kept for reporting and for the classical-PDG rule.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Dict, Tuple

ANGLE_NAMES = {"theta", "phi", "lam", "gamma", "params", "duration"}
QUBIT_NAMES = {"qubit", "qubits", "qarg", "qargs", "control_qubits", "target_qubit", "control_qubit", "target_qubit1",
               "target_qubit2", "control_qubit1", "control_qubit2", "qubit1", "qubit2", "ancilla_qubits", "target_qubits"}
CLBIT_NAMES = {"cbit", "clbit", "clbits", "cargs"}
NOT_GATES = {"append", "compose", "if_test", "while_loop", "for_loop", "switch", "measure_all", "measure_active",
             "remove_final_measurements", "add_register", "draw", "copy", "decompose", "assign_parameters", "to_gate",
             "to_instruction", "inverse", "power", "control", "size", "depth", "width", "count_ops", "qasm",
             "initialize", "unitary", "store", "box", "add_var", "add_input", "add_uninitialized_var",
             "add_capture", "add_stretch", "break_loop", "continue_loop", "has_register", "find_bit", "repeat",
             "reverse_bits", "reverse_ops", "tensor", "clear", "reset", "barrier", "measure", "delay", "pauli",
             "prepare_state",
             # methods that take qubits but add no operation: a constructor, the non-context form of if_else
             # (control flow is read from with blocks), and timing queries
             "from_instructions", "if_else", "qubit_duration", "qubit_start_time", "qubit_stop_time"}


@dataclass(frozen=True)
class Sig:
    args: Tuple[Tuple[str, str], ...]  # (parameter name, kind: "q", "c", "angle", "other") in call order

    def kinds(self):
        return [k for _, k in self.args]


def _kind(p: str) -> str:
    if p in QUBIT_NAMES:
        return "q"
    if p in CLBIT_NAMES:
        return "c"
    if p in ANGLE_NAMES:
        return "angle"
    return "other"


def _from_qiskit() -> Dict[str, Sig]:
    from qiskit import QuantumCircuit
    out = {}
    for name, fn in inspect.getmembers(QuantumCircuit, inspect.isfunction):
        if name.startswith("_") or name in NOT_GATES:
            continue
        ps = list(inspect.signature(fn).parameters)[1:]
        kinds = [(p, _kind(p)) for p in ps]
        if any(k == "q" for _, k in kinds):
            out[name] = Sig(tuple(kinds))
    return out


def _legacy() -> Dict[str, Sig]:
    """Methods removed from QuantumCircuit in Qiskit 1.0 that Bugs4Q programs still call."""
    q, a = "q", "angle"
    spec = {
        "u1": [("theta", a), ("qubit", q)], "u2": [("phi", a), ("lam", a), ("qubit", q)],
        "u3": [("theta", a), ("phi", a), ("lam", a), ("qubit", q)], "iden": [("qubit", q)], "i": [("qubit", q)],
        "cnot": [("control_qubit", q), ("target_qubit", q)], "toffoli": [("control_qubit1", q), ("control_qubit2", q), ("target_qubit", q)],
        "fredkin": [("control_qubit", q), ("target_qubit1", q), ("target_qubit2", q)],
        "cu1": [("theta", a), ("control_qubit", q), ("target_qubit", q)],
        "cu3": [("theta", a), ("phi", a), ("lam", a), ("control_qubit", q), ("target_qubit", q)],
        "mct": [("control_qubits", q), ("target_qubit", q), ("ancilla_qubits", q)],
        "mcrx": [("theta", a), ("control_qubits", q), ("target_qubit", q)],
        "mcry": [("theta", a), ("control_qubits", q), ("target_qubit", q)],
        "mcrz": [("lam", a), ("control_qubits", q), ("target_qubit", q)],
        "mcu1": [("lam", a), ("control_qubits", q), ("target_qubit", q)],
    }
    return {k: Sig(tuple(v)) for k, v in spec.items()}


def _special() -> Dict[str, Sig]:
    q, c = "q", "c"
    return {"measure": Sig((("qubit", q), ("cbit", c))), "reset": Sig((("qubit", q),)),
            "barrier": Sig((("qargs", q),)), "delay": Sig((("duration", "angle"), ("qarg", q))),
            "initialize": Sig((("params", "other"), ("qubits", q))), "unitary": Sig((("obj", "other"), ("qubits", q)))}


GATES: Dict[str, Sig] = {**_legacy(), **_from_qiskit(), **_special()}
NOT_SLICED = {"barrier", "delay", "noop"}  # directives and no-ops: never part of a slice
