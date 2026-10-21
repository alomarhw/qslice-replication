"""Dependence catalogue (PROTOCOL_ICPC.md section 2.2 and Deviation I-1): golden circuits, one per
dependence kind, with every expected outcome written down BEFORE any slicer is run on them.

Expectations were derived by hand from the definitions:
- influence (section 2.1, joint perturbation): o_k influences q iff some operation in o_k's place
  changes q's unconditional end-of-circuit reduced state for some product input;
- du: qslice/qdg.py naive_classical_backward_slice (controlled gate writes its targets only;
  classical bits are ignored);
- lc: QDGControlFixed without ENTANGLEMENT edges, backward_slice (wire light cone + classical control);
- yz: slicers/yuzhao.py (design log in that file): DATA + CONTROL + flow-insensitive ENTANGLEMENT
  reachability;
- q: entanglement_pruned_slice (falls back to lc on non-unitary circuits);
- 4e_unfixed / 4e_fixed: fouredge QSlice-full, seeded at criterion measurements / at the
  criterion's last operation of any kind;
- lcq (Qiskit LightCone, union over X/Y/Z): only "sound and subset of lc" (or not applicable on
  dynamic circuits), Deviation I-1 item 5.

A disagreement between an expectation and a run is REPORTED, never fixed by editing this file,
unless the oracle shows the expectation itself is wrong; that is logged as a deviation.
Instruction positions are indices into qc.data, in the order the builders append them.
"""

from __future__ import annotations

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister

THETA_RY, THETA_RZ = 0.7, 0.4


def _c(n_qubits: int, n_clbits: int = 0) -> QuantumCircuit:
    return QuantumCircuit(n_qubits, n_clbits) if n_clbits else QuantumCircuit(n_qubits)


def k1():
    qc = _c(1); qc.h(0); qc.x(0); return qc


def k2():
    qc = _c(2); qc.h(0); qc.cx(0, 1); return qc


def k3():  # phase kickback: q1 in |->, control q0 in |+> becomes |->
    qc = _c(2); qc.x(1); qc.h(1); qc.h(0); qc.cx(0, 1); return qc


def k4():  # symmetric controlled phase; S on q1 commutes with CZ (influencing, no as-written effect)
    qc = _c(2); qc.h(0); qc.h(1); qc.s(1); qc.cz(0, 1); return qc


def k5():  # partner history reaches the control through entanglement
    qc = _c(2); qc.h(0); qc.ry(THETA_RY, 1); qc.cx(0, 1); return qc


def k6():  # no-signalling: partner operations after the last interaction
    qc = _c(2); qc.h(0); qc.cx(0, 1); qc.x(1); qc.rz(THETA_RZ, 1); return qc


def k6b():
    qc = k6(); qc.h(0); return qc


def k7():
    qc = _c(2); qc.ry(0.9, 1); qc.swap(0, 1); return qc


def k8():  # entangle, disentangle, re-entangle; X q2 is the preparation (Deviation I-1 item 6)
    qc = _c(3); qc.h(0); qc.x(2); qc.cx(0, 2); qc.cx(0, 2); qc.cx(0, 1); return qc


def k9():  # chained entanglement, then uncompute the first link
    qc = _c(3); qc.h(2); qc.cx(2, 1); qc.cx(1, 0); qc.cx(2, 1); return qc


def k10():  # U ... U^dagger with a cancelling CX pair on the criterion
    qc = _c(3); qc.ry(0.5, 2); qc.cx(2, 1); qc.cx(1, 0); qc.cx(1, 0); qc.cx(2, 1); qc.ry(-0.5, 2); return qc


def k11():  # mid-circuit measurement of a partner, no feedback (H q1 keeps it non-terminal)
    qc = _c(2, 1); qc.h(0); qc.cx(0, 1); qc.measure(1, 0); qc.h(1); return qc


def k11b():
    qc = k11(); qc.h(0); return qc


def k12():  # measurement + classical feedback
    qc = _c(2, 1); qc.h(1); qc.measure(1, 0)
    with qc.if_test((qc.clbits[0], 1)):
        qc.x(0)
    return qc


def k13():  # teleportation of RY/RZ-prepared q0 onto q2
    q = QuantumRegister(3, "q"); c0 = ClassicalRegister(1, "c0"); c1 = ClassicalRegister(1, "c1")
    qc = QuantumCircuit(q, c0, c1)
    qc.ry(1.1, 0); qc.rz(0.3, 0); qc.h(1); qc.cx(1, 2); qc.cx(0, 1); qc.h(0)
    qc.measure(0, c0[0]); qc.measure(1, c1[0])
    with qc.if_test((c1, 1)):
        qc.x(2)
    with qc.if_test((c0, 1)):
        qc.z(2)
    return qc


def k14():  # overwritten classical bit: only the second measurement is a dependence
    qc = _c(3, 1); qc.h(1); qc.h(2); qc.measure(1, 0); qc.measure(2, 0)
    with qc.if_test((qc.clbits[0], 1)):
        qc.x(0)
    return qc


def k15():  # reset of a partner after the interaction
    qc = _c(2); qc.h(0); qc.cx(0, 1); qc.reset(1); return qc


def k16():  # multi-bit register condition
    q = QuantumRegister(3, "q"); c = ClassicalRegister(2, "c")
    qc = QuantumCircuit(q, c)
    qc.h(1); qc.h(2); qc.measure(1, c[0]); qc.measure(2, c[1])
    with qc.if_test((c, 3)):
        qc.x(0)
    return qc


def k17():  # GHZ on q0-q3, then uncompute q3 and q2
    qc = _c(4); qc.h(0); qc.cx(0, 1); qc.cx(1, 2); qc.cx(2, 3); qc.cx(2, 3); qc.cx(1, 2); return qc


def k18():  # Deutsch, balanced f: kickback without entanglement
    qc = _c(2); qc.x(1); qc.h(0); qc.h(1); qc.cx(0, 1); qc.h(0); return qc


def k19():  # Bell pair
    qc = _c(2); qc.h(0); qc.cx(0, 1); return qc


def k20():  # measured-then-corrected criterion qubit
    qc = _c(1, 1); qc.h(0); qc.measure(0, 0)
    with qc.if_test((qc.clbits[0], 1)):
        qc.x(0)
    return qc


def _all(n):
    return set(range(n))


def _e(infl, du, lc, yz, q, e4u, e4f, du_sound, e4u_sound=True, dynamic=False):
    return {"influence": set(infl), "du": set(du), "lc": set(lc), "yz": set(yz), "q": set(q),
            "4e_unfixed": set(e4u), "4e_fixed": set(e4f),
            "sound": {"du": du_sound, "lc": True, "yz": True, "q": True,
                      "4e_unfixed": e4u_sound, "4e_fixed": True},
            "dynamic": dynamic}


# (id, kind, builder, criterion qubit, expectations)
CATALOGUE = [
    ("K1", "data, same wire", k1, 0, _e({0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, True)),
    ("K2", "control -> target", k2, 1, _e({0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, True)),
    ("K3", "phase kickback", k3, 0, _e(_all(4), {2}, _all(4), _all(4), _all(4), _all(4), _all(4), False)),
    ("K4", "symmetric controlled phase", k4, 0,
     _e(_all(4), {0}, _all(4), _all(4), {0, 1, 3}, _all(4), _all(4), False)),
    ("K5", "partner history via entanglement (kickback category)", k5, 0,
     _e(_all(3), {0}, _all(3), _all(3), _all(3), _all(3), _all(3), False)),
    ("K6", "no-signalling: partner after last interaction", k6, 0,
     _e({0, 1}, {0}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, False)),
    ("K6b", "no-signalling, later op on criterion", k6b, 0,
     _e({0, 1, 4}, {0, 4}, {0, 1, 4}, _all(5), {0, 1, 4}, _all(5), _all(5), False)),
    ("K7", "SWAP moves state", k7, 0, _e({0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, True)),
    ("K8", "entangle, disentangle, re-entangle", k8, 0,
     _e({0, 2, 3, 4}, {0}, _all(5), _all(5), {0, 2, 3, 4}, _all(5), _all(5), False)),
    ("K9", "indirect (chained) entanglement", k9, 0,
     _e({0, 1, 2}, {0, 1, 2}, {0, 1, 2}, {0, 1, 2}, {0, 1, 2}, {0, 1, 2}, {0, 1, 2}, True)),
    ("K10", "uncomputation U ... U^dagger", k10, 0,
     _e({2, 3}, _all(4), _all(4), _all(4), {2, 3}, _all(4), _all(4), True)),
    ("K11", "partner mid-circuit measurement, no feedback", k11, 0,
     _e({0, 1}, {0}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, False, dynamic=True)),
    ("K11b", "partner measurement, later op on criterion", k11b, 0,
     _e({0, 1, 4}, {0, 4}, {0, 1, 4}, _all(5), {0, 1, 4}, _all(5), _all(5), False, dynamic=True)),
    ("K12", "measurement + classical feedback", k12, 0,
     _e(_all(3), {2}, _all(3), _all(3), _all(3), _all(3), _all(3), False, dynamic=True)),
    ("K13", "teleportation", k13, 2,
     _e(_all(10), {2, 3, 8, 9}, _all(10), _all(10), _all(10), _all(10), _all(10), False, dynamic=True)),
    ("K14", "overwritten classical bit", k14, 0,
     _e({1, 3, 4}, {4}, {1, 3, 4}, {1, 3, 4}, {1, 3, 4}, _all(5), _all(5), False, dynamic=True)),
    ("K15", "reset of a partner after the interaction", k15, 0,
     _e({0, 1}, {0}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, False, dynamic=True)),
    ("K16", "register condition (multi-bit)", k16, 0,
     _e(_all(5), {4}, _all(5), _all(5), _all(5), _all(5), _all(5), False, dynamic=True)),
    ("K17", "GHZ partial uncompute (criterion q0)", k17, 0,
     _e({0, 1}, {0}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, False)),
    ("K17", "GHZ partial uncompute (criterion q1)", k17, 1,
     _e(_all(6), {0, 1}, _all(6), _all(6), _all(6), _all(6), _all(6), True)),
    ("K18", "Deutsch: kickback without entanglement", k18, 0,
     _e(_all(5), {1, 4}, _all(5), _all(5), _all(5), _all(5), _all(5), False)),
    ("K19", "Bell pair (criterion q1)", k19, 1, _e({0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, True)),
    ("K19", "Bell pair (criterion q0)", k19, 0, _e({0, 1}, {0}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, False)),
    ("K20", "measured-then-corrected criterion", k20, 0,
     _e({1, 2}, {0, 1, 2}, {0, 1, 2}, {0, 1, 2}, {0, 1, 2}, {0, 1}, {0, 1, 2}, True, e4u_sound=False,
        dynamic=True)),
]
