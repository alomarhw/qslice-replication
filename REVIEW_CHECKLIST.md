# Review checklist: every ICSE reviewer point and rebuttal promise

Source: `ICPC_QSLICE_PLAN.md` §4a; full text in `~/Projects/RP/Docs/REVIEWS_AND_REBUTTAL.md`.

Every row must end as **done** or **declined + reason**, and a declined row's reason must appear in the
paper. Phase 7 checks this file against the PDF.

Status values:
- **todo**;
- **partly** (what exists and what is missing);
- **done** (where the evidence is);
- **declined** (the reason).

Last updated: 2026-10-23, after Checkpoint B. "evidence done" means the experiment and its committed result exist;
the row becomes **done** only when the paper text answers it (Phase 5). Evidence files are named in each row.

## Reviewer A (Weak reject)

| # | Point | Answer in the ICPC paper | Status |
|---|---|---|---|
| A1 | Q1: how superposition affects the dependence graph; could it "explode"? | §III paragraph: the graph is built from operations and qubits, never amplitudes; it grows with operation count. The exponential cost is only in the pruning check, measured in RQ4. | evidence done; paper text: Phase 5. Graph size depends on operations only (`results/icpc/cost`, graph columns); the pruning cost is exponential (RQ4). |
| A2 | Larger depth vs performance (not just qubit count) | RQ2 depth sweep at fixed width; RQ4 cost vs depth | evidence done; paper text: Phase 5. Depth sweep (`results/icpc/cost`: S-q 1.4 s at depth 17 → over 120 s at depth ~190); families F-depth; corpus L. |
| A3 | Main weakness: no demonstrated practical use (debugging) | RQ3 fault-localization study | evidence done; paper text: Phase 5. RQ3: 5,688 seeded faults (`results/icpc/rq3`), Bugs4Q (`rq3_bugs4q`, `source_map`), MBFL (`mbfl`), LLM T1/T2 (`results/llm`). |
| A4 | Q2: debugging on real hardware; noise affecting analysis; a small hardware experiment | Discussion: slices are static, and noise affects only their execution. The hardware PoC is recomputed with rebuttal Correction 4/6 applied, with phase-blind TVD stated. | evidence done; paper text: Phase 5. Hardware recomputed (D11/R18: 16/18; noise-free TVD 0 on 18/18); noisy simulation (`results/icpc/noise`). Discussion only (author decision §7.1). |
| A5 | "A bit dense at times" | Plainer prose, one running example, fewer RQs | todo (Phase 5 writing). |
| A6 | Make the motivating example ↔ Fig. 1 link explicit | Fig. 1 drawn on the motivating circuit itself | todo (Phase 5): the new motivating example (Deutsch kickback + separable-bug case) must be Fig. 1's circuit. |

## Reviewer B (Reject)

| # | Point | Answer in the ICPC paper | Status |
|---|---|---|---|
| B1 | Novelty: dependence concepts already known; distinguish definitions, mechanisms, and guarantees from prior work | Related work plus a comparison table vs [27], static entanglement analysis, and Qiskit LightCone. Contributions stated modestly. | evidence done; paper text: Phase 5. The contribution is now validation of dependence definitions against a semantic ground truth (`FOUNDATIONS_REVIEW.md`, `PAPER_OUTLINE.md`), not a new edge type. |
| B2 | Def-use baseline is weak, not an accepted baseline; implementation choices may explain failures | RQ1: def-use presented as a pitfall. Primary baselines: light cone (cross-checked with Qiskit `LightCone`) and re-implemented [27]. | evidence done; paper text: Phase 5. Baselines: wire light cone, Qiskit `LightCone` (Deviations I-9, I-10), Yu & Zhao re-implementation; def-use reported as a pitfall (216/784 unsound). |
| B3 | Disentanglement is the hard part; RQ2 only reports overall size; only the repeated-CX example | RQ2 structure families (multipartite, interleaved, re-entangled, uncomputation) reported per family | evidence done; paper text: Phase 5. Structure families (`results/icpc/families`: 119 circuits), catalogue (24 entries), robustness (`rq2_robustness`, `rq2_robustness_lcq`). |
| B4 | Exact evaluation limited to ≤14 qubits / 220 gates; RQ5 structural only; end-to-end scalability unknown | RQ4 end-to-end time and memory (exists in corrected RQ5; extend with width/depth). Limits stated. | evidence done; paper text: Phase 5. Corpus L, 15–20 qubits (`results/icpc/corpus_l`: 39/55 completed); end-to-end cost (`results/icpc/cost`). |
| B5 | Q2: guarantees and limits for indirect/multipartite entanglement and inverse operations | §III "Guarantees and limits" box, plus RQ2 robustness to other inputs and parameters | evidence done; paper text: Phase 5. Guarantee stated as data: pruning holds at the given input only (H3: 26.6% of pruned pairs robust under Haar inputs); the light cone's soundness for every input is machine-checked (`isabelle/`). |
| B6 | No evidence slicing addresses developer needs; metrics self-defined; no link to fault localization, understanding, or maintenance | RQ3. Motivation cites the empirical study of quantum developers' debugging needs (arXiv 2506.17306). | evidence done; paper text: Phase 5. RQ3 debugging study as in A3. |
| B7 | If slicing is for efficiency, show end-to-end time/space savings; RQ5 excluded MI and simulation cost | RQ4, including pruning cost. Explicitly *not* claiming execution savings unless measured. | evidence done; paper text: Phase 5. RQ4 end-to-end time and peak memory including MI and re-simulation (`results/icpc/cost`). |
| B8 | Q1: concrete practical problems slicing solves beyond the paper's metrics | RQ3 plus a short Discussion "When to use which slicer" | evidence done; paper text: Phase 5. Answered by RQ3 (fault localization, LLM tasks) and Discussion guidance. |
| B9 | Artifact covered only RQ1–RQ3; fetch script only QASMBench | One `reproduce.sh` for every RQ; all corpora shipped or pinned (Phase 6) | partly. replication-v2 covers RQ1–RQ7 and ships the corpora; still missing: one ICPC `reproduce.sh`/`run_all.py` with `--quick`, PROVENANCE for the ICPC numbers (Phase 6). |
| B10 | Roadmap omits Sec. VI; truncated "a 95,"; QPDG/QSlice and baseline labels mixed | Phase 5 editorial checklist; one name per concept | todo (Phase 5): roadmap, no truncated sentences, consistent names (TQDG / light cone / S-* ids). |

## Reviewer C (Weak reject)

| # | Point | Answer in the ICPC paper | Status |
|---|---|---|---|
| C1 | Novelty incremental vs [27]; the difference is only the reduced-state criterion and separability pruning | Own this: the contribution *is* precision beyond the light cone, plus evidence of when it helps (RQ2, RQ3) | evidence done; paper text: Phase 5. As B1; RQ1 compares with [27] directly. |
| C2 | Q1: include [27] as a baseline | RQ1/RQ2 re-implementation of [27], with documented interpretation choices | evidence done; paper text: Phase 5. [27] re-implemented (`slicers/yuzhao.py`): sound 784/784, recall 1.000, 78.6% of the circuit. |
| C3 | Q3: classical slicing works if dependencies are defined both ways; reframe around how to define dependencies for controlled gates | Thesis in §I follows C exactly | evidence done; paper text: Phase 5. Thesis answers it: dependence must be defined symmetrically per gate (kickback) and the criterion must become joint; reachability itself is classical. |
| C4 | Q4: if a bug makes an entangled state separable, does pruning hide it? | RQ3 metric counting exactly this, plus the joint-qubit criterion as the remedy | evidence done; paper text: Phase 5. 769 units where pruning removes the faulty operation; the joint criterion S-qW recovers 691 (`results/icpc/rq3`). |
| C5 | Q2: developers write Qiskit, not OpenQASM; what about higher-level programs? | Source-line mapping (Phase 3, step 8; plan §7) used in RQ3 on Bugs4Q. Full srcSlice extension for Qiskit/OpenQASM is the tool-demo paper. | evidence done; paper text: Phase 5. Source map in Qiskit lines (`results/icpc/source_map`, Deviation I-11; cross-check 127/127 with the authors' slicer); full source-level slicing is the tool paper. |

## Rebuttal promises (as submitted on HotCRP)

| # | Promise | Where | Status |
|---|---|---|---|
| R1 | Reframe per Reviewer C | §I | evidence done; paper text: Phase 5. Reframed per Reviewer C (`PAPER_OUTLINE.md`). |
| R2 | Bidirectional cone becomes the primary baseline | RQ1/RQ2 | evidence done; paper text: Phase 5. The wire light cone is the primary baseline; Qiskit `LightCone` added. |
| R3 | Add a documented re-implementation of [27] | Phase 3, step 2 | evidence done; paper text: Phase 5. As C2. |
| R4 | Rename the graph to avoid confusion with [27] | e.g. TQDG | todo (Phase 5): rename the graph (e.g. TQDG) consistently. |
| R5 | State pruning limits: \|0…0⟩ input only; runtime check, not mechanized; exact re-simulation confines it to simulable sizes; non-unitary fallback; not minimal | §III limits box. RQ2 robustness tests the first limit directly. | evidence done; paper text: Phase 5. Each limit measured: input-specificity (H3), fallback on non-unitary circuits (§3.1), non-minimality (families: 212 sound-but-not-minimal S-q rows of 819), cost (RQ4). |
| R6 | Add multipartite and uncomputation examples | RQ2 structure families + one worked example in §III | evidence done; paper text: Phase 5. Families include GHZ/W partial uncompute, entangle–disentangle chains, interleaved indirect entanglement, U…U† (`families/generate.py`). |
| R7 | Report end-to-end cost including pruning | RQ4 | evidence done; paper text: Phase 5. As B7. |
| R8 | Superposition discussion | A1 | evidence done; paper text: Phase 5. As A1. |
| R9 | Joint-state criterion for the "lost entanglement" question | C4 + RQ2 criterion granularity | evidence done; paper text: Phase 5. S-qW joint criterion (`slicers/registry.py::qslice_set`); C-Q4 remedy result. |
| R10 | Qiskit source mapping as future work | C5 | evidence done; paper text: Phase 5. Source map done for the research paper; full mapping is the tool paper. |
| R11 | "We did not conduct a user study or debugging-task evaluation; the revision will state this and add a seeded-fault localization study." | RQ3 is this promise; it is mandatory. State plainly that there is no user study. | evidence done; paper text: Phase 5. Debugging-task evaluation now exists (RQ3); no user study — the paper must say so. |
| R12 | Consolidated artifact: one script, all corpora, pinned QASMBench, provenance doc | Already in replication-v2; extend in Phase 6 | partly. As B9. |
| R13 | Fix roadmap, "a 95,", naming, example-to-Fig. 1 link | B10, A6 | todo (Phase 5). As B10. |
| R14 | Correction 1: re-run RQ1–RQ5 with the Sec. III implementation | Done in `experiments/`; verify in Phase 1 | evidence done; paper text: Phase 5. RQ1–RQ4 regenerate byte for byte (Phase 1); all ICPC results come from the released code at logged commits (`experiments/logs/icpc/runs.log`). |
| R15 | Correction 2: forward completeness no longer by construction | Done (0.988 vs 1.000). Drop the claim as too small to matter. | evidence done; paper text: Phase 5. Forward completeness dropped as circular; replaced by the §2.1 ground-truth recall. |
| R16 | Correction 5: "regenerate the ablation (Table VI)" | Done (`rq4_ablation_rerun`); fix the 5 unsound pairs (Phase 3, step 3) | evidence done; paper text: Phase 5. Ablation re-run with the four-edge seeding fix on 962 pairs (`results/icpc/ablation_fixed`: QSlice-full SVR 0.5% → 0%). |
| R17 | Correction 3: RQ4/RQ7 used TVD, not fidelity; fix Table I | Ablation rerun uses fidelity. Hardware stays TVD and is labeled so. | evidence done; paper text: Phase 5. Every ICPC result is judged by the fidelity oracle. |
| R18 | Correction 4: recompute the RQ7 QAOA cases from the captured jobs, with the slice's actual register | **Not done yet.** Do it, or drop hardware. | done (2026-10-21; JOURNAL). 16/18 with the corrected rule. |
| R19 | Correction 5: withdraw the RQ6 claim; mechanize only causal-cone soundness | Done in `isabelle/QSliceSoundness.thy`; build it and word the claim exactly | evidence done; paper text: Phase 5. `isabelle/QSliceSoundness.thy` proves causal-cone soundness only (`cone_sound`, every input), no `sorry`/axioms. Paper: one sentence, never claim pruning is proved. |
| R20 | Report only results regenerated from the released code | Integrity rule 4 + Phase 6 final check | evidence done; paper text: Phase 5. Every number comes from `paper/numbers.tex` (`experiments/icpc/make_numbers.py`, 201 numbers, each with its source). |
