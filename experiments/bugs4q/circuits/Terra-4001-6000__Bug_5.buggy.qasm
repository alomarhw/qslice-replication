OPENQASM 2.0;
include "qelib1.inc";
gate unitary q0,q1,q2 { u(0,5*pi/8,-3*pi/8) q0; u(0,pi/16,pi/16) q1; cx q0,q2; rz(-pi/4) q2; cx q1,q2; cx q0,q2; rz(-pi/8) q2; cx q1,q2; }
qreg qae[2];
qreg b[2];
unitary qae[0],b[0],b[1];