"""Step 2 of the OpenQASM 2 front-end validation: the layer's trace, read from srcML, equals the circuit
qiskit.qasm2.load builds with Qiskit's legacy instructions, operation by operation, in order: the operation's name, its
qubits, the bit a measurement writes, and the bits a condition reads. Barriers are compared too.
Usage: python -m tool.tests.check_qasm_layer FILE...   (prints one line per file)"""
import sys
from qiskit import qasm2
from tool import qasm_layer

NAME = {"u": "u", "U": "u", "CX": "cx"}
# Qiskit's names for qelib1.inc gates whose Qiskit class is named differently; only the name differs.
QISKIT_NAME = {"c3x": "mcx", "c4x": "mcx", "c3sqrtx": "c3sx", "rc3x": "rcccx"}


def qiskit_ops(path):
    qc = qasm2.load(str(path), custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
    qi = {b: i for i, b in enumerate(qc.qubits)}
    ci = {b: i for i, b in enumerate(qc.clbits)}
    out = []
    for inst in qc.data:
        op = inst.operation
        cond = []
        body = op
        if op.name == "if_else":                       # if(c==n) qop; as Qiskit 2 builds it
            reg = op.condition[0]                     # OpenQASM 2 conditions on a whole register
            cond = sorted(ci[b] for b in reg)
            blk = op.blocks[0]
            bq = {b: qi[q] for b, q in zip(blk.qubits, inst.qubits)}
            bc = {b: ci[c] for b, c in zip(blk.clbits, inst.clbits)}
            for bi in blk.data:
                out.append((bi.operation.name, tuple(bq[q] for q in bi.qubits),
                            bc[bi.clbits[0]] if bi.operation.name == "measure" else -1, tuple(cond)))
            continue
        out.append((op.name, tuple(qi[q] for q in inst.qubits),
                    ci[inst.clbits[0]] if op.name == "measure" else -1, ()))
    return out


def layer_ops(path):
    return [(QISKIT_NAME.get(NAME.get(n, n), NAME.get(n, n)), tuple(q), mb, tuple(sorted(c)))
            for n, q, mb, c, _, _ in qasm_layer.ops(path)]


def compare(path):
    a, b = layer_ops(path), qiskit_ops(path)
    if a == b:
        return True, ""
    for k, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return False, f"op {k}: layer {x} qiskit {y}"
    return False, f"lengths {len(a)} vs {len(b)}"


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p, *compare(p))
