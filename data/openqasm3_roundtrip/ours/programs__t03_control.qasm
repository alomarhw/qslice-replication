OPENQASM 3.0;
include "stdgates.inc";
bit[3] c0;
qubit[3] q0;
h q0[0];
c0[0] = measure q0[0];
if (c0[0]) {
  x q0[1];
  cx q0[1], q0[2];
}
x q0[2];
h q0[2];
h q0[1];
cx q0[1], q0[2];
ry(0.3) q0[0];
t q0[0];
t q0[1];
t q0[2];
c0[1] = measure q0[1];
c0[2] = measure q0[2];
