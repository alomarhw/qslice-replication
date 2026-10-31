OPENQASM 3.0;
include "stdgates.inc";
bit[1] c;
qubit[3] q;
h q[0];
h q[1];
c[0] = measure q[0];
c[0] = measure q[1];
if (c[0]) {
  x q[2];
}
