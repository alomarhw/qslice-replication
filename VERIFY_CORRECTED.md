# Verification of the corrected run (Phase 1)

Date: 2026-10-20. Base: replication-v2 at `2b00bc1` plus its uncommitted working tree, imported as
`31e5a3d` on branch `icpc`.

Each defect below was checked in the code, not taken from the docs. Paths are relative to this
repository, and `qdg.py` means `qslice/qdg.py`, the Sec. III method the corrected run imports.

## 1. Regeneration

Environment:
- `~/venvs/qslice-icpc`: Python 3.12.2, `experiments/requirements.lock`, qiskit 2.3.0, numpy 1.26.4
  (`phase1_logs/pip_freeze_main.txt`).
- `~/venvs/qslice-icpc-hw`: for the hardware table only. Its pins are those of `reproduce.sh`, which
  leave qiskit unpinned, so it resolved qiskit 2.4.2 and qiskit-ibm-runtime 0.50.0
  (`phase1_logs/pip_freeze_hw.txt`).

| Step | Command | Result | Log |
|---|---|---|---|
| Corpus hashes | `fetch_data.py --verify` | OK: every shipped corpus file matches `MANIFEST.sha256.tsv` | `fetch_verify.log` |
| Oracle tests | `experiments/tests/test_oracle.py` | pass: random unitary circuits vs `Statevector` max error 2.2e-16; teleportation with feedback 2.2e-16; reset, mid-circuit and terminal measurement OK | `test_oracle.log` |
| RQ1–RQ4 | `experiments/regenerate.py` | **16/16 IDENTICAL** byte for byte (`rq4_ablation/` 4 files, `method_primary/` 6, `method_secondary/` 6), 13 min 18 s | `regenerate_rq1_rq4.log` |
| RQ5 | `fetch_data.py` then `regenerate.py --with-rq5` | running at commit time; added in a follow-up commit | `fetch_full.log`, `regenerate_with_rq5.log` |
| Hardware (RQ7) | `hardware/regenerate.py` | **IDENTICAL (content; line endings differ)**, `TAB_hardware_ibmq.csv`: 16/18 within TVD 0.05 (uncorrected; see D11) | `hardware_regenerate.log` |
| Isabelle (RQ6) | `isabelle build -d . QSliceSoundness` (temp copy, Isabelle2025-2) | **exit 0**, including the first build of the HOL and HOL-Library heaps (22 s). The grep for `sorry`, `oops` and `axiomatization` finds nothing. | `isabelle_build.log` |

## 2. Defects D1–D6, D8, D9 (and D10)

| # | ICSE defect | Check made | Evidence | Verdict |
|---|---|---|---|---|
| D1 | Parser dropped unsupported gates, `measure`, `reset`, `if`, custom gates | **Counted operations in every corpus-A raw `.qasm`** with a parser that shares no code with qiskit (`phase1_checks/d1_instruction_counts.py`: register broadcast expanded; gate bodies, declarations and barriers skipped), and compared with `qasm2.load` as `common/corpus.py:60` calls it | `qasm2.load` equals the raw count on **160/160** parsable circuits. The 161st, `vqe_uccsd_n4`, fails to parse and is the documented exclusion. For contrast, the submitted loader (`selection/qasm_loader.py`, byte-identical to the archived one) **dropped 907 operations on 118 of 161 circuits**, e.g. `ipea_n2` 41→8 and `cc_n12` 59→22. Per-circuit table: `phase1_checks/d1_instruction_counts.csv` | **fixed** |
| D2 | Oracle shared the slicer's simulator | Read the imports and call paths of `common/oracle.py` | It imports only `numpy` and `qiskit` (`QuantumCircuit`, `Clbit`, `ClassicalRegister`, `quantum_info.Operator`), nothing from `qslice/`, `fouredge/` or `selection/`. It is its own pure-state branching simulator (`_Sim.run_block`), taking gate matrices from qiskit (`op.to_matrix()`/`Operator`). The slicer's internal check uses qiskit `Statevector` + `partial_trace` (`qdg.py:482-547`). They share only qiskit's gate definitions. Both drivers judge every slice only through `materialise` + `reduced_states` + `fidelity` (`method_eval/run.py:57-78`, `rq4_ablation_rerun/run.py:63`). | **fixed**. See note N1 |
| D3 | "Naive" baseline was ops touching the target | Read `naive_classical_backward_slice` (`qdg.py:392-430`) | A genuine def-use port: a controlled gate writes its targets and reads controls plus targets (`num_ctrl_qubits`); other gates read and write all their qubits. A backward pass keeps an op iff it writes a needed qubit, then adds the qubits it reads. | **fixed** |
| D4 | "Causal" baseline was the connected component | Read `QDG.build` DATA edges (`qdg.py:113-126`), `_add_control_edges` with the patch (`method_eval/control_fix.py`), and `backward_slice` (`qdg.py:307-334`); the driver uses `remove_edge_type(ENTANGLEMENT).backward_slice` (`method_eval/run.py:62-66`) | DATA edges link each op to the previous op on *each* of its qubits, so a multi-qubit gate depends on all its wires. CONTROL edges link a measurement to the conditioned op. Backward reachability from the ops on the target gives the past light cone plus classical control: ops on a partner after its last interaction are not predecessors and are excluded. The corrected results show it sound on 784/784 pairs. | **fixed**. See note N2 |
| D5 | The Sec. III method was never run | Compared `entanglement_pruned_slice` (`qdg.py:462-549`) line by line with the algorithm in `paper/QSlice_31399_ICSE_final.tex` lines 149-164, and checked that the driver calls it (`method_eval/run.py:65`) | Every step matches:<br>- causal cone (l.3);<br>- non-unitary fallback (l.4);<br>- full reference state (l.5);<br>- partner-only candidates (l.6);<br>- one O(L) statevector pass with MI < `sep_eps` = 1e-9 (l.7-8);<br>- descending trial prunes, kept iff the trace distance to the reference < 1e-9 (l.9-13). | **fixed**. See note N3 |
| D6 | Forward completeness computed from the ground truth | Read `method_eval/run.py:79-96` | The truth is the qubits whose exact reduced state moves (trace distance > 1e-9) when X is applied to the criterion at the input, computed by the independent oracle. `covered` comes from the slicer's forward slice alone and is **not** intersected with the truth. | **fixed**. See note N4 |
| D8 | Outcome-enforcing acceptance checks | Grepped all active code (`experiments/`, `qslice/`, `fouredge/src/`, `selection/`) for `raise`, `assert` and `exit`, and read each hit | Every hit is a data-validity guard:<br>- unsupported instruction or more than 4096 branches (`oracle.py`);<br>- timeout (`rq5_scalability/run.py:63`);<br>- the pre-registered Table VII selection check (`rq5_scalability/run.py:188`);<br>- "no circuits loaded" (`qslice/main.py:486,579`);<br>- missing-data errors (`selection/qasm_loader.py`).<br>None depends on which slicer wins. `validate_results`, which raises unless QPDG has 0% invalid slices, exists only in `archive/submitted_artifact/` (the byte-identical record of the submission, `main.py:343-355`), and no active code imports it. | **fixed in active code**. See note N5 |
| D9 | ε inconsistent (1e-4 / 1e-6 / 0.999999) | Grepped code and docs | One threshold: `common/evaluate.py:12` `FIDELITY_EPS = 1e-6`, used by both drivers. `oracle.fidelity` is the exact qubit Uhlmann fidelity, tr(ρσ) + 2√(det ρ det σ), in the same squared convention as the paper's Eq. 1. The docs match (`PROTOCOL.md` §1, `experiments/README.md`). The old values remain only in `archive/`. The slicer's internal prune check is stricter (trace distance < 1e-9), as the paper states. | **fixed** |
| D10 | qiskit unpinned; the paper claims 2.4.2 | `experiments/requirements.lock` | qiskit 2.3.0, numpy 1.26.4 and the rest pinned; installs cleanly. The paper `.tex` line 230 still says "Qiskit 2.4.2, Qiskit Aer 0.17.2", which is false for the corrected run (Aer is not used at all). | **fixed in code; paper text todo**. The hardware env is still unpinned; see N6 |

## 3. Notes: things the next phases must handle

- **N1, oracle vs plan rule §1.3.** The plan asks for an oracle based on `Statevector`/`partial_trace`.
  The corrected oracle is an independent branching simulator, *validated against* `Statevector` +
  `partial_trace` (2e-16), because `Statevector` cannot handle mid-circuit measurement, reset and
  `if_else`. This meets the rule's intent (no shared simulation code). Say exactly this in the paper.
- **N2, two different "causal cones".** The method evaluation's causal slice is light cone + classical
  control and is sound on all 784 corpus-A pairs. The four-edge implementation's `CAUSAL_CONE` variant
  (`fouredge/src/slicer.py:42`, UED+ED only, no MD/CD) is **unsound on 118 of 962 ablation pairs**:
  - all 118 are dynamic-circuit pairs (118 of 258);
  - none is a unitary pair (0 of 704).

  The ICPC paper must use one definition. The plan's (b) is the bidirectional wire cone *with
  classical control*. Never report the four-edge variant under that name.
- **N3, "QPDG" vs what the method uses.** `entanglement_pruned_slice` never uses the ENTANGLEMENT
  edges: it is light cone + MI nomination + exact verification. The ENTANGLEMENT edges (a union-find
  closure over coupled qubits, i.e. the old connected component) are used only by `forward_slice` and
  by the full-QDG `backward_slice`. This supports the plan's renaming (TQDG) and the Reviewer C
  framing. The paper should not claim the pruned slice is "QPDG reachability".

  The worked example in the ICSE `.tex` (line 169) still describes the causal baseline as "every
  operation on any qubit ever coupled to the target", which is the old D4 definition. Rewrite it.

  Also: `extract_slice_circuit` (`qdg.py:456-459`) silently skips instructions that fail to append.
  This affects only the slicer's internal check, since the oracle judges the materialised slice, but
  the ICPC code should log such cases.
- **N4, forward completeness 1.000 by over-inclusion.** QPDG's forward slice uses the ENTANGLEMENT
  closure, so it covers whole coupled components. Completeness 1.000 is honest, not circular, but its
  precision is not measured. This supports dropping RQ3 as planned.
- **N5, the archived `validate_results`.** Rule 1 says to delete outcome-enforcing checks. In the
  archive it is the evidence of what was submitted, and deleting it would rewrite that record. It is
  not executed by anything. Recommendation: keep the archive byte-identical, and add one line to
  `PROVENANCE.md` saying it is retained as history and never run. Author's call.
- **N6, unpinned hardware env.** `reproduce.sh` installs `qiskit-ibm-runtime>=0.40` with qiskit
  unpinned, so the hardware table was recomputed under qiskit 2.4.2 and runtime 0.50.0, not 2.3.0. It
  still came out identical. But runtime 0.50 warns that `qiskit_ibm_runtime.utils.json`, which
  `recompute_hardware_tvd.py:11` imports, will be removed, so a future runtime will break the
  recomputation. Pin `qiskit-ibm-runtime` and qiskit in a `hardware/requirements.lock` (Phase 6).
- **N7, the four-edge slicer's 5 unsound pairs.** Confirmed in `results/rq4_ablation/records.csv`:
  - `shor_n5` q4 (F = 0.5);
  - `bb84_n8` q0 (F = 0.0), q3 (0.5) and q6 (0.5);
  - `cc_n12` q11 (F = 0.854).

  All are dynamic circuits. This is Phase 3 step 3.
- **N8, pre-registration evidence in the corrected repo.**
  - `PROTOCOL_HISTORY.txt` matches `git log` (`90b2991` freeze → `229bbcf` Deviation 1 → `157c6ae`
    → the runs start at 14:19:50 → `7cd658c` RQ5 freeze → the RQ5 run at 19:23:39).
  - The run logs committed at `229bbcf` are a *failed* invocation (an argparse usage error). The logs
    of the real runs exist only as **uncommitted** changes in `$Q-corrected`, byte-identical to
    replication-v2's `experiments/logs/`. The timeline is still consistent, but the actual run logs
    were never committed.
  - When describing pre-registration, cite the freeze commits and the timestamps in `runs.log`. Do
    not claim the run logs are in version control.
- **N9, D11 still open.** The hardware recomputation is the uncorrected 16/18. Rebuttal Correction 4
  (the QAOA register mismatch) is not applied.
- **N10, Isabelle claim wording.** `cone_sound` is proved relative to two locale assumptions
  (`locality`, `dependence`). They are shown satisfiable only in a **classical** model
  (`interpretation classical`). The quantum density-matrix instance is stated as standard and **not
  mechanized**, and pruning is not covered (theory header and `isabelle/README.md`). So "the light
  cone's soundness is machine-checked" (plan §4) slightly overstates it. Accurate wording: "soundness
  of causal-cone slicing is machine-checked relative to two no-signalling assumptions satisfied by
  CPTP semantics (the quantum instance is not mechanized); pruning is checked at run time".
