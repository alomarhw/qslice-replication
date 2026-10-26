> **Anonymized replication package** for double-blind review. All author and affiliation identifiers
> have been removed.

# Quantum Program Slicing for Comprehension: replication package

This repository contains everything behind the paper: the static slicer for Qiskit programs, the
pre-registered study that compares quantum dependence definitions against a semantic ground truth, the
mechanized soundness proof, and the paper's sources. Every number in the paper is a LaTeX macro that
`experiments/icpc/make_numbers.py` computes from the committed result files, so no number is typed by hand.

## Results at a glance

| Question | Result |
|---|---|
| RQ1 soundness and completeness | On 784 circuit–qubit pairs, the classical PDG gives wrong slices for 26.0% of them; the wire rule is wrong on none, has recall 1.000 and keeps 70.4% of a circuit, 4.8 points above the dependences themselves (65.6%); entanglement closure is sound but keeps 78.6% |
| RQ2 precision beyond the wire slice | Commutation pruning stays correct on random inputs but fails on 4 of 175 pairs when angles change; treating angles as symbols is robust on all 175. State-based pruning is 23.2% smaller but stays correct under random inputs on only 55.4% of pairs |
| RQ3 fault localization | The wire slice contains the fault in 95.7% of 5,688 units, state-based pruning in 82.2%; pruning removes the fault in 769 units, and a joint criterion recovers 691; language models lose up to 14.5 points from state-based slices |
| RQ4 cost | The wire slice takes at most 7 ms per criterion; state-based pruning exceeds 120 s at the largest depths |
| Static slicer | Trace equals the built circuit on 15 of 15 runnable programs; on Bugs4Q it reproduces 7 of 8 prepared circuits and the line slices of all 17 mapped units; 111 of 151 Bugs4Q programs, 60 of 72 textbook notebooks and 4,136 of 7,567 LintQ-corpus programs yield a circuit, with no crashes |

## Layout
```
tool/                  the static slicer for Qiskit programs (Section IV)
  srcml.py             parses a program with srcML (positions on)
  interp.py            static interpretation over an abstract domain -> operation trace
  slicer.py            the wire rule on the trace (Algorithm 1) -> lines, iterations, classical lines
  gates.py             gate signatures derived from Qiskit
  cli.py               command line
  tests/               trace and slice checks, the nested-condition check, test programs
  corpus/              coverage runs over program corpora
experiments/
  PROTOCOL_ICPC.md     the pre-registered protocol and every dated deviation (I-1 to I-15)
  icpc/                drivers for RQ1-RQ4, the tool's acceptance tests, make_numbers.py, make_result_figs.py
  common/, slicers/    the independent oracle and the slicer implementations the study compares
  bugs4q/, families/   the ported Bugs4Q bugs and the generated circuits with known structure
  results/icpc/        every result file the paper reads (numbers.json maps each macro to its source)
  logs/icpc/           logs of every run
isabelle/              mechanized soundness proof (Isabelle/HOL), see isabelle/README.md
data/                  benchmark circuits (MQT Bench, QASMBench, VeriQBench); fetch_data.py
paper/                 LaTeX sources, numbers.tex, figures and the scripts that generate them
```
Other top-level folders (`qslice/`, `fouredge/`, `selection/`, `hardware/`, `archive/`) hold the code of an
earlier version of this study. The current study reuses `selection/` (corpus definition) and the hardware
runs that the Discussion reports.

## Requirements
- Python 3.12 with the pinned packages in `experiments/requirements.lock` (qiskit 2.3.0, numpy 1.26.4);
  the noise analysis uses `experiments/requirements_noise.lock`.
- srcML 1.1 on the PATH for the static slicer.
- `pdflatex` with `latexmk` to build the paper; Isabelle2025 to check the proof (optional).

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r experiments/requirements.lock
```

## Reproduce

**Numbers and figures from the committed results** (minutes):
```bash
cd experiments
python icpc/make_numbers.py          # writes paper/numbers.tex and results/icpc/numbers.json
python icpc/make_result_figs.py      # writes the pgfplots sources of Figs. 6-9
cd ../paper && latexmk -pdf main.tex
```

**The static slicer:**
```bash
python -m tool.cli PROGRAM.py                        # slice of every qubit: operations, quantum and classical lines
python -m tool.cli PROGRAM.py --qubits 0,1           # one joint criterion; add --annotate, --trace or --json
python -m tool.tests.dev_summary                     # trace and slice checks on tool/tests/programs and tool/tests/big
python -m tool.tests.nested_check                    # nested conditional blocks against the oracle
(cd experiments && python icpc/tool_acceptance.py --bugs4q-root BUGS4Q_ROOT --tag tool-v4)   # T1 and T2
python -m tool.corpus.coverage CORPUS_DIR OUT.csv    # T3 coverage on a corpus of Qiskit programs
```
The tool reads programs and never runs them. The Bugs4Q, Qiskit textbook and LintQ corpora are not
included; download them and pass their directory. The study used Bugs4Q at commit `7a71983`.

**The study** (hours; run from `experiments/`, each script documents its options):
```bash
python icpc/rq1_run.py --data-root ../data --eval-code ../selection --out results/icpc/rq1
python icpc/cpdg_run.py --data-root ../data --eval-code ../selection
python icpc/lcq_remap.py --data-root ../data --eval-code ../selection
python icpc/lcq_symbolic.py --part corpus-a --data-root ../data --eval-code ../selection
python icpc/families_run.py
python icpc/corpus_l_run.py --data-root ../data
python icpc/rq2_robustness.py --data-root ../data --eval-code ../selection --out results/icpc/rq2_robustness
python icpc/rq2_robustness_lcq.py --data-root ../data --eval-code ../selection
python icpc/rq3_run.py --data-root ../data --eval-code ../selection --out results/icpc/rq3
python icpc/mbfl.py --data-root ../data
python icpc/rq3_bugs4q.py
python icpc/confirmatory.py                      # H1-H5
python icpc/cost_run.py --data-root ../data --eval-code ../selection
python icpc/noise_run.py --data-root ../data --eval-code ../selection   # in the noise environment
```
The language-model tasks (`icpc/llm_tasks.py`) call paid APIs and a local model server. Their raw answers
and scores are committed, so the numbers regenerate without new calls.

## Pre-registration
`experiments/PROTOCOL_ICPC.md` was committed before any run. Each later change is a dated deviation with
its reason, and deviations made after a result say so. The static slicer is frozen at git tags
`tool-v1` to `tool-v4`. Each version's results are kept, and the paper reports `tool-v4`.
