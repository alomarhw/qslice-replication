# Bugs4Q triage (pre-registered, before any slicer run)

Source: Bugs4Q, https://github.com/Z-928/Bugs4Q, commit `7a719839662f94614872d65f9e9fbcd07408437c` (Apache-2.0).
Interpreter: Python 3.12, qiskit 2.3.0 (no Aer, no IBM runtime). No slicer was imported or run.

Files:
- `triage.csv` has one row per candidate (107 rows).
- `circuits/` holds the prepared buggy and fixed circuits of the 11 included bugs:
  - 8 pairs as OpenQASM 2 (`.qasm`);
  - 3 pairs as QPY (`.qpy`), because OpenQASM 2 cannot express them.
- `extract.py` reproduces everything. Run it as `python -I extract.py <unpacked Bugs4Q root> <out dir>`. It never executes a Bugs4Q file. The circuit-building code of each built bug is re-typed in its `PORTS` dictionary, which cites the original line numbers. `ANCHORS` checks those lines against the source before anything is built.

## How a candidate is defined

- **One bug folder is one candidate.** Split layouts such as `6255_Bug` / `6255_Fixed` / `6255_Mod` or `Bug_5` / `Fixed_5` / `mod5` count once, under the Bug folder.
- **Each `Program/*.py` file is one candidate.**
- **Fixed file:** we use `fix.py`, `Fixed.py`, `Fix.py`, `fixed.py` or `fixed_version.py`. `mod.py` / `modify.py` are only change snippets, so they are never used as the fixed program.
- **Excluded without being built:** candidates with no fixed program, and Cirq / Q# candidates (out of scope).
- **Scripts touching cloud services were never executed.** This covers anything needing IBMQ, provider or credential access. In fact, no Bugs4Q script was executed at all.

## Counts

### By top-level folder

| Folder | Candidates | Included | Excluded |
|---|---:|---:|---:|
| Terra-0-4000 | 24 | 1 | 23 |
| Terra-4001-6000 | 11 | 1 | 10 |
| Terra-6000-7100 | 11 | 0 | 11 |
| Aer | 3 | 0 | 3 |
| Program | 6 | 0 | 6 |
| StackExchange | 20 | 3 | 17 |
| StackExchange-page-1-25 | 13 | 2 | 11 |
| StackExchange_2 | 2 | 0 | 2 |
| stackoverflow-1-5 | 5 | 1 | 4 |
| stackoverflow-6-10 | 3 | 3 | 0 |
| **Qiskit subtotal** | **98** | **11** | **87** |
| Cirq (out of scope) | 7 | 0 | 7 |
| Q# (out of scope) | 2 | 0 | 2 |
| **Total** | **107** | **11** | **96** |

### By exclusion reason (first failing rule)

| Reason | n |
|---|---:|
| rule 1: no fixed version (buggy script only) | 32 |
| rule 1: no buggy version (fixed script only) | 1 |
| rule 1: needs non-mechanical port (aqua / opflow / ignis / nature, `QuantumCircuit.__add__`, `iden`, `wait`, `save_statevector`, `ccx(label=)`, `transform_registers`, QuantumProgram) | 15 |
| rule 1: no runnable circuit in the scripts (pulse only, operator only, fragments, undefined circuit, link only) | 9 |
| rule 1: script invalid or crashes (SyntaxError, NameError, TypeError/AttributeError, or `CircuitError` raised by the buggy 6540) | 8 |
| rule 2: too large | 0 |
| rule 3: prepared buggy and fixed circuits identical | 22 |
| rule 4: unsupported control flow | 0 |
| out of scope (Cirq 7, Q# 2) | 9 |
| **Excluded** | **96** |
| **Included** | **11** |

### By stage and kind (98 Qiskit candidates)

| Stage | circuit-semantic | api-classical | Total | Included |
|---|---:|---:|---:|---:|
| input | 2 | 5 | 7 | 2 |
| operation | 13 | 42 | 55 | 8 |
| output | 6 | 30 | 36 | 1 |
| **Total** | **21** | **77** | **98** | **11** |

Restricted to the 64 Qiskit candidates that have both a buggy and a fixed script: 21 are circuit-semantic and 43 are api-classical.

All 11 included bugs are circuit-semantic. The 10 circuit-semantic bugs that were excluded are:

- **Five measurement-only bugs**, removed by preparation because their only change is in terminal measurements (rule 3): Aer/bug_1, Aer/bug_7, StackExchange/5, StackExchange/9, Terra-6000-7100/6571_Bug.
- **Five bugs that fail rule 1:** Terra-0-4000/1 (aqua), Terra-0-4000/3 (`ccx(label=)`), StackExchange/1 (buggy SyntaxError), StackExchange/10 (fixed NameError), StackExchange/18 (aqua).

### How stages were assigned

- **input:** state preparation, initial values and initial states.
- **operation:** gates, operands, parameters and conditions. This includes circuit-construction API misuse and transpiler/DAG manipulation.
- **output:** measurement, readout mapping and post-processing. This includes drawing and printing, execution and simulator or noise configuration, and observable / expectation evaluation.

For the 33 bugs that lack one of the two scripts, kind is inferred from the script that exists. These labels are low-confidence and are marked in `notes`.

## Included bugs

| bug_id | qubits | instr. buggy/fixed | fault-site positions (buggy) | format |
|---|---:|---:|---|---|
| Terra-0-4000/22 | 4 | 1/1 | 0 | qasm |
| Terra-4001-6000/Bug_5 | 4 | 1/1 | 0 | qasm |
| StackExchange/4 | 8 | 84/88 | 9;14;18;19;20;21;31;32;33;34;35;38;39;40;42;43;48;53;57;58;59;60;70;71;72;73;74;77;78;79;81;82 | qasm |
| StackExchange/15 | 4 | 14/13 | 7;9;11 | qpy (a register named `s` clashes with the `s` gate) |
| StackExchange/16 | 5 (buggy 4) | 3/3 | 0;1;2 | qasm |
| StackExchange-page-1-25/Bug_9 | 4 | 6/10 | 0;1;3 (pure insertion of the H layer) | qasm |
| StackExchange-page-1-25/Bug_19 | 2 | 7/7 | 1 | qpy (`initialize` contains `reset`) |
| stackoverflow-1-5/1 | 3 | 9/9 | 0;7;8 | qasm |
| stackoverflow-6-10/bug_1 | 3 | 6/6 | 5 | qasm |
| stackoverflow-6-10/bug_2 | 2 | 3/3 | 1 | qasm |
| stackoverflow-6-10/bug_3 | 3 | 14/14 | 3;4;6;7;8;9;10;11;12;13 | qasm |

## What share of real Qiskit bugs can a circuit-level slicer address?

A circuit-level slicer can only help when the defect is visible in the circuit, after measurements that do not feed back into the circuit are stripped. Of the 98 Qiskit candidates in Bugs4Q:

- 77 (79%) are api-classical. Their defect is in an API call, execution or backend configuration, transpiler arguments, drawing, or classical post-processing. The buggy and fixed circuits are the same, or there is no circuit at all.
- Only 21 (21%) change the circuit.
- Five of those 21 change only terminal measurements (bit order, extra or missing final measurements), which the pre-registered preparation removes.
- That leaves 16 bugs (16% of Qiskit candidates, 25% of the 64 with a buggy/fixed pair) whose fault is a gate, operand, parameter, condition or state-preparation instruction.
- Under qiskit 2.3 with only mechanical ports, 11 of those 16 can be reconstructed. That is 11% of all Qiskit candidates, and 17% of the paired ones.

So in this benchmark, most real Qiskit bugs are outside what a circuit slicer can reach. The slicer's addressable population is about one bug in six of those that have a fix. Results on the 11 included bugs should be read as results on that minority, not on Qiskit bugs in general.

## Judgment calls flagged for review

1. **`cu1 -> cp` treated as mechanical.** It is the controlled form of the listed `u1 -> p` rename, with the same matrix. It affects StackExchange/15 and stackoverflow-6-10/bug_3. If it is judged non-mechanical, both bugs drop out.
2. **Missing-import additions treated as mechanical.** StackExchange/15 never imports `math` or `numpy` (the fixed script never imports `math`). Terra-0-4000/13 has no imports at all, but it is excluded on rule 3 anyway.
3. **`iden -> id` treated as non-mechanical** because it is not on the list. This decides Terra-0-4000/8. With the rename, that pair would differ (an empty circuit vs one `id`, a semantic no-op workaround) and would be included.
4. **StackExchange/10 excluded** because the fixed script crashes at line 24 (`qc` is undefined). That line is a terminal measurement that preparation drops anyway. With `qc -> circuit`, this teleportation-correction bug (cx/cz vs conditional z/x) would be included.
5. **Terra-6000-7100/7032_Bug excluded under rule 1** (removed opflow Gradient). Read literally, its circuits build and differ only in decomposition level (one `RealAmplitudes` instruction vs its `ry` gates, same unitary). That would pass rules 2-4.
6. **stackoverflow-1-5/1 is included by the mechanical rule, but its fault site is not meaningful.** The documented cause is measuring q2 after `execute()`. The "fix" is Qiskit's teleportation example, with a different input state (`u(0.3,0.2,0.1)` vs `x`) and `if_test` corrections instead of cx/cz. Position 0 is therefore a non-fault edit.
7. **Two included bugs are degenerate one-instruction circuits.** In Terra-4001-6000/Bug_5, the faulty `crz` operands sit inside an `Operator` appended as one 3-qubit `unitary`. In Terra-0-4000/22, the fault is in DAG-substitution code and the output is one `ghz` gate on permuted qubits. Neither gives a slicer anything to slice.
8. **StackExchange/16 is a rewrite with a different register layout** (4 vs 5 qubits), so the aligned diff marks every instruction.
9. **Rule 3 uses the pre-registered signature** (name, qubits, rounded params, condition), which ignores clbit targets. Circuit width alone does not count as a difference. Terra-0-4000/11 is 0 vs 1 qubit with no instructions, so it is counted as identical.
10. **Terminal measurements are dropped to a fixpoint:** a measurement followed only by other dropped measurements counts as terminal.
11. **Circuit choice when a script builds several circuits.** Terra-6000-7100/6892 uses `bound_circuit` as the fixed circuit. Terra-0-4000/22 uses the final `dag_to_circuit(dag)`. Terra-4001-6000/Bug_5 uses the top-level `qc` rather than the sub-circuit `circ`.
