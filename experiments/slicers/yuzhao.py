"""S-yz: a documented re-implementation of the slicing of Yu & Zhao's Quantum Program Dependence Graph
(QPDG), "The Quantum Program Dependence Graph and Its Uses in Quantum Software Development", Q-SE 2025,
pp. 48-55, DOI 10.1109/Q-SE66736.2025.00014. Referenced as [27] in the paper.

[27] defines its dependences informally, over the statements of a Qiskit program, and gives no
construction algorithm and no implementation ("Experimental studies are planned", p. 55). Every
choice needed to make it executable on a circuit is logged here. All choices were fixed BEFORE the
slicer was run on any circuit (PROTOCOL_ICPC.md section 1; Deviation I-1).

Design log
----------
D-yz-1  Unit. A node is one circuit instruction (a statement of the circuit-building program in [27]
        corresponds to one appended instruction for hand-written Qiskit code).
D-yz-2  Criterion. [27]'s static criterion (s, V): s = the last instruction acting on the criterion
        qubit q, V = {q}. Backward slicing is reverse reachability (p. 53) from every instruction on q,
        which equals reachability from the last one because the DATA edges chain them.
D-yz-3  Classical data dependence (p. 50): "u is directly data-dependent on v if the value of a variable
        computed at v directly influences the value computed at u". For qubit variables every gate
        computes a new value of every qubit it acts on, so u depends on the latest earlier instruction
        acting on each qubit of u (per-wire last-writer edges, the DATA edges of qslice/qdg.py).
D-yz-4  Classical control dependence (p. 50) only arises from classical conditions in a circuit; it is
        realised together with D-yz-7.
D-yz-5  Entanglement dependence (p. 50): "two qubits in statements u and v, respectively, are entangled
        within a quantum program". [27] gives no rule for when qubits are entangled. We use the static,
        flow-insensitive over-approximation of static entanglement analysis: qubits are entangled iff
        they are connected by multi-qubit gates anywhere in the circuit (union-find closure), and an edge
        v -> u is added for every earlier v and later u acting on qubits of the same component. This is
        the ENTANGLEMENT edge set of qslice/qdg.py. A flow-sensitive alternative (entangled only after
        the first coupling gate) is discussed as a threat to validity, not run.
D-yz-6  No-cloning dependence (pp. 50-51): its example (Listing 3) is a CNOT "copy", which is already a
        data dependence under D-yz-3. It defines no additional edge.
D-yz-7  Measurement dependence (p. 52): "the measurement of one qubit directly influences subsequent
        program behavior, particularly in control flow" (Listing 5, measure then c_if). Realised as an
        edge from the most recent earlier measurement of each classical bit a condition reads to the
        conditioned instruction (the CONTROL edges of method_eval/control_fix.py).
D-yz-8  Temporal dependence (p. 51) concerns coherence time and execution timing; its example uses a
        Python time.sleep that is not part of the circuit. It has no counterpart in the circuit's
        semantics and is omitted.
Consequence: S-yz = backward reachability over DATA + CONTROL + ENTANGLEMENT edges of the
control-fixed QDG, i.e. the full-graph backward slice of the corrected run's QDG.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Set

from qiskit import QuantumCircuit


def yuzhao_slice(qc: QuantumCircuit, target_qubit: int, method_code: str | Path) -> Set[int]:
    """Backward S-yz slice (instruction positions) of `qc` for criterion qubit `target_qubit`."""
    if str(method_code) not in sys.path:
        sys.path.insert(0, str(method_code))
    from method_eval.control_fix import QDGControlFixed
    g = QDGControlFixed(qc, "yz")
    g.build(include_entanglement=True, include_control=True)
    return set(g.backward_slice(target_qubit))
