OPENQASM 3.0;
include "stdgates.inc";
bit[8] c;
bit[1] out;
qubit[9] q;
U(0.4, 0.2, 0.1) q[0];
h q[1];
cx q[1], q[2];
cx q[0], q[1];
h q[0];
c[0] = measure q[0];
c[1] = measure q[1];
if (c[1]) {
  x q[2];
}
if (c[0]) {
  z q[2];
}
h q[3];
cx q[3], q[4];
cx q[2], q[3];
h q[2];
c[2] = measure q[2];
c[3] = measure q[3];
if (c[3]) {
  x q[4];
}
if (c[2]) {
  z q[4];
}
h q[5];
cx q[5], q[6];
cx q[4], q[5];
h q[4];
c[4] = measure q[4];
c[5] = measure q[5];
if (c[5]) {
  x q[6];
}
if (c[4]) {
  z q[6];
}
h q[7];
cx q[7], q[8];
cx q[6], q[7];
h q[6];
c[6] = measure q[6];
c[7] = measure q[7];
if (c[7]) {
  x q[8];
}
if (c[6]) {
  z q[8];
}
out[0] = measure q[8];
