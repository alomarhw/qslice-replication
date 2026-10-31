OPENQASM 3.0;
include "stdgates.inc";
bit[1] c;
qubit[3] q;
ry(1.2) q[0];
h q[1];
c[0] = measure q[1];
while (c[0]) {
  reset q[1];
  cx q[0], q[1];
  h q[1];
  c[0] = measure q[1];
}
cx q[1], q[2];
h q[0];
