# isabelle/: mechanized soundness of causal-cone slicing (RQ6)

```bash
isabelle build -d . QSliceSoundness      # Isabelle2025-2; about 20 s including HOL-Library
```

The build succeeds with no `sorry`, no `oops` and no `axiomatization`.

## What is proved
`QSliceSoundness.thy` works inside a locale `local_semantics` with two assumptions:

| Assumption | Statement | Why it holds for quantum circuits |
|---|---|---|
| `locality` | an operation acting outside W leaves the reduced state on W unchanged | no-signalling: a CPTP map on qubits disjoint from W commutes with the partial trace onto W |
| `dependence` | the reduced state on W after an operation depends only on the reduced state on W together with the operation's support | the partial trace over everything outside that union commutes with the operation |

These cover unitaries, non-selective measurement and reset. A measurement together with the gate it
controls is covered too, taken as one operation on the union of their qubits.

Results:
- **`cone_sound`:** the causal-cone backward slice `cone P W` preserves the reduced state of the
  criterion qubits W, for every circuit P and every initial state.
- **`cone_sound_gen`:** the generalised form used in the induction.
- **`cone_subseq`:** the slice is a subsequence of the circuit.
- **`criterion_needed`:** the criterion qubits are always needed.
- **`interpretation classical`:** the assumptions hold in a concrete classical model, so they are
  satisfiable and the theorems are not vacuous.
- **`classical_example`:** a worked example in that model.

## What is not proved
- **The quantum instance.** That density matrices with partial trace satisfy the two assumptions is
  standard linear algebra, but it is not mechanized here.
- **Separability pruning.** The theorem covers the causal cone, which is QSlice's sound starting point.
  QSlice removes further operations only when an exact check confirms that the criterion's reduced
  state is unchanged. Each such prune is justified by that runtime check, not by this proof.
- **Correspondence with the Python implementations.** That `cone` and the implementations' causal
  slices compute the same set is argued informally. Empirically, the causal slices are sound on every
  pair in experiment 2 (`../experiments/results/method_primary`).

## Relation to the submitted theory
The submitted `SemanticPreservation_v2.thy` also built with exit 0, but only from global axioms. Two of
them were unsound as stated:
- `unitary_off_V_preserves_rdm` quantified over a qubit that did not occur in the operation;
- `rdm_locality` is false for entangling gates.

Its `project` function was also the naive slice. It is withdrawn and replaced by this theory. See
`../PROVENANCE.md`.
