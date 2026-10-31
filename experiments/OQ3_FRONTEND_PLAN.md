# OpenQASM 3 front end: coverage and validation plan (groundwork, 2026-10-30)

Goal: the same design as the OpenQASM 2 front end (`tool/qasm_srcml.py`, `tool/qasm_layer.py`). A parser for the
official grammar writes srcML with Behler et al.'s elements, losslessly and with positions, and the quantum layer reads
it. Unlike OpenQASM 2, OpenQASM 3 has loops, branches, subroutines and classical computation, so the layer applies E2
here as it does to Qiskit: it unrolls, inlines, follows branches, and over-approximates what it cannot know.

Source of truth: `data/openqasm3_grammar/qasm3Parser.g4` and `qasm3Lexer.g4` (official grammar, read as data).

## Statements (qasm3Parser.g4, `statement`) and what each needs

| Statement | Element (Behler et al. where defined) | Quantum layer | Tier |
|---|---|---|---|
| `OPENQASM 3.0;` | `<version>` | check | A |
| `include "f";` | `<include>` | `stdgates.inc` read from its own markup for E1; other files likewise | A |
| `qubit[n] q;`, `qreg q[n];` | `<decl_stmt>` with `<type>` (Behler: `qubit` type with index) | allocate qubits | A |
| `bit[n] c;`, `int/uint/float/angle/bool/complex/duration/stretch x [= e];`, `const`, arrays | `<decl_stmt>` | allocate bits; classical values for E2 | A |
| `input`/`output` declarations | `<decl_stmt>` with a specifier | inputs are unknown values: over-approximate | A |
| `x = e;`, `x op= e;`, `c[i] = measure q[j];` | `<expr_stmt>`, `<measure>` inside | classical values; a measurement writes its bits | A |
| `measure q -> c;` (old style) | `<measure>` | writes the bits | A |
| gate call with modifiers `ctrl @`, `negctrl @`, `inv @`, `pow(k) @`, `gphase` | `<expr_stmt><call>` with `<argument_list type="quantum">`, modifiers as `<specifier>` | one operation on all its qubits, controls included | A |
| `gate g(p) a, b { ... }` | `<gate>` with `<parameter_list type="quantum">`, `<block>` | role-table entry | A |
| `def f(...) -> t { ... }`, `return`, calls | `<function>`, `<return>`, `<call>` | inlined at each call with its arguments, as E2 does for Python functions | A |
| `if (e) s else s` | `<if_stmt>` | condition known: that branch; else every branch, conditioned on the bits the condition reads | A |
| `for type i in [a:b:c] / {set} / expr` | `<for>` | unrolled with each iteration recorded; unknown length repeated as a device loop | A |
| `while (e) s`, `break`, `continue`, `end` | `<while>`, `<break>`, `<continue>` | as Section IV-F of the paper (device loops) | A |
| `switch (e) { case ...: {} default: {} }` | `<switch>`, `<case>`, `<default>` (srcML) | every case conditioned on the bits of e | A |
| `let a = q[0:2] ++ r;` | `<decl_stmt>` with an alias specifier | the alias denotes those qubits | A |
| `reset q;`, `barrier q;`, `nop q;` | `<reset>`, `<barrier>`, `<nop>` | writes the qubits; never sliced; never sliced | A |
| `delay[d] q;` | `<delay>` | an operation on its qubits | B |
| `box[d] { ... }` | `<box>` | its body is read in place | B |
| `extern f(...) -> t;` | `<extern>` | its result is unknown: over-approximate | B |
| `defcalgrammar`, `cal { }`, `defcal ...` | `<defcalgrammar>`, `<calibration>` | pulse level: kept in the markup, reported as not read | B |
| `pragma`, `@annotation` | `<pragma>`, `<annotation>` | kept in the markup, not read | B |
| expressions: 15 precedence levels, casts, `durationof`, literals (binary, octal, hex, imaginary, bitstring, timing, hardware qubits `$0`), index and range | `<expr>` with `<operator>`, `<literal type=...>`, `<call>`, `<index>`, `<range>` | evaluated where E2 needs the value (indices, sizes, loop ranges, conditions), unknown otherwise | A |

Tier A is what slicing needs and what the corpora use. Tier B is marked up losslessly; the layer either applies a
sound rule or reports that it does not read the construct.

## Data, all on disk

| Set | Files | Answer | Use |
|---|---|---|---|
| `data/openqasm3_grammar/tests/reference` | 35 YAML cases | the official expected parse tree | grammar coverage, valid programs |
| `data/openqasm3_grammar/tests/invalid` | 11 files | must be rejected | invalid programs |
| `data/openqasm3_examples` | 21 programs | none: lossless markup, and a trace that runs | the specification's own programs |
| VeriQBench OpenQASM 3 | 94 files | none: lossless markup, and a trace that runs | real files (subroutines, modifiers) |
| `data/openqasm3_roundtrip/ours` | 24 programs | the trace our Qiskit front end builds for the same Python program | the two front ends agree, including while, if/else, for, switch |
| `data/openqasm3_roundtrip/corpus` | 1,245 files | the circuit Qiskit loaded before exporting it | gate calls, gates, measurements, if at scale |

Qiskit's OpenQASM 3 importer and the reference parser are not installed (installing them runs downloaded code), so
the answers above are what the front end is checked against.

## Validation steps (as for OpenQASM 2)

1. Lossless markup for every file of every set.
2. Round trip: `ours` equal to the Qiskit front end's trace, operation by operation (names, qubits, bits, conditions,
   iterations, may-operations); `corpus` equal to the loaded circuit.
3. Every valid grammar test case is accepted, and its markup's structure matches the reference parse tree for the
   statements the tree names; every invalid case is rejected.
4. The specification's examples and VeriQBench yield a trace or a reported construct the layer does not read, never
   a crash.
5. Behler et al.'s elements for every construct they define.

## Order of work

1. Lexer and parser for Tier A, with lossless emission (the OpenQASM 2 emitter and element builder are reused).
2. The layer for Tier A, reusing tool.interp's machinery for loops, branches and inlining where it applies.
3. Steps 1 and 2 of the validation on the round-trip corpus, then the grammar tests.
4. Tier B markup and reporting.
