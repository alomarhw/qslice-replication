OPENQASM 2.0;
include "qelib1.inc";
gate ghz q0,q1,q2 { h q0; cx q0,q1; cx q1,q2; }
qreg qr[4];
ghz qr[1],qr[0],qr[2];