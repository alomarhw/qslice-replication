# qslice/beta_run/: the run behind the beta manuscript

**These are the results reported in the beta manuscript** (the June 24, 2026 draft): 242 circuits,
1,356 exact slices, naive invalid 22.1%, slice size 0.437 vs 0.727, forward incompleteness 0.81%.
They were produced by the method implementation in `../` (`qdg.py` with its June 28 driver `main.py`).
They are **not** the results of the submitted paper, which came from a simplified implementation (see
`../../PROVENANCE.md`).

## Files (byte-identical to the evaluation workspace's archived copies)
- `results.3suite.json`: the results, whose key numbers are:
  - circuits: 242, of which QASMBench 31, MQT Bench 46, VeriQBench 165;
  - slices: 1,356;
  - naive invalid rate: 22.12%;
  - QPDG invalid rate: 0%;
  - slice size, QPDG vs causal: 0.4370 vs 0.7271, i.e. 29.0% mean reduction;
  - naive forward incompleteness: 0.81%.
- `run_3suite_exact.log`: the run log, including every circuit loaded.
- `corpus_meta.json`: corpus counts.
- `regenerate.py`: reruns the prototype and compares (written for this package).

## Timeline
| When (EDT) | Evidence |
|---|---|
| 2026-06-20 00:38 | previous archived build; these files are not yet present |
| 2026-06-21 04:38 | an internal design document dated then already cites "242 simulable circuits / 1,356 exact slices" |
| 2026-06-24 01:53 | beta manuscript PDF created with these numbers |
| 2026-06-28 16:20 | the prototype code in `../` exported |
| 2026-06-28 16:35 | files first archived; the build log stored the same 19 metrics |

The run itself therefore happened between June 20 00:38 and June 21 04:38. It was not recorded as a
separate build, and no per-slice records were saved.

## Regeneration
```bash
python ../../fetch_data.py         # full QASMBench layout
python regenerate.py               # about 15-20 minutes
```
The unchanged June 28 code, run as `main.py --medium --mqt --veriq --max-qubits 14 --no-figures` on
the package's corpus:
- loads the same 242 circuits, with the same coverage line;
- reproduces every field of `results.3suite.json` except the naive slicer's mean fidelity, which
  differs by 1.3e-11 (floating-point summation order).

So the results are numerically, but not byte-for-byte, identical. That this exact file version
produced the June 20-21 run cannot be proven, because no copy of the code from that date survives. The
agreement to 1e-11 on every metric is strong evidence that the code is the same.

## What this evaluation does
- **Corpus:** unitary circuits only, with terminal measurements stripped. Circuits are capped at
  14 qubits and 200 gates after flattening gates wider than 8 qubits. At most 8 target qubits per
  circuit are sampled, evenly spread.
- **Slicers:** naive def-use, causal cone (data and control reachability; a two-qubit gate depends on
  the previous operation on both wires), and the Sec. III method.
- **Oracle:** the target's reduced-state fidelity >= 1 - 1e-6.
- **Input state:** soundness is checked only for the all-zero input |0...0>, which is also the only
  input the method's own pruning check uses.
