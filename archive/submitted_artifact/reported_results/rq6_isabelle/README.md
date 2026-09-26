# rq6_isabelle/: submitted Isabelle/HOL theory (Table VIII, Fig. 4)

`SemanticPreservation_v2.thy` and `ROOT` are byte-identical to the submitted artifact.

```bash
isabelle build -d . QSlicePreserv      # Isabelle2025-2
```

This builds with exit code 0. The only occurrence of `sorry` is in a comment. **The build does not
establish the paper's claim.** The theory proves its obligations relative to four axioms (lines
64-74), and two of them are unsound as stated:

- `unitary_off_V_preserves_rdm` has a premise `q ∉ V` about a qubit `q` that does not occur in
  `apply_unitary rho U`. It therefore asserts that every unitary preserves every reduced state on V
  (for any V that leaves out some qubit).
- `rdm_locality` asserts that equal reduced states on V stay equal under any program. That is false
  for entangling gates acting across V and its complement.

Also, `project V` keeps exactly the gates that touch V, which is the naive slice rather than the QPDG
slice. The mechanization claim is withdrawn; see `../../PROVENANCE.md`, D3.
