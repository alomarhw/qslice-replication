# Dependence catalogue: run vs committed expectations

24 entries; 4 disagreement(s) with the expectations committed in e1dfdc3.

- K6b q0 4e_unfixed: expected [0, 1, 2, 3, 4], got [0, 1, 4]
- K6b q0 4e_fixed: expected [0, 1, 2, 3, 4], got [0, 1, 4]
- K11b q0 4e_unfixed: expected [0, 1, 2, 3, 4], got [0, 1, 4]
- K11b q0 4e_fixed: expected [0, 1, 2, 3, 4], got [0, 1, 4]

## Cause of the disagreements (diagnosed 2026-10-21; expectations NOT edited)
All 4 are the four-edge slicer on K6b and K11b. The expectation assumed that its "transitive
entanglement" edges link gates on either qubit of an entangled pair.
`fouredge/src/qdg.py::_add_transitive_entanglement_edges` instead iterates `list(frozenset({qa, qb}))`
and adds edges only from gates on the first-listed qubit to later gates on the second (here q0 → q1).
- The post-interaction gates on q1 (positions 2 and 3) get no edge into the later H on q0, so they
  are not in the slice.
- The slice is sound and equals the light cone on these entries.
- The asymmetry depends on set iteration order.

It is a second latent defect of the four-edge implementation. It is not covered by the
pre-registered measured-criterion fix (Deviation I-1 item 4), so it is reported, not changed. It
affects the meaning of "ED" in the ablation (RQ1), and the paper must say so.

## Summary against the committed expectations
- **Influence (semantic-dependence ground truth):** matches the hand derivation on all 24 entries.
- **du, lc, yz, q:** match on all entries, slices and soundness.
- **4e_unfixed and 4e_fixed:** match except K6b and K11b (above). The fix repairs K20, where
  4e_unfixed is unsound and 4e_fixed is sound.
- **lcq:** sound and ⊆ lc on every applicable entry. It is a strict subset on K4 and K8, where
  LightCone drops gates that commute with the backward-propagated observable. It is not applicable
  on K12, K13, K14 and K16 (`if_else`).
- **lcq_z (descriptive):** unsound on 10 entries. A single Z observable does not determine the
  reduced state.
