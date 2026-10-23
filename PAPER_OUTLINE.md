# ICPC 2027 Research Track: paper outline (for the author's review)

Written 2026-10-23, after Checkpoint B (`CHECKPOINT_B.md`) and the foundations review
(`FOUNDATIONS_REVIEW.md`). Author's decision: **split**. This research paper (abstract Oct 29, paper
Nov 5) establishes the correct quantum dependences and slicing criteria. The srcML/srcSlice extension
for Qiskit and OpenQASM becomes the Tool Demonstration paper (Nov 19). Every claim below names its
committed result. Nothing here is paper text yet.

## 1. Thesis and title

**Thesis.** Quantum program slicing has been proposed, but never defined against the semantics of
quantum programs. The one proposal (Yu & Zhao's QPDG) reuses the classical criterion (s, V) and
graph reachability. We define quantum dependence semantically and evaluate every candidate
definition against that ground truth. The results:
- reading gates classically is unsound;
- entanglement closure is sound but imprecise;
- one simple rule is sound, complete and input-independent;
- the classical single-variable criterion must become a joint-qubit criterion;
- extra precision beyond that rule either keeps soundness for every input (commutation) or holds
  only at one input (state-based pruning).

We then show what each choice does to a developer who is localizing a fault.

**Title options** (must differ from the ICSE preprint):
1. *What Does a Quantum Program Slice Depend On? Defining and Validating Quantum Dependences for Debugging*
2. *Quantum Program Slicing, Validated: Dependences, Criteria, and Their Cost for Fault Localization*
3. *Not Just Entanglement: Validating Quantum Dependence Definitions for Program Slicing*

## 2. Why this is a strong paper, not a weaker ICSE version

- **A gap named by the field's own roadmaps.**
  - Ye et al. (TOSEM 2026, p. 273:10) say "constructing, validating, and maintaining" QPDG-style
    models "remains challenging".
  - Murillo et al. (TOSEM 2025, p. 154:11) endorse the QPDG as one that "facilitates slicing" with
    no evaluation.
  - Sicilia et al. (Springer QSE book 2022, Ch. 10, pp. 198–203) note that reused classical
    constructs are "not validated". They list "Propose and validate constructs ... of quantum code
    structure" as an open need (RD_STR_2).
  - We do exactly this.
- **A rigorous method.** The study has:
  - a semantic ground truth that no slicer computes;
  - a pre-registered protocol with dated deviations;
  - an independent oracle;
  - a machine-checked theorem: light-cone soundness for every input
    (`isabelle/QSliceSoundness.thy`, `cone_sound`);
  - negative results reported in full.

  ICPC reviewers reward this kind of rigor.
- **Debugging evidence**, which all three ICSE reviewers asked for:
  - 5,688 seeded faults;
  - real Bugs4Q bugs;
  - an MBFL baseline;
  - LLM fault localization (ICPC's "comprehension in the era of LLMs" topic).
- **Every reviewer point is answered by a result** (Section 6 of this outline).

## 3. Contributions (claims, each with its evidence)

| # | Contribution | Evidence (committed) |
|---|---|---|
| C1 | **Semantic definitions.** Quantum dependence ("a change at operation o can change the criterion's state, for some input") and two slice properties: state preservation at an input, and dependence completeness. The criterion is generalized from one variable to a set of qubits (joint reduced state) | `icpc/influence.py`; PROTOCOL §2.1; 24-entry dependence catalogue (`results/icpc/catalogue`) |
| C2 | **The first validated comparison of quantum dependence definitions.** Six definitions on 784 (circuit, qubit) pairs (`results/icpc/rq1`, `rq1_lcq_remap`; `rq2_robustness`, `rq2_robustness_lcq`). See the table below | the files named in each row |
| C3 | **Why the classical criterion fails, and the fix.** A single-qubit criterion loses the faulty gate when a bug changes correlations: 769 of 5,688 seeded faults. The joint criterion recovers 691 | `results/icpc/rq3` |
| C4 | **Debugging study.** Fault containment, inspection cost, MBFL and LLM localization for each definition | `rq3`, `rq3_bugs4q`, `mbfl`, `results/llm` |
| C5 | **Cost.** The rule is near-free; state-based pruning grows with simulation | `results/icpc/cost` |

The six definitions compared in C2:

| Definition | Result |
|---|---|
| Classical def-use per qubit | unsound on 216 pairs (phase kickback) |
| Yu & Zhao QPDG reachability | sound, recall 1.0, but 79% of the circuit |
| Wire rule: a gate reads and writes all its qubits | sound, recall 1.0, robust on every input regime, 70% |
| Commutation (Qiskit `LightCone`) | sound, robust 100% on random inputs, recall 0.93 |
| Four-edge graph | sound only after a seeding fix; depends on edge orientation |
| State-based pruning (QSlice) | 23% smaller, but robust on 26.6% of pruned pairs under random inputs; recall 0.81 |

QSlice's role is stated plainly: an **input-specific** slicer (state-based pruning at a given
input), with its measured benefits (size) and costs (robustness, containment). It is not presented
as a general slice.

## 4. Structure (10 pages + 2 of references)

1. **Introduction (1 p).**
   - Motivation: comprehension and debugging are hard (Ali et al. CACM 2022 p. 88; d'Aloisio et al.
     ESEM 2024 p. 475; Murillo et al. p. 154:10).
   - The gap: slicing is proposed, never validated.
   - The thesis and contributions C1–C5, phrased modestly.
2. **Motivating example (0.75 p).** Phase kickback in Deutsch's algorithm. The oracle leaves the top
   qubit "unchanged" in the classical reading (Combarro, QSE book Ch. 1, p. 18), yet the answer is
   read from it. So classical def-use and the (s, V) criterion drop the oracle. A second panel shows
   a bug that makes two qubits separable, where a single-qubit criterion drops the faulty gate (the
   C-Q4 case) and a joint criterion keeps it. Replaces the ICSE Bell example (A6: tie it to Fig. 1).
3. **Quantum dependence, defined (1.5 p).**
   - Semantic dependence; the two slice properties; the joint criterion.
   - The candidate definitions as precise rules: def-use, QPDG per Yu & Zhao (our documented
     reading), wire rule, commutation, state-based pruning.
   - The light-cone theorem (machine-checked).
   - A superposition paragraph (A-Q1).
4. **Study design (1 p).** Pre-registration, corpora (corpus A, structure families, corpus L,
   Bugs4Q), oracle, ground truth, deviations, statistics.
5. **Results (4 p).**
   - **RQ1: Which definitions are sound and complete?** Def-use, QPDG, wire rule, Qiskit
     `LightCone`, four-edge; the catalogue; families.
   - **RQ2: How much precision beyond the wire rule is safe?** Commutation vs state-based pruning:
     size, robustness under three input regimes, corpus L.
   - **RQ3: What does each choice do to fault localization?** Containment, inspection cost, C-Q4
     and the joint criterion, Bugs4Q, MBFL, LLM T1/T2.
   - **RQ4: What does it cost?** End-to-end time and memory vs width and depth.
6. **Discussion (0.75 p).**
   - Guidance for tool builders, e.g. to the authors of QPDG-based slicers: use the wire rule, the
     joint criterion, and commutation, never syntactic entanglement closure.
   - Hardware and noise (A-Q2).
   - The source level: the tool paper.
7. **Threats (0.5 p).**
8. **Related work (0.75 p).**
   - Yu & Zhao QPDG; Xia & Zhao static entanglement analysis (**to read**).
   - Qiskit `LightCone` and light-cone reduction in simulation.
   - Static entanglement analyses; Zhao's ESEM 2026 entanglement metrics.
   - Classical slicing: Weiser; dynamic slicing (Korel & Laski).
   - Muskit/QMutPy and the QuMu fault model (QSE book Ch. 9).
   - Bugs4Q; QBugs.
   - KDM/UML modernization that models qubits as variables (QSE book Ch. 11, pp. 221–225: prior
     art for the per-qubit view).
   - srcML for quantum languages (Behler et al. QCE 2024; IEEE Software 2025).
9. **Conclusion (0.25 p).**

## 5. What is still standing (from `ICPC_QSLICE_PLAN.md` and the reading)

**Read 2026-10-23: Xia & Zhao, "Static Entanglement Analysis of Quantum Programs" (arXiv
2304.05049; Q-SE 2023).** It is an entanglement analysis for Q#, not slicing. It tracks per-qubit
0/1/superposition states, adds an entanglement edge when a controlled gate has a superposition
control, and removes edges for exact inverse pairs ("uncomputation"). It has no tool and no
evaluation (§5, §7), and its soundness argument is informal (§4.5). Positioning, now a headline
claim: **quantum dependence is not entanglement.**
- **Dependence without entanglement:** phase kickback, where the state stays a product state.
  Their rule that phase gates on a control "do not change the control relationship" (p. 4) is
  blind to it.
- **Entanglement without dependence:** by no-signaling, a later gate on an entangled partner cannot
  change the criterion's unconditional reduced state. This contradicts the QPDG's entanglement
  edge (Yu & Zhao, p. 48). It matches RQ1: the wire rule with no entanglement edges is sound on
  784/784. Correlations do change, which the joint criterion captures.
- State the no-signaling point carefully (unconditional state vs post-measurement outcomes) and
  check it against the catalogue.
- Before citing its claim that entanglement is "transitive" (§2.2, after Perdrix 2007), check
  Perdrix's definition.
- New related work (entanglement analyses, none of them slicing):
  - Perdrix, ENTCS 2007 and SAS 2008;
  - ScaffCC (JavadiAbhari et al., 2015);
  - Honda (arXiv 1511.01572);
  - Prost & Zerrari (UC 2009);
  - Twist (Yuan et al., POPL 2022).

**Must do before Nov 5:**
- [ ] Check Shen et al. Q-SE 2025 (state-based analyses) and Luo & Zhao JSS 2025. Get the published
  Q-SE 2023 version of Xia & Zhao (DOI 10.1109/Q-SE59154.2023.00013) for the citation.
- [ ] Re-read our `slicers/yuzhao.py` interpretation log against the QPDG paper's text. The QPDG
  paper's Listing 3 (`x(0); cx(0,1)`, p. 51) calls a product state entangled. Fix the exact wording
  of our "documented reading".
- [ ] Qiskit source map for Bugs4Q in lines (plan Phase 3 step 8; cutoff Oct 31). It reports RQ3 in
  Qiskit source lines and bridges to the tool paper.
- [ ] `run_all.py`, `numbers.tex`, `results/run_metadata.json` (Phase 4). Every number in the paper
  comes from `numbers.tex`.
- [ ] Update `REVIEW_CHECKLIST.md`: most rows are now covered by results.
- [ ] Paper text fixes carried over: D10 (qiskit 2.3.0, no Aer); B10/R13 (roadmap, naming); rename
  the graph (R4); AI-use disclosure; anonymity pass.
- [ ] Artifact (Phase 6): one-command reproduction, `--quick`, `PROVENANCE.md`, anonymous link.
- [ ] Phase 7: independent pre-submission review by a fresh agent.

**Author decisions still open:**
- H5's primary inspection measure (size; EXAM alongside).
- Title.
- The tool paper's anonymity conflict (plan §7): it is non-anonymous and its notification date
  matches this paper's. Check the ICPC policy or ask the chairs.

## 6. Reviewer points and where the paper answers them

| Point | Answer in the paper |
|---|---|
| A-Q1 superposition | §3 paragraph; graph size depends on operations only (RQ4) |
| A-Q2 hardware, noise | Discussion: hardware 16/18 corrected; noisy simulation |
| A3, B6, B8 practical value | RQ3 debugging study (seeded, Bugs4Q, MBFL, LLM) |
| A2, B4, B7 depth and end-to-end cost | RQ4 (depth sweep, corpus L) |
| B1, C1 novelty vs known concepts and [27] | The contribution is validation and definitions, not a new edge type; RQ1 compares with [27] directly |
| B2, C2 weak baseline; include [27] | Baselines: QPDG [27], wire rule, Qiskit `LightCone`; def-use is a pitfall |
| B3, B5 disentanglement, multipartite, inverse operations | Structure families; catalogue; robustness |
| C3 different in principle? | Yes in two ways (kickback, and the joint criterion); no in the reachability machinery. The thesis answers C3 directly |
| C4 pruning hides bugs? | RQ3: 769 cases; the joint criterion recovers 691 |
| C5 Qiskit, not OpenQASM | Source map in RQ3 (Bugs4Q in lines); the tool paper |
| B9 artifact | One-command artifact; all corpora pinned |
| Corrections 1–5 | No ICSE number reused; all regenerated; Isabelle limited to the light cone |

## 7. The Tool Demonstration paper (Nov 19), for later

"srcSlice-Q": source-level slicing for Qiskit (Python srcSlice plus a Qiskit effect table
implementing the validated wire rule) and OpenQASM (QStatic, Behler et al.), with the joint
criterion. It can reuse the capstone Quantum Slicer's front end and Bugs4Q benchmark page. Check
first whether the capstone `DataQubitRule` treats `cx` as writing only the target; that is the
def-use pitfall of RQ1. Built Nov 6–18.
