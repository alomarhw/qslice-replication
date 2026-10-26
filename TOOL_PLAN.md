# A static slicer for Qiskit programs (decided 2026-10-25)

**Goal.** Turn the study's circuit-level slicer into a real program slicer.
- **Input:** a Qiskit program's source code and a criterion (a set of qubits, at the end of the
  circuit or at a statement).
- **Output:** the source lines, and for loops the iterations, whose operations the criterion depends on,
  plus the classical lines that compute those operations' qubits, conditions and loop bounds.
- **Statically:** the program is never executed. The rule is the validated wire rule (Section 3), with
  the all-angles commutation refinement (Deviation I-14, B1) as an option.

**Why static.** The study's source map *runs* a re-typed copy of each program. A tool for developers, and
for Bugs4Q originals that we may not execute, must read the source.

## Prior design we build on (Behler et al., QCE 2024 §IV; IEEE Software 2025 p. 5)
Their srcML-based *execution-order analysis* for OpenQASM is the closest prior design.
- **How it works.** It walks the srcML tree, keeps a per-qubit operation list, stores gate and function
  definitions and inlines them at calls with parameters substituted, and unrolls `for` ranges by
  substituting the loop variable. The output is the operations on each qubit over time, with control
  and target roles.
- **Its limitations (QCE 2024 §IV-C):**
  - no `while` loops;
  - qubits passed classically to functions are skipped;
  - calls inside conditions, or several calls in one expression, are skipped;
  - branching is future work.
- **Status.** Their OpenQASM parser is unreleased, and the inputs were marked up by hand.
- **Slicing** of individual qubits is their stated future work (IEEE Software p. 8).

**Our tool:**
1. carries execution-order analysis over to Qiskit programs, which srcML 1.1 parses;
2. makes it sound where it cannot resolve:
   - unknown indices, conditions and loop bounds are over-approximated and flagged;
   - every call in any expression is processed;
   - functions take quantum arguments;
3. adds classical control (`if_test`, `c_if`) and the provenance of classical values;
4. turns the operation order into a slice with the validated wire rule.

The trace format keeps one operation per record (gate, qubits with roles, bits, condition bits, line,
iteration). An OpenQASM front end can therefore feed the same back end once the srcML parser exists.

## Components and tools
| Component | Tool | Status |
|---|---|---|
| Parsing, positions | srcML 1.1 (Python), `/usr/local/bin/srcml` | Installed. Parses all 218 Bugs4Q files with no errors (probe, 2026-10-25) |
| Classical def/use of variables | srcSlice (fixed Python build), `/usr/local/bin/srcslice` | Installed. Gives per-variable def/use lines. It sees no quantum dependence (a gate is a "use" of `qc`), so it is used for the classical side only |
| Gate semantics | Qiskit 2.3 gate classes: arity, number of controls, parameters | In the qslice venv |
| Static interpretation | new: `tool/interp.py` | To build |
| Quantum dependence | the wire rule (backward pass, reaching definitions for bits, joint criterion); optional all-angles commutation via `LightCone` on symbolic angles | Core exists (`icpc/wire_swap.py` pass, `icpc/lcq_symbolic.py`); to be refactored into `tool/` |
| Output | JSON, plus annotated source (and later the VS Code front end for the demo) | To build |

## Pipeline
1. **Parse.** `srcml --position -l Python prog.py` gives XML with line and column per element.
2. **Interpret statically (`tool/interp.py`).** Walk the srcML tree with an abstract environment.
   - **Values:** ints, floats, strings, bools, lists, tuples, `range`, `None`, and *unknown*.
     Expressions are evaluated from srcML expression tokens by a small safe evaluator.
   - **Quantum objects:** `QuantumRegister`, `ClassicalRegister`, `QuantumCircuit`, and qubit and bit
     references (register plus index).
   - **Statements:**
     - assignment, including tuples;
     - `for` over ranges, lists and registers, unrolled with an iteration count per loop;
     - `if` on known conditions; both branches when unknown (may-operations);
     - `def`, inlined at call sites with the call line recorded;
     - `return`;
     - `with qc.if_test(...)`, and `.c_if(...)`.
   - **Circuit calls:**
     - every standard gate method;
     - `measure`, with register broadcasting;
     - `measure_all`, `reset`, `barrier`;
     - `append(gate, qargs)`, `compose`;
     - `initialize`, `unitary`.

     Each call becomes an operation with its gate, qubits, bits, condition bits, source line, iteration
     vector and call-site lines.
   - **Soundness when unresolved.**
     - An unknown qubit index makes the operation act on every qubit of the register (a may-write).
     - An unknown loop bound, unknown control flow, or an unsupported construct is recorded and flagged.
     - The tool never silently drops an operation.
3. **Slice (`tool/slicer.py`).**
   - The wire-rule backward pass over the operation trace, from the criterion qubits, with reaching
     definitions for classical bits and the joint criterion.
   - Optionally, all-angles commutation, with every angle symbolic, which a static trace has by nature.
4. **Classical closure (`tool/classical.py`).**
   - Add the lines that define the variables used by the sliced operations' arguments (indices,
     conditions, loop bounds, register sizes), transitively.
   - Use srcSlice's def/use profiles, cross-checked against the interpreter's own def/use record.
5. **Report.** Lines and iterations in the slice, unresolved constructs, and per-line provenance (which
   dependence brought the line in).

## Validation: an acceptance check, not a rerun
- **T1, trace equivalence.**
  - For our own programs (the figure programs and the test programs), the static trace must equal the
    circuit Qiskit builds by running them: same gates, qubits and order.
  - For the Bugs4Q originals, which we never run, compare with the prepared RQ3 circuits through the
    committed source map (`results/icpc/source_map/instructions.csv`): same (gate, qubits, original
    line) sequence.
- **T2, slice equivalence.** On the RQ3 Bugs4Q units, the tool's wire-rule line slices must equal the
  committed line results (`results/icpc/source_map/units.csv`).
  - If they are equal, the paper's Bugs4Q line numbers are computed by the tool.
  - Every difference is reported, never edited away.
- **T3, coverage at scale.** Run on all 218 Bugs4Q Python files. Report how many programs are fully
  resolved, partly resolved (with may-operations) or unsupported, and why.
- **T4, unit tests.** A test file per construct: loops, functions, `if_test`, `c_if`, registers,
  broadcasting, `append`, `compose`, unknown indices.
- **Integrity.**
  - Deviation I-15 is recorded before any T1–T3 output.
  - The tool is developed on the figure programs and the unit tests only. T1–T3 are run when the tool is
    frozen, and the commit is recorded.

## Paper
- **Section 3 or 4:** "Approach and tool". The pipeline above, Algorithm 1 (the static interpretation
  plus the wire-rule pass), and the ansatz as the worked example (loops, iterations, symbolic angles).
- **RQ3:** Bugs4Q in source lines computed by the tool, with the T2 result. T3 as the coverage of the tool.
- **RQ4:** the tool's time, including srcML parsing.
- **Anonymity.**
  - srcML and srcSlice are cited in the third person, as open-source infrastructure.
  - No author-identifying claims.
  - The Tool Demo (Nov 19) presents the tool itself.

## Schedule (paper due Nov 5; abstract Oct 29)
- Oct 25–27: parser and interpreter on the figure programs; unit tests; the slicer.
- Oct 28: classical closure, output, freeze. I-15, then T1–T3.
- Oct 29: abstract (the author).
- Oct 30–Nov 1: paper text, Algorithm 1, RQ3 and RQ4 updates.
- Nov 2–4: review and buffer.

## Out of scope before Nov 5
- OpenQASM through srcML: srcML has no OpenQASM parser yet, and QStatic's inputs are marked up by hand.
- Programs that build circuits through Qiskit library classes (for example `QFT(n)`, `TwoLocal`). These
  are treated as one opaque operation on their qubits, which is sound under the wire rule, and flagged.
