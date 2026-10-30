> **Anonymized replication package** for double-anonymous review. Author and affiliation identifiers have been removed.

# What Must a Quantum Slice Keep? Replication package

This package holds everything behind the paper: the definitions' mechanized soundness proof, the slicers the study
compares, the independent reference simulator, the pre-registered protocol with every dated deviation, every result
file, and the paper's sources. Every number in the paper is a LaTeX macro that `experiments/icpc/make_numbers.py`
computes from the committed result files, and `paper/numbers.tex` names the source file of each.

## Results at a glance

| Question | Result |
|---|---|
| RQ1 sound and complete slices | On 784 circuit-qubit pairs the classical PDG gives wrong slices for 26.0%; the QDG is wrong on none, recalls every measured dependence, and keeps 4.8 points of a circuit more than the dependence set |
| RQ2 safe precision | Commutation pruning stays correct for fixed angles; state-based pruning stays correct for random inputs on 55.4% of pairs (H3 fails) |
| RQ3 fault localization | The QDG slice contains the fault in 95.7% of 5,688 seeded-fault units; state-based pruning loses 13.5 points (H4 fails); no slice improves mutation-based ranking |
| RQ4 cost | At most 7 ms per criterion for the QDG; state-based pruning exceeds 120 s at the largest depths |

## Layout
```
experiments/
  PROTOCOL_ICPC.md       the pre-registered protocol and every dated deviation, marked when made after a result
  RERUNS.md              every rerun, kept beside the original results
  icpc/                  the drivers below, make_numbers.py, make_result_figs.py
  common/, slicers/      the reference simulator and the slicers the study compares
  bugs4q/, families/     the ported Bugs4Q bugs and the generated circuits
  results/icpc/          every result file the paper reads; results/llm/ for the language-model tasks
  tests/                 oracle checks and the catalog of hand-derived cases
qdg/, selection/         the QDG slice on circuits and the corpus loader
fouredge/                the exploratory graph with one entanglement edge per two-qubit gate
isabelle/                the mechanized soundness proof, see isabelle/README.md
data/                    the benchmark circuits and their licenses; DATA_SOURCES.md and MANIFEST.sha256.tsv describe them
paper/                   the paper's sources (paper/new/main.tex), numbers.tex, references.bib, figures
```

## Where each result comes from

| In the paper | Driver (experiments/icpc/) | Results (experiments/results/icpc/) |
|---|---|---|
| Table IV, RQ1 | rq1_run.py, cpdg_run.py, qpdg_ro_run.py, yz_flow.py, lcq_remap.py, lcq_symbolic.py | rq1/, cpdg/, qpdg_ro/, yz_flow/, rq1_lcq_remap/, rq1_lcq_symbolic/ |
| Dependence set, nesting | influence.py, nesting.py, gt_convergence.py | rq1/, nesting/, gt_convergence/ |
| Two-qubit gate check | gate_signal.py | gate_signal/ |
| Corpus L | corpus_l_select.py, corpus_l_run.py | corpus_l/ |
| Table V, RQ2 | rq2_robustness.py, rq2_robustness_lcq.py, make_result_figs.py | rq2_robustness/, rq2_robustness_lcq/ |
| Noise, RQ2 | noise_run.py | noise/ |
| Table VI, RQ3 | mutate.py, rq3_run.py, rq3_size_control.py, mbfl.py, mbfl_all.py | rq3/, rq3_size_control/, mbfl/ |
| Bugs4Q units and line slices | rq3_bugs4q.py, qiskit_source_map.py | rq3_bugs4q/, source_map/ |
| Language models | llm_tasks.py | ../llm/ |
| RQ4 cost | families_run.py, cost_run.py | families/, cost/ |
| Hypotheses H1 to H5 | confirmatory.py, cluster_ci.py | confirmatory/, cluster_ci/ |
| Every number | make_numbers.py | numbers.json, and paper/numbers.tex |

## Reproducing

`bash reproduce.sh` checks the corpora against their checksums, runs the oracle checks, regenerates Table V and every
number from the committed results, compares `paper/numbers.tex` with the shipped copy, builds the paper, and builds
the Isabelle theory when Isabelle is installed. It needs Python 3.11 or 3.12 and pdflatex, and installs
`experiments/requirements.lock` into `.venv`. The full study, which recomputes the result files, runs each driver
above; most finish in minutes, and state-based pruning, corpus L and the noise analysis take hours.

The language-model tasks called hosted models; their prompts, raw answers and scores are in `experiments/results/llm/`,
and rescoring needs no model call.

Figures 1 and 2 are shipped as PDF with their LaTeX sources. The operations, outcomes, dependences and fidelities they
show are recorded in `paper/figures/src/fig_bv_facts.json` and the circuits of Fig. 2 in
`paper/figures/src/programs/`. The host-code lines marked in both figures were computed by a classical slice of the
program, which is not part of this package.
