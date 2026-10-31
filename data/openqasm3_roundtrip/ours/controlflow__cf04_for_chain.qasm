OPENQASM 3.0;
include "stdgates.inc";
qubit[4] q;
ry(1.1) q[0];
for _ in [0:2] {
  cx q[0], q[1];
  cx q[1], q[2];
  cx q[2], q[3];
  swap q[0], q[1];
}
h q[3];
