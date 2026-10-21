# Paper blueprint for the ICPC 2027 Research Track

This is the design for a more robust, clearer and more professional version of the QSlice paper. It
draws on three sources, read in full on 2026-10-21:
- the three ICSE reviews and the rebuttal;
- `ICPC_QSLICE_PLAN.md`;
- `Docs/ICPC-2026/` (8 papers) and its `Book/` folder (Serrano, Pérez-Castillo and Piattini, eds.,
  *Quantum Software Engineering*, Springer 2022, 16 chapters).

Every page reference below is checked. Nothing here changes the frozen experiments. Changes to
`PROTOCOL_ICPC.md` are listed in §6 and need the author's approval before the protocol is frozen.

---

## 1. What the reading changes

**1.1 The field's flagship roadmaps credit QPDG with slicing that has never been evaluated.**
- **Who credits it:**
  - Murillo et al. (TOSEM 2025) say QPDG "facilitates slicing and dependency analysis, aiding in the
    debugging, testing, and understanding of quantum programs" (p. 154:11).
  - The LLM-for-QSE roadmap (TOSEM 2026, Zhao's group) says the same (p. 273:7).
- **What [27] actually is** (Yu & Zhao, Q-SE 2025, pp. 48–55, read in full):
  - a source-level model whose nodes are Qiskit *statements*;
  - four informal quantum dependence kinds;
  - reachability slicing;
  - no algorithm, no implementation and no evaluation ("Experimental studies are planned", p. 55).
- **The opening:** being the first to *define dependences semantically and test them*. That beats
  claiming a better slicer, and it answers C1/C2/B1 head-on.

**1.2 Three of [27]'s four quantum dependence kinds do not hold up under a semantic test.**
- **Entanglement dependence** is defined by measurement correlation: "the measurement of one qubit
  directly impacts the state of another" (p. 48).
  - No-signalling says the opposite: a local operation, including a non-selective measurement, on a
    partner never changes q's reduced state.
  - The same misconception appears in Murillo et al. (p. 154:5, "Altering the state of one qubit
    immediately changes the state of the other") and in the book (Ch. 5, p. 94).
  - **Our no-signalling negatives (catalogue K6, K11, K15) test this directly.**
- **No-cloning dependence** (Listing 3) is ordinary control→target flow through a CNOT.
- **Temporal dependence** is about coherence time, i.e. noise. Its example uses Python's
  `time.sleep`, which is not part of the circuit.
- **Measurement dependence** (measure → `c_if`) is real. It is our feedback category.
- **[27] never mentions phase kickback**, the dependence Reviewer C raised. The book's Deutsch
  derivation (Ch. 1, pp. 18–19) is the canonical case: the control acquires the information as a
  phase, with no entanglement. Ch. 5 (p. 92) even misattributes the Deutsch algorithm to entanglement.

**1.3 The community itself says debugging is open.**
- "the debugging, testing, and verification of quantum circuits are still an open research question"
  (Book Ch. 4, p. 72).
- Debugging challenges include "an inability to directly monitor quantum software states … a lack of
  best practices" and "tailoring classical debugging tactics … to debug programs on quantum
  simulators" (Ali, Yue and Abreu, CACM 2022, p. 88).
- "Directly reading intermediate states destroys superposition … Direct breakpoints not possible"
  (ibid., Table 2, p. 87).
- Quantum errors "are non-local. Their source may be far from where the error manifests" (LLM
  roadmap, pp. 273:16–17).

A sound static slice narrows where to look without measuring anything. That is the comprehension
and debugging value the ICSE reviewers said was missing.

**1.4 The LLM era gives a concrete, measurable hook (ICPC topic).**
- OpenQASM "can become exceedingly long … exceeding the context window … diluting the model's
  attention" (LLM roadmap, p. 273:11).
- LLMs reach "less than 40%" accuracy on quantum tasks (QuanBench, p. 273:11).
- "precise fault locations … can dramatically improve the success rate" of repair (p. 273:23).
- Labelled semantic data for quantum analysis is missing (pp. 273:11–12).
- d'Aloisio et al. (ESEM 2024) show that context improves LLM explanations of OpenQASM, but use a
  subjective 1–5 score (Krippendorff α = 0.47) on 7 programs.
- **Our slices and our semantic ground truth give an objective version of that question.**

**1.5 The fault-localization study must be rebuilt on correct foundations.**
- **Operator provenance:**
  - Muskit (ASE 2021) has gate add/remove/replace.
  - QMutPy (ICSE 2022) adds measurement insertion and deletion.
  - Our "qubit-operand swap", "control/target swap" and "parameter perturbation" are **not**
    Muskit/QMutPy operators.
  - QuMu (Book Ch. 9, Table 9.1, pp. 178–180) has "Swap controls and controlled qubits",
    "Control gate removal" and an entanglement-fault family.
- **Phase-only mutants:** "injured" mutants change phase but not measurement statistics (Ch. 9,
  pp. 185–186). We need two oracles.
- **Closest prior work:** mutation-based fault localization for quantum programs (Ishimoto et al.,
  EASE 2025, arXiv:2505.09059) reports a median EXAM of 1.2% on seeded faults and 19.4% on 23 real
  faults. It is the closest RQ3 work, and we must report the same metric.
- **Scope of real bugs:** many Bugs4Q bugs are API or classical bugs that no gate-level slice can
  localize, e.g. Mao et al.'s `RealAmplitudes` missing `.decompose()` (Q-SE 2025, p. 6). Bugs4Q must
  be split by stage (input / operation / output, after Huang and Martonosi, Ch. 9, pp. 169–170).

**1.6 Our terminology must be more precise than the field's.**
- The book never defines reduced state, partial trace, no-signalling, light cone, kickback or
  mid-circuit measurement. Its own chapters contradict each other on CNOT and separability (Ch. 1
  p. 16 vs Ch. 5 p. 92). Ch. 7 (p. 124) calls a density matrix "a projector", which is true only for
  pure states.
- **Define everything ourselves, citing Nielsen & Chuang.**
- **Scope the criterion exactly:** the slice preserves the **unconditional** ρ_q, which is generally
  mixed. That fixes the statistics of every measurement on q alone. It does not preserve joint or
  post-selected statistics (Book Ch. 1, pp. 8–13; developers read joint histograms).
- A partner measurement is a no-signalling negative only for the unconditional state.

---

## 2. Thesis, title, contributions

**Thesis** (following Reviewer C):
- Quantum slicing does not need a new philosophy. It needs dependences defined by what can actually
  change the criterion qubit's state.
- We give that definition, test every existing dependence notion against it, and show what a correct
  slicer buys a developer when localizing faults, both by hand and with an LLM.

**Working titles** (they must differ from any preprint):
- *What Must a Quantum Slicer Track? Semantic Dependences for Comprehending and Debugging Quantum
  Circuits*
- *Beyond Def-Use and the Light Cone: Testing Dependence Definitions for Quantum Circuit Slicing*

**Contributions**, stated modestly:
1. A **semantic definition of quantum dependence** for slicing: influence on the unconditional ρ_q,
   tested by perturbation. It is the quantum analogue of Podgurski and Clarke's semantic dependence,
   which [27] itself cites (ref. [12] there).
2. A **dependence catalogue and taxonomy** (same-wire, written-operand, kickback, measurement/
   feedback, and the no-signalling negatives). Every dependence notion (def-use, [27] operationalized,
   the light cone, Qiskit `LightCone`, QSlice) is tested against it on 784 benchmark pairs and 17
   golden circuits.
3. **Precision beyond the light cone, and its limits:** QSlice slices are 23% smaller at |0…0⟩
   (existing result). Robustness to other inputs and parameters, the structure families, and
   multi-qubit criteria show when that holds.
4. **Debugging evidence:** fault containment and inspection cost (EXAM) on seeded faults with
   provenance-labelled operators and on circuit-level Bugs4Q bugs, compared with mutation-based fault
   localization. Plus the C-Q4 count: how often pruning hides the bug, and the remedy of a joint
   criterion.
5. **LLM-era comprehension:**
   - (a) Does an LLM know which operations affect a qubit? Its answers are scored against the
     ground truth.
   - (b) Does giving it a sound slice instead of the full circuit improve its fault localization?
6. A **replication package** with one script, three pinned corpora and per-claim provenance (already
   largely in place).

**Things we do not claim:**
- execution-time savings on hardware;
- that pruning is proved;
- any user study (rebuttal R11);
- "first ever".

---

## 3. Research questions (four, fitting in 10 pages)

| RQ | Question | Main evidence | Reviewer points |
|---|---|---|---|
| **RQ1** Dependence | Which dependence definitions capture what really affects a qubit? | Semantic-dependence ground truth (recall and precision per slicer, misses by kind); catalogue table; invalid rate on 784 pairs; LightCone cross-check; four-edge fix | C3, C1, C2, B1, B2, R2, R3, R16 |
| **RQ2** Precision and limits | How much smaller than the light cone can a sound slice be, and when does it stay sound? | Size (H2); robustness (H3); structure families; criterion size; fallback count; corpus L (15–20 qubits) | B3, B5, A2, B4, R5, R6, R9 |
| **RQ3** Debugging | Do slices help localize faults, by hand and with an LLM? | Containment, inspection cost and EXAM on mutants and Bugs4Q; MBFL comparison; C-Q4 + joint remedy; LLM localization and dependence questions | A3, B6, B8, C4, C5, R11 |
| **RQ4** Cost | What does a correct slicer cost? | End-to-end time, memory and graph size vs width and depth; structural build on 1,124 circuits | B4, B7, A1, R7 |

Hardware and noise go in the Discussion: Correction 4 recomputed, and the noisy-simulation study.

---

## 4. Paper structure (IEEE conference, 10 pages + 2 of references)

| § | Content | Pages |
|---|---|---|
| I Intro | The debugging-without-breakpoints problem (§1.3 quotes); why def-use fails and the light cone is safe but blunt; Reviewer C's framing; RQs; contributions; an explicit "no user study" sentence | 1.0 |
| II Background and running example | The circuit model; ρ_q and the partial trace; no-signalling; measurement and feedback; kickback, using **one running circuit** that contains a kickback, an entangle–disentangle and a feedback correction. It is also Fig. 1. A box titled "Three misconceptions our definitions rule out" (entanglement as a signalling channel; CNOT as control→target only; partner measurement as influence), sourced neutrally. | 1.25 |
| III Dependences for slicing | Def. 1, semantic dependence; Def. 2, slice soundness (unconditional ρ_q, and ρ_W for sets); the dependence kinds; four slicers as dependence definitions: def-use, [27] operationalized (with its interpretation log), the light cone with classical control, and QSlice (light cone + MI nomination + exact check). A "Guarantees and limits" box: light-cone soundness machine-checked *relative to two no-signalling assumptions* (Isabelle; the quantum instance is not mechanized); pruning checked at run time only, \|0…0⟩-specific unless RQ2 shows otherwise, not minimal, falls back on dynamic circuits. One superposition paragraph (A1). | 1.5 |
| IV Study design | Pre-registration (frozen commits, deviations); corpora A, B, L, families; the oracle (independent, validated against `Statevector`); the ground-truth procedure; faults and oracles; the LLM protocol; statistics (Holm; effect sizes first) | 1.25 |
| V Results | RQ1 (1.0), RQ2 (1.0), RQ3 (1.0), RQ4 (0.4) | 3.4 |
| VI Discussion | When to use which slicer (practical guidance); noise and hardware; from circuits to Qiskit source lines (source map, srcSlice outlook); implications for tool builders and LLM assistants | 0.7 |
| VII Threats | Construct (ρ_q vs joint statistics; tolerance; ideal simulator); internal (implementation, prompt sensitivity); external (≤20 qubits, OpenQASM 2, logical vs transpiled circuits, hybrid and variational programs, Qiskit API churn, library abstractions such as `TwoLocal` that expand one line into many gates); conclusion (multiple testing) | 0.5 |
| VIII Related work | Classical slicing (Weiser; Ferrante; Horwitz; Podgurski–Clarke); quantum dependence ([27]; Xia & Zhao entanglement analysis; LintQ/QChecker); light-cone use in compilation and simulation; quantum debugging (Miranskyy; Metwalli; Sato–Katsube; Huang–Martonosi; Proq); mutation and MBFL (Muskit; QMutPy; QuMu; Ishimoto et al.); LLMs for quantum code (d'Aloisio; repair by Guo et al.); comprehension metrics (Cruz-Lemus understandability) | 0.5 |
| IX Conclusion | | 0.25 |

---

## 5. Evaluation design: what makes it robust

### 5.1 RQ1: ground truth before metrics
- **Semantic dependence by perturbation:** 11 inputs × 2 perturbations, with measurement outcomes
  flipped classically. Already in `PROTOCOL_ICPC.md` §2.1.
- **The catalogue's expected outcomes are committed before any run (§2.2).** Add the textbook
  circuits as named entries: Bell, **Deutsch** (kickback without entanglement), GHZ, and
  teleportation (the classical wire carries the dependence; without the corrections, Bob's
  unconditional state does not depend on ψ).
- **[27] operationalized** with a decision log. Each of its four kinds is mapped to an edge rule or
  documented as non-operational (no-cloning, temporal). The catalogue then shows where its
  entanglement rule over-includes (K6, K11, K15) and that it lacks kickback.

### 5.2 RQ2: robustness decides the framing
- H3 is already pre-registered (pair robustness under Haar product inputs ≥ 0.95).
- The book's lifecycle chapter adds a strong justification: circuits are written input-independent
  and state preparation "is encoded in the next phase by prepending a suited state preparation
  circuit" (Ch. 4, p. 72). A slice computed at |0…0⟩ is therefore only useful if it survives other
  inputs.
- **Add covariates** (Ch. 10, pp. 197–198): width, depth, gate count, two-qubit count, distinct
  gates, and width × depth. Report whether QSlice's gain over the light cone is explained by depth or
  entanglement structure alone.

### 5.3 RQ3: a fault-localization study reviewers will accept
- **Operators, with a provenance column:**
  - Muskit: gate insert, delete, replace;
  - QMutPy: plus measurement insert and delete;
  - QuMu: swap controls and targets, control-gate removal (e.g. CCX→CX, CX→X), and the
    entanglement-fault family (force unentanglement, entanglement corruption, wrong entanglement
    initialization);
  - ours: parameter perturbation, labelled as such.
- **Two oracles**, both computed exactly:
  - (a) the Z-basis distribution, which is what a developer sees;
  - (b) the criterion's ρ_q.

  Classify each mutant as **killed / injured (phase only) / alive**, after QuMu (Ch. 9,
  pp. 183–186). Report the results under each oracle.
- **Equivalent mutants:** exact unitary equivalence up to global phase (or QCEC, Ch. 12, p. 236)
  plus our random-input check. Report how many were removed per operator.
- **Bugs4Q:**
  - classify every bug by stage (input / operation / output) and as circuit-semantic or API/classical;
  - slice only circuit-semantic bugs, and report the fraction;
  - the fault site is the instruction diff between the buggy and fixed circuits.
  - Show the `ccx(0,1,2)` → `ccx(2,1,0)` bug (LLM roadmap, Fig. 2, p. 273:20) as a worked example:
    the bug is exactly about which wire is "read" and which is "written".
- **Baselines:**
  - the full circuit;
  - a **random subset of equal size** (the trivial-baseline habit, after Mao et al.);
  - def-use, the light cone, [27] and QSlice;
  - **MBFL** (Ishimoto et al.): either reproduce their QMutPy-based ranking on our faults, or report
    EXAM on the same scale and cite their numbers. The strongest version is "slice-filtered MBFL",
    i.e. MBFL ranking restricted to the slice.
- **Metrics:** containment, slice size, and EXAM computed the way Ishimoto et al. do (fraction of
  code examined), so the numbers are comparable.
- **Seeded vs real faults:** answer the realism threat (Murillo et al., p. 154:14) by reporting
  Bugs4Q next to the mutants, and the coupling-effect framing (Ch. 9, p. 176).

### 5.4 RQ3b: LLM localization and dependence questions (make it core)
Two tasks, both with **objective** answers. This is what d'Aloisio et al. lacked.
- **T1, the dependence question:**
  - Prompt: "Which operations of this circuit can affect the final state of qubit q? List indices."
  - Score: precision and recall against the semantic ground truth.
  - The question this answers: *do LLMs understand quantum dependences?* It feeds back into RQ1.
  - It is cheap, novel and very ICPC.
- **T2, localization:**
  - Inputs: buggy circuit + observed-wrong qubit, given as (i) the full circuit, (ii) the light-cone
    slice, (iii) the QSlice slice, (iv) the def-use slice as a negative control.
  - Scoring: top-1/top-3 hit on the fault site.
- **Design**, after d'Aloisio:
  - at least 3 models, including one small open model; fixed versions;
  - temperature reported (0 for determinism, plus one sampled setting);
  - 3 runs;
  - context prompt variants (none vs algorithm name + qubit count, reusing their prompt);
  - a held-out set;
  - every prompt and output logged.
- **Statistics:** McNemar (hits) and Wilcoxon (scores); Holm; Cliff's δ; p-values capped at 1
  (d'Aloisio's Table 4 is not).
- **Cost control:** T1 on 200 sampled corpus-A pairs plus the catalogue; T2 on at most 300 faults.
- **Fallback:** if the API budget or time runs out, T1 alone is still a complete, publishable result.

### 5.5 Claims discipline
- **Generated numbers:** every number comes from `numbers.tex`, and each claim carries a pointer
  (claim → script → result file) in `PROVENANCE.md`.
- **Unfavourable results are reported:** if H3 fails, the paper says pruning is input-specific and
  the light cone becomes the recommended slicer (GO-empirical framing).

---

## 6. Proposed changes to the unfrozen `PROTOCOL_ICPC.md`

1. **§4.1 operators:** rewrite with a provenance column (Muskit / QMutPy / QuMu / ours). Add
   control-gate removal, the entanglement-fault family and measurement insert/delete. Keep at most 5
   per operator per circuit.
2. **§4.2:** two oracles (Z distribution and ρ_q); the killed/injured/alive classification;
   equivalent-mutant filtering by exact equivalence.
3. **§4.1 Bugs4Q:** stage and kind classification. RQ3 runs only on circuit-semantic bugs, and the
   fraction is reported.
4. **§4.3:** add the random equal-size baseline, the MBFL comparison (QMutPy-based, after Ishimoto et
   al.), and EXAM computed as in that paper.
5. **§6 LLM study:** from optional to **planned**, with T1 (dependence questions vs ground truth) and
   T2 (localization with slices). Design per §5.4. T1 is the must-have core; T2 can be dropped by
   2026-10-31 with the reason reported.
6. **§3:** covariates in the size and robustness analyses (Ch. 10 metrics).
7. **§2.2:** add the Deutsch (kickback, no entanglement) and Bell/GHZ textbook entries. State the
   unconditional-state scope of K11 and K15.
8. **Terminology section:** ρ_q is the unconditional, generally mixed reduced state. "Product across
   the cut" replaces "separable", except in the textbook mixed-state sense. A "test oracle" is never
   called a "quantum oracle".

---

## 7. Writing and terminology rules

- **One name per concept:**
  - TQDG (our graph) vs QPDG ([27]);
  - "light cone" = the wire cone with classical control;
  - "def-use port";
  - "QSlice";
  - "criterion qubit q / criterion set W";
  - "dynamic circuit" = mid-circuit measurement, reset or feedback.
- **Define before use**, with Nielsen & Chuang as the source: reduced state, partial trace,
  no-signalling, kickback, mid-circuit measurement, global phase (irrelevant to ρ_q).
- **Never write that** entanglement lets a local operation "change the state of" a distant qubit.
  Use the LLM roadmap's correlation wording (p. 273:5).
- **Remove** "All numbers are measured; none are projected", the bold Takeaway boxes, "first ever",
  "provably sound" for pruning, and astronomically small p-values (write "p < 10⁻¹⁰").
- **Editorial:** the roadmap must match the sections; no truncated sentences; units carry a space
  ("0.10 ms"); OpenQASM 2 vs 3 named correctly.
- **Self-citations** in the third person; the anonymity pass covers IBM job metadata.
- **Acknowledgements** disclose AI use (draft for the author).

---

## 8. Figures and tables: professional standard (author's Oct 20 request)

**One style module** (`paper/figstyle.py`) used by every figure:
- vector PDF output;
- IEEE column width 3.5 in (7.16 in for double width);
- 8 pt fonts matching the body text;
- the Okabe–Ito colour-blind-safe palette, with one fixed colour and marker per slicer across all
  figures, readable in grayscale;
- no titles inside plots;
- CIs drawn wherever a mean is shown;
- the circuit convention: double wire = classical.

**Planned set** (about 4 figures + 4 tables):

| Item | Content |
|---|---|
| Fig. 1 | The running example circuit drawn once, with the def-use, light-cone and QSlice slices as coloured bands and the dependence kinds labelled. This is the A6 link. |
| Table I | The dependence catalogue: kinds × slicers, cells sound ✓ / misses ✗ / over-includes ○. This is the paper's core table. |
| Fig. 2 | RQ1: dependence recall vs precision per slicer (dot + CI), with misses stacked by kind |
| Table II | RQ1/RQ2 main results per corpus: invalid rate, size, robustness |
| Fig. 3 | RQ2: size reduction vs the light cone per structure family and robustness regime (paired dot plot) |
| Fig. 4 | RQ3: containment vs inspection cost per slicer, seeded vs Bugs4Q (scatter with CIs), plus the LLM panel |
| Table III | RQ3: EXAM and containment, with the MBFL comparison; C-Q4 counts |
| Table IV | RQ4: cost vs width and depth (compact) |

Every figure has one generator script reading `results/*.json`, listed in `PROVENANCE.md`, so a
figure regenerates with the numbers.

---

## 9. Schedule against the deadlines (abstract Oct 29, paper Nov 5)

| By | Work |
|---|---|
| Oct 22 | Author approves this blueprint; `PROTOCOL_ICPC.md` revised per §6 and **frozen** (committed) |
| Oct 25 | Implement: ground-truth harness; catalogue tests; S-yz, S-lcq, S-qW; the four-edge fix; mutation tool with provenance; Bugs4Q triage; LLM harness (T1). **Checkpoint A** |
| Oct 27 | Run RQ1–RQ4 and T1. **Checkpoint B: GO/NO-GO** |
| Oct 28 | Abstract and title (author decides the framing) |
| Oct 29–Nov 4 | T2 if on track; write; figures from the style module; artifact |
| Nov 4–5 | Independent review pass (plan Phase 7); submit |

**If time runs short, cut in this order** (each cut is reported in the paper):
1. T2;
2. noisy simulation;
3. corpus L;
4. the full family grid (keep one instance per family);
5. the Qiskit source map.

**Never cut:** RQ1 ground truth + catalogue, H2, H3, RQ3 on mutants, T1.
