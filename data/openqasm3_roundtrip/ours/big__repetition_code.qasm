OPENQASM 3.0;
include "stdgates.inc";
bit[4] syn;
bit[5] final;
qubit[5] data;
qubit[4] anc;
ry(0.7) data[0];
cx data[0], data[1];
cx data[0], data[2];
cx data[0], data[3];
cx data[0], data[4];
x data[2];
cx data[0], anc[0];
cx data[1], anc[0];
syn[0] = measure anc[0];
cx data[1], anc[1];
cx data[2], anc[1];
syn[1] = measure anc[1];
cx data[2], anc[2];
cx data[3], anc[2];
syn[2] = measure anc[2];
cx data[3], anc[3];
cx data[4], anc[3];
syn[3] = measure anc[3];
if (syn[0]) {
  x anc[0];
}
if (syn[1]) {
  x anc[1];
}
if (syn[2]) {
  x anc[2];
}
if (syn[3]) {
  x anc[3];
}
if (syn[0]) {
  if (syn[1]) {
    x data[1];
  }
}
if (syn[1]) {
  if (syn[2]) {
    x data[2];
  }
}
if (syn[2]) {
  if (syn[3]) {
    x data[3];
  }
}
cx data[0], data[4];
cx data[0], data[3];
cx data[0], data[2];
cx data[0], data[1];
final[0] = measure data[0];
final[1] = measure data[1];
final[2] = measure data[2];
final[3] = measure data[3];
final[4] = measure data[4];
