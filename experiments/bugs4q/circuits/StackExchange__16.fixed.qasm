OPENQASM 2.0;
include "qelib1.inc";
qreg q26[5];
creg c17[5];
ccx q26[0],q26[1],q26[3];
ccx q26[2],q26[3],q26[4];
ccx q26[0],q26[1],q26[3];