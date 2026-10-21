# redrawn_figures/: new drawing scripts for Figs. 1 and 4

The scripts that drew the submitted Figs. 1 and 4 were not saved. These two scripts were written for
this package. They redraw each figure from its real source. Their output is a **redrawing**, not the
original file, and they add no new results.

| Script | Source it draws from | Check it performs |
|---|---|---|
| `fig1_qpdg_teleportation.py` | runs the unchanged four-edge implementation (`../reported_results/rq4_ablation/src/qdg.py`, `qdg_from_circuit`) on the teleportation circuit | compares the 17 typed edges it builds with the edges read off the submitted Fig. 1 and prints IDENTICAL or DIFFERENT. Result: **IDENTICAL**, so Fig. 1 depicts that implementation's graph |
| `fig4_proof_obligations.py` | the unchanged `../reported_results/rq6_isabelle/SemanticPreservation_v2.thy`; runs `isabelle build` if available | marks each of the 7 theorems machine-checked only if the build succeeds. **Unlike the submitted figure**, it also lists the axioms each proof cites and flags the two that are unsound (PROVENANCE.md, D3) |

```bash
python fig1_qpdg_teleportation.py out/     # needs qiskit>=2.3, networkx, matplotlib
python fig4_proof_obligations.py out/      # needs matplotlib; isabelle optional
```

Layout and colours follow the submitted figures. Pixel-level identity is not expected.

Fig. 1 shows the four-edge implementation (UED/ED/MD/CD). The code that produced Tables III-V and VII
has only state-carry and entanglement edges (PROVENANCE.md, D1).
