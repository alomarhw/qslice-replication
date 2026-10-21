"""
src/qdg.py — Typed Quantum Dependency Graph (QDG) construction.

Implements four edge types:
  UED: Unitary-Evolution Dependence (single-qubit gates)
  ED:  Entanglement Dependence (two-qubit gates, transitive closure)
  MD:  Measurement-Collapse Dependence (measurement operations)
  CD:  Classical-Feedback Dependence (classically-conditioned gates)

Uses qubit-object identity (not deprecated Qubit.index) for Qiskit >= 1.2.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

import networkx as nx
from qiskit import QuantumCircuit
from qiskit.circuit import Qubit, Clbit


class EdgeType(str, Enum):
    UED = "UED"  # Unitary-evolution dependence
    ED = "ED"    # Entanglement dependence
    MD = "MD"    # Measurement-collapse dependence
    CD = "CD"    # Classical-feedback dependence


@dataclass
class GateNode:
    gate_id: int
    name: str
    qubits: Tuple[int, ...]       # qubit indices (by position in circuit)
    clbits: Tuple[int, ...]       # classical bit indices
    is_measurement: bool = False
    is_conditioned: bool = False  # classically conditioned gate

    def label(self) -> str:
        q_str = ",".join(f"q{q}" for q in self.qubits)
        return f"{self.name}[{q_str}]"


@dataclass
class QDG:
    circuit_name: str
    graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    nodes: Dict[int, GateNode] = field(default_factory=dict)
    construction_time_ms: float = 0.0
    n_qubits: int = 0

    def add_node(self, node: GateNode):
        self.nodes[node.gate_id] = node
        self.graph.add_node(
            node.gate_id,
            label=node.label(),
            name=node.name,
            qubits=node.qubits,
            is_measurement=node.is_measurement,
            is_conditioned=node.is_conditioned,
        )

    def add_edge(self, src: int, dst: int, etype: EdgeType):
        if self.graph.has_edge(src, dst):
            existing = self.graph[src][dst].get("types", set())
            existing.add(etype)
            self.graph[src][dst]["types"] = existing
        else:
            self.graph.add_edge(src, dst, types={etype})

    def edges_of_type(self, etype: EdgeType) -> List[Tuple[int, int]]:
        return [
            (u, v)
            for u, v, data in self.graph.edges(data=True)
            if etype in data.get("types", set())
        ]

    def backward_slice(
        self,
        criterion_qubit: int,
        enabled_edge_types: Optional[Set[EdgeType]] = None,
    ) -> Set[int]:
        """
        Compute backward slice from all nodes touching criterion_qubit.
        Returns set of gate_ids in the slice.
        """
        if enabled_edge_types is None:
            enabled_edge_types = {EdgeType.UED, EdgeType.ED, EdgeType.MD, EdgeType.CD}

        # Find criterion nodes: measurements or last gate on criterion qubit
        criterion_nodes = set()
        for gate_id, node in self.nodes.items():
            if criterion_qubit in node.qubits and node.is_measurement:
                criterion_nodes.add(gate_id)
        if not criterion_nodes:
            # Use all nodes touching the criterion qubit
            for gate_id, node in self.nodes.items():
                if criterion_qubit in node.qubits:
                    criterion_nodes.add(gate_id)

        if not criterion_nodes:
            return set()

        # Build reverse graph filtered by enabled edge types
        rev = nx.DiGraph()
        rev.add_nodes_from(self.graph.nodes())
        for u, v, data in self.graph.edges(data=True):
            types = data.get("types", set())
            if types & enabled_edge_types:
                rev.add_edge(v, u)

        # BFS/DFS from criterion nodes on reversed graph
        visited: Set[int] = set()
        queue = list(criterion_nodes)
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            for pred in rev.successors(node):
                if pred not in visited:
                    queue.append(pred)

        return visited


def qdg_from_circuit(
    circuit: QuantumCircuit,
    circuit_name: str = "circuit",
) -> QDG:
    """
    Construct a typed QDG from a Qiskit QuantumCircuit.
    Uses qubit-object identity (not deprecated Qubit.index).
    """
    t0 = time.perf_counter()
    qdg = QDG(circuit_name=circuit_name, n_qubits=circuit.num_qubits)

    # Map qubit objects to indices
    qubit_index: Dict[Qubit, int] = {q: i for i, q in enumerate(circuit.qubits)}
    clbit_index: Dict[Clbit, int] = {c: i for i, c in enumerate(circuit.clbits)}

    # Track last gate on each qubit (for UED/ED edges)
    last_gate_on_qubit: Dict[int, int] = {}  # qubit_idx -> gate_id
    # Track entanglement groups: union-find on qubits
    # Simple approach: track entangled sets
    entangled_pairs: Set[FrozenSet[int]] = set()

    gate_id = 0
    for instruction in circuit.data:
        op = instruction.operation
        qubits_involved = tuple(qubit_index[q] for q in instruction.qubits)
        clbits_involved = tuple(clbit_index[c] for c in instruction.clbits)

        is_meas = op.name in ("measure", "reset")
        is_cond = hasattr(op, "condition") and op.condition is not None

        node = GateNode(
            gate_id=gate_id,
            name=op.name,
            qubits=qubits_involved,
            clbits=clbits_involved,
            is_measurement=is_meas,
            is_conditioned=is_cond,
        )
        qdg.add_node(node)

        # Add edges based on qubit interactions
        if len(qubits_involved) == 1:
            q = qubits_involved[0]
            if q in last_gate_on_qubit:
                if is_meas:
                    qdg.add_edge(last_gate_on_qubit[q], gate_id, EdgeType.MD)
                elif is_cond:
                    qdg.add_edge(last_gate_on_qubit[q], gate_id, EdgeType.CD)
                else:
                    qdg.add_edge(last_gate_on_qubit[q], gate_id, EdgeType.UED)
            last_gate_on_qubit[q] = gate_id

        elif len(qubits_involved) >= 2:
            # Two-qubit gate: add ED edges and UED for each qubit
            for q in qubits_involved:
                if q in last_gate_on_qubit:
                    qdg.add_edge(last_gate_on_qubit[q], gate_id, EdgeType.ED)
                last_gate_on_qubit[q] = gate_id

            # Mark entanglement between all qubit pairs in this gate
            for i in range(len(qubits_involved)):
                for j in range(i + 1, len(qubits_involved)):
                    entangled_pairs.add(frozenset([qubits_involved[i], qubits_involved[j]]))

        # Classical feedback: if conditioned, add CD edges from last measurement nodes
        if is_cond and clbits_involved:
            # Find last measurement affecting these clbits
            for prev_id, prev_node in qdg.nodes.items():
                if prev_id < gate_id and prev_node.is_measurement:
                    if set(prev_node.clbits) & set(clbits_involved):
                        qdg.add_edge(prev_id, gate_id, EdgeType.CD)

        gate_id += 1

    # Add transitive entanglement edges (ED transitive closure)
    # For each pair of gates sharing qubits that are entangled, add ED edges
    _add_transitive_entanglement_edges(qdg, entangled_pairs)

    t1 = time.perf_counter()
    qdg.construction_time_ms = (t1 - t0) * 1000.0
    return qdg


def _add_transitive_entanglement_edges(qdg: QDG, entangled_pairs: Set[FrozenSet[int]]):
    """
    For any two gate nodes where one qubit set overlaps with entangled qubits
    of the other, add ED edges to capture transitive entanglement.
    Only forward-in-time edges.
    """
    # Build qubit -> gates mapping
    qubit_to_gates: Dict[int, List[int]] = {}
    for gid, node in qdg.nodes.items():
        for q in node.qubits:
            qubit_to_gates.setdefault(q, []).append(gid)

    # For each entangled pair, if gates on q1 precede gates on q2 or vice versa,
    # add ED edges for cross-qubit ordering
    for pair in entangled_pairs:
        pair_list = list(pair)
        if len(pair_list) < 2:
            continue
        q1, q2 = pair_list[0], pair_list[1]
        gates_q1 = sorted(qubit_to_gates.get(q1, []))
        gates_q2 = sorted(qubit_to_gates.get(q2, []))
        # Add ED edges between consecutive gates on entangled qubits
        for g1 in gates_q1:
            for g2 in gates_q2:
                if g1 < g2 and not qdg.graph.has_edge(g1, g2):
                    # Only add if g1 and g2 are within a reasonable topological distance
                    # (avoid adding spurious long-range edges)
                    # Check if both are in entanglement relationship via shared gate
                    n1 = qdg.nodes[g1]
                    n2 = qdg.nodes[g2]
                    if (set(n1.qubits) & {q1, q2}) and (set(n2.qubits) & {q1, q2}):
                        qdg.add_edge(g1, g2, EdgeType.ED)


def slice_from_qdg(
    qdg: QDG,
    criterion_qubit: int,
    enabled_edge_types: Optional[Set[EdgeType]] = None,
) -> Set[int]:
    """Compute backward slice from QDG for a given criterion qubit."""
    return qdg.backward_slice(criterion_qubit, enabled_edge_types)