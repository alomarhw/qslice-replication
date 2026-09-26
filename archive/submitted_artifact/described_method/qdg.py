"""
qdg.py
Quantum Dependency Graph (QDG) implementation.

Constructs a typed directed graph over quantum circuit operations with three
edge types:
  - DATA: reversible state-carry along qubit lifelines
  - CONTROL: classical-quantum control dependence (c_if / if_test blocks)
  - ENTANGLEMENT: transitive closure of two-qubit-gate coupling

Backward slicing traverses the graph from a target qubit to extract a
semantically equivalent sub-circuit. Uses qubit-object identity (NOT the
deprecated Qubit.index attribute).

API compatible with Qiskit 2.3.0 / qiskit-aer 0.17.2.
"""

# Requirements:
#   qiskit==2.3.0
#   networkx==3.4.2
#   numpy==1.26.4

import os
import math
import copy
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Instruction

RANDOM_SEED = int(os.environ.get("RP_RANDOM_SEED", 42))


class EdgeType(str, Enum):
    DATA = "data"
    CONTROL = "control"
    ENTANGLEMENT = "entanglement"


@dataclass
class QDGNode:
    """A node in the QDG representing one gate/instruction in the circuit."""
    node_id: int
    gate_name: str
    position: int          # Position (index) in circuit.data
    qubits: List[int]      # Qubit indices (from qubit-object identity)
    cbits: List[int]       # Classical bit indices
    is_measurement: bool = False
    is_classical_control: bool = False
    # Source/target qubit names for display
    qubit_labels: List[str] = field(default_factory=list)


class QDG:
    """
    Quantum Dependency Graph with typed edges.

    Nodes: one per gate/instruction in the circuit.
    Edges: directed, typed (DATA, CONTROL, ENTANGLEMENT).
           Edge direction: from dependency TO dependent operation
           (i.e., if A must execute before B for B to be correct, edge A→B).

    Backward slicing from a target qubit q: find all nodes with a
    directed path TO a node that operates on q.
    """

    def __init__(self, qc: QuantumCircuit, circuit_id: str = ""):
        self.qc = qc
        self.circuit_id = circuit_id
        self.graph = nx.DiGraph()
        self.nodes: Dict[int, QDGNode] = {}
        self.qubit_to_idx: Dict = {}
        self.cbit_to_idx: Dict = {}
        self._built = False

    def build(self, include_entanglement: bool = True,
              include_control: bool = True) -> None:
        """Construct the QDG from the quantum circuit."""
        qc = self.qc

        # Map qubit/cbit objects to indices (identity-based, no Qubit.index)
        self.qubit_to_idx = {q: i for i, q in enumerate(qc.qubits)}
        self.cbit_to_idx = {b: i for i, b in enumerate(qc.clbits)}

        # ── 1. Create nodes ───────────────────────────────────────────────
        for pos, instruction in enumerate(qc.data):
            op = instruction.operation
            q_indices = [self.qubit_to_idx[q] for q in instruction.qubits
                         if q in self.qubit_to_idx]
            c_indices = [self.cbit_to_idx[b] for b in instruction.clbits
                         if b in self.cbit_to_idx]
            node = QDGNode(
                node_id=pos,
                gate_name=op.name,
                position=pos,
                qubits=q_indices,
                cbits=c_indices,
                is_measurement=(op.name == "measure"),
                is_classical_control=self._is_classical_control_op(op),
                qubit_labels=[f"q{i}" for i in q_indices],
            )
            self.nodes[pos] = node
            self.graph.add_node(pos, **{
                "gate": op.name,
                "qubits": q_indices,
                "position": pos,
            })

        # ── 2. DATA edges — qubit lifeline dependencies ───────────────────
        # Last node to write each qubit
        last_writer: Dict[int, int] = {}
        for pos, instruction in enumerate(qc.data):
            q_indices = [self.qubit_to_idx[q] for q in instruction.qubits
                         if q in self.qubit_to_idx]
            for qi in q_indices:
                if qi in last_writer:
                    prev = last_writer[qi]
                    if not self.graph.has_edge(prev, pos):
                        self.graph.add_edge(prev, pos,
                                            edge_type=EdgeType.DATA,
                                            qubit=qi)
                last_writer[qi] = pos

        # ── 3. CONTROL edges — classical conditioning ─────────────────────
        if include_control:
            self._add_control_edges()

        # ── 4. ENTANGLEMENT edges — transitive two-qubit coupling ─────────
        if include_entanglement:
            self._add_entanglement_edges()

        self._built = True

    def _is_classical_control_op(self, op) -> bool:
        """Check if operation has classical conditioning."""
        if hasattr(op, "condition") and op.condition is not None:
            return True
        if op.name in ("if_else", "switch_case", "for_loop", "while_loop"):
            return True
        try:
            from qiskit.circuit.controlflow import IfElseOp
            if isinstance(op, IfElseOp):
                return True
        except ImportError:
            pass
        return False

    def _add_control_edges(self) -> None:
        """
        Add control-dependence edges: from measurement nodes to classically-
        conditioned nodes that depend on the measurement outcome.
        """
        qc = self.qc
        # Find measurement nodes and their classical bit outputs
        meas_by_cbit: Dict[int, int] = {}
        for pos, instruction in enumerate(qc.data):
            op = instruction.operation
            if op.name == "measure":
                for cb in instruction.clbits:
                    ci = self.cbit_to_idx.get(cb, -1)
                    if ci >= 0:
                        meas_by_cbit[ci] = pos

        # Find classically-conditioned operations
        for pos, instruction in enumerate(qc.data):
            op = instruction.operation
            # c_if style
            if hasattr(op, "condition") and op.condition is not None:
                cond = op.condition
                # cond is (ClassicalRegister or Clbit, int_value)
                if hasattr(cond[0], "bits"):
                    # ClassicalRegister
                    for cb in cond[0].bits:
                        ci = self.cbit_to_idx.get(cb, -1)
                        if ci in meas_by_cbit:
                            src = meas_by_cbit[ci]
                            if not self.graph.has_edge(src, pos):
                                self.graph.add_edge(src, pos,
                                                    edge_type=EdgeType.CONTROL,
                                                    cbit=ci)
                else:
                    # Single Clbit
                    ci = self.cbit_to_idx.get(cond[0], -1)
                    if ci in meas_by_cbit:
                        src = meas_by_cbit[ci]
                        if not self.graph.has_edge(src, pos):
                            self.graph.add_edge(src, pos,
                                                edge_type=EdgeType.CONTROL,
                                                cbit=ci)

            # IfElseOp style (if_test blocks)
            try:
                from qiskit.circuit.controlflow import IfElseOp
                if isinstance(op, IfElseOp):
                    cond = op.condition
                    if cond is not None:
                        if hasattr(cond[0], "bits"):
                            for cb in cond[0].bits:
                                ci = self.cbit_to_idx.get(cb, -1)
                                if ci in meas_by_cbit:
                                    src = meas_by_cbit[ci]
                                    if not self.graph.has_edge(src, pos):
                                        self.graph.add_edge(src, pos,
                                                            edge_type=EdgeType.CONTROL,
                                                            cbit=ci)
                        else:
                            ci = self.cbit_to_idx.get(cond[0], -1)
                            if ci in meas_by_cbit:
                                src = meas_by_cbit[ci]
                                if not self.graph.has_edge(src, pos):
                                    self.graph.add_edge(src, pos,
                                                        edge_type=EdgeType.CONTROL,
                                                        cbit=ci)
            except (ImportError, Exception):
                pass

    def _add_entanglement_edges(self) -> None:
        """
        Add entanglement-dependence edges as transitive closure of two-qubit-gate coupling.
        For each two-qubit gate, adds an edge between ALL operations on the coupled qubits.
        """
        qc = self.qc
        n_qubits = qc.num_qubits

        # Find all pairs coupled by two-qubit gates (direct coupling)
        direct_coupling: Set[Tuple[int, int]] = set()
        for pos, instruction in enumerate(qc.data):
            q_indices = [self.qubit_to_idx[q] for q in instruction.qubits
                         if q in self.qubit_to_idx]
            if len(q_indices) == 2:
                i, j = q_indices[0], q_indices[1]
                direct_coupling.add((min(i, j), max(i, j)))

        # Transitive closure via union-find
        parent = list(range(n_qubits))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            parent[find(x)] = find(y)

        for (i, j) in direct_coupling:
            union(i, j)

        # Group qubits by component
        component: Dict[int, Set[int]] = {}
        for q in range(n_qubits):
            r = find(q)
            component.setdefault(r, set()).add(q)

        # For each pair of qubits in the same entanglement component,
        # add edges between their operations in circuit order
        for root, qubits_in_comp in component.items():
            if len(qubits_in_comp) < 2:
                continue
            qlist = sorted(qubits_in_comp)
            # For each pair, add entanglement edges across all ops
            for a in range(len(qlist)):
                for b in range(a + 1, len(qlist)):
                    qi, qj = qlist[a], qlist[b]
                    # Nodes on qi
                    nodes_qi = [pos for pos, node in self.nodes.items()
                                if qi in node.qubits]
                    # Nodes on qj
                    nodes_qj = [pos for pos, node in self.nodes.items()
                                if qj in node.qubits]
                    # Add directed edges: earlier node → later node
                    for ni in nodes_qi:
                        for nj in nodes_qj:
                            if ni < nj and not self.graph.has_edge(ni, nj):
                                self.graph.add_edge(ni, nj,
                                                    edge_type=EdgeType.ENTANGLEMENT,
                                                    qubit_pair=(qi, qj))
                            elif nj < ni and not self.graph.has_edge(nj, ni):
                                self.graph.add_edge(nj, ni,
                                                    edge_type=EdgeType.ENTANGLEMENT,
                                                    qubit_pair=(qi, qj))

    def remove_edge_type(self, edge_type: EdgeType) -> "QDG":
        """Return a copy of this QDG with all edges of the given type removed."""
        new_qdg = copy.deepcopy(self)
        edges_to_remove = [
            (u, v) for u, v, data in new_qdg.graph.edges(data=True)
            if data.get("edge_type") == edge_type
        ]
        new_qdg.graph.remove_edges_from(edges_to_remove)
        return new_qdg

    def remove_edge_types(self, *edge_types: EdgeType) -> "QDG":
        """Return a copy with multiple edge types removed."""
        new_qdg = copy.deepcopy(self)
        edges_to_remove = [
            (u, v) for u, v, data in new_qdg.graph.edges(data=True)
            if data.get("edge_type") in edge_types
        ]
        new_qdg.graph.remove_edges_from(edges_to_remove)
        return new_qdg

    def backward_slice(self, target_qubit: int) -> Set[int]:
        """
        Compute backward slice from target_qubit.
        Returns set of node IDs (positions) in the slice.
        Traverses the graph backward from all nodes operating on target_qubit.
        """
        # Find all nodes that operate on the target qubit
        seed_nodes = {pos for pos, node in self.nodes.items()
                      if target_qubit in node.qubits}

        if not seed_nodes:
            return set()

        # Backward reachability: reversed graph BFS/DFS from seeds
        rev_graph = self.graph.reverse(copy=False)
        slice_nodes = set()
        visited = set()
        queue = list(seed_nodes)
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            slice_nodes.add(node)
            for pred in rev_graph.neighbors(node):
                if pred not in visited:
                    queue.append(pred)
        return slice_nodes

    def forward_slice(self, target_qubit: int) -> Set[int]:
        """Forward slice from target_qubit: every operation causally INFLUENCED by it.

        Dual of :meth:`backward_slice` — forward reachability over this graph's edges. For the full
        QPDG (data+control+entanglement) this captures entanglement-mediated influence (an op on a
        qubit entangled with the target is downstream of it); the causal-classical variant
        (``remove_edge_type(ENTANGLEMENT).forward_slice``) propagates only through shared wires.
        """
        seed_nodes = {pos for pos, node in self.nodes.items()
                      if target_qubit in node.qubits}
        if not seed_nodes:
            return set()
        slice_nodes: Set[int] = set()
        visited: Set[int] = set()
        queue = list(seed_nodes)
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            slice_nodes.add(node)
            for succ in self.graph.neighbors(node):  # forward: successors
                if succ not in visited:
                    queue.append(succ)
        return slice_nodes

    def naive_classical_forward_slice(self, target_qubit: int) -> Set[int]:
        """Forward slice the way a CLASSICAL program slicer would — the unsound port (forward dual).

        Classical def-use forward slicing keeps an op iff it READS a currently-affected qubit, then
        marks the qubits it WRITES as affected. The unsoundness mirrors the backward case: a
        controlled gate WRITES only its target, so it never marks the CONTROL as affected. Slicing
        forward from a qubit that becomes a control therefore MISSES its entangled partner — an op on
        the partner is influenced by the criterion through entanglement, but no classical read/write
        relation expresses that. A quantum-aware QPDG keeps it via entanglement edges.
        """
        qc = self.qc
        ops = list(qc.data)
        qidx = {q: i for i, q in enumerate(qc.qubits)}
        affected = {target_qubit}
        include: Set[int] = set()
        for i, ci in enumerate(ops):
            qubits = [qidx[q] for q in ci.qubits if q in qidx]
            g = ci.operation
            nc = int(getattr(g, "num_ctrl_qubits", 0) or 0)
            if nc and len(qubits) > nc:
                controls, targets = qubits[:nc], qubits[nc:]
                reads = set(controls) | set(targets)
                writes = set(targets)            # control is read-only in classical def-use
            else:
                reads = writes = set(qubits)
            if reads & affected:
                include.add(i)
                affected |= writes
        return include

    def naive_classical_backward_slice(self, target_qubit: int) -> Set[int]:
        """Backward slice the way a CLASSICAL program slicer would — the faithful port that ignores
        quantum semantics. This is the baseline the paper argues is unsound.

        Classical def-use semantics: a statement WRITES its left-hand side and READS its right-hand
        side. Mapping that onto a quantum gate, a *controlled* gate reads its control qubit(s) and
        writes its target qubit(s); a plain gate reads+writes the qubits it touches. A standard
        backward dynamic slice then keeps an op iff it writes a qubit currently needed, pulling in the
        ops that wrote the qubits it reads.

        The unsoundness: a controlled gate does NOT "write" its control, so slicing FROM a control
        qubit drops the entangling gate — even though that gate changes the control's reduced state
        (entanglement). No classical read/write relation expresses that, so the slice is semantically
        wrong. A quantum-aware QPDG (with entanglement edges) keeps it.
        """
        qc = self.qc
        ops = list(qc.data)
        qidx = {q: i for i, q in enumerate(qc.qubits)}
        writes: List[Set[int]] = []
        reads: List[Set[int]] = []
        for ci in ops:
            qubits = [qidx[q] for q in ci.qubits if q in qidx]
            g = ci.operation
            nc = int(getattr(g, "num_ctrl_qubits", 0) or 0)
            if nc and len(qubits) > nc:
                controls, targets = qubits[:nc], qubits[nc:]
                writes.append(set(targets))            # control is read-only in classical def-use
                reads.append(set(controls) | set(targets))
            else:
                writes.append(set(qubits))
                reads.append(set(qubits))

        needed = {target_qubit}
        include: Set[int] = set()
        for i in range(len(ops) - 1, -1, -1):
            if writes[i] & needed:
                include.add(i)
                needed |= reads[i]
        return include

    def extract_slice_circuit(self, slice_nodes: Set[int]) -> QuantumCircuit:
        """
        Extract a sub-circuit containing only the instructions in slice_nodes.
        Preserves original qubit ordering.
        """
        qc = self.qc
        # Build sub-circuit with same registers
        slice_qc = QuantumCircuit(qc.num_qubits,
                                   qc.num_clbits if qc.num_clbits > 0 else 0,
                                   name=f"{qc.name}_slice")
        # Copy global phase
        slice_qc.global_phase = qc.global_phase
        # Re-append instructions with properly REMAPPED qubits/clbits. Appending raw CircuitInstruction
        # objects (whose Qubit/Clbit belong to the original circuit) yields a circuit that statevector
        # evolution rejects; mapping by index produces a clean, simulable slice.
        q_index = {q: i for i, q in enumerate(qc.qubits)}
        c_index = {c: i for i, c in enumerate(qc.clbits)}
        for pos in sorted(slice_nodes):
            if pos >= len(qc.data):
                continue
            ci = qc.data[pos]
            qargs = [slice_qc.qubits[q_index[q]] for q in ci.qubits if q in q_index]
            cargs = ([slice_qc.clbits[c_index[c]] for c in ci.clbits if c in c_index]
                     if slice_qc.num_clbits else [])
            try:
                slice_qc.append(ci.operation, qargs, cargs)
            except Exception:
                pass
        return slice_qc

    def entanglement_pruned_slice(self, target_qubit: int, sep_eps: float = 1e-9) -> Set[int]:
        """Flow-sensitive, entanglement-aware backward slice — the PROPOSED method (corrected).

        The classical light-cone slice (data + control reachability) is already SOUND: by no-signaling,
        the target's reduced state cannot depend on anything outside its causal cone. But that cone
        OVER-INCLUDES operations on qubits that become *separable* from the target during the circuit
        (e.g. after an entangle-then-disentangle pattern). Those operations cannot affect the target's
        reduced state, yet classical data/control analysis keeps them because the disentangling gate
        links the two timelines.

        This method starts from the sound classical slice and prunes partner operations whose qubits
        are separable from the target (detected via quantum mutual information, not data flow),
        verifying that the target's reduced density matrix is preserved. The result is a strictly
        smaller SOUND slice than classical whenever disentanglement is present — the precision win
        classical dependence analysis cannot achieve. Soundness here is the target's reduced density
        matrix (basis-independent), checked against the full circuit as an INDEPENDENT oracle.

        Falls back to the sound classical slice for non-unitary circuits (measurement/reset/feedback),
        where statevector separability is not defined.
        """
        from qiskit.quantum_info import Statevector, partial_trace  # local: heavy import
        import numpy as np

        qc = self.qc
        n = qc.num_qubits
        trace_out = [q for q in range(n) if q != target_qubit]

        # Sound starting point: classical (data+control) light cone.
        classical = set(self.remove_edge_type(EdgeType.ENTANGLEMENT).backward_slice(target_qubit))

        try:
            full_sv = Statevector(qc)
        except Exception:
            return classical  # non-unitary → keep the sound classical slice, no pruning

        ref = partial_trace(full_sv, trace_out).data  # target reduced state of the FULL circuit

        def _vn(rho) -> float:
            ev = np.linalg.eigvalsh(rho).real
            ev = ev[ev > 1e-12]
            return float(-np.sum(ev * np.log2(ev))) if ev.size else 0.0

        def _rho_t(positions) -> Optional[np.ndarray]:
            try:
                return partial_trace(Statevector(self.extract_slice_circuit(set(positions))), trace_out).data
            except Exception:
                return None

        def _mutual_info(sv, q) -> float:
            """Quantum mutual information I(target; q) in state ``sv``."""
            rho_t = partial_trace(sv, [x for x in range(n) if x != target_qubit]).data
            rho_q = partial_trace(sv, [x for x in range(n) if x != q]).data
            rho_tq = partial_trace(sv, [x for x in range(n) if x not in (target_qubit, q)]).data
            return _vn(rho_t) + _vn(rho_q) - _vn(rho_tq)

        # Precompute prefix statevectors INCREMENTALLY (state after ops[0..k]) — O(ops) total instead
        # of rebuilding each prefix from scratch (which made pruning O(ops²) and intractable on real
        # benchmark circuits with hundreds of gates).
        # Candidate prune sites: partner-only ops in the classical slice (target not among their qubits).
        candidates = {pos for pos in classical
                      if pos in self.nodes and self.nodes[pos].qubits
                      and target_qubit not in self.nodes[pos].qubits}

        # ONE forward pass evolving a single statevector; at each candidate position record whether the
        # op's qubits are already separable from the target (MI≈0). We keep only the scalar verdict per
        # position, never the full prefix states — so memory stays at one 2**n statevector, making the
        # method tractable on larger (medium) circuits rather than OOMing on stored prefixes.
        qidx = {q: i for i, q in enumerate(qc.qubits)}
        separable_here: Dict[int, bool] = {}
        sv = Statevector.from_int(0, 2 ** n)
        for k, ci in enumerate(qc.data):
            try:
                sv = sv.evolve(ci.operation, [qidx[q] for q in ci.qubits])
            except Exception:
                return classical  # non-unitary op slipped in → keep the sound classical slice
            if k in candidates:
                separable_here[k] = all(_mutual_info(sv, q) < sep_eps for q in self.nodes[k].qubits)

        # Drop separable-partner ops, re-verifying each prune against the full circuit's reduced state
        # (separability only tells us WHERE to look; the verification keeps the slice provably sound).
        kept = set(classical)
        for pos in sorted(candidates, reverse=True):
            if separable_here.get(pos):
                trial = kept - {pos}
                r = _rho_t(trial)
                if r is not None and np.linalg.norm(r - ref, ord="nuc") / 2.0 < sep_eps:
                    kept = trial
        return kept

    def edge_type_counts(self) -> Dict[str, int]:
        """Count edges by type."""
        counts = {EdgeType.DATA.value: 0,
                  EdgeType.CONTROL.value: 0,
                  EdgeType.ENTANGLEMENT.value: 0}
        for _, _, data in self.graph.edges(data=True):
            et = data.get("edge_type", EdgeType.DATA)
            key = et.value if isinstance(et, EdgeType) else str(et)
            if key in counts:
                counts[key] += 1
        return counts

    def control_dependence_frequency(self) -> float:
        """Control-dependence edges as fraction of all edges."""
        total = self.graph.number_of_edges()
        if total == 0:
            return 0.0
        ctrl = sum(1 for _, _, d in self.graph.edges(data=True)
                   if d.get("edge_type") == EdgeType.CONTROL)
        return ctrl / total


def build_qdg_variants(qc: QuantumCircuit, circuit_id: str = "") -> Dict[str, QDG]:
    """
    Build all five QDG variants for a circuit:
      - full_qdg: data + control + entanglement
      - classical_pdg: data + control (no entanglement)
      - qdg_no_ent: data + control (same as classical PDG — entanglement removed)
      - qdg_no_ctrl: data + entanglement (no control)
      - qdg_no_ent_ctrl: data only
    Returns dict keyed by variant name.
    """
    variants = {}

    # Full QDG
    full = QDG(qc, circuit_id)
    full.build(include_entanglement=True, include_control=True)
    variants["full_qdg"] = full

    # Classical PDG (no entanglement)
    classical = QDG(qc, circuit_id)
    classical.build(include_entanglement=False, include_control=True)
    variants["classical_pdg"] = classical

    # QDG-noEnt (same as classical PDG)
    no_ent = QDG(qc, circuit_id)
    no_ent.build(include_entanglement=False, include_control=True)
    variants["qdg_no_ent"] = no_ent

    # QDG-noCtrl
    no_ctrl = QDG(qc, circuit_id)
    no_ctrl.build(include_entanglement=True, include_control=False)
    variants["qdg_no_ctrl"] = no_ctrl

    # QDG-noEntCtrl (data only)
    no_ent_ctrl = QDG(qc, circuit_id)
    no_ent_ctrl.build(include_entanglement=False, include_control=False)
    variants["qdg_no_ent_ctrl"] = no_ent_ctrl

    return variants