# Review checklist: every ICSE reviewer point and rebuttal promise

Source: `ICPC_QSLICE_PLAN.md` §4a; full text in `~/Projects/RP/Docs/REVIEWS_AND_REBUTTAL.md`.

Every row must end as **done** or **declined + reason**, and a declined row's reason must appear in the
paper. Phase 7 checks this file against the PDF.

Status values:
- **todo**;
- **partly** (what exists and what is missing);
- **done** (where the evidence is);
- **declined** (the reason).

Last updated: Phase 1 (2026-10-20). Evidence for "done" and "partly" is in `VERIFY_CORRECTED.md` and
`phase1_logs/`.

## Reviewer A (Weak reject)

| # | Point | Answer in the ICPC paper | Status |
|---|---|---|---|
| A1 | Q1: how superposition affects the dependence graph; could it "explode"? | §III paragraph: the graph is built from operations and qubits, never amplitudes; it grows with operation count. The exponential cost is only in the pruning check, measured in RQ4. | todo. Phase 1 confirms the premise in code: `qslice/qdg.py` builds nodes and edges from `qc.data` only; amplitudes appear only in `entanglement_pruned_slice`. Measured in `PROTOCOL_ICPC.md` §8 (graph size vs operations, width and depth). |
| A2 | Larger depth vs performance (not just qubit count) | RQ2 depth sweep at fixed width; RQ4 cost vs depth | todo |
| A3 | Main weakness: no demonstrated practical use (debugging) | RQ3 fault-localization study | todo |
| A4 | Q2: debugging on real hardware; noise affecting analysis; a small hardware experiment | Discussion: slices are static, and noise affects only their execution. The hardware PoC is recomputed with rebuttal Correction 4/6 applied, with phase-blind TVD stated. | todo. `hardware/regenerate.py` still gives the uncorrected 16/18 (see R18). Planned: `PROTOCOL_ICPC.md` §7.1 (Correction 4) and §7.2 (noisy density-matrix simulation of slice vs full). |
| A5 | "A bit dense at times" | Plainer prose, one running example, fewer RQs | todo |
| A6 | Make the motivating example ↔ Fig. 1 link explicit | Fig. 1 drawn on the motivating circuit itself | todo |

## Reviewer B (Reject)

| # | Point | Answer in the ICPC paper | Status |
|---|---|---|---|
| B1 | Novelty: dependence concepts already known; distinguish definitions, mechanisms, and guarantees from prior work | Related work plus a comparison table vs [27], static entanglement analysis, and Qiskit LightCone. Contributions stated modestly. | todo |
| B2 | Def-use baseline is weak, not an accepted baseline; implementation choices may explain failures | RQ1: def-use presented as a pitfall. Primary baselines: light cone (cross-checked with Qiskit `LightCone`) and re-implemented [27]. | partly. The genuine def-use port and the wire light cone exist and were verified (D3, D4). Still missing: the LightCone cross-check and [27]. |
| B3 | Disentanglement is the hard part; RQ2 only reports overall size; only the repeated-CX example | RQ2 structure families (multipartite, interleaved, re-entangled, uncomputation) reported per family | todo |
| B4 | Exact evaluation limited to ≤14 qubits / 220 gates; RQ5 structural only; end-to-end scalability unknown | RQ4 end-to-end time and memory (exists in corrected RQ5; extend with width/depth). Limits stated. | partly. Corrected RQ5 part E measures end-to-end cost (median 43 ms, at most 214 MB); see `phase1_logs/regenerate_with_rq5.log`. Still missing: width/depth scaling (`PROTOCOL_ICPC.md` §8), larger real circuits at 15–20 qubits and ≤1,000 instructions (corpus L, §3.5), and stated limits. |
| B5 | Q2: guarantees and limits for indirect/multipartite entanglement and inverse operations | §III "Guarantees and limits" box, plus RQ2 robustness to other inputs and parameters | todo |
| B6 | No evidence slicing addresses developer needs; metrics self-defined; no link to fault localization, understanding, or maintenance | RQ3. Motivation cites the empirical study of quantum developers' debugging needs (arXiv 2506.17306). | todo |
| B7 | If slicing is for efficiency, show end-to-end time/space savings; RQ5 excluded MI and simulation cost | RQ4, including pruning cost. Explicitly *not* claiming execution savings unless measured. | partly. Corrected RQ5 part E includes MI and verification cost. Still missing: the paper wording and the light-cone comparison. |
| B8 | Q1: concrete practical problems slicing solves beyond the paper's metrics | RQ3 plus a short Discussion "When to use which slicer" | todo |
| B9 | Artifact covered only RQ1–RQ3; fetch script only QASMBench | One `reproduce.sh` for every RQ; all corpora shipped or pinned (Phase 6) | partly. replication-v2's `reproduce.sh` covers RQ1–RQ7, ships MQT Bench and VeriQBench, and pins QASMBench; all regenerate in Phase 1. Still missing: the ICPC experiments, `--quick` timing, corpus license notices (see `DATA_SOURCES.md`), and a pinned hardware env. |
| B10 | Roadmap omits Sec. VI; truncated "a 95,"; QPDG/QSlice and baseline labels mixed | Phase 5 editorial checklist; one name per concept | todo |

## Reviewer C (Weak reject)

| # | Point | Answer in the ICPC paper | Status |
|---|---|---|---|
| C1 | Novelty incremental vs [27]; the difference is only the reduced-state criterion and separability pruning | Own this: the contribution *is* precision beyond the light cone, plus evidence of when it helps (RQ2, RQ3) | todo |
| C2 | Q1: include [27] as a baseline | RQ1/RQ2 re-implementation of [27], with documented interpretation choices | todo |
| C3 | Q3: classical slicing works if dependencies are defined both ways; reframe around how to define dependencies for controlled gates | Thesis in §I follows C exactly | todo |
| C4 | Q4: if a bug makes an entangled state separable, does pruning hide it? | RQ3 metric counting exactly this, plus the joint-qubit criterion as the remedy | todo |
| C5 | Q2: developers write Qiskit, not OpenQASM; what about higher-level programs? | Source-line mapping (Phase 3, step 8; plan §7) used in RQ3 on Bugs4Q. Full srcSlice extension for Qiskit/OpenQASM is the tool-demo paper. | todo |

## Rebuttal promises (as submitted on HotCRP)

| # | Promise | Where | Status |
|---|---|---|---|
| R1 | Reframe per Reviewer C | §I | todo |
| R2 | Bidirectional cone becomes the primary baseline | RQ1/RQ2 | partly. The corrected run's "causal" slicer is the wire light cone (D4 verified). Still missing: the paper text and the Qiskit `LightCone` cross-check. |
| R3 | Add a documented re-implementation of [27] | Phase 3, step 2 | todo |
| R4 | Rename the graph to avoid confusion with [27] | e.g. TQDG | todo |
| R5 | State pruning limits: \|0…0⟩ input only; runtime check, not mechanized; exact re-simulation confines it to simulable sizes; non-unitary fallback; not minimal | §III limits box. RQ2 robustness tests the first limit directly. | todo. Phase 1 confirms each limit in code (`qdg.py` `entanglement_pruned_slice`: \|0…0⟩ start, Statevector re-simulation, non-unitary fallback, greedy and not minimal). Measured: robustness (§3.2), fallback count (§3.1), non-minimality (§3.3). |
| R6 | Add multipartite and uncomputation examples | RQ2 structure families + one worked example in §III | todo |
| R7 | Report end-to-end cost including pruning | RQ4 | partly. Measured in corrected RQ5 part E (regenerated in Phase 1, deterministic columns only). Still missing: the paper text. |
| R8 | Superposition discussion | A1 | todo |
| R9 | Joint-state criterion for the "lost entanglement" question | C4 + RQ2 criterion granularity | todo |
| R10 | Qiskit source mapping as future work | C5 | todo |
| R11 | "We did not conduct a user study or debugging-task evaluation; the revision will state this and add a seeded-fault localization study." | RQ3 is this promise; it is mandatory. State plainly that there is no user study. | todo |
| R12 | Consolidated artifact: one script, all corpora, pinned QASMBench, provenance doc | Already in replication-v2; extend in Phase 6 | partly (see B9) |
| R13 | Fix roadmap, "a 95,", naming, example-to-Fig. 1 link | B10, A6 | todo |
| R14 | Correction 1: re-run RQ1–RQ5 with the Sec. III implementation | Done in `experiments/`; verify in Phase 1 | partly. RQ1–RQ4 regenerate byte for byte from the released code (16/16 IDENTICAL, `phase1_logs/regenerate_rq1_rq4.log`); RQ5 regenerates on its deterministic columns (`phase1_logs/regenerate_with_rq5.log`). Still missing: the paper text. |
| R15 | Correction 2: forward completeness no longer by construction | Done (0.988 vs 1.000). Drop the claim as too small to matter. | partly. The measurement is fixed (D6 verified; regenerated). Still missing: dropping the claim from the paper. |
| R16 | Correction 5: "regenerate the ablation (Table VI)" | Done (`rq4_ablation_rerun`); fix the 5 unsound pairs (Phase 3, step 3) | partly. The rerun regenerates (see `phase1_logs/regenerate_rq1_rq4.log`); the 5 unsound four-edge pairs are still open. |
| R17 | Correction 3: RQ4/RQ7 used TVD, not fidelity; fix Table I | Ablation rerun uses fidelity. Hardware stays TVD and is labeled so. | partly. The ablation rerun judges with the exact oracle's fidelity (`rq4_ablation_rerun/run.py`). Still missing: the hardware TVD label in the paper and the Table I fix. |
| R18 | Correction 4: recompute the RQ7 QAOA cases from the captured jobs, with the slice's actual register | **Not done yet.** Do it, or drop hardware. | todo. `hardware/regenerate.py` reproduces the uncorrected 16/18. |
| R19 | Correction 5: withdraw the RQ6 claim; mechanize only causal-cone soundness | Done in `isabelle/QSliceSoundness.thy`; build it and word the claim exactly | partly. Builds with Isabelle2025-2 (exit 0); no `sorry`, `oops` or `axiomatization` (`phase1_logs/isabelle_build.log`). Still missing: the exact claim wording in the paper. |
| R20 | Report only results regenerated from the released code | Integrity rule 4 + Phase 6 final check | todo |
