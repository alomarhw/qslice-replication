# Checkpoint B: GO/NO-GO for the ICPC 2027 Research Track

Prepared 2026-10-23 for the author's decision (plan Phase 4; rules fixed in `PROTOCOL_ICPC.md` §9
before any result). The abstract is due Thu 29 Oct AoE; no abstract is written until the author
picks a framing. Numbers: `experiments/results/icpc/confirmatory/summary.json` and the files cited.
Background: `FOUNDATIONS_REVIEW.md`.

## 1. The pre-registered confirmatory family (Holm across H1–H5, α = 0.05)

| | Hypothesis | Result | Verdict |
|---|---|---|---|
| H1 | S-q is invalid on fewer pairs than def-use | 0 vs 216 of 784 pairs; exact McNemar, Holm p < 10⁻¹⁰ | **Holds** |
| H2 | S-q is smaller than the light cone S-lc | Mean size 54.0% vs 70.4% of the circuit: difference 16.3 points, 95% CI [15.1, 17.7], relative reduction 23.2%; smaller on 477/784; Wilcoxon Holm p < 10⁻¹⁰, r = 1.00 | **Holds** |
| H3 | S-q stays valid under Haar product inputs on ≥ 95% of pairs | 434/784 = **55.4%**, Wilson CI [51.9, 58.8]; on pruned pairs 127/477 = **26.6%** [22.9, 30.8]; Holm p = 1 | **Fails.** Pruning is input-specific |
| H4 | S-q contains the fault no worse than S-lc − 5 points | 82.2% vs 95.7% on 5,688 units: difference **−13.5 points**, CI [−14.4, −12.6]; 769 units lost, 0 gained | **Fails.** S-q is significantly worse (the small p-value is for that direction) |
| H5 | S-q costs less to inspect than S-lc, on units both contain | Slice size: 2.9 fewer instructions, CI [2.7, 3.1], Holm p < 10⁻¹⁰ | **Holds on size.** The EXAM rank, reported alongside, is *worse* for S-q (−0.061, CI [−0.065, −0.057]), so the fault ranks later in the smaller slice |

H5 note: §4.3 lists two inspection-cost measures (size, EXAM). The analysis fixed size as primary
because it is listed first; both are shown. Author, please confirm or correct.

## 2. What the GO/NO-GO rules give

| Rule (§9) | Condition | Met? |
|---|---|---|
| GO-strong | H2 lower CI bound > 0 **and** relative reduction ≥ 0.15 **and** H3 ≥ 0.95 **and** S-q invalid on 0/784 | H2 yes, 0/784 yes, **H3 no** |
| GO-empirical | S-q sound on corpus A, but robustness or size fails | **Yes** |
| NO-GO | S-q unsound at \|0…0⟩, or fewer than 200 observable mutants | No (0/784 unsound; 5,688 units) |

**The rules give GO-empirical.** Two results the rules do not mention point the same way:
- Qiskit's `LightCone` gets most of the H2 reduction without depending on the input. S-q is only
  12.3% smaller than it, and larger on 72 of 732 pairs. `LightCone` is robust on 732/732 pairs
  under both random-input regimes (Deviations I-9, I-10).
- H4 fails by a wide margin.

## 3. The three framings

### GO-strong: "QSlice: precision beyond the light cone" (not supported)
- Would claim that verified separability pruning gives smaller slices that are still correct.
- Contradicted by H3 (26.6% robust on pruned pairs), by H4, and by Qiskit's `LightCone` already
  giving most of the reduction robustly.
- Reviewers B and C would find the same weaknesses as at ICSE.

### GO-empirical: "What does correct quantum slicing need, and what does extra precision cost?" (recommended)
An empirical study for program comprehension and debugging. Its claims, each backed by a
pre-registered result:
1. **Dependences, not a new paradigm (answers C-Q3).** Def-use reading of gates is unsound (216/784).
   The wire light cone, where a gate depends on all its qubits, is sound, complete against a semantic
   ground truth (recall 1.0), and robust on every input regime. Yu & Zhao's QPDG is sound but larger.
2. **Precision that holds.** Commutation pruning (Qiskit `LightCone`) cuts the light cone on 243/732
   pairs and stays correct on all random inputs. It gives up some dependence completeness (recall
   0.93).
3. **Precision that does not hold.** State-based pruning (QSlice) cuts 23% more than the light cone
   but is valid for one input only. It loses the faulty operation in 769 of 5,688 seeded faults. A
   joint criterion (S-qW) recovers 691 of them. LLMs localize worse with its slices.
4. **Debugging evidence (answers B-Q1):** fault containment on seeded faults and on Bugs4Q, the MBFL
   comparison, and the LLM localization tasks T1/T2.
5. **Cost and hardware (answers B, A-Q2):** S-lc takes milliseconds, while S-q exceeds 120 s at
   depth ~190. Noise and hardware go in the Discussion.

This is the plan's anticipated fallback. It is still a Research Track paper: ICPC asks for
significance to comprehension and debugging, and every claim above is a debugging-relevant measured
result, including the negative ones. Risks:
- The novelty must be argued as a study (the first pre-registered comparison of dependence
  definitions for quantum slicing, against a semantic ground truth), not as a tool.
- The title must differ from the ICSE preprint's.

### NO-GO for the Research Track: RENE (negative results) or ERA (not recommended)
- Rule 3 is not triggered.
- Section 2 above gives positive findings (claims 1 and 2) as well as negative ones, so a
  negative-results-only paper would undersell them.
- If chosen, the RENE and ERA deadlines must be checked on conf.researchr.org first.

## 4. What the author decides
1. Framing: GO-strong, **GO-empirical (recommended)**, or NO-GO.
2. H5: confirm slice size as the primary inspection cost (EXAM alongside), or name EXAM.
3. The Isabelle proof (RQ6 of ICSE): replace it with causal-cone soundness only, as the rebuttal
   promised, or drop it.

After the decision: abstract by Oct 28 for the author to edit (HotCRP deadline Oct 29 AoE), then the
paper by Nov 5.
