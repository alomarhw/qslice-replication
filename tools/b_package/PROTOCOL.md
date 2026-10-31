# Protocol log of the evaluation

Every analysis of the paper was planned before its output and changed only through a dated entry. This log collects
those entries for the package. Each keeps its date, its label in the project's protocol (the `Deviation I-n` that
comments in the code cite), and whether it was recorded before or after the output it governs. Entries, and parts of
entries, about analyses this paper does not report are left out. All analyses are exploratory.

Names. The circuit-level reference slicer, called S-lc in the project's protocol, is the light cone of the circuit
Qiskit builds (`experiments/icpc/b_reference.py`, `light_cone`). The QPDG baseline is Yu and Zhao's quantum program
dependence graph (`b_reference.QPDG`). Earlier working names of the tool (QSlice) are written srcSlice-Q.

## I-15 (2026-10-25, recorded before any Bugs4Q output of the tool): a static program slicer
- **The tool (`tool/`).** srcML 1.1 parses the program with positions. A static interpreter (`tool/interp.py`) turns
  it into an operation trace (gate, qubits, bits, condition bits, line, iteration, call sites, classical provenance)
  and never runs the program. Unresolved indices, conditions and loops are over-approximated and recorded. The wire
  rule's backward pass (`tool/slicer.py`) gives the slice as operations, quantum lines and classical lines.
- **Development** on programs of our own only (`tool/tests/programs/`, `tool/tests/big/`, the figure programs). On
  them the static trace must equal the circuit Qiskit builds, and every qubit's slice the light cone of that circuit
  (`tool/tests/check_trace.py`, `check_slice.py`, `dev_summary.py`).
- **Acceptance tests, fixed before the tool was frozen.**
  - T1. For each Bugs4Q bug, the static trace against the ported circuit, as (gate, qubits, original line) sequences,
    through the line map of `data/bugs4q_ported/`. Barriers and terminal measurements are left out, and gate names
    are normalized for Qiskit's API renamings (`u1`->`p`, `cu1`->`cp`, `cnot`->`cx`, `toffoli`->`ccx`, `u3`->`u`,
    `iden`->`id`).
  - T2. For each unit (bug, criterion qubit), the original lines of the tool's slice against those of the light
    cone of the ported circuit.
  - T3. Coverage on every Bugs4Q Python file (resolved, partly resolved, unsupported, and why).
  - Differences are reported as found. A difference T1 or T2 finds may be fixed only in a new, dated tool version,
    with both versions' results reported.
- **Nested conditions (addendum, 2026-10-25).** On a repetition code of our own that nests `if_test` blocks
  (`tool/tests/big/repetition_code.py`), the light cone reads only the outer condition of a nested `if_else`, and its
  slice of data[3] is wrong on 29 of 30 random product inputs under exact simulation. The tool's slice, which reads
  every enclosing condition, is wrong on none (`tool/tests/nested_check.py`). A terminal measurement is one that no
  later instruction depends on, counting every bit an `if_else` reads, nested conditions included.
- **Freeze (2026-10-26, before any T1-T3 output).** Tag `tool-v1`. Bugs4Q at commit 7a71983 (218 Python files).
- **tool-v1 (2026-10-26).** T1: 7 of 8 bugs trace-exact (136 of 137 operations). T2: 17 of 17 units with mapped lines
  line-equal. tool-v1 crashed on `Terra-0-4000/22`, which builds its circuit by rewriting a `DAGCircuit`.
- **tool-v2 (tag `tool-v2`).** Non-integer slice bounds evaluate to unknown, and converting a circuit to a DAG is
  reported as untraced. T1 and T2 rerun; both versions kept.
- **tool-v3 (tag `tool-v3`).** Functions and methods defined but never called are analysed as entry points with
  unknown arguments. A circuit of unknown size is handled soundly (registers grow to cover the indices used, an
  unknown index stands for any qubit). A global step budget and statement-level errors are reported as not traced.
  All checks rerun.
- **tool-v4 (tag `tool-v4`), a soundness fix.** tool-v3 interpreted the body of a loop of unknown length twice, too
  few for a dependence carried through more iterations (body `cx(2,3); cx(1,2); cx(0,1)`, criterion q3). tool-v4
  repeats the body len(touched)+1 times, at least twice, which covers every dependence chain
  (`tool/tests/programs/unknown_loop.py`). All checks rerun; earlier results kept.

## I-17 (2026-10-26, after the results above): forward slices and slice profiles
- **tool-v5 (tag `tool-v5`)** adds `forward_slice` and `slice_profile` and their CLI options. The backward slicer and
  the interpreter are unchanged, and every earlier check must give the tool-v4 results.
- **Slice profiles** (`tool/corpus/profiles.py`) on Bugs4Q, the Qiskit textbook and a seeded sample of 500 LintQ
  programs. Per qubit: operations, lines, the names in its qubit arguments, use inside functions, dependent qubits,
  conditioned operations, and backward against forward line counts. Descriptive.

## I-18 (2026-10-26, after the results above): tool-v6 and tool-v7
- **tool-v6 (tag `tool-v6`).** Two soundness bugs found by review and reproduced on small programs. The branches of an
  unknown condition ran one after another in one state, and a `return`, `break` or `continue` inside such a branch
  ended interpretation. Fixed by a join of the branch states, by may-paths for such exits, by widening variables that
  change across the copies of an unknown loop, and by counting bits as well as qubits in the loop bound. The forward
  pass drops a reached bit that an unaffected measurement overwrites (`t08_bit_overwrite.py`). Dev checks, the nested
  check and T1/T2 equal tool-v5.
- **tool-v7 (tag `tool-v7`).** The per-file limit of the corpus runs was not enforced (SIGALRM cannot interrupt long
  C-level calls). tool-v7 stops at a wall-clock deadline, counts a file that reaches it as a timeout, and runs each
  file in its own process killed at the limit plus 15 s (`tool/corpus/hardlimit.py`). Slices without a limit are
  unchanged. Acceptance, coverage and profiles are rerun on tool-v7, which the paper reports.

## I-20 (2026-10-27, recorded before any srcSlice output on the corpora): classical lines from srcSlice
- **srcSlice build.** Upstream srcSlice at ce86ef8 with the patch in `srcslice/` and its regression suite; srcML 1.1.0.
- **Method (`tool/srcslice.py`).** srcSlice's profiles of the program's srcML. For a qubit's slice the start lines are
  its quantum lines and the headers of the loops, conditions and `with` blocks that enclose them. A profile is seeded
  when its use set holds a start line. The closure adds a profile's definition lines, every profile whose dvars hold
  its name, and, for a parameter at position k of f, every profile whose cfuncs hold f{k}. The classical lines are
  the closure's lines minus the quantum lines.
- **Comparison (`experiments/icpc/srcslice_classical.py`).** Per qubit of the dev programs, Bugs4Q, the textbook and
  the LintQ sample, srcSlice's classical lines against the interpreter's provenance lines.
- **Decision rule.** srcSlice-Q reports srcSlice's lines if, over the dev programs and Bugs4Q, they contain the
  interpreter's lines for at least 95% of the qubits. Either way the paper reports the agreement.
- **Outcome.** 82% over all 1,610 qubits, 85% over the dev programs and Bugs4Q, below the threshold. The misses come
  from three srcSlice gaps (uses inside subscripts, returned values, module variables read in functions).
  Kept in `results/icpc/srcslice_i20/`.

## I-21 (2026-10-27, after the I-20 result): two srcSlice gaps fixed, comparison rerun
- srcSlice records a name inside a subscript as a use, and a read inside a function falls back to the file-scope
  variable. The third gap, returned values, is outside srcSlice's forward design and stays. A regression case is
  added and all 122 checks pass. The comparison is rerun unchanged with the I-20 rule, and because the fix followed
  the I-20 result, the paper reports both runs.
- **Outcome.** 90% of all qubits and 97% over the dev programs and Bugs4Q, above the threshold, so srcSlice-Q reports
  srcSlice's classical lines by default (`--classical srcslice`).

## I-22 (2026-10-28, recorded before any output of the analyses below): scalability, LintQ and QChecker, comprehension
- **Scalability (`experiments/icpc/scale_run.py`).** S1, every LintQ-corpus file, with per-stage times. S2, QASMBench
  medium and large: reading, one slice and all qubits. S3, our own parametric programs (QFT, GHZ, QAOA ring,
  repetition code). Baselines on S2: Qiskit's DAG ancestors of a qubit's last operation after `qasm2.load`, Qiskit's
  `LightCone` pass on the circuit with barriers and terminal measurements dropped, and building the QPDG and slicing
  one qubit. A 600 s limit per input for the baselines. Baselines run by size in batches of four and are not run on
  circuits larger than a batch in which every circuit hit the limit (recorded as skipped).
- **LintQ and QChecker (`experiments/icpc/lintq_compare.py`).** Data only, neither tool is run. C1, for each LintQ
  true positive on its corpus that srcSlice-Q traces, whether the warned line is in the warned qubit's profile and a
  profile predicate exposes the pattern (rules `ql-operation-after-measurement`, `ql-double-measurement`,
  `ql-oversized-circuit`, `ql-conditional-without-measurement`, `ql-unmeasurable-qubits`; corrected before any C1
  output). C2, operations created beyond the 10th loop iteration and over-approximated operations in the traces of
  LintQ's corpus. C3, LintQ Figs. 1, 5, 6, 11b and QChecker Fig. 5 transcribed as our own programs and sliced. Data
  in `data/lintq_artifact/`.
- **Comprehension.** Per qubit, the lines of its slice over the program's code lines (non-blank, non-comment).
- **Findings during the runs.** A known `for` loop was cut at 10,000 iterations without a note; a longer loop is now
  read as a loop of unknown length with a note, and S1 and S3 are rerun. The LightCone baseline was first run on
  circuits with terminal measurements, which the pass rejects, and is rerun on prepared circuits.

## I-23 (2026-10-28, recorded before any output below)
- **LintQ predicates on rejected warnings.** The I-22 predicates, unchanged, on the warnings of the five qubit rules
  that LintQ's inspection labels false positives, and on every SARIF warning of those rules.
- **Held-out srcSlice comparison.** `srcslice_classical.py` unchanged on 500 LintQ files (seed 20261028) outside the
  I-17 sample and the files inspected for I-21, against the same 95% threshold.
- **Like-for-like timing.** On S2, srcSlice-Q's one-qubit slice against Qiskit's one-qubit DAG ancestors, each without
  reading, and srcSlice-Q's all-qubit slice against n one-qubit Qiskit slices.
- **Coverage.** S1 files that yield no circuit, classified by a fixed rule on the file text.

## I-25 (2026-10-28, recorded before the data was downloaded): Qiskit HumanEval
- github.com/qiskit-community/qiskit-human-eval at commit 555f329 (Apache-2.0), read and never executed. One file per
  task, the measures of S1 unchanged, files with no circuit classified by the I-23 rule (`experiments/icpc/qhe_run.py`).
- Corrected before any output: 151 tasks per set, reported per set and difficulty; a hard-set file is the canonical
  solution alone; each file runs under the 120 s hard limit.

## I-26 (2026-10-28, recorded before any code or output): in-circuit control flow
- `while_loop`, `for_loop`, `switch` and the `else` branch of `if_test` run on the device. A circuit loop is sliced
  by repeating its body until the needed qubits and bits stop growing, with every operation in it conditioned on the
  bits its condition reads. `switch` cases and the `else` branch are conditioned on the target's bits. A `for_loop`
  over a known index set is unrolled.
- **Validation (`tool/tests/check_controlflow.py`).** Programs of our own with these constructs. For each qubit, the
  circuit with every operation outside the slice deleted must give the qubit the same reduced state as the whole
  circuit (Qiskit Aer density matrix, fidelity >= 1 - 1e-6) at |0...0> and at seeded random product inputs. The real
  programs that use these constructs are traced statically. Negative controls in `check_controlflow_negative.py`.
- **Findings.** All 33 slices of the 10 programs are sound at all six inputs.

## I-27 (2026-10-29, recorded before the measurements below): role table and unmodelled calls
- Five QuantumCircuit methods that take qubits but add no operation leave the role table (68 methods); one LintQ file
  calls one and is rerun (`RERUNS.md`). `noop` joins `barrier` and `delay` as never sliced.
- Unmodelled calls are counted per program on LintQ's corpus, the textbook, Bugs4Q and Qiskit HumanEval
  (`experiments/icpc/unmodelled_calls.py`), and calls of each kind of method are counted from the source text with one
  rule per row (`experiments/icpc/calls_per_kind.py`; `circuit_to_dag` counted as `name(`, corrected after the first
  count).

## OpenQASM 2 through srcML (2026-10-30, the checks fixed before their runs)
- `tool/qasm_srcml.py` writes Behler et al.'s markup for the whole OpenQASM 2 grammar of the specification, and
  `tool/qasm_layer.py` reads it. Checks: the specification's examples, valid and invalid grammar cases checked
  against Qiskit's strict parser, and Behler's elements (`tool/tests/test_qasm_srcml.py`); on every OpenQASM 2 file of
  the corpora, counted by distinct contents, the markup gives back the file byte for byte
  (`qasm_srcml_lossless.py`) and the layer's operations equal the circuit `qiskit.qasm2.load` builds, with every file
  the front end rejects rejected by Qiskit too (`qasm_srcml_equiv.py`, `qasm_srcml_rejected.py`). S2 is rerun with
  srcSlice-Q reading through srcML (`RERUNS.md`, 2026-10-31).

## OpenQASM 3 subset (2026-10-30, plan `experiments/OQ3_FRONTEND_PLAN.md`, written before the front end)
- `tool/qasm3_srcml.py` and `tool/qasm3_layer.py`: declarations, gates with modifiers, measurement, reset, barrier,
  `box`, `if`, `for`, `while`, `switch`, scopes; `def`, `let`, `delay` and calibration are kept in the markup and
  reported. Checks (`experiments/icpc/qasm3_check.py`): the official grammar suite (reference cases statement for
  statement, invalid statements rejected or reported, never accepted); a round-trip corpus written by Qiskit's
  OpenQASM 3 exporter from our programs and from the OpenQASM 2 corpora, whose traces must equal the Qiskit front end's
  and the loaded circuits (`oq3_export_corpus.py`); the official examples and VeriQBench's OpenQASM 3 files, each
  traced, rejected or reported, never a crash.

## Package (2026-10-31, after all results; no rule, run or reported slice changes)
- **Quantum markup (`tool/quantum_markup.py`, `qiskit2srcml`, `qasm2srcml --layer`).** The layer's roles and traced
  operations as attributes in a `qu:` namespace. Check (`experiments/icpc/quantum_markup_check.py`): on every file of
  the study, the markup's text is the file and every operation of the sliced circuit is on a marked call.
- **Reference code.** The light cone, the QPDG, the LightCone wrapper, circuit preparation and exact simulation are in
  `experiments/icpc/b_reference.py`, with the Bugs4Q checks in `b_bugs4q.py`. Run with it, the dev checks, the nested
  check and T1/T2 give byte-identical result files, and every slice equals the one the study recorded. The QPDG is
  built faster than in the code that produced the original timings, so its S2 timings, and Qiskit LightCone's, are
  rerun with this code (`RERUNS.md`).
- **tool-v8 (tag `tool-v8`, 2026-11-01).** A function that srcML marks up without a body is reported instead of
  crashing the interpreter (found by the quantum-markup check on a Cirq file of Bugs4Q). Every earlier check gives the
  tool-v7 results; only that file's coverage row changes (`RERUNS.md`).
- **tool-v9 (tag `tool-v9`, 2026-11-01).** srcML reads programs as UTF-8, the encoding of Python source; before, it
  mis-decoded non-ASCII characters. The 70 programs this changes are rerun in every result that reads them, every other
  row copied (`RERUNS.md`).
