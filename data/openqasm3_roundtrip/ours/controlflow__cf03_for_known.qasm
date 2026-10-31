OPENQASM 3.0;
include "stdgates.inc";
bit[1] c;
qubit[3] q;
h q[0];
for _loop_i_0 in [0:2] {
  rx(_loop_i_0) q[1];
  cx q[1], q[2];
}
cz q[0], q[1];
c[0] = measure q[2];
