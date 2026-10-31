OPENQASM 3.0;
include "stdgates.inc";
bit[1] c;
qubit[3] q;
h q[0];
ry(0.3) q[2];
c[0] = measure q[0];
while (c[0]) {
  h q[0];
  cx q[0], q[1];
  c[0] = measure q[0];
}
x q[2];
