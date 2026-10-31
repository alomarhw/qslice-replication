OPENQASM 3.0;
include "stdgates.inc";
bit[1] c;
qubit[3] q;
x q[2];
h q[2];
h q[1];
h q[0];
c[0] = measure q[0];
while (c[0]) {
  cx q[1], q[2];
  h q[0];
  c[0] = measure q[0];
}
h q[1];
