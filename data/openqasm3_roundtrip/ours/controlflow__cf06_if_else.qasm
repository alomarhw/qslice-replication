OPENQASM 3.0;
include "stdgates.inc";
bit[1] c;
qubit[3] q;
ry(0.9) q[0];
h q[2];
c[0] = measure q[0];
if (c[0]) {
  x q[1];
} else {
  cx q[2], q[1];
}
h q[2];
