# Data Dictionary

Add your dataset following the columns below (place files in this `data/` folder).

| Variable | Type | Units | Description |
|---|---|---|---|
| n_ops | integer | operations | Number of parsed quantum operations/gates in the circuit after loader filtering. |
| method | categorical | none | Slicing/dependency method evaluated in the controlled experiment. |
| repeat | integer | repeat number | Experimental repeat index for stochastic or repeated runs. |
| n_qubits | integer | qubits | Number of logical qubits parsed for the circuit after loader filtering. |
| query_id | integer/string | none | Identifier for a slice query within a circuit, if multiple target operations/qubits are evaluated. |
| n_methods | integer | methods | Circuit-summary number of distinct methods observed for a circuit after exclusions. |
| slice_ops | integer | operations | Number of operations retained in the produced backward slice for the given method/query. |
| circuit_id | string/categorical | none | Unique identifier for the OpenQASM circuit/benchmark instance, commonly derived from benchmark name or file stem such as hs4_n4. |
| source_file | string/path | none | Path to the raw .qasm/.qasm2/.qasm3 circuit file or result file from which the circuit record was derived. |
| target_qubit | integer | qubit index | Qubit index targeted by the slice query or fidelity check. |
| n_result_rows | integer | rows | Circuit-summary count of included method/query/repeat result rows for a circuit. |
| target_op_index | integer | operation index | Operation/gate index targeted by the backward slice query. |
| analysis_exclude | boolean | none | Whether the row should be excluded from primary statistical analysis because of missing method, unknown method, or no usable metrics. |
| invalid_slice_rate | float | proportion | Fraction of evaluated slice queries that produce invalid or non-executable/non-equivalent slices under the study validity criterion. At row level this may be a 0/1 invalid indicator if only one query is represented. |
| _source_result_file | string/path | none | Provenance path of the raw CSV/JSON/JSONL result table that contributed the row. |
| target_state_fidelity | float | proportion/fidelity | Fidelity between the target state/amplitude distribution from the full circuit and the sliced circuit under exact simulation where caps permit. |
| analysis_exclude_reason | string | none | Semicolon-delimited reasons for excluding a row from primary analysis. |
| invalid_slice_rate_mean | float | proportion | Circuit-summary mean invalid_slice_rate across included methods/queries/repeats. |
| qpdg__invalid_slice_rate | float | proportion | Wide-table method-specific invalid_slice_rate for QPDG. |
| invalid_slice_rate_missing | boolean | none | Flag indicating invalid_slice_rate was absent or invalid after validation. |
| slice_size_fraction_of_ops | float | fraction of operations | Slice compactness metric: number of operations retained in the slice divided by total operations in the original circuit. |
| target_state_fidelity_mean | float | fidelity/proportion | Circuit-summary mean target_state_fidelity across included methods/queries/repeats. |
| qpdg__target_state_fidelity | float | fidelity/proportion | Wide-table method-specific target_state_fidelity for QPDG. |
| target_state_fidelity_missing | boolean | none | Flag indicating target_state_fidelity was absent or invalid after validation. |
| forward_influence_completeness | float | proportion | Fraction of forward-influence dependencies/light-cone effects preserved or recovered by the slice relative to the reference influence set. |
| slice_size_fraction_of_ops_mean | float | fraction of operations | Circuit-summary mean slice_size_fraction_of_ops across included methods/queries/repeats. |
| qpdg__slice_size_fraction_of_ops | float | fraction of operations | Wide-table method-specific slice_size_fraction_of_ops for QPDG. |
| slice_size_fraction_of_ops_missing | boolean | none | Flag indicating slice_size_fraction_of_ops was absent or invalid after validation. |
| forward_influence_completeness_mean | float | proportion | Circuit-summary mean forward_influence_completeness across included methods/queries/repeats. |
| qpdg__forward_influence_completeness | float | proportion | Wide-table method-specific forward_influence_completeness for QPDG. |
| forward_influence_completeness_missing | boolean | none | Flag indicating forward_influence_completeness was absent or invalid after validation. |
| naive_classical_pdg__invalid_slice_rate | float | proportion | Wide-table method-specific invalid_slice_rate for the Naive classical PDG baseline (def-use port). |
| causal_classical_pdg__invalid_slice_rate | float | proportion | Wide-table method-specific invalid_slice_rate for the Causal classical PDG baseline (data+control light cone). |
| naive_classical_pdg__target_state_fidelity | float | fidelity/proportion | Wide-table method-specific target_state_fidelity for the Naive classical PDG baseline. |
| causal_classical_pdg__target_state_fidelity | float | fidelity/proportion | Wide-table method-specific target_state_fidelity for the Causal classical PDG baseline. |
| naive_classical_pdg__slice_size_fraction_of_ops | float | fraction of operations | Wide-table method-specific slice_size_fraction_of_ops for the Naive classical PDG baseline. |
| causal_classical_pdg__slice_size_fraction_of_ops | float | fraction of operations | Wide-table method-specific slice_size_fraction_of_ops for the Causal classical PDG baseline. |
| naive_classical_pdg__forward_influence_completeness | float | proportion | Wide-table method-specific forward_influence_completeness for the Naive classical PDG baseline. |
| causal_classical_pdg__forward_influence_completeness | float | proportion | Wide-table method-specific forward_influence_completeness for the Causal classical PDG baseline. |

## Notes
The script is schema-tolerant because the execution excerpt does not show the exact filenames or columns emitted by analysis.py/main.py. It preserves missing metric values as NA rather than imputing them, adds missingness flags, validates all bounded metrics to [0,1], validates non-negative counts, derives slice_size_fraction_of_ops from slice_ops/n_ops when available, canonicalizes the three experimental methods/baselines, and writes both long and wide analysis tables. Rows with unknown method or no usable metrics are flagged with analysis_exclude instead of silently deleted. For strict reproducibility, run with --strict and inspect processed/data_quality_report.json before statistical testing.
