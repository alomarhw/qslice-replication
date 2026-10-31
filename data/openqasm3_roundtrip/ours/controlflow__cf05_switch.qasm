OPENQASM 3.0;
include "stdgates.inc";
bit[2] c;
int switch_dummy;
qubit[4] q;
h q[0];
h q[1];
ry(0.4) q[3];
c[0] = measure q[0];
c[1] = measure q[1];
switch_dummy = c;
switch (switch_dummy) {
  case 0 {
    x q[2];
  }
  case 1, 2 {
    cx q[3], q[2];
  }
  default {
    h q[2];
  }
}
z q[3];
