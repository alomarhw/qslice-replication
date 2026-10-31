OPENQASM 3.0;
include "stdgates.inc";
bit[1] c;
qubit[4] q;
h q[0];
h q[1];
h q[2];
c[0] = measure q[2];
while (c[0]) {
  cx q[0], q[1];
  cx q[1], q[2];
  h q[2];
  c[0] = measure q[2];
}
cx q[0], q[3];
