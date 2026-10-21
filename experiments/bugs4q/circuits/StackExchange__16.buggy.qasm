OPENQASM 2.0;
include "qelib1.inc";
qreg q24[2];
qreg q25[2];
ccx q25[0],q25[1],q24[1];
x q24[1];
ccx q25[0],q25[1],q24[1];