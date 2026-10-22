# Journal

## 2026-10-20: Phase 1

**Done.**
- Copied replication-v2 to `qslice-icpc` on branch `icpc`. The first commit records replication-v2's
  uncommitted edits and the untracked `archive/` as found.
- Added `paper/` with the ICSE `.tex` and `.bib`.
- Built pinned venvs outside the repo (`~/venvs/qslice-icpc`, `~/venvs/qslice-icpc-hw`).
- Ran: corpus verification, oracle tests, regeneration (RQ1–RQ4, then RQ5 after fetching QASMBench),
  the hardware recomputation and the Isabelle build. Logs are in `phase1_logs/`.
- Wrote `VERIFY_CORRECTED.md`, `DATA_SOURCES.md` and `REVIEW_CHECKLIST.md`.

**Found.**
- D1–D6, D8 and D9 are fixed in the active code (details in `VERIFY_CORRECTED.md`).
  - D1, measured: `qasm2.load` keeps every operation on 160/160 parsable corpus-A circuits.
  - The submitted loader had dropped 907 operations on 118 circuits.

**Surprised by (reported to the author).**
- The four-edge implementation's `CAUSAL_CONE` variant has no MD/CD edges. It is unsound on 118
  dynamic-circuit pairs, while the method evaluation's light cone is sound on all 784 pairs. There are
  two different "causal cones" in the package.
- `entanglement_pruned_slice` never uses ENTANGLEMENT edges. The method is light cone + MI-nominated,
  verified pruning.
- The real run logs of the corrected experiments were never committed in `$Q-corrected` (the
  committed ones are a failed invocation).
- The hardware env is unpinned (qiskit 2.4.2, runtime 0.50.0), and runtime 0.50 deprecates the import
  the recompute script uses.
- The Isabelle theory's assumptions are shown satisfiable only in a classical model; the quantum
  instance is not mechanized.
- No upstream license notices ship with any corpus.

**Author note (Oct 20): figures.** The ICSE paper's graphs were not professional quality. Plan for
Phase 5/6:
- redraw every figure from the regenerated `results/*.json` with one consistent style, sized for the
  IEEE two-column layout, colour-blind-safe, legible in grayscale;
- no titles inside plots;
- Fig. 1 drawn on the running example (A6);
- one generator script per figure, listed in PROVENANCE.

Not part of Phase 1.

**Searched RP and RP-old for missing pieces (author's request).**
- **VeriQBench commit: recovered.** No local clone exists, but the git blob SHAs of all 966 shipped
  files match upstream `Veri-Q/Benchmark` at every commit from `dc2651c` (2025-04-11) on
  (`phase1_checks/veriqbench_upstream_match.txt`).
- **MQT Bench export options: not found.** There is no generator clone or configuration in either
  tree, only copies of the shipped circuits.
- **The lost 34-circuit Table VI driver (D2): not found.**
  - The only other four-edge driver is `bc5893cf/main.py` (Jun 23; artifact copy Jun 28;
    byte-identical in RP-old). It is the general pipeline (default 80 circuits), not the unsaved
    Jun 29–30 run.
  - The plan forbids that workspace anyway (fake user-study code).
  - D2 stays "not reproducible", as PROVENANCE says.

## 2026-10-21: Phase 3

**RQ1 full run** (commit `5e5232e`, 21 min, `logs/icpc/rq1.log`).
- 784 pairs.
- 3 circuits excluded at load (`excluded.json`): one QASM parse error and two Grover circuits that
  exceed 220 instructions after decomposition.

**Miss-classifier bug, found after the run and fixed.**
- **Bug:** `classify_miss` did not expand a QASM 2 `if(creg==v)` condition. The condition is a
  `ClassicalRegister`, which has no `__iter__` attribute. So measurement→condition (CONTROL) edges
  were missed.
- **Effect:** 134 S-du misses on dynamic circuits (dqc_*, inverseqft_n4, qec_sm_n5) were labelled
  "unreachable", a label the code itself says contradicts no-signalling.
- **Fix:** `icpc/rq1_reclassify.py` recomputes only the category column; the old value is kept as
  `category_before_fix`. All 134 are now "feedback", and none remain "unreachable"; the other 6,229
  rows are unchanged.
- **Unaffected:** the classifier is not used for any slice, soundness, influence or recall number.

**RQ2 robustness and RQ3 full runs** were started at `440d12d` (8 workers each). The classifier fix
does not touch either of them.

**LLM T1, open arms** (items frozen at `6c03f7c`; prompts unchanged).
- O-mid: 221 primary and 150 consistency calls; all parse.
- O-small: same call counts. Its answers are string lists, which led to **Deviation I-4**. My slip:
  the development output was chained into the scored run without being read.
- **GPU serving:** vLLM needed `VLLM_USE_FLASHINFER_SAMPLER=0`, since no CUDA toolkit is available
  for FlashInfer's JIT (`llm_models.md`).
- **Lesson:** `pkill -f "vllm serve"` over ssh kills the ssh shell itself; use the `[b]in/vllm` pattern.

**Hardware, rebuttal Correction 4 (§7.1)**, computed from the 18 captured `ibm_cleveland` jobs; no new
hardware time. Script: `hardware/scripts/recompute_hardware_tvd_corrected.py`. Output:
`experiments/results/icpc/hardware/hardware_tvd_corrected.csv`.

**Defects in the ICSE script** (`recompute_hardware_tvd.py`, kept unchanged because it reproduces the
reported table):
1. It reads only the first classical register. The QAOA circuits have three one-bit registers.
2. It guesses the criterion bit as the slice bit closest to 1/2, at the same position in the full
   register. For QAOA it compared bit 0, while the slice measures bit 1. That is where
   P_slice = 0.0 and TVD ≈ 0.49 came from.

**Corrected rule.** Compare the bits the slice actually measures. In all 18 jobs, those bits measure
the same virtual qubit in both pubs (checked via the layout).

**Result.**
- Still **16/18** within TVD 0.05.
- qaoa: 0.491 → **0.053**. qaoa-T: 0.490 → **0.131**.
- **Noise-free TVD of the submitted circuits is 0 for all 18**, so every slice run on hardware is
  sound. The QAOA gaps are hardware noise: the full and slice circuits ran on different physical
  qubits, and the qaoa-T full circuit has P(1) = 0.639 against an ideal 0.5.

**Correction to the rebuttal.** It said the two exceptions "reflect our analysis rather than hardware
noise". That holds for the size of the ICSE TVD values, but not for the corrected ones.

**Caveats that stay.**
- The TVD is Z-basis, so it is phase-blind.
- The hardware slices came from the four-edge `QSLICE_FULL` variant, not the Sec. III method.

**Decision for the author (§7.1):** a Discussion paragraph, or drop hardware.

**Author decision (§7.1):** hardware is kept as one Discussion paragraph on noise, using the
Correction 4 numbers only (`PROTOCOL_ICPC.md`).

**Author decision (Deviation I-4):** the frozen parser is primary. The post-hoc string-index parser is
a labelled sensitivity check, reported for O-small.
