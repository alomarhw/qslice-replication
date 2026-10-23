# Foundations review: what in the ICSE QSlice paper still holds

Written 2026-10-23, before Checkpoint B and before any ICPC text. For each foundational claim of the
ICSE paper (`paper/QSlice_31399_ICSE_final.tex`), this lists the reviewers' objection
(`~/Projects/RP/Docs/REVIEWS_AND_REBUTTAL.md`), what the corrected and pre-registered ICPC runs show,
and a verdict. Every number comes from a committed result file named in the row. Nothing here is a
paper claim yet.

## Two properties the ICSE paper treated as one

The corrected runs separate two things the paper called "soundness":

- **(a) State preservation.** Running only the slice reproduces the criterion qubit's reduced state.
  This is the paper's Eq. 1, checked at one input (|0…0⟩).
- **(b) Dependence completeness.** The slice contains every operation where a change (a fault) could
  change the criterion qubit's state, for some input. This is the §2.1 semantic-dependence ground
  truth (`icpc/influence.py`: a random unitary inserted after the operation, at |0…0⟩ and 10 Haar
  product inputs).

(b) is what a developer debugging a wrong qubit needs. A slice can have (a) and still drop the
faulty operation. Most of the verdicts below follow from this distinction.

## Verdicts

| # | ICSE claim | Reviewer objection | Corrected evidence | Verdict |
|---|---|---|---|---|
| F1 | Classical slicing is unsound for quantum programs; entanglement is the gap (motivating Bell example, Sec. III-A) | **C-Q3:** it depends on how gate dependences are defined; a controlled gate that depends on both wires fixes the Bell example | The def-use port is unsound on 216/784 pairs (27.6%; the ICSE paper said 42.9%). Its misses are kickback (1,737), same-wire (835), written-operand (654), feedback (134). The **wire light cone**, where a multi-qubit gate depends on all its wires, is sound on 784/784 with dependence recall 1.000, with no entanglement edges at all (`results/icpc/rq1`) | **Does not hold as stated. Reviewer C is right.** The failure comes from reading a gate as "reads control, writes target", not from a missing quantum relation. In the ICPC paper it is a pitfall, not a contribution |
| F2 | Entanglement dependency (ED, union-find closure) is a new relation that soundness requires (Def. ED, RQ4 "ED dominant, ΔSVR +0.588") | **B:** concepts already known; **C:** [27] already has an entanglement edge | Sound slices need no ED edges (S-lc above). In the four-edge graph, removing ED raises SVR to 0.639 with the fixed seed (`results/icpc/ablation_fixed`), but that graph's own edges are not wire-symmetric. The golden tests also found an order-dependent asymmetry in its transitive-ED edges (K6b, K11b; `results/icpc/catalogue`). Yu & Zhao's slicing with entanglement edges is sound too (784/784) but larger (78.6% of the circuit vs 70.4%) | **Does not hold as a semantic claim.** ED is "needed" only to repair an implementation whose other edges are one-directional. The ablation shows what each edge does inside that graph, not what quantum programs need |
| F3 | Reduced-state fidelity ≥ 1−10⁻⁶ is a basis-independent soundness criterion (Eq. 1) | none directly; **B-Q2** asks for guarantees | The criterion is sound as a definition and is the oracle all runs use (D9, `VERIFY_CORRECTED.md`). It is checked at one input. At |0…0⟩ every slicer except def-use satisfies it | **Holds, but narrower than presented.** It is state preservation (a) **at the given input**, not slice soundness for all inputs. The paper must say "sound at input ψ" |
| F4 | The light cone is sound by no-signaling | — | S-lc: 784/784 sound at |0…0⟩, and **100% robust** under random basis inputs, Haar product inputs and parameter rebinding (`results/icpc/rq2_robustness`). No unsound slice in any structure family (`results/icpc/families`). Dependence recall 1.000 | **Holds, and it is the solid foundation.** It is the one dependence definition with both (a) for all tested inputs and (b) |
| F5 | Separability pruning gives "precision at equal soundness": QSlice slices are 43% smaller than the causal cone (RQ2) | **B:** only overall size reductions reported; **C:** novelty vs [27] is only the pruning | S-q is 54.0% of the circuit vs 70.4% for S-lc: **22.8% smaller per pair** (pooled 21.1%), smaller on 477/784. Against **Qiskit's `LightCone`** (732 pairs, Deviation I-9) S-q is only **12.3% smaller** (pooled 10.8%), and **larger on 72 pairs**. `LightCone` finds the paper's own worked example (K8) exactly (`results/icpc/rq1_lcq_remap`) | **Does not hold as stated.** The 43% came from the old, simplified evaluation. The real reduction is 23% against our cone and 12% against the standard tool developers already have |
| F6 | MI nominates prunes and exact re-verification makes the slice "provably sound" (Algorithm, line 13) | **B-Q2:** guarantees for indirect, multipartite, uncomputed entanglement? | Every prune is verified, so (a) holds at |0…0⟩ on 784/784. But pruned slices stay valid under **Haar product inputs on only 26.6%** of pairs, random basis inputs 65.8%, parameter rebinding 78.1% (`results/icpc/rq2_robustness`, pruned pairs only). Of the 2,847 operations S-q removes, **1,618 influence the criterion and change it for some input**; only 669 never influence it. Dependence recall 0.807, against 1.000 for S-lc (`results/icpc/rq1`) | **Holds only for the one input.** "Provably sound" overclaims: the prune is a property of a run at |0…0⟩, not of the program. QSlice gives (a) at that input and gives up (b) |
| F7 | Smaller sound slices help debugging ("never excluding the faulty one", Discussion) | **C-Q4:** what if a bug makes an entangled state separable? **B-Q1, A:** practical value not shown | Fault containment on 5,688 seeded faults: S-q **82.2%**, S-lc 95.7%, Yu & Zhao 97.4%, random equal-size 62.4%. In **769** units S-lc contains the fault and S-q does not (C-Q4); the joint criterion S-qW recovers 691 of them (`results/icpc/rq3`). With LLMs, S-q slices *lower* fault localization against the full circuit and against S-lc (T2, p ≤ 0.02, `results/llm`). Slice-filtered MBFL is no better (`results/icpc/mbfl`) | **Does not hold. Reviewer C's concern is confirmed.** Pruning removes the faulty operation in 13.5% of cases where the light cone keeps it |
| F8 | QPDG differs from Yu & Zhao [27] by the soundness criterion and the pruning | **C-Q1:** include [27] as a baseline | Re-implemented (`slicers/yuzhao.py`): sound 784/784, dependence recall 1.000, precision 0.835, fault containment 97.4% | **The difference is real but not in our favour.** [27]'s reachability already gives sound, complete slices; what we add (pruning) costs completeness |
| F9 | Forward completeness 1.0 vs 0.70 (RQ3, Table V) | (Correction 2: held by construction) | Not re-run as an RQ. The §2.1 ground truth replaces it with a non-circular measure | **Withdrawn.** Use the ground-truth recall in F1/F6 instead |
| F10 | QPDG construction is sub-second up to 169 qubits (RQ5) | **B:** excludes the MI and simulation cost | End to end (`results/icpc/cost`): S-lc stays at milliseconds. Graph build grows about 4× per depth doubling (0.03 s → 21.7 s). S-q takes about 1.3 s at depth 17, 10 s at 45, 50 s at 92, and passes the 120 s limit at depth ~190 on 4 of 5 circuits (8 qubits). Width 14: up to 8.7 s | **Structural claim holds; the practical one does not.** Pruning is bounded by exact simulation, as Reviewer B said |
| F11 | Isabelle proof of the semantic-preservation theorem (RQ6) | (Correction 5: axioms too strong) | Builds with no `sorry` (`VERIFY_CORRECTED.md`), but the rebuttal promised to replace it with causal-cone soundness only | **Must be replaced or dropped.** Not yet done |
| F12 | IBM hardware: 16/18 within TVD 0.05 (RQ7) | **A-Q2:** noise and real hardware | Recomputed with the corrected register (D11): 16/18 within threshold; noise-free TVD 0 on all 18. Noisy simulation: S-lc's D_cross = 0 (`results/icpc/hardware`, `results/icpc/noise`) | **Holds as a discussion point only** (author decision, §7.1) |
| F13 | Superposition does not enlarge the graph (rebuttal A-Q1) | **A-Q1** | Consistent with all runs: graph size depends on operations only (`results/icpc/cost`, graph columns) | **Holds** |

## What this means for the ICPC paper

1. **The foundation is the wire light cone with classical control**, not the QPDG's entanglement
   edges. It answers C-Q3 directly: quantum slicing is not different in principle; gate dependences
   must be defined symmetrically, and then a classical-style reachability slice is sound and
   complete.
2. **Be precise about which property each slicer has.**
   - S-lc: (a) at every tested input, and (b).
   - Qiskit `LightCone`: (a), smaller than S-lc on 243/732 pairs, never unsound at |0…0⟩, but
     recall 0.93. It drops gates that commute with the observable, yet a fault there can still
     matter. Its robustness to other inputs has **not** been measured yet (open item below).
   - QSlice (S-q): (a) at |0…0⟩ only, recall 0.807.
3. **QSlice's pruning is an input-specific explanation, not a program slice.** It answers "which
   operations shaped this qubit in this run at this input", which can still be useful, but it is
   not what fault localization needs, and the data say so (F6, F7).
4. **The ICSE headline numbers must not be reused.** That covers 42.9%, 43%, 0.588 and 1.0 vs 0.70.
   They came from the simplified evaluation the rebuttal disclosed.
5. This points to the **GO-empirical** framing of plan Phase 4, not GO-strong. GO-strong requires
   robustness ≥ ~95%; the pruned slices reach 26.6–78.1%. The author decides at Checkpoint B.

## Open items before Checkpoint B

- **Robustness of S-lcq.** RQ2 tested only S-lc and S-q. Running S-lcq under the same three input
  regimes would show whether Qiskit's pass is input-independent, as theory suggests. This needs a
  pre-registration note, because §3 names only S-lc and S-q.
- **Isabelle (F11).** Replace the theory with causal-cone soundness, or drop RQ6.
- **Paper text D10.** The ICSE text still says Qiskit 2.4.2 and Aer; the corrected run uses qiskit
  2.3.0 and no Aer.
