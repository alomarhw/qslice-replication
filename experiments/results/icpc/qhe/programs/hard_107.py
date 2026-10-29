from qiskit.quantum_info import ScalarOp

def compose_scalar_ops():
    op1 = ScalarOp(2, 2)
    op2 = ScalarOp(2, 2)
    composed_op = op1.compose(op2)
    return composed_op
