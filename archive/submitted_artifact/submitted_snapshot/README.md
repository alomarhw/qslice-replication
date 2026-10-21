> **Anonymized replication package** — prepared for double-blind peer review. All author and affiliation identifiers have been removed. Reproduce the results with `bash reproduce.sh`.

# Entanglement-Aware Program Slicing for Quantum Programs

QSlice is the first semantics-preserving program slicer for quantum programs. It is built on a typed
**Quantum Program Dependence Graph (QPDG)** modeling four dependency types — unitary-evolution (UED),
entanglement (ED), measurement-collapse (MD), and classical-feedback (CD) — and computes backward slices
that preserve the marginal measurement distribution (reduced density matrix) of the criterion qubits.
A semantic-refinement pass yields the smallest sound slice. The semantic-preservation guarantee is
machine-checked in Isabelle/HOL.

## Evaluation
161 real circuits across three public benchmark suites — **QASMBench (39), MQT Bench (42), VeriQBench
(80)** — 791 (circuit, criterion) backward slices per method, exact-statevector marginal oracle (eps=1e-4),
against naive classical-PDG and sound causal-cone baselines. The 4-way edge-type ablation
(`results/TAB_ablation.csv`) shows removing entanglement (ED) edges is by far the most damaging (+0.59 SVR).

## Layout
- `qdg.py` — QPDG construction, `backward_slice`, `semantic_refine_qpdg`, `forward_coverage` (the slicer).
- `qasm_loader.py`, `main.py` — corpus loading and the experiment driver.
- `analysis.py`, `plots.py`, `figures_qpdg.py` — analysis, result tables, figures.
- `isabelle/SemanticPreservation_v2.thy`, `isabelle/ROOT` — the machine-checked proof.
- `results/` — `results.json` (canonical), `TAB1.csv`, `TAB_per_corpus.csv`, `TAB_ablation.csv`, record CSVs.
- `figures/` — method (`fig_qpdg_concept_4edge.png`, `fig_qpdg_graph.png`, `fig_qpdg_slice.png`), results,
  ablation (`fig_edgetype_ablation.png`), and proof (`fig_proof_obligations.png`) figures.
- `data/` — QASMBench, MQT Bench, VeriQBench (+ dynamic) circuits; `data/ibm_cleveland_jobs/` raw IBM Q SamplerV2 job results.
- `scripts/recompute_hardware_tvd.py` — recomputes the real-hardware TVDs from the captured jobs.

## Reproduce
```bash
bash reproduce.sh          # venv + pinned deps + fetch + main.py + analysis.py + plots.py
```
Writes `results/` (incl. `results.json` and the tables) and `figures/`. Proof:
```bash
isabelle build -d isabelle QSlicePreserv   # Isabelle 2025-2; exits 0 with no `sorry`
```
Random seed fixed (`RANDOM_SEED = 42`) for deterministic reproduction.


## Data availability

The following large data files are **not** included in this package because they exceed GitHub's 100 MB per-file limit. Regenerate them by running the included fetch/reproduce scripts (`python fetch_data.py` / `bash reproduce.sh`), which download each dataset from its original source:

- `data/QASMBench-master.zip`
