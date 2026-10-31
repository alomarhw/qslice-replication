"""The reference slicers and the exact simulation that Paper B's evaluation compares srcSlice-Q against, on the circuit
Qiskit builds. They work on circuit instructions, never on source code, and share no code with the tool.

  prepare(qc)          the circuit as the reference slicers read it: barriers and terminal measurements dropped
                       (a terminal measurement is read by nothing later), gates on more than 8 qubits decomposed
  light_cone(qc, t)    the instructions the final state of qubit t can depend on: backward over the qubit wires,
                       and from a conditioned instruction to the latest earlier measurement of each bit it reads
  qpdg_slice(qc, t)    Yu and Zhao's quantum program dependence graph (Q-SE 2025), built as a graph: the light
                       cone's edges, plus an entanglement edge between every two instructions on qubits that
                       two-qubit gates connect, from the earlier to the later; the slice is backward reachability
  lightcone_pass(..)   Qiskit's LightCone transpiler pass, with each instruction labelled so its slice maps back
  reduced_states(..)   exact end-of-circuit reduced state of each qubit, branching on mid-circuit measurements; a
                       terminal measurement dephases its qubit
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Set

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Clbit, ClassicalRegister
from qiskit.circuit.library import UnitaryGate
from qiskit.quantum_info import Operator

WIDE = 8                 # gates on more than WIDE qubits are decomposed before slicing and simulation
FIDELITY_EPS = 1e-6      # a slice is wrong for an input when the qubit's fidelity to the full circuit is below 1 - eps
DIRECTIVES = {"barrier", "delay"}


# ---- preparation ---------------------------------------------------------------------------------------------
def condition_bits(op) -> List[Clbit]:
    """The bits a classical condition reads: one bit, or every bit of a register."""
    cond = getattr(op, "condition", None)
    if cond is None:
        return []
    return [cond[0]] if isinstance(cond[0], Clbit) else list(cond[0])


def terminal_measurements(qc: QuantumCircuit) -> Set[int]:
    """Positions of the measurements nothing later depends on: no later instruction on the qubit, and no later
    condition reads the bit (a condition nested in a block reads the bits of its instruction)."""
    out, read, touched = set(), set(), set()
    for k in range(len(qc.data) - 1, -1, -1):
        inst = qc.data[k]
        name = inst.operation.name
        if name == "measure" and inst.qubits[0] not in touched and inst.clbits[0] not in read:
            out.add(k)
        if name == "if_else":
            read.update(condition_bits(inst.operation))
            read.update(inst.clbits)
        if name not in DIRECTIVES:
            touched.update(inst.qubits)
    return out


def prepare(qc: QuantumCircuit) -> QuantumCircuit:
    term = terminal_measurements(qc)
    out = qc.copy_empty_like()
    for k, inst in enumerate(qc.data):
        if inst.operation.name != "barrier" and k not in term:
            out.append(inst)
    for _ in range(16):
        wide = sorted({i.operation.name for i in out.data
                       if i.operation.num_qubits > WIDE and i.operation.name != "if_else"})
        if not wide:
            break
        out = out.decompose(gates_to_decompose=wide)
    return out


def materialise(qc: QuantumCircuit, positions: Iterable[int]) -> QuantumCircuit:
    """A slice as a circuit: the instructions at the positions, in order, on the same registers."""
    keep = set(positions)
    out = qc.copy_empty_like()
    for k, inst in enumerate(qc.data):
        if k in keep:
            out.append(inst)
    return out


# ---- reference slicers ---------------------------------------------------------------------------------------
def _instr(qc: QuantumCircuit):
    qi = {q: i for i, q in enumerate(qc.qubits)}
    ci = {c: i for i, c in enumerate(qc.clbits)}
    return [([qi[q] for q in inst.qubits if q in qi], [ci[c] for c in inst.clbits if c in ci], inst.operation)
            for inst in qc.data], ci


def _is_conditioned(op) -> bool:
    return getattr(op, "condition", None) is not None or op.name in ("if_else", "switch_case", "for_loop", "while_loop")


def _preds(qc: QuantumCircuit) -> Dict[int, Set[int]]:
    """Wire edges (the previous instruction on each qubit) and condition edges (the latest earlier measurement of
    each bit a condition reads), as the predecessors of each instruction."""
    ins, ci = _instr(qc)
    preds: Dict[int, Set[int]] = defaultdict(set)
    last_on: Dict[int, int] = {}
    last_meas: Dict[int, int] = {}
    for k, (qs, cs, op) in enumerate(ins):
        for q in qs:
            if q in last_on:
                preds[k].add(last_on[q])
            last_on[q] = k
        if _is_conditioned(op):
            for b in condition_bits(op):
                j = last_meas.get(ci.get(b, -1))
                if j is not None:
                    preds[k].add(j)
        if op.name == "measure":
            for c in cs:
                last_meas[c] = k
    return preds


def _backward(preds, seeds) -> Set[int]:
    seen, stack = set(), list(seeds)
    while stack:
        x = stack.pop()
        if x not in seen:
            seen.add(x)
            stack.extend(p for p in preds.get(x, ()) if p not in seen)
    return seen


def light_cone(qc: QuantumCircuit, t: int) -> Set[int]:
    ins, _ = _instr(qc)
    return _backward(_preds(qc), [k for k, (qs, _, _) in enumerate(ins) if t in qs])


class QPDG:
    """Yu and Zhao's dependence graph, materialised: the cost of a QPDG slice is the cost of building it."""

    def __init__(self, qc: QuantumCircuit):
        import networkx as nx
        ins, _ = _instr(qc)
        self.on = [qs for qs, _, _ in ins]
        g = nx.DiGraph()
        g.add_nodes_from(range(len(ins)))
        for k, ps in _preds(qc).items():
            g.add_edges_from((p, k) for p in ps)
        parent = list(range(qc.num_qubits))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for qs in self.on:
            if len(qs) == 2:
                parent[find(qs[0])] = find(qs[1])
        comp: Dict[int, List[int]] = defaultdict(list)
        for q in range(qc.num_qubits):
            comp[find(q)].append(q)
        by_qubit: Dict[int, List[int]] = defaultdict(list)
        for k, qs in enumerate(self.on):
            for q in qs:
                by_qubit[q].append(k)
        for qubits in comp.values():
            for a in range(len(qubits)):
                for b in range(a + 1, len(qubits)):
                    for i in by_qubit[qubits[a]]:
                        for j in by_qubit[qubits[b]]:
                            if i != j:
                                g.add_edge(min(i, j), max(i, j))
        self.g = g

    def slice(self, t: int) -> Set[int]:
        rev = self.g.reverse(copy=False)
        return _backward({k: set(rev.neighbors(k)) for k in rev.nodes}, [k for k, qs in enumerate(self.on) if t in qs])


def qpdg_slice(qc: QuantumCircuit, t: int) -> Set[int]:
    return QPDG(qc).slice(t)


class NotApplicable(Exception):
    """The pass cannot slice this circuit (reported, not counted as a result)."""


def lightcone_pass(qc: QuantumCircuit, t: int, paulis: Iterable[str] = ("Z",)) -> Set[int]:
    from qiskit.transpiler import PassManager
    from qiskit.transpiler.passes import LightCone
    labelled = qc.copy_empty_like()
    for k, inst in enumerate(qc.data):
        op = inst.operation.to_mutable()
        op.label = f"__k{k}"
        labelled.append(op, inst.qubits, inst.clbits)
    keep: Set[int] = set()
    for p in paulis:
        try:
            out = PassManager([LightCone(bit_terms=p, indices=[t])]).run(labelled)
        except Exception as exc:  # control flow the pass does not support
            raise NotApplicable(f"LightCone({p}): {type(exc).__name__}: {exc}") from exc
        for inst in out.data:
            lab = getattr(inst.operation, "label", None) or ""
            if not lab.startswith("__k"):
                raise NotApplicable(f"LightCone({p}) returned an unlabelled instruction {inst.operation.name}")
            keep.add(int(lab[3:]))
    return keep


# ---- exact simulation ----------------------------------------------------------------------------------------
def haar_product_input(n: int, rng: np.random.Generator) -> List[np.ndarray]:
    """A Haar-random single-qubit unitary per qubit: applied to |0>, a random product input."""
    from scipy.stats import unitary_group
    return [unitary_group.rvs(2, random_state=rng) for _ in range(n)]


def with_input(qc: QuantumCircuit, prep: Optional[Sequence[np.ndarray]]) -> QuantumCircuit:
    if prep is None:
        return qc
    out = qc.copy_empty_like()
    for q, u in enumerate(prep):
        out.append(UnitaryGate(u, check_input=False), [out.qubits[q]])
    for inst in qc.data:
        out.append(inst)
    return out


class SimulationError(RuntimeError):
    pass


def _gate(state: np.ndarray, mat: np.ndarray, qs: Sequence[int], n: int) -> np.ndarray:
    """Apply a k-qubit matrix in Qiskit's order (its first qubit least significant) to a state of shape (2,)*n
    whose axis n-1-q is qubit q."""
    k = len(qs)
    axes = [n - 1 - q for q in reversed(qs)]          # the matrix's row index, most significant qubit first
    m = mat.reshape((2,) * (2 * k))
    out = np.tensordot(m, state, axes=(list(range(k, 2 * k)), axes))
    return np.moveaxis(out, list(range(k)), axes)


def _holds(op, bits: Dict[int, int], cmap) -> bool:
    target, value = op.condition
    if isinstance(target, Clbit):
        return bits[cmap[target]] == int(value)
    if isinstance(target, ClassicalRegister):
        return sum(bits[cmap[c]] << i for i, c in enumerate(target)) == int(value)
    raise SimulationError(f"unsupported condition {op.condition!r}")


def _run(data, branches, qmap, cmap, n, terminal, dephased, mats):
    for k, inst in enumerate(data):
        op, qs = inst.operation, [qmap[q] for q in inst.qubits]
        if op.name in DIRECTIVES:
            continue
        if op.name in ("measure", "reset"):
            if op.name == "measure" and terminal is not None and k in terminal:
                dephased.add(qs[0])
                continue
            ax, nxt = n - 1 - qs[0], []
            for p, st, bits in branches:
                for b in (0, 1):
                    part = np.take(st, b, axis=ax)
                    pb = float(np.vdot(part, part).real)
                    if p * pb <= 1e-14:
                        continue
                    new = np.zeros_like(st)
                    idx = [slice(None)] * n
                    idx[ax] = b if op.name == "measure" else 0
                    new[tuple(idx)] = part / np.sqrt(pb)
                    nb = dict(bits)
                    if op.name == "measure":
                        nb[cmap[inst.clbits[0]]] = b
                    nxt.append((p * pb, new, nb))
            if len(nxt) > 4096:
                raise SimulationError("more than 4096 measurement branches")
            branches = nxt
        elif op.name == "if_else":
            if not isinstance(getattr(op, "condition", None), tuple):
                raise SimulationError("if_else without a bit or register condition")
            yes = [b for b in branches if _holds(op, b[2], cmap)]
            no = [b for b in branches if not _holds(op, b[2], cmap)]
            for body, group in ((op.blocks[0], yes), (op.blocks[1] if len(op.blocks) > 1 else None, no)):
                if body is not None and group:
                    bq = {b: qmap[o] for b, o in zip(body.qubits, inst.qubits)}
                    bc = dict(cmap) | {b: cmap[o] for b, o in zip(body.clbits, inst.clbits)}
                    group[:] = _run(body.data, group, bq, bc, n, None, dephased, mats)
            branches = yes + no
        elif op.num_clbits == 0 and getattr(op, "blocks", None) is None:
            key = (op.name, op.num_qubits, tuple(repr(p) for p in op.params))
            if key not in mats:
                try:
                    mats[key] = np.asarray(op.to_matrix(), dtype=complex)
                except Exception:
                    mats[key] = Operator(op).data
            branches = [(p, _gate(st, mats[key], qs, n), bits) for p, st, bits in branches]
        else:
            raise SimulationError(f"unsupported instruction {op.name}")
    return branches


def reduced_states(qc: QuantumCircuit, qubits: Iterable[int], max_qubits: int = 16) -> Dict[int, np.ndarray]:
    n = qc.num_qubits
    if n > max_qubits:
        raise SimulationError(f"more than {max_qubits} qubits")
    st = np.zeros((2,) * n, dtype=complex)
    st[(0,) * n] = 1.0
    dephased: Set[int] = set()
    branches = _run(qc.data, [(1.0, st, dict.fromkeys(range(qc.num_clbits), 0))], {q: i for i, q in enumerate(qc.qubits)},
                    {c: i for i, c in enumerate(qc.clbits)}, n, terminal_measurements(qc), dephased, {})
    total = sum(p for p, _, _ in branches)
    out = {}
    for q in qubits:
        rho = np.zeros((2, 2), dtype=complex)
        for p, s, _ in branches:
            m = np.moveaxis(s, n - 1 - q, 0).reshape(2, -1)
            rho += p * (m @ m.conj().T)
        rho /= total
        out[q] = np.diag(np.diag(rho)) if q in dephased else rho
    return out


def fidelity(rho: np.ndarray, sigma: np.ndarray) -> float:
    """Uhlmann fidelity of two single-qubit states, in closed form."""
    f = np.trace(rho @ sigma).real + 2.0 * np.sqrt(max(np.linalg.det(rho).real, 0.0) * max(np.linalg.det(sigma).real, 0.0))
    return float(min(max(f, 0.0), 1.0))
