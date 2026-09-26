# data/: benchmark circuits

| Folder | Content | Source and version |
|---|---|---|
| `mqtbench/` | all 78 MQT Bench circuits as used (shipped) | MQT Bench, https://github.com/cda-tum/mqt-bench. The generator source on disk was at commit `a10a74b4926826d5ac8250393dfe7bd895fc5ecd` (v2.2.2-26). The export options were not recorded, so regenerating from the generator may not give byte-identical files; use the shipped files. |
| `veriqbench/` | all 966 VeriQBench circuits as used (shipped), in combinational / dynamic / sequential / variational families | VeriQBench, https://github.com/Veri-Q/Benchmark. The upstream commit was not recorded; use the shipped files. |
| `qasmbench/` | shipped: the 39 circuits within the exact-simulation caps. After `fetch_data.py`: all 134 circuits of the flattened layout | QASMBench, https://github.com/pnnl/QASMBench, commit `357b942396d5c2b7cbc1c229c585a6ef5ccaebac` |
| `QASMBench-master/QASMBench-master/` | created by `fetch_data.py`: the full suite at that commit | same |
| `qasmbench_layout.tsv` | how each `qasmbench/<size>/<benchmark>.qasm` maps to its upstream file, with SHA-256 | written for this package |

**RQ1-RQ3** (`main.py`) read `qasmbench/`, `mqtbench/` and `veriqbench/`. They keep circuits with at most
14 qubits and 220 operations, sorted by (qubits, operations, name), and at most 80 per corpus. That
gives QASMBench 39, MQT Bench 42 and VeriQBench 80, 161 circuits in all (`run_metadata.json`). Every
QASMBench circuit within the caps is shipped, so RQ1-RQ3 need no download.

**RQ5** (`scripts/scalability.py`) scans `qasmbench/`, `QASMBench-master/`, `mqtbench/` and `veriqbench/`,
deduplicating by (name, qubits, operations). This matches the two QASMBench layouts that were on
disk when Table VII was produced. It needs `python fetch_data.py` first.

The 134 flattened QASMBench files are all byte-identical to files in the upstream commit.
`fetch_data.py` checks each one against `qasmbench_layout.tsv`, and checks every shipped file against
`MANIFEST.sha256.tsv`.
