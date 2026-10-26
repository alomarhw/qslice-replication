# Pre-registered protocol for the ICPC 2027 extensions

This protocol extends `PROTOCOL.md` and `PROTOCOL_RQ5.md`. Their choices stand unless this file says
otherwise:
- environment, preparation, oracle and statistics helpers;
- ε = 1e-6 on the criterion's Uhlmann fidelity;
- corpus A = 158 circuits and 784 (circuit, qubit) pairs.

It is committed **before** any experiment below is run and before any code it names exists in final
form. Development uses only debugging runs on at most 3 corpus-A circuits plus the synthetic examples
named in §8, and their outputs are deleted. Each full run is executed once and reported as produced.

Any later change goes in a dated "Deviations (ICPC)" section at the end of this file, with its
reason, and must say whether any result of the affected experiment had been seen.

The corrected run's results (`results/method_primary`, `results/rq4_ablation`,
`results/rq5_scalability`) are reused as they are. They regenerate byte for byte
(`../phase1_logs/regenerate_rq1_rq4.log`). Nothing here re-runs or replaces them.

Author decisions recorded on 2026-10-20:
- robustness runs on all 784 pairs;
- ε stays 1e-6 everywhere;
- the study has four research questions;
- the LLM study (§6) is **planned**. T1 is required; T2 may be dropped by 2026-10-31 with the reason
  reported (author decision 2026-10-21, approving `../PAPER_BLUEPRINT.md`);
- H4's non-inferiority margin is 0.05 (confirmed 2026-10-21);
- the archived submission stays byte-identical;
- hardware is decided after Correction 4 is computed (§7).

## 0. Research questions

| RQ | Question | Status |
|---|---|---|
| RQ1 | Which dependence definitions capture the true quantum and classical dependences of a qubit, and so give sound backward slices on real benchmark circuits? | confirmatory (H1); descriptive dependence ground truth (§2.1) and dependence catalogue (§2.2) |
| RQ2 | How much smaller than the light cone are QSlice slices, and when do they stay valid? | confirmatory (H2, H3); descriptive per family, criterion size, and on larger circuits (corpus L, §3.5) |
| RQ3 | Does slicing help localize faults, by hand and with an LLM? | confirmatory (H4, H5); descriptive C-Q4, MBFL comparison, and the LLM tasks T1 and T2 (§6) |
| RQ4 | What does QSlice cost end to end, against width and depth? | descriptive, including graph size (§8) and the larger corpus L (§3.5) |
| Discussion | What does a developer see when running a slice on a noisy device? | descriptive: noisy simulation (§7.2) and the corrected hardware result (§7.1) |

## 1. Slicers (RQ1–RQ3)

All slicers are judged only through `common/evaluate.py::materialise` and the exact oracle.

| Id | Slicer | Source |
|---|---|---|
| S-du | Genuine def-use port | `qdg.py::naive_classical_backward_slice`, unchanged. A controlled gate reads its controls and targets and writes its targets. |
| S-lc | Wire light cone with classical control | the corrected run's causal slicer: `QDGControlFixed` without ENTANGLEMENT edges, `backward_slice`, unchanged |
| S-lcq | Qiskit `LightCone` | `qiskit.transpiler.passes.LightCone` (qiskit 2.3.0): the union, over P ∈ {X, Y, Z}, of the instructions kept by `LightCone(bit_terms=P, indices=[t])`. Mapped back to instruction positions. The union over the three Paulis is what preserves the full reduced state. The Z-only cone is reported descriptively. |
| S-yz | Re-implementation of Yu & Zhao's QPDG slicing [27] | new `slicers/yuzhao.py`: backward reachability over entanglement, measurement and classical edges as [27] defines them. Every interpretation choice is logged at the top of the file before the run. No-cloning and temporal dependence are omitted, because [27] does not define them operationally (as the rebuttal states). |
| S-q | QSlice | `qdg.py::entanglement_pruned_slice` on `QDGControlFixed`, unchanged (`sep_eps` = 1e-9) |
| S-qW | QSlice, set criterion | new: the same algorithm with criterion W (a set of qubits). Mutual information is I(W; x) and verification uses the joint reduced state ρ_W. It is identical to S-q when \|W\| = 1, and this is checked on all 784 pairs before the run. |
| S-4e | Four-edge slicer (ablation) | `fouredge/src`. The measured-criterion fix of plan Phase 3 step 3: a criterion on a measured qubit is seeded from that qubit's last non-measurement operation. Results are reported **before and after** the fix. The unfixed results are the existing `results/rq4_ablation`. |

The four-edge `CAUSAL_CONE` variant (UED+ED, no MD/CD) is **not** a light cone and is never reported
under that name.

## 2. RQ1: soundness of dependence definitions

- **Corpus:** corpus A, 784 pairs.
- **Metrics per slicer:**
  - invalid-slice rate under the oracle;
  - mean criterion fidelity;
  - per-corpus and per-dynamic breakdowns.
- **LightCone cross-check:** for each pair, whether S-lcq and S-lc select the same instruction set.
  - Report the agreement rate and list every disagreement with its cause.
  - If `LightCone` raises on a circuit (for example on `if_else`), record it as "not applicable",
    not as a disagreement.
  - S-lcq is also judged by the oracle.
- **Four-edge fix:** SVR of S-4e QSlice-full before and after the fix, on the 962 ablation pairs. The
  ablation table is reported again with the fixed slicer.
- **H1:** S-q is invalid on fewer pairs than S-du. Exact McNemar test, as in the corrected run, now
  part of the confirmatory family.

### 2.1 Dependence ground truth: which operations really influence the criterion
A slice can be sound for the whole end state yet still miss, or wrongly include, individual
dependences. This section measures dependences one operation at a time, against a semantic ground
truth that no slicer computes.

- **Semantic influence:** operation o_k influences criterion qubit q iff inserting a perturbation
  right after o_k, on o_k's qubits, changes q's exact end-of-circuit reduced state (fidelity < 1 − 1e-6)
  for at least one input. This is the quantum analogue of semantic dependence in classical slicing
  theory (Podgurski and Clarke), cited as such.
  - **Inputs:** |0…0⟩ plus 10 Haar-random product inputs (seed 20261023).
  - **Perturbations:** for each (o_k, input), 2 independent Haar-random single-qubit unitaries on
    each qubit of o_k.
  - **Measurements:** a measurement o_k is perturbed in two ways, and influences q if either
    changes ρ_q:
    1. the quantum part: the same perturbation on the measured qubit right after the measurement;
    2. the classical part: the recorded outcome is inverted for every later `if_else` that reads the
       bit. A single-bit condition `c == v` becomes `c == 1 − v`; a register condition compares
       against the value with that bit flipped.
  - Computed by the oracle only, for all qubits of each circuit at once.
- **Corpus:** corpus A, every (circuit, qubit) pair. Circuits whose influence computation exceeds the
  limits in §8 are excluded and listed.
- **Metrics per slicer (S-du, S-lc, S-lcq, S-yz, S-q, S-4e full):**
  - **dependence recall** = |slice ∩ influencing| / |influencing|;
  - **dependence precision** = |slice ∩ influencing| / |slice|;
  - both as means over pairs, and the fraction of pairs with recall = 1.
- **Classification of every missed dependence**, i.e. an influencing operation outside the slice.
  - By no-signalling, any influence on q arrives through some later gate that acts on q.
  - The category says how q takes part in that gate, so it separates what classical def-use can see
    from what it cannot.
  - It is assigned by a fixed rule over the dependence paths from o_k to q (in order, the first that
    applies):
    1. **same-wire:** o_k acts on q;
    2. **feedback:** every path from o_k to q passes a measurement → condition edge;
    3. **written-operand:** some path enters q through a gate that *writes* q under def-use (q is a
       target, or an operand of a non-controlled multi-qubit gate such as SWAP or RZZ);
    4. **kickback:** every path enters q only through controlled gates in which q is a *control*.
       This is the quantum dependence that a def-use port cannot represent (Reviewer C).

  Report a table of missed dependences per slicer × category. This is the evidence for Reviewer C's
  framing: which dependence definition misses which kind of dependence.
- **Expected by theory, checked, not assumed:**
  - S-lc and S-lcq have dependence recall 1 on every pair (no-signalling: influence needs a causal
    path);
  - S-du misses kickback dependences;
  - S-q may miss an influencing operation only where the influence vanishes at |0…0⟩, which links
    this result to the robustness result of §3.2.

  Every deviation from these expectations is reported and explained.
- **Pruning against influence:**
  - the fraction of operations S-q removes that are non-influencing (correct prunes) vs influencing
    (prunes valid only at |0…0⟩);
  - for S-lc, the fraction of its operations that are non-influencing (the over-inclusion that
    pruning targets).

### 2.2 Dependence catalogue (golden tests)
Hand-built circuits, each isolating one dependence kind. Each circuit starts with the preparations
that make its dependence non-trivial, such as H on the qubits whose measurement outcome or control
value should be random. The exact circuits are fixed in the test file below. The **expected slice of every slicer and
the expected influence set (§2.1)** are written into `tests/dependence_catalogue.py` and committed
**before** any slicer is run on them. A disagreement is reported. It is never fixed by editing the
expectation, unless the expectation is shown to be wrong by the oracle, and that is logged as a
deviation.

| Id | Dependence kind | Circuit (criterion in bold) |
|---|---|---|
| K1 | data, same wire | H **q0**; X **q0** |
| K2 | control → target | H q0; CX(q0 → **q1**) |
| K3 | phase kickback, target → control | X q1; H q1; H **q0**; CX(**q0** → q1) (the control's state changes) |
| K4 | symmetric controlled phase | H q0; H q1; CZ(**q0**, q1) with a phase gate before it on q1 |
| K5 | partner's history reaches the control through entanglement | H q0; RY(θ) q1; CX(**q0**, q1). Criterion **q0**: RY on q1 changes q0's reduced state (coherence lost to the partner), a kickback-category dependence |
| K6 | no-signalling: partner after its last interaction | H q0; CX(q0, q1); X q1; RZ q1. Criterion **q0**: the operations on q1 after the CX do **not** influence it |
| K7 | SWAP moves state | RY q1; SWAP(**q0**, q1) |
| K8 | entangle, disentangle, re-entangle | CX(**q0**, q2); CX(**q0**, q2); CX(**q0**, q1), as in the paper's worked example |
| K9 | indirect (chained) entanglement | CX(q2, q1); CX(q1, **q0**); uncompute CX(q2, q1) |
| K10 | uncomputation U … U† | U(q1, q2); CX(q1, **q0**); CX(q1, **q0**); U†(q1, q2) |
| K11 | mid-circuit measurement of a partner, no feedback | H q0; CX(q0, q1); measure q1. Criterion **q0** is unchanged by non-selective measurement |
| K12 | measurement + classical feedback | H q1; measure q1 → c; if (c = 1) X **q0** (MD + CD) |
| K13 | teleportation | the standard circuit; criterion **Bob's qubit** depends on Alice's preparation through MD + CD |
| K14 | overwritten classical bit | measure q1 → c; measure q2 → c; if (c = 1) X **q0**. Only the second measurement is a dependence |
| K15 | reset of a partner after the interaction | H q0; CX(q0, q1); reset q1. Criterion **q0** is unchanged |
| K16 | register condition (multi-bit) | measure q1 → c[0]; measure q2 → c[1]; if (c = 3) X **q0** |
| K17 | GHZ partial uncompute | GHZ on q0–q3; uncompute q2, q3; criterion **q0** |
| K18 | textbook kickback without entanglement (Deutsch) | X q1; H q0; H q1; oracle U_f as CX(q0 → q1) (balanced f); H **q0**. Criterion **q0**: the oracle's information reaches the control as a phase. The state stays a product, so no entanglement is involved. |
| K19 | textbook Bell pair | H q0; CX(q0 → **q1**) and the symmetric criterion **q0** |

**Scope of the no-signalling negatives.** K6, K11 and K15 are negatives for the **unconditional**
reduced state ρ_q, which averages over every mid-circuit measurement outcome. A developer who
post-selects on a partner's outcome sees a conditional state that does depend on that measurement.
That is outside this criterion, and the paper says so.

Report one table: kinds × slicers, each cell = sound / misses the dependence / over-includes. This
table is the paper's comparison of dependence definitions (Reviewer C, Q3; Reviewer B, point 1).

**Scope of classical control.** The corpora are OpenQASM 2, so classical control is `if` on bits and
registers. Qiskit control flow beyond `if_else` (`while_loop`, `for_loop`, `switch_case`) is out of
scope for the circuit-level slicers and the oracle. Bugs4Q programs that need it are excluded with
that reason (§4.1). Classical dependences in the *Python* program that builds a circuit (loops,
index arithmetic, parameter computation) are the source-level layer of the srcSlice extension (plan
§7). They are not part of this protocol.

## 3. RQ2: precision beyond the light cone, and its limits

### 3.1 Size (H2)
- **Units:** the pairs of corpus A that are sound under both S-q and S-lc (the corrected run's
  definition).
- **Measures:**
  - mean of (size S-lc − size S-q), with sizes as fractions of prepared instructions;
  - bootstrap 95% CI (10,000 resamples, seed 42);
  - Wilcoxon signed-rank test with rank-biserial effect size;
  - the number of pairs where S-q is strictly smaller.
- **Also:** the same against S-yz on pairs sound under both.
- **H2:** S-q is smaller than S-lc. Effect sizes and CIs are the primary report.
- **Fallback (rebuttal limit R5):** the number and fraction of corpus-A pairs where S-q returns the
  light cone unpruned because the circuit is non-unitary (mid-circuit measurement, reset, feedback),
  per corpus. Size results are also reported with those pairs excluded.

### 3.2 Robustness to inputs and parameters (H3)
The question is whether a QSlice slice computed at |0…0⟩ stays sound for other inputs and
parameters. The slice's instruction positions stay **fixed**; only the input or the parameters
change.

- **Units:** all 784 pairs of corpus A (author decision).
  - On a pair where S-q equals S-lc, soundness holds by no-signalling, and the check verifies it.
  - Results are reported for all 784 pairs **and** separately for the *pruned* pairs (S-q ⊊ S-lc).
    The pruned subset is descriptive.
- **Draws per pair (seed 20261021, one generator per regime):**
  - **R-basis:** 100 uniformly random computational-basis inputs |x⟩, prepared by X gates
    prepended to both the full circuit and the slice.
  - **R-haar:** 100 Haar-random product inputs, with each qubit independently Haar-random, prepared
    by a `U` gate per qubit prepended to both.
  - **R-param:** 100 rebindings for circuits with at least one rotation angle. Every angle of every
    parameterized gate (`rx`, `ry`, `rz`, `p`, `u*`, `cu*`, `crz`, `cp`, `rzz`, …) is redrawn
    uniformly from [0, 2π) in both the full circuit and the slice, with the same values in both.
    Input |0…0⟩.
- **Soundness per draw:** oracle fidelity of the criterion ≥ 1 − 1e-6, prepared input or rebound
  circuit vs the same for the slice. Dynamic circuits use the oracle's branching, as in corpus A.
- **Measures per regime:**
  - pair robustness = fraction of pairs sound on **all** 100 draws;
  - draw robustness = fraction of all (pair, draw) checks that are sound;
  - the same for S-lc, as a control that should be 1.000.
- **H3:** pair robustness of S-q under R-haar is at least 0.95. This is the GO criterion in §9.
  Report the exact value with a Wilson 95% CI, and say plainly that a lower value means pruning is
  input-specific.

### 3.2a Covariates (descriptive)
Every size and robustness result is also broken down by standard circuit metrics:
- width, depth, gate count, two-qubit gate count, distinct gates, and width × depth;
- the number of entangling layers.

A rank regression of the per-pair relative reduction (S-lc − S-q)/S-lc on these covariates reports
whether QSlice's gain is explained by depth or entanglement structure alone. This analysis is
descriptive and not a hypothesis test.

### 3.3 Structure families (descriptive)
Generated by a new `families/generate.py` with fixed seeds. The ground truth is known by construction:
the set of operations that can affect the criterion's reduced state, derived symbolically per family
and checked by the oracle.

| Family | Construction | Sizes |
|---|---|---|
| F-ghz | GHZ preparation on n qubits, then uncompute the CX chain from k qubits | n ∈ {3,…,10}, k ∈ {1,…,n−2} |
| F-w | W-state preparation on n qubits, then uncompute part of it | n ∈ {3,…,8} |
| F-red | entangle → disentangle → re-entangle chains between the criterion and m partners | m ∈ {1,…,6}, 1–3 rounds |
| F-int | interleaved indirect entanglement: q0–q1, q1–q2, then uncompute q0–q1 (and longer chains) | chain length 3–8 |
| F-inv | U … U† uncomputation, with U a seeded random circuit on a subset | width 4–10, depth of U 2–20 |
| F-depth | fixed width 8, random entangling layers with uncompute segments, depth swept | depth ∈ {10, 20, 40, 80, 160} × 5 seeds |

Every qubit is a criterion. Per family report:
- the invalid rate of every slicer;
- size relative to S-lc;
- **recall of removable operations** = |removed by S-q ∩ removable| / |removable|, where removable =
  in S-lc but outside the ground-truth set;
- the number of pairs where S-q is sound but not minimal.

### 3.4 Criterion granularity (descriptive)
On corpus A, compare S-qW for three kinds of criterion:
- **single:** \|W\| = 1 (= S-q);
- **pair:** W = {q_i, q_j} for every pair coupled by at least one two-qubit gate;
- **measured:** W = the qubits measured in the raw circuit, only when \|W\| ≤ 6. Larger sets are
  excluded and listed (a 2^\|W\| density matrix).

Soundness for \|W\| > 1 is the Uhlmann fidelity of ρ_W ≥ 1 − 1e-6, computed with the oracle extended
to joint reduced states. The extension is checked against `Statevector`/`partial_trace` on random
unitary circuits before the run, in the same way as `tests/test_oracle.py`.

Report: invalid rate, size relative to S-lc, and how much of S-q's reduction remains as \|W\| grows.

### 3.5 Beyond the exact-evaluation caps: corpus L (descriptive; Reviewer B, point 2)
Corpus A stops at 14 qubits and 220 instructions. Corpus L tests soundness, size and cost on larger
real circuits.

- **Selection** (fixed now, from sizes only):
  - every circuit in `qasmbench/` (full, after `fetch_data.py`), `mqtbench/` and `veriqbench/`
    with 15–20 qubits and at most 1,000 instructions after the corpus-A preparation;
  - de-duplicated by (name, qubits, instructions);
  - sorted by (qubits, instructions, path);
  - at most 40 per corpus, smallest first.

  The selected list is written to `corpus_l.json` and committed **before** any slicer runs on it.
- **Oracle:** the same algorithm, with the qubit limit raised from 16 to 20. Above 16 qubits the
  branch limit is 64 (memory). The change is checked before the run: on random unitary circuits of
  17–20 qubits it must agree with `Statevector` + `partial_trace` to 1e-12.
- **Slicers:** S-du, S-lc, S-lcq, S-yz, S-q. Every qubit is a criterion.
- **Limits:** 600 s wall time and 8 GiB resident memory per circuit, at most 2 concurrent. A slicer or
  oracle run that hits a limit is reported as not completed, with the limit it hit. That is part of
  the result.
- **Report, per slicer:**
  - completion rate;
  - invalid rate;
  - mean size relative to S-lc;
  - S-q time and peak memory per circuit;
  - the fallback count (§3.1).

  §2.1 (dependence ground truth) and §3.2 (robustness) are not run on corpus L, because of cost.

## 4. RQ3: fault localization (the comprehension RQ)

No user study or debugging-task study with people is run. The paper says so (rebuttal promise R11).

### 4.1 Faults
- **Seeded mutants** (new `faults/mutate.py`). Every operator is cited to the tool that defines it,
  and the paper's operator table has a provenance column.

  | Id | Operator | Provenance |
  |---|---|---|
  | M-ins | gate insertion (a random 1-qubit gate from {x, y, z, h, s, t, sx}) | Muskit (Mendiluze et al., ASE 2021); QMutPy |
  | M-del | gate deletion | Muskit; QMutPy |
  | M-rep | gate replacement, same arity (1q↔1q from the set above; 2q from {cx, cz, cy, swap}) | Muskit; QMutPy |
  | M-mins | measurement insertion (mid-circuit, on a random qubit, into a fresh classical bit) | QMutPy (Fortunato et al., ICSE 2022) |
  | M-mdel | measurement deletion (non-terminal measurements only) | QMutPy |
  | M-cts | swap control and target of a controlled gate | QuMu "Swap controls and controlled qubits" (Book Ch. 9, Table 9.1) |
  | M-crm | control-gate removal (drop one control: ccx→cx, cx→x, cz→z, …) | QuMu "Control gate removal" |
  | M-qsw | qubit-operand swap (re-target one operand of a multi-qubit gate to another qubit) | QuMu bridging fault ("a multi-qubit gate which connects wrong qubits", Ch. 9 p. 177) |
  | M-ent | entanglement faults: force unentanglement (delete the H that feeds an entangling CX), entanglement corruption (move that H after the CX) | QuMu entanglement-fault family |
  | M-par | parameter perturbation (+δ, δ uniform in [π/8, π]) | ours, labelled as such |

  **Sampling:** for every corpus-A circuit and operator, up to 5 mutants drawn uniformly over valid
  sites (seed 20261022). That is at most 158 × 10 × 5 = 7,900 mutants.

  **Equivalent mutants are removed before any slicer runs.**
  - Unitary circuits: equal operator up to global phase, `Operator.equiv`.
  - Dynamic circuits: equal ρ_q for every qubit on |0…0⟩ and on 20 Haar product inputs.

  The number removed is reported per operator.
- **Real bugs:** Bugs4Q, https://github.com/Z-928/Bugs4Q, commit
  `7a719839662f94614872d65f9e9fbcd07408437c` (Apache-2.0).
  - **Inclusion:** the buggy and fixed versions both build a `QuantumCircuit` under qiskit 2.3.0,
    with at most mechanical API updates (each logged per bug); at most 14 qubits and 220 instructions
    after preparation; and the two circuits differ.
  - Every candidate bug is listed with its inclusion decision and reason **before** any slicer is run
    on it.
  - **Stage and kind classification:** every candidate is classified by stage (input / operation /
    output, after Huang and Martonosi) and as either *circuit-semantic* (the buggy and fixed circuits
    differ in gates, operands, parameters, measurement or conditions) or *API/classical* (e.g. a
    missing `.decompose()`, a wrong backend call, or a post-processing bug).
    - RQ3 runs only on circuit-semantic bugs.
    - The paper reports the counts of every class, so the share of real bugs that a circuit slicer
      can address is itself a result.
  - **Fault site:** the instructions that differ between the buggy and fixed circuits (an aligned
    instruction diff).

### 4.2 Criterion: what a developer can observe, and two oracles
Both oracles are computed exactly from the buggy and fixed (or original) circuits only.
- **Oracle Z (what a developer sees):** the qubits whose exact single-qubit Z-basis marginal differs
  by more than 1e-6.
- **Oracle ρ (full state):** the qubits whose reduced state ρ_q differs (fidelity < 1 − 1e-6).
- **Outcome of each non-equivalent mutant,** after QuMu:
  - **killed:** some qubit differs under oracle Z;
  - **injured:** no qubit differs under Z, but some does under ρ (a phase-only change);
  - **alive:** neither oracle sees a difference on the evaluated inputs.

  Report the counts per operator.
- **Units:**
  - the primary analysis uses killed faults, with criteria the observable-wrong qubits under Z;
  - a secondary analysis adds injured faults, with criteria from oracle ρ;
  - alive faults are excluded and counted.
- **Unit:** each (fault, observable-wrong qubit) pair.
- **Slicing:** every slicer slices the **buggy** circuit, the program the developer has.

### 4.3 Metrics per slicer (S-du, S-lc, S-yz, S-q; the full circuit as reference)
- **Fault containment:**
  - Does the slice contain a fault-site instruction?
  - For a deletion, the fault site is the instructions immediately before and after the deletion
    point on the deleted gate's qubits.
- **Inspection cost:**
  - slice size in instructions;
  - an EXAM-style score: the rank of the first fault-site instruction, with the slice ordered by
    descending position (latest first), divided by slice size;
  - for Bugs4Q with the source map (§5), the same in lines of the Qiskit program.
- **C-Q4 count:** units where the fault site is in S-lc but **not** in S-q, i.e. pruning removed the
  faulty operation.
  - Count it, and report its share among the units where S-lc contains the fault.
  - **Remedy:** re-slice with S-qW, W = all observable-wrong qubits of that fault, and report how many
    C-Q4 units it recovers.
- **H4 (soundness costs nothing in containment):** containment of S-q ≥ that of S-lc minus 0.05. This
  is a one-sided paired comparison: exact McNemar on discordant units plus the CI of the difference.
  H4 holds if the CI's lower bound is above −0.05.
- **H5 (precision helps inspection):** the inspection cost of S-q is lower than S-lc's, on units
  contained by both. Wilcoxon signed-rank test with effect size and CI.
- **Baselines besides the slicers:**
  - **full circuit:** containment 1, cost = all instructions;
  - **random equal-size subset:** for each unit, 100 random instruction sets of the S-q slice's size
    (seed 20261024), giving expected containment and EXAM;
  - **MBFL:** mutation-based fault localization as in Ishimoto et al. (EASE 2025):
    - QMutPy-style mutants of the *buggy* circuit are run under oracle Z;
    - instructions are ranked by the Ochiai suspiciousness formula over the units' observable
      behaviour;
    - EXAM is reported on the same scale;
    - also reported: **slice-filtered MBFL**, the same ranking restricted to the S-q slice and to the
      S-lc slice.
- **EXAM, for comparability:** in addition to the in-slice EXAM above, report EXAM as Ishimoto et
  al. define it: the fraction of all instructions examined, in rank order, before the first
  fault-site instruction, under the best-, worst- and average-case tie policy.
- **Breakdowns:** per mutation operator, per oracle outcome (killed / injured), per corpus, mutants
  vs Bugs4Q.

## 5. Qiskit source map (descriptive; dropped if not working by 2026-10-31)
`qiskit_source_map.py` wraps `QuantumCircuit.append` while a Bugs4Q program builds its circuit, and
records the creating file:line of every instruction. A slice is then shown as source lines. It is
used only for the RQ3 inspection cost in lines and for one figure. If it is dropped, the paper says
so.

## 6. LLM tasks (RQ3; descriptive, with effect sizes and CIs)

Two tasks with **objective** answers. Neither is in the confirmatory family.

### 6.1 Models (author decision 2026-10-21: any Claude model, or any free model on the author's GPU)
- **Claude:** `claude-opus-5-5`, `claude-sonnet-5-5` and `claude-haiku-5-5`, through the Anthropic
  API. The exact model id returned by the API is logged.
- **Open-weight, served locally on the author's GPU (vLLM or ollama):**
  - **O-mid:** the largest Qwen2.5-Coder-Instruct (32B, 14B or 7B) that fits the GPU in bf16 or 8-bit;
  - **O-small:** Qwen2.5-Coder-1.5B-Instruct, the small-model control (after d'Aloisio et al.'s
    TinyLlama).

  The size is chosen from GPU memory alone, before any run. The Hugging Face repo and revision hash
  are recorded.
- **Settings:** temperature 0 for the primary run (1 run). Temperature 0.8 (d'Aloisio et al.), 3 runs,
  for the consistency analysis on a 50-item subset. Maximum output 2,048 tokens. No tools.

### 6.2 Circuit presentation (fixed)
- **Format:** OpenQASM 2 as produced by `qiskit.qasm2.dumps` of the prepared circuit.
- **Indices:** every instruction line is suffixed with `// [k]`, its position in the full circuit.
- **Slices:** a slice is shown as the sub-circuit with the original indices kept, so every answer is
  in the same index space.

### 6.3 T1: does the model know what affects a qubit?
- **Items:**
  - 200 corpus-A (circuit, qubit) pairs, sampled stratified by corpus (seed 20261025);
  - all catalogue circuits (K1–K19).
- **Prompt** (fixed, no tuning):
  > "Here is a quantum circuit in OpenQASM 2. Each instruction ends with its index as `// [k]`.
  > `<circuit>`
  > Which instructions can affect the final quantum state of qubit q[`<t>`] (its reduced density
  > matrix at the end of the circuit)? Answer with a JSON list of instruction indices and nothing else."
- **Scoring:**
  - precision, recall and F1 against the semantic-influence set of §2.1;
  - also against S-lc, to separate "missed a real dependence" from "different but sound";
  - an unparsable answer scores 0 recall and is counted.
- **Report:** per model, per dependence kind (§2.1 categories: which kinds LLMs miss), and against the
  slicers' recall and precision on the same items.

### 6.4 T2: does a slice help the model localize a fault?
- **Items:** up to 300 RQ3 units, sampled stratified by operator (seed 20261026), plus every
  circuit-semantic Bugs4Q unit.
- **Inputs per item**, with the circuit shown as the buggy circuit or one of its slices:
  - (i) the full circuit;
  - (ii) the S-lc slice;
  - (iii) the S-q slice;
  - (iv) the S-du slice, a negative control that may omit the fault.
- **Prompt context:**
  - **primary:** algorithm name (file stem) + qubit count, reusing d'Aloisio et al.'s context
    prompt;
  - **ablation:** no context, run for inputs (i) and (iii) only.
- **Prompt** (fixed):
  > "This quantum circuit has a bug: the measured distribution of qubit q[`<t>`] is wrong. `<context>`
  > `<circuit>`
  > Which instruction is most likely the faulty one? Answer with a JSON list of up to 3 instruction
  > indices, most likely first, and nothing else."
- **Scoring:**
  - top-1 and top-3 hit on the fault site (§4.3 definition);
  - prompt tokens;
  - unparsable answers count as misses.
- **Comparisons:**
  - (iii) vs (i) and (iii) vs (ii): exact McNemar on top-3 hits per model, with the difference and its
    CI;
  - consistency: the agreement across the three temperature-0.8 runs.
- **Budget:** one call per (model, item, input, context) in the primary run, about 6,000 calls in
  total. The run stops, and is reported as partial, if API cost exceeds an amount the author fixes
  before the run.

### 6.5 Development and logging
- **Format checks only:** prompts are checked for output format on 5 development items (catalogue
  K1–K3 and two corpus-A circuits), which are excluded from scoring.
- **No prompt changes after that check.**
- **Logging:** every prompt, raw output, model id, timestamp and token count goes to
  `results/llm/*.jsonl`.

## 7. Noise and hardware (Reviewer A, Q2)

### 7.1 Hardware (old RQ7)
Rebuttal Correction 4 is computed in Phase 3. The two QAOA circuits are recomputed from the captured
jobs, comparing the register the slice actually measures. The author then decides between:
- one Discussion paragraph, stating that TVD is phase-blind;
- dropping hardware.

No hardware number is reported without that recomputation.

### 7.2 Noisy simulation (descriptive)
Slices are computed statically, so noise cannot change *which* operations a slice contains. What noise
can change is whether running the slice tells a developer the same thing as running the full program.

- **Environment:** a separate lock, `requirements_noise.lock` = `requirements.lock` +
  `qiskit-aer==0.17.2` + `psutil==7.2.2` (checked installable on 2026-10-21).
- **Circuits:** the corpus-A pairs with at most 10 qubits (density-matrix memory).
- **Slices per pair:** S-lc and S-q.
- **Noise model:**
  - both the full circuit and each slice are transpiled to basis {`u`, `cx`} with
    `optimization_level=0`;
  - depolarizing error p1 on every `u` and p2 on every `cx`, with p2 ∈ {1e-3, 1e-2, 3e-2} and
    p1 = p2/10;
  - no readout error (the comparison is on reduced states).
- **Simulation:** `AerSimulator(method="density_matrix")`, which handles mid-circuit measurement,
  reset and `if_else`. The criterion's reduced state is ρ_q.
- **Measures per (pair, slicer, level):**
  - D_full = TD(ρ_q of the noisy full circuit, ρ_q ideal);
  - D_slice = TD(ρ_q of the noisy slice, ρ_q ideal);
  - D_cross = TD(noisy slice, noisy full).
- **Report:**
  - medians and 95th percentiles;
  - the fraction of pairs with D_slice ≤ D_full;
  - how D_cross grows with p2 and with the number of instructions the slice removes.

  Descriptive only: this shows what a developer would see when running a slice instead of the full
  circuit on a noisy device. It is not a claim about real hardware.

## 8. RQ4: cost (descriptive)
- **Measured:**
  - S-q end to end: QDG build + mutual-information nomination + exact verification, for every
    criterion;
  - S-lc time;
  - peak resident memory.
- **Inputs:** F-depth (depth sweep at width 8), plus a width sweep (F-inv and F-ghz at widths 4–14).
- **Limits and parallelism:** the same as `PROTOCOL_RQ5.md` (120 s, 4 GiB, 4 concurrent, a fresh
  process per circuit). The machine is recorded in `machine.json`.
- **Reported:** median, 95th percentile and maximum times; peak memory against width and against
  depth; and completion rates.
- **Graph size (Reviewer A, Q1):** QDG nodes and edges by type (DATA, CONTROL, ENTANGLEMENT), against
  operation count, width and depth, on the same inputs and on corpus A. This measures the claim that
  the graph grows with the operations, not with superposition or amplitudes. The exponential cost is
  only in the pruning check, which is reported separately above.
- **Reused:** the existing structural (1,124 circuits) and end-to-end (corpus A) RQ5 results, labelled
  structural vs end to end.

**Synthetic examples allowed during development:**
- the paper's worked examples (Bell; entangle–disentangle q0–q2; teleportation), which are also the
  golden tests;
- one small instance per family in §3.3.

## 9. Statistics, multiple comparisons and GO/NO-GO

**Confirmatory family:** H1–H5, with Holm correction at α = 0.05 across the five.
- Effect sizes and CIs are reported first.
- p-values below 1e-10 are written "p < 10⁻¹⁰".
- Everything else is descriptive and is not tested for significance.

**GO/NO-GO for Checkpoint B.** The author picks the framing; these are the recommendation rules,
fixed now:

| Recommendation | Condition |
|---|---|
| **GO-strong** | H2: the lower CI bound of the mean size reduction (S-lc − S-q) is > 0 and the relative reduction is ≥ 0.15, **and** H3: pair robustness under R-haar is ≥ 0.95, **and** S-q is invalid on 0 of 784 pairs |
| **GO-empirical** | S-q is sound on corpus A, but the robustness condition or the size condition fails. Reframe as an empirical study of what sound slicing costs and when the extra precision holds; the light cone is the recommended practical slicer. |
| **NO-GO (Research Track)** | S-q is unsound on corpus A at \|0…0⟩, or RQ3 cannot be run (fewer than 200 observable mutants). Consider the RENE or ERA track. |

## 10. Exclusions and reporting
- Every exclusion (load failure, oracle branch limit, not observable, LightCone not applicable,
  Bugs4Q inclusion failure, Bugs4Q API/classical bug, equivalent or alive mutant, size cap, corpus-L
  limit, noisy-simulation size cap, unparsable LLM answer) is written to an `excluded.json` with its
  reason, and counted in the paper.
- Results are reported whatever their direction:
  - if pruning is input-specific;
  - if S-yz or S-lcq differ from S-lc;
  - if QSlice does not help fault localization.
- Every number in the paper comes from `results/*.json` through the generated `paper/numbers.tex`.

## 11. Terminology (binding for code, results and the paper)
- **ρ_q** is the *unconditional* reduced density matrix of qubit q at the end of the circuit: the
  partial trace over all other qubits, averaged over all mid-circuit measurement outcomes. It is in
  general mixed. ρ_W is the same for a set W.
- **"Product across the cut"** (ρ = ρ_A ⊗ ρ_B) replaces "separable", except in the textbook
  mixed-state sense.
- **"Test oracle"** is the exact reference simulator. It is never called a "quantum oracle", a term
  reserved for U_f.
- **Light cone (S-lc)** is the wire light cone *with classical control*. The four-edge `CAUSAL_CONE`
  is not a light cone.
- **TQDG** names our graph and **QPDG** names [27]'s. "Dynamic circuit" means a circuit with
  mid-circuit measurement, reset or feedback.

## Deviations (ICPC)

### Deviation I-1 (2026-10-21, before any ICPC result): design corrections found while deriving the catalogue expectations
These were found while deriving the catalogue's expected outcomes by hand. No ICPC experiment code had
run, and no ICPC result existed.

1. **§2.1, the perturbation.**
   - *Was:* independent single-qubit Haar unitaries on each qubit of o_k.
   - *Now:* **one Haar-random unitary on the joint space of o_k's qubits** (o_k acts on at most 8
     qubits after preparation).
   - *Reason:* a product of single-qubit unitaries cannot reveal a dependence carried by
     entanglement. For example, q0 after the CX of a Bell pair is maximally mixed, so no local
     unitary on q0 or q1 changes ρ_q0, and the CX would wrongly be labelled non-influencing. The
     joint perturbation is the faithful analogue of Podgurski and Clarke's semantic dependence:
     o_k influences q iff *some* operation in o_k's place would change ρ_q.
2. **§2.1, the expectation for S-q.**
   - *Was:* "S-q may miss an influencing operation only where the influence vanishes at |0…0⟩".
   - *Why it is wrong:* QSlice removes operations whose effect *as written* is nil, and that can hold
     for every input. In K4, an S gate before a CZ on the other wire commutes with the CZ, so it never
     changes ρ_q0, yet a different gate there would.
   - *Now:* S-q is expected to miss influencing operations whose as-written contribution is nil.
3. **§2.1, an added descriptive measure.** **As-written contribution:** o_k contributes to q iff
   deleting o_k alone changes ρ_q, at |0…0⟩ and at the same 10 Haar product inputs. Each pruning of
   S-q is then classified as:
   - a non-influencing removal;
   - an influencing operation with no contribution at any tested input;
   - an influencing operation that contributes at some input (an input-specific prune).

   This separates *dependence* (what q could depend on: the right target for fault localization)
   from *contribution* (what QSlice optimizes).
4. **§1, the four-edge fix.**
   - *Was:* "seeded from that qubit's last non-measurement operation".
   - *Now:* **seeded from the criterion qubit's last operation of any kind.**
   - *Reason:* a mid-circuit measurement or reset of the criterion qubit changes ρ_q and must be in
     the slice. The original defect is that the slice was seeded *only* at measurement nodes, which
     drops every later operation on the criterion qubit.
5. **§1, the expectation for S-lcq.** Qiskit's `LightCone` drops gates that commute with the
   backward-propagated observable, so its exact sets cannot be derived reliably by hand.
   - **Catalogue expectation:** sound, and a subset of S-lc.
   - Every catalogue entry where it is a strict subset is reported.
   - On dynamic circuits the expectation is "not applicable, or sound and ⊆ S-lc".
6. **§2.2, catalogue additions.** None of these changes an existing entry's circuit or criterion.
   - **K6b:** K6 plus a later H on the criterion qubit.
   - **K11b:** K11 plus a later H on the criterion qubit.

     These are the only cases where a flow-insensitive entanglement dependence (S-yz) over-includes
     no-signalling partner operations.
   - **K17, a second criterion q1.** With q0 as the criterion, the partial uncompute is causally
     irrelevant, because q0's last operation precedes it.
   - **K20:** a measured-then-corrected criterion qubit (H q0; measure q0 → c; if c = 1: X q0). This
     is the pattern behind the four-edge slicer's 5 unsound pairs.
   - **K8:** an X on q2 is prepended as a preparation. The ICSE worked example prunes CX(q0, q2),
     which touches the criterion, but Sec. III's algorithm prunes only operations that do not touch
     the criterion qubit. With the X q2 preparation, K8 exercises the algorithm as specified. The
     paper's worked example is rewritten to match.

### Deviation I-2 (2026-10-21, before any RQ3 result): cost limits found while implementing RQ3
1. **§4.1, equivalent-mutant filtering.** `Operator.equiv` is used only when both circuits are
   unitary and have at most 10 qubits. A 14-qubit operator is a 2^14 × 2^14 complex matrix (about
   4 GB).
   - Larger unitary circuits use the rule already specified for dynamic circuits: equal ρ_q for
     every qubit, on |0…0⟩ and on 20 Haar product inputs.
   - The rule used is recorded per mutant.
2. **§4.3, MBFL.** It needs, per fault unit, (instructions × MBFL mutants × 21 test inputs) exact
   simulations, so it runs on the same stratified sample as T2: up to 300 units, seed 20261026,
   stratified by operator, plus every Bugs4Q unit. Every other RQ3 metric covers all units.
   - Both decisions were taken from cost estimates alone, before any RQ3 code had run on corpus A.

### Deviation I-3 (2026-10-21, before any LLM call): settings the current Claude API does not accept
These were found while implementing §6, from the API documentation. No LLM call had been made.

1. **Sampling (§6.1).**
   - `claude-opus-5-5`, `claude-sonnet-5-5` and `claude-haiku-5-5` reject non-default sampling
     parameters (`temperature`, `top_p`, `top_k`) with HTTP 400. For the Claude arms, *temperature 0*
     and *temperature 0.8* cannot be set.
   - Claude arms: default sampling, with effort fixed at **`medium`** for all three models via
     `output_config.effort`. That is the default for Opus 5.5 and Haiku 5.5; Sonnet 5.5 defaults to
     `high` and is set to `medium` for comparability.
   - Primary run: 1 call per item. Consistency analysis: 3 calls per item on the 50-item subset, at
     the same settings.
   - Open-weight arms (vLLM): unchanged, temperature 0 primary and 0.8 × 3 for consistency.
2. **Reasoning tokens (§6.1).** All three Claude models think adaptively. Opus 5.5 cannot disable
   thinking, and thinking tokens count against `max_tokens`. A 2,048-token cap would truncate
   answers, so `max_tokens` is **16,000** for the Claude arms. The open arms keep 2,048.
   - Thinking text is not requested (`display` left at its default, "omitted") and is not scored.
3. **Refusals.** The server-side refusal fallback is **not** enabled. It would let a different model
   answer, which breaks the per-model comparison. `stop_reason == "refusal"` is recorded as a refusal
   and scored as unparsable. Refusal counts are reported per model.
4. **Answer parsing (§6.3, §6.4), fixed now.**
   - First, the whole text response, stripped, is parsed with `json.loads`.
   - If that fails, the **last** JSON array of integers in the text (regex `\[[0-9,\s]*\]`) is
     parsed.
   - Anything else is unparsable.
   - Indices that are not instruction positions of the shown circuit are dropped and counted.
5. **Circuit text (§6.2).** If the number of instruction lines in `qasm2.dumps` differs from the
   number of instructions (so the `// [k]` labels cannot be placed exactly), the item is excluded and
   listed.
6. **Prices for the budget cap** (USD per 10^6 input / output tokens, Anthropic list price,
   2026-10-06): Opus 5.5 4 / 20; Sonnet 5.5 2 / 10; Haiku 5.5 0.10 / 0.50. Cost is computed from
   each response's `usage`.

7. **Details §6 leaves open, fixed in `icpc/llm_tasks.py` before any call (2026-10-21).**
   - **Qubit name.** The qubit is named as in the QASM text (register and index, e.g. `q[3]`).
   - **Prompt wording.** The `// [k]` in the T1 prompt is sent with its backticks, as written in
     §6.3.
   - **Single-bit conditions.** Catalogue K12, K14 and K20 use single-bit conditions, which
     OpenQASM 2 cannot write. They are shown with every classical bit in its own one-bit register.
     The instructions and indices are the same; only the notation changes.
   - **T1 sample.** The 200 pairs are allocated in proportion to each corpus's pairs, using largest
     remainders. The two corpus-A development pairs are drawn from the remaining pairs with seed
     20261025.
   - **T2 sample.** Primary units only, since the prompt says the *measured* distribution is wrong.
     30 per operator (all of them when there are fewer), seed 20261026.
   - **Context string.** The words are those of d'Aloisio et al.'s context-aware prompt: "The name of
     the algorithm is: <file stem>. The code includes <n> qubits."
   - **Inserted-measurement register.** The extra register of an inserted measurement (M-mins) is
     shown as `c_extra`, not `mut`.
   - **Consistency subset.** 50 scored items per task, runs 1–3. T1 uses its single input. T2 uses
     inputs (i) and (iii) with context.
   - **Open-model seeds.** Open-arm runs 1–3 use seed = run number.
   - **Call order.** Claude calls are ordered item-major in a seeded item order. A run stopped by the
     cap therefore covers a random subset of items on every arm.
   - **Scope of the cap.** The cap covers all Claude spend logged for the task, including the
     development check.

### Deviation I-4 (2026-10-21, AFTER the O-small T1 scored run): a sensitivity parser, added post hoc
- **What happened.** O-small writes its index lists as strings, e.g. `["0", "1"]` or `["[17]", "[18]"]`.
  Its 5 development items showed this. They were run in the same command chain as the scored runs,
  and the output was not read before the scored and consistency runs started. This was a procedural
  slip: §6.5 intends the format check to be inspected first.
- **Primary stays frozen.** The Deviation I-3 item 4 rule is unchanged and remains primary
  (`t1_scores.csv`). Under it, 23% of O-small's answers parse.
  - The fallback of that rule reads `["[17]", "[18]"]` as `[18]`, the last inner integer list. Such
    answers count as parsed, with a truncated answer.
- **Sensitivity score (post hoc).** `score --lenient` writes `<task>_scores_lenient.csv` and is
  applied identically to every arm. It uses `json.loads` first; otherwise it takes the last
  top-level list whose elements are all indices, written as `7`, `"7"`, `[7]` or `"[7]"`.
  - It is reported as sensitivity only, and labelled post hoc.
  - O-mid and the Claude development answers are unaffected, since their answers are integer lists.
- **The author decides** how O-small is reported: format failure as primary, with the sensitivity
  score in the text.
- **The prompt is not changed.**

### Deviation I-5 (2026-10-21, author decision, before any scored Claude call): Opus dropped; budget cap
- **Opus dropped.** The Claude arms are `claude-sonnet-5-5` and `claude-haiku-5-5`.
  `claude-opus-5-5` is dropped for cost, and its 5 development-check calls stay logged but unscored.
- **Budget cap (§6.4).** USD 60 in total, set by the author: T1 USD 15, T2 USD 45. The T1 cap counts
  the USD 0.09 development check.

### Deviation I-6 (2026-10-21, after the first RQ3 run crashed, before any RQ3 result was written)
- **The crash.** The first full RQ3 run (`440d12d`) crashed after 7.5 h with `StopIteration` in
  `exam_scores`. A mutant had an empty fault site. This happens when M-del or M-ent ("unentangle")
  deletes the only instruction on its qubits: there is then no instruction before or after the
  deletion point to mark as the fault site (§4.1).
- **No outputs.** No output files were written, so no RQ3 result was seen.
- **Rule added to §10.** Such mutants are excluded with the reason "empty fault site", recorded in
  `mutants.csv` with `outcome = excluded`, and counted.
- **Checkpointing.** The driver now writes a per-circuit checkpoint (`results/icpc/rq3/partial/`), so a
  crash no longer loses completed circuits.
- **Smoke test.** It was run on the same 3 debug circuits as before; its output was deleted.

### Author decision on §7.1 (2026-10-21)
- **Decision.** Hardware is kept as **one Discussion paragraph**, answering Reviewer A on noise.
- **Numbers.** It reports only the Correction 4 numbers from
  `results/icpc/hardware/hardware_tvd_corrected.csv`:
  - 16/18 within δ = 0.05;
  - the noise-free TVD, which is 0 for all 18;
  - the QAOA gaps attributed to hardware noise.
- **Caveats, stated in the text:**
  - a Z-basis TVD is phase-blind;
  - the slices came from the four-edge `QSLICE_FULL` variant;
  - full and slice ran on different physical qubits.
- **Excluded.** No hardware number enters an RQ or the abstract.

### Author decision on Deviation I-4 (2026-10-21)
- **Primary.** The frozen parser (Deviation I-3 item 4) is primary for every arm. All tables and
  tests use `<task>_scores.csv`.
- **Sensitivity.** The post-hoc parser (`<task>_scores_lenient.csv`) is reported next to O-small's
  numbers only, labelled "post hoc (string indices accepted)". Its effect on the other arms is
  stated in one sentence.
- **The same rule applies to T2.**

### Deviation I-7 (2026-10-22, before the family and noise runs; the corpus-L selection was committed at `ba56c1b`)
1. **§3.3 ground truth.**
   - **Change:** the set of operations that can affect each criterion is computed with the §2.1
     semantic-dependence oracle (`icpc/influence.py`). It is not derived symbolically per family.
   - **Why:** this is the paper's definition of ground truth. A hand derivation for six parameterized
     families, two of them random, would add a second, error-prone definition.
   - **Constructions:** they follow the §3.3 table and are written down in `families/generate.py`.
     For F-w, "uncompute part of it" is fixed as undoing the last ⌊n/2⌋ preparation steps.
2. **§3.5 corpus L.**
   - **Memory limit:** resident memory is polled with `ps`, because `psutil` is not in
     `requirements.lock`. Per-stage results are logged, so a run that hits a limit is attributed to
     its stage.
   - **Fallback:** counted with QSlice's own rule, namely that `Statevector(circuit)` fails.
3. **§7.2 noise.**
   - **Terminal measurements** are removed before the final density matrix is saved.
   - **Measurement, reset or `if_else`:** a circuit that still contains one is simulated with 1,024
     shots, and Aer's shot average serves as the unconditional state. That value is an estimate;
     circuits without these operations are exact with one shot.
   - **Seeds:** the simulator seed is derived from the circuit path.

### Author decision on Deviation I-7 (2026-10-22)
- **Decision:** the structure families keep the §2.1 semantic-dependence oracle as ground truth.
- **Why:**
  - one definition of "can affect the criterion" for the whole paper;
  - it covers the two random families (F-inv, F-depth);
  - it is the same oracle that checks every slice's soundness.
- **The paper states** that family ground truth is computed by this oracle, not derived per family.

### Deviation I-8 (2026-10-22, AFTER all T1 and T2 calls; author decision): answer-line parser primary
- **Found.** The pre-registered parser (Deviation I-3 item 4) falls back to "the last integer list
  anywhere in the text", and that fallback reads non-answers.
  - Qwen2.5-Coder-1.5B often answers with an instruction's text, such as `["cx q[0],q[4]"]`. The
    fallback reads the qubit reference `q[4]` as instruction 4.
  - Claude Sonnet 5.5 sometimes ends with a list of strings, such as `["6", "10", "5"]`. The fallback
    takes the last prose citation instead, such as "[5] is the next candidate".
  - In T2 this changes 24% of Sonnet's answers and 25% of Qwen-1.5B's.
  - These are measurement errors, not a strictness choice.
- **New primary rule (`parse_answer_line`).**
  - Apply `json.loads` to the reply with code fences removed.
  - Otherwise, take the reply's last non-empty line with Markdown emphasis stripped. It counts only if
    it is exactly a list whose elements are all indices (`7`, `"7"`, `[7]`, `"[7]"`).
  - A bracket inside prose or an identifier never counts.
  - The rule is applied identically to every arm and to both tasks.
- **Agreement.** On every T1 and T2 answer of Haiku 5.5 and Qwen2.5-Coder-32B, and on every T1 answer
  of Sonnet, the new rule gives the same answer as the pre-registered rule.
- **Kept as sensitivity.** The pre-registered rule is reported as a labelled sensitivity analysis
  (`<task>_scores_frozen.csv`). It supersedes the Deviation I-4 decision. `_lenient` files are kept for
  the record.
- **Effect on findings.** The main T2 finding has the same direction under both rules: S-q slices
  lower top-3 fault localization against the full circuit and against S-lc, for Sonnet, Haiku and
  Qwen-32B. Only the magnitudes change (e.g. Sonnet, full circuit: 0.84 vs 0.73).

### Deviation I-9 (2026-10-23, AFTER the RQ1 run; author decision): S-lcq mapped back by order, not by labels alone
- **Found.** `slicers/registry.py::_lightcone` labels each instruction, runs `LightCone`, and reads the
  labels back. `LightCone` returns copies of QASM-defined gates (qasm2 `_DefinedGate`: `mcx`, `qft`,
  oracles) without their labels. The RQ1 run therefore recorded 142 of its 184 "not applicable" S-lcq
  pairs because of our wrapper, not because `LightCone` raised. §2 allows "not applicable" only when
  the pass raises. The other 42 are the pass's own refusal (measurements with an observable).
- **Change (`icpc/lcq_remap.py`).** The pass keeps an in-order subsequence of its input (it walks the
  DAG in reverse topological order and re-applies kept nodes at the front). The output is aligned to
  the input in order. Labelled instructions anchor. Unlabelled ones match an input instruction with
  the same name, qubits, clbits and parameters between anchors. The alignment is computed
  earliest-first and latest-first, and a pair whose two alignments differ is "ambiguous" and stays not
  applicable. Scoring is unchanged (§2).
- **Checked before the run.** On the 600 pairs the label mapping already handled, the new mapping
  gives the identical S-lcq slice on all 600. It maps 132 of the other 184; 52 stay not applicable.
- **Reporting.** The RQ1 S-lcq results (600 pairs) stay in `results/icpc/rq1` unchanged. The remapped
  results go to `results/icpc/rq1_lcq_remap` and are primary for the LightCone cross-check; both are
  reported. RQ1 code is not modified.
- **Direction.** The change can only widen the baseline's coverage; it cannot make S-q look better.

### Deviation I-10 (2026-10-23, before any S-lcq robustness result; author decision): RQ2 robustness of S-lcq
- **Why.** §3.2 tests the robustness of S-lc and S-q only. The foundations review
  (`FOUNDATIONS_REVIEW.md`) shows that Qiskit's `LightCone` (S-lcq) is smaller than S-lc on 243 of
  732 pairs and never unsound at |0…0⟩. Whether it stays valid at other inputs decides whether it,
  rather than S-lc, is the input-independent baseline QSlice must be compared with.
- **Design (`icpc/rq2_robustness_lcq.py`).** The §3.2 regimes (R-basis, R-haar, R-param), draws (100),
  seeds and soundness rule, imported unchanged from `icpc/rq2_robustness.py`, so every draw equals
  the RQ2 run's. S-lcq uses the Deviation I-9 mapping and, like S-lc and S-q, is computed once at
  |0…0⟩ on the circuit as written. Not-applicable pairs are recorded, not dropped silently.
- **Reproduction check.** S-lc is re-run on the same draws. Its sound-draw counts must equal
  `results/icpc/rq2_robustness` on every (pair, regime); a mismatch stops the analysis.
- **Expectation stated before the run.** Commutation with the observable is input-independent, so
  S-lcq should be robust under R-basis and R-haar. Under R-param, a gate may commute with the
  observable only at its written angle (e.g. an angle of 0), so S-lcq may fail there.
- **Reporting.** Descriptive; robust rate per regime, overall and for the pairs where S-lcq is
  strictly smaller than S-lc. Not part of the confirmatory family.

### Deviation I-11 (2026-10-23, before any source-map result): how the §5 source map is built
- **Why.** §5 says the map wraps `QuantumCircuit.append` "while a Bugs4Q program builds its
  circuit". The Bugs4Q programs are never executed: `bugs4q/extract.py` builds every circuit from
  a re-typed port with the original line numbers cited in comments. So the map goes through the
  ports.
- **Map (`icpc/qiskit_source_map.py`).**
  1. Run each buggy port with `QuantumCircuit._append` wrapped. Record the innermost port line on
     the call stack for every instruction appended to the port's circuit (gates built in helper
     functions get the helper's line; composed sub-circuits get the `compose`/`append` line).
  2. Map each port line to a line of the original buggy file. Use the port's `# Lnn` comment where
     there is one. Otherwise take the most similar original line (difflib ratio ≥ 0.6 on
     whitespace-stripped text, comments removed), searched between the original lines of the
     nearest commented port lines before and after it. Below 0.6, the line is unmapped and
     counted.
  3. Map each instruction of the prepared buggy circuit (the one RQ3 slices,
     `rq3_bugs4q._load`) to a traced instruction. Align (name, qubits) sequences with difflib.
     Within an unequal block of equal length, match by qubits. Every other instruction is unmapped
     and counted.
- **Measures (descriptive, per RQ3 Bugs4Q unit and slicer).**
  - fault lines = the original lines of the fault-site instructions;
  - line containment = whether the slice's lines include a fault line;
  - line inspection cost = the number of distinct original lines in the slice, also relative to the
    lines that create any instruction.
- **Cross-check.** The buggy original programs are sent to the authors' own Quantum Slicer
  (`qiskit-static` mode, which never executes them). Its per-instruction lines are compared with
  this map on (name, qubits)-aligned instructions, and the agreement rate is reported.
- **Cutoff.** §5's: dropped, and said so, if it is not working by 2026-10-31.
- **Fix found by the cross-check (2026-10-23, before any line result was reported or used).** In
  the first run, step 2 sent repeated identical statements (e.g. `circuit.x(search_register)`)
  to the first matching original line. The cross-check flagged them, and the authors' tool was
  right. Step 2 now searches in order: after the previous mapped line and before the next cited
  one. The first run's output is replaced and kept out of any result.

### Deviation I-12 (2026-10-23, author decision, before any S-cpdg result): the full classical PDG as a baseline
- **Why.** The pre-registered S-du ports classical *data* dependence only. It ignores classical bits,
  so it has no control dependence from a measurement to the gates its bit conditions. A classical
  slicer follows both kinds of dependence. The author decided that the comparison must include the
  full classical PDG, and that a correct slice must account for data, control and quantum dependence.
- **S-cpdg (`icpc/cpdg.py`).** S-du's qubit rule unchanged, plus classical bits: a measurement also
  writes its bit, and an `if_else` also reads the bits its condition tests. S-du's backward pass.
- **Checked before any result.** S-cpdg equals S-du on all 704 unitary corpus-A pairs. It is larger on
  35 of the 80 dynamic pairs. On the catalogue's teleportation entry (K13) it equals S-lc.
- **Scoring (`icpc/cpdg_run.py`).** Exactly as the pre-registered runs: RQ1 soundness at |0…0⟩,
  dependence recall and miss categories; RQ3 containment and size on the same units; families
  soundness and recall.
- **Reporting.** S-du stays reported as pre-registered (H1 is unchanged). S-cpdg is reported beside
  it, descriptively, as the strongest classical baseline. In the paper, the wire rule is presented
  as classical data and control dependence plus quantum dependence (a multi-qubit gate acts on all
  its qubits).
- **Fixed before any S-cpdg output (2026-10-23).** The first run was stopped by hand before it wrote
  anything. Its backward pass copied S-du's, which never removes a written location, so a bit measured
  twice would also pull in the overwritten measurement. S-cpdg now uses reaching definitions for
  classical bits, as the definition in the paper and the wire rule's control edges do. Qubits are
  unaffected: every rule reads what it writes. Rechecked: equal to S-du on all 704 unitary pairs, and
  equal to S-lc on the catalogue's overwritten-bit entry (K14).

### Deviation I-13 (2026-10-25, AFTER all RQ1 results; author decision): slice size against the dependence floor
- **Why.** Table I reports mean slice size as a share of the circuit. Read alone, the wire rule's 70.4%
  looks weak, but no dependence-complete slice can be smaller than the dependences themselves. The
  sizes need that reference point.
- **Added measures (descriptive, from committed files only; no new run, no test).** Computed in
  `icpc/make_numbers.py` from `results/icpc/rq1/records.csv`, `rq1_lcq_remap/records.csv` and
  `corpus_l/{circuits,slices}.csv`:
  - the dependence floor, the mean of `n_influencing / n_ops` per pair;
  - the wire slice's and the QPDG reading's mean excess over it, and the number of pairs where the
    wire slice equals the dependence set;
  - mean size by width bin (2–3, 4–6, 7–10, 11–14 qubits) for the floor, wire, QPDG reading and
    commutation (applicable pairs);
  - corpus-L mean sizes (size / n_ops), measured in the cost run but not reported before.
- **Exclusion.** Two corpus-L circuits (`ham15-109-214`, `ham15-70`) were loaded with zero operations.
  They have no size and are excluded from the size means, and counted.
- **Reported.** A reference row in Table I (size and recall/precision only; the dependence set is not
  run as a slice, so it has no soundness value), one RQ1 paragraph, and a size-by-width figure
  (`icpc/make_result_figs.py::size`). None of the 267 earlier numbers changes; checked by diffing
  `results/icpc/numbers.json`.

### Deviation I-14 (2026-10-25, AFTER all results; author decision; exploratory): a tighter sound rule
- **Why.** The wire slice is 4.7 points above the dependence floor on average, and commutation fails
  under angle rebinding on 4 of 175 pairs. The author asked whether a tighter rule is possible.
- **Status.** Exploratory and post hoc. It is outside the confirmatory family H1–H5, and no
  pre-registered result is changed or replaced.
- **B1, commutation for all angles (`icpc/lcq_symbolic.py`).** Replace every numeric gate angle by a
  fresh `Parameter` before Qiskit's `LightCone`, which keeps a gate whose commutation depends on an
  unbound angle. Union over X, Y and Z as in S-lcq; positions mapped back by name, qubits and clbits
  in order. Scored as RQ1 (soundness at |0…0⟩, recall and precision), robustness as Deviation I-10
  (R-basis, R-haar, R-param), and on the families and the catalogue.
- **B2, the wire rule's excess (`icpc/wire_excess.py`).** Per-position influence for the pairs whose
  wire slice exceeds the dependence set (`icpc/influence.py`, oracle only). Each excess operation is
  tagged: (a) its removal alone changes the criterion's state; (b) removed by B1; (c) the criterion's
  final state is the same under every perturbation; (d) cut off by a reset or measurement; (e) other.
- **Decision gate (fixed now, before any B1 or B2 output).** A rule is reported as a slicer only if it:
  - is independent of input and angle, with a written soundness argument;
  - is 0 unsound on corpus A, the families and the catalogue;
  - is robust on 100% of its applicable pairs in R-basis, R-haar and R-param;
  - and, for a rule built from B2, reduces mean corpus-A size by at least 1 point.
  Otherwise the result is reported as a finding, with its counts, and the rule is not used.
- **B2 outcome and the rule it suggests (2026-10-25, after B2's output, before the rule's output).** Of the
  1,548 excess operations on 225 pairs, 644 are removed by B1 and 4 change the criterion when deleted alone.
  Of the remaining 844, 538 are in circuits with SWAP gates. Checked by hand on `basis_test_n4`: the
  circuit ends with SWAPs, so the criterion's final state is the state of another wire, and a Givens block
  that never reaches that wire is kept by the wire rule. **Rule S-lcw (`icpc/wire_swap.py`):** the wire
  rule, except that a top-level, unconditioned `swap(a, b)` is a move. It joins the slice if a or b is
  needed, and the needed set is permuted, a ↔ b, instead of being widened to both. A SWAP exchanges the
  two wires' states exactly, for every input and with no angle, so the backward pass is sound by the
  argument of Theorem 1 applied to the relabelled wires. Checked before scoring: with the move disabled the
  pass must equal S-lc on every corpus-A pair. Scored as B1 (corpus A soundness and recall/precision,
  robustness in all three regimes, families, catalogue) against the same gate.
- **Gate outcome (2026-10-25).** B1 (S-lcqs) passes: 0 unsound on corpus A (732 applicable), families
  and catalogue; robust 732/732, 732/732, 175/175; mean size 65.2% (S-lcq 64.4%). It is reported as a
  slicer. S-lcw fails the size condition: 0 unsound, robust 784/784, 784/784, 187/187, recall 1.000, but
  mean size 69.6% against 70.4%, a 0.74-point reduction (20 pairs in 5 circuits; 40 pairs have SWAPs).
  It is not reported as a slicer; its counts may be reported as a finding about the wire rule's excess.
