> **Anonymized replication package** for double-anonymous review.

# srcSlice-Q: Static Program Slicing for Quantum Programs

srcSlice-Q slices Qiskit and OpenQASM programs without running them. It extends the srcML infrastructure and the
srcSlice slicer with a quantum layer that identifies the quantum role of each statement, reconstructs the circuit a
program builds, and slices every qubit, including loops that run on the quantum device. Each slice gives the source
lines, the loop iterations that contribute operations, and the classical statements that determine them.

This package holds the tool, its OpenQASM front ends to srcML, the evaluation's scripts, data and results, and the
paper's sources. Every number in the paper is a LaTeX macro that `experiments/icpc/make_numbers_b.py` computes from
the committed result files.

## Results at a glance

| Question | Result |
|---|---|
| RQ1, faithfulness | The trace equals the circuit Qiskit builds on 16 of 16 runnable programs of our own, and the slices equal the circuit's light cone on 15; on the 16th, which nests conditions, exact simulation finds the light cone wrong on 29 of 30 inputs and srcSlice-Q's slice never. On Bugs4Q, 7 of 8 traces equal the ported circuit and the line slices of all 17 mapped units equal the light cone's. OpenQASM 2: on 1,212 distinct corpus files the trace is identical to Qiskit's circuit for 1,127 and the other 85 are rejected as Qiskit rejects them; 1,228 files are marked up losslessly. OpenQASM 3 subset: 35 of 35 reference cases of the official grammar suite, no invalid statement accepted, 24 of 24 of our programs and 1,117 corpus files exported by Qiskit traced identically. Device control flow: all 33 slices of 10 programs sound under exact simulation |
| RQ2, classical statements | srcSlice's classical lines contain the interpreter's for 90% of qubits, and 86% on held-out programs |
| RQ3, cost | 4,182 of 7,568 GitHub programs sliced in a median of 131 ms each; a 5.8-million-operation circuit, every qubit, in 10 s after a 12-minute markup |
| RQ4, what a slice shows | A median slice holds 24% of a program's code lines |

## Install

With srcML 1.1.0 (https://github.com/srcML/srcML/releases/tag/v1.1.0) and the patched srcSlice on the `PATH`
(`srcslice/README.md`; without srcSlice, classical lines come from the interpreter):
```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r experiments/requirements.lock      # the pinned versions of the study (Qiskit 2.3.0)
pip install .                                     # the commands below
```
Or everything in one image, srcML and patched srcSlice included:
```bash
docker build -t srcslice-q .
docker run --rm -v "$PWD":/work -w /work srcslice-q srcslice-q PROGRAM.py
```

## Commands

```bash
srcslice-q PROGRAM.py                      # slice of every qubit: operations, quantum and classical lines
srcslice-q PROGRAM.py --qubits 0,1         # one joint criterion; also --annotate, --trace, --json
srcslice-q PROGRAM.py --qubits 0 --profile # slice profile of q0
srcslice-q PROGRAM.py --forward 25         # forward slice from the operations of line 25
srcslice-q CIRCUIT.qasm                    # OpenQASM 2 or 3, through its srcML front end
qasm2srcml CIRCUIT.qasm                    # OpenQASM 2 or 3 in srcML, Behler et al.'s markup, lossless
qiskit2srcml PROGRAM.py                    # srcML of a program with the quantum layer's roles (below)
qasm2srcml CIRCUIT.qasm --layer            # the same for OpenQASM
```
The tool reads programs and never runs them.

**Quantum markup.** `qiskit2srcml` and `qasm2srcml --layer` add what the quantum layer reads to srcML's markup, as
attributes in the namespace `http://www.srcML.org/srcML/quantum` (prefix `qu`), so another srcML tool can use the
quantum roles. The text of the markup stays the program, character for character.
```xml
<call qu:role="gate" qu:gate="cx" qu:ops="2" qu:qubits="0-2"><name>qc.cx</name>(<argument qu:arg="control">i</argument>, <argument qu:arg="target">i + 1</argument>)</call>
```
`qu:role` is gate, measure, reset, barrier, compose, call (a function whose body adds operations), control (device
control flow), circuit, qreg or creg; `qu:arg` is control, target, qubit, clbit or angle; `qu:ops`, `qu:qubits`,
`qu:clbits`, `qu:cond` and `qu:may` give the operations the call adds over every iteration. See
`srcslice_q/quantum_markup.py`.

## Layout
```
srcslice_q/            the tool
  srcml.py             srcML access (Python)
  interp.py            E2: the static trace of a Qiskit program
  gates.py             E1: the role table, from Qiskit's signatures
  slicer.py            the backward and forward slices; srcslice.py: classical lines from srcSlice (E4)
  profile.py           E5: qubit slice profiles
  qasm_srcml.py        OpenQASM 2 to srcML, the whole grammar; qasm_layer.py reads it
  qasm3_srcml.py       OpenQASM 3 to srcML, the slicing subset; qasm3_layer.py reads it
  quantum_markup.py    qiskit2srcml and qasm2srcml --layer
  cli.py               srcslice-q
  tests/               the checks of RQ1 and the test programs (all our own, safe to run)
  corpus/              coverage and profile runs over corpora, with a hard per-file time limit
srcslice/              the srcSlice patch (accuracy fixes and Python support) and how to build it
experiments/
  PROTOCOL.md          every planned analysis and dated change
  RERUNS.md            every rerun, with the old and new value of each number that changed
  icpc/                the evaluation's scripts, b_reference.py (the light cone, the QPDG, exact simulation),
                       make_numbers_b.py and make_fig_scale.py
  results/icpc/        every result file the paper reads (numbers_b.json maps each macro to its source)
data/                  the corpora shipped as data (licences in data/LICENSES/), see DATA_SOURCES.md
paper/                 the paper's LaTeX sources, numbers.tex, figures and the scripts that draw them
```

## Reproduce

**Every number and figure from the committed results** (minutes): `bash reproduce.sh` runs the tool's tests,
regenerates `paper/numbers.tex` and the scale figure, checks that both equal the committed copies, and builds the
paper. Step by step:
```bash
cd experiments
python icpc/make_numbers_b.py        # paper/numbers.tex and results/icpc/numbers_b.json
python icpc/make_fig_scale.py        # paper/figures/src/fig_scale.tex
cd ../paper && latexmk -pdf main.tex
```

**The runs** (hours). The corpora that are not shipped are downloaded by `python fetch_data.py` (QASMBench at the
pinned commit, checked file by file) or by hand (LintQ's corpus, Bugs4Q at commit 7a71983, the Qiskit textbook, Qiskit
HumanEval at commit 555f329; see DATA_SOURCES.md), into a data root passed as `DATA_ROOT`.
```bash
python -m srcslice_q.tests.test_qasm_srcml            # OpenQASM 2 front end: grammar, invalid programs, the spec's examples
python -m srcslice_q.tests.test_qasm3_grammar         # OpenQASM 3 front end on the official grammar suite
python -m srcslice_q.tests.dev_summary                # trace and slices of our programs against the built circuit
python -m srcslice_q.tests.nested_check               # nested conditions under exact simulation
python -m srcslice_q.tests.check_controlflow          # device control flow under exact simulation
(cd experiments && python icpc/b_bugs4q.py --bugs4q-root BUGS4Q_ROOT)   # T1, T2 and fault lines on Bugs4Q
python experiments/icpc/qasm_srcml_lossless.py        # OpenQASM 2 markup, byte for byte
python experiments/icpc/qasm_srcml_equiv.py           # OpenQASM 2 traces against Qiskit's circuits
python experiments/icpc/oq3_export_corpus.py && python experiments/icpc/qasm3_check.py   # OpenQASM 3 subset
python experiments/icpc/srcslice_classical.py --data-root DATA_ROOT     # classical lines, srcSlice against the interpreter
python experiments/icpc/scale_run.py s1 --data-root DATA_ROOT           # cost on LintQ's corpus (s2: QASMBench, s3: parametric)
python experiments/icpc/lintq_compare.py --data-root DATA_ROOT          # profiles on LintQ's warnings and both papers' examples
python experiments/icpc/quantum_markup_check.py --data-root DATA_ROOT   # the quantum markup on every file
```
Each script documents its options and output. No downloaded file is executed: programs are read as text, and
circuits are loaded as data.
