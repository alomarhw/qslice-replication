#!/usr/bin/env python3
"""Pre-registered triage of the Bugs4Q benchmark for the circuit-slicer
fault-localisation study.

Source: https://github.com/Z-928/Bugs4Q  commit 7a719839662f94614872d65f9e9fbcd07408437c
(Apache-2.0).  No slicer is imported or run here.

Usage (run from a scratch directory outside the downloaded tree):

    python -I extract.py <BUGS4Q_ROOT> <OUT_DIR>

<BUGS4Q_ROOT> is the unpacked "Bugs4Q-7a71983..." directory.  The script never
imports or executes any Bugs4Q file.  For every candidate that passes rule 1,
the circuit-building part of the buggy and fixed scripts has been re-typed into
the PORTS dictionary below, with comments citing the original lines and every
API change logged.  The script checks that the cited original lines still
contain the expected text (ANCHORS) before it builds anything.

Inclusion rule (pre-registered; applied exactly):
  1. buggy and fixed both build a qiskit.QuantumCircuit under qiskit 2.3.0 with
     at most mechanical API updates (renamed imports / execution dropped,
     c_if -> if_test, u1/u2/u3 -> p/u, cnot -> cx, toffoli -> ccx, removed
     Qubit.index);
  2. <= 14 qubits and <= 220 instructions after preparation (drop barriers,
     drop terminal measurements, decompose gates wider than 8 qubits);
  3. prepared buggy and fixed circuits differ;
  4. only if_else control flow.
"""
from __future__ import annotations

import csv
import difflib
import hashlib
import io
import math
import os
import sys
import warnings

import numpy as np

warnings.filterwarnings("ignore")

import qiskit  # noqa: E402
from qiskit import QuantumCircuit, qasm2, qpy  # noqa: E402
from qiskit.circuit import Clbit, ClassicalRegister, ParameterExpression  # noqa: E402

COMMIT = "7a719839662f94614872d65f9e9fbcd07408437c"
MAX_QUBITS = 14
MAX_INSTR = 220
WIDE_GATE = 8
FORBIDDEN_CF = {"while_loop", "for_loop", "switch_case"}

# ---------------------------------------------------------------------------
# Reason vocabulary (one line per exclusion)
# ---------------------------------------------------------------------------
OOS_CIRQ = "out of scope: Cirq program (study is Qiskit-only)"
OOS_QS = "out of scope: Q# program (study is Qiskit-only)"
NOFIX = "rule 1: no fixed version in Bugs4Q (buggy script only)"
NOBUGGY = "rule 1: no buggy version in Bugs4Q (fixed script only)"
IDENT = "rule 3: prepared buggy and fixed circuits are identical"

# ---------------------------------------------------------------------------
# Every candidate.  action = "build" -> PORTS entry is built and rules 2-4 are
# evaluated; action = "exclude" -> excluded by the stated reason without
# building (rule 1 fails or out of scope).  Stage after Huang & Martonosi:
# input / operation / output (mapping conventions documented in TRIAGE.md).
# Fields: bug_id, buggy_file, fixed_file, stage, kind, action, reason, notes
# ---------------------------------------------------------------------------
T0 = "Terra-0-4000"
T4 = "Terra-4001-6000"
T6 = "Terra-6000-7100"
SE = "StackExchange"
SP = "StackExchange-page-1-25"
S2 = "StackExchange_2"
SO1 = "stackoverflow-1-5"
SO6 = "stackoverflow-6-10"

C = []


def cand(bug_id, buggy, fixed, stage, kind, action, reason="", notes=""):
    C.append(dict(bug_id=bug_id, buggy_file=buggy, fixed_file=fixed, stage=stage,
                  kind=kind, action=action, reason=reason, notes=notes))


NF_KIND = "kind inferred from the buggy script alone (no fix to diff)"

# --- Terra-0-4000 ----------------------------------------------------------
cand(f"{T0}/1", f"{T0}/1/buggy.py", f"{T0}/1/Fixed.py", "operation", "circuit-semantic", "exclude",
     "rule 1: needs non-mechanical port: circuit is produced by qiskit.aqua.operators "
     "(EvolvedOp/PauliTrotterEvolution), removed algorithm library",
     "fix changes the evolved operator Z@X -> -1j*(Z@X) (mod.py confirms); folder not listed in the README table; Fixed.py also lacks the aqua import")
cand(f"{T0}/2", f"{T0}/2/buggy.py", "", "operation", "api-classical", "exclude", NOFIX,
     "QASM import of an undefined custom gate; " + NF_KIND)
cand(f"{T0}/3", f"{T0}/3/buggy.py", f"{T0}/3/Fixed.py", "operation", "circuit-semantic", "exclude",
     "rule 1: needs non-mechanical port: buggy line 5 qc.ccx(..., label='Label', ctrl_state=1) raises "
     "TypeError in qiskit 2.3 (ccx has no label=); dropping the argument is not on the mechanical list",
     "framework bug (label + ctrl_state on controlled gates); fix also changes ccx ctrl_state 1 ('01') -> '00', cx ctrl_state 0 -> '0' (same)")
cand(f"{T0}/4", f"{T0}/4/buggy.py", "", "operation", "api-classical", "exclude", NOFIX,
     "pulse calibration of a custom gate; needs a backend; " + NF_KIND)
cand(f"{T0}/5", f"{T0}/5/buggy.py", "", "operation", "api-classical", "exclude", NOFIX,
     "opaque gate in QASM + removed qiskit.unroll API; " + NF_KIND)
cand(f"{T0}/6", f"{T0}/6/buggy.py", f"{T0}/6/Fixed.py", "operation", "api-classical", "exclude",
     "rule 1: needs non-mechanical port: buggy uses QuantumProgram/Qconfig credentials and ibmqx5 (removed API, cloud); circuit methods iden -> id not on the list",
     "never executed (credentials); circuits would be identical apart from iden/id naming; also 16 qubits and ~2000 instructions (would fail rule 2)")
cand(f"{T0}/7", f"{T0}/7/buggy.py", f"{T0}/7/Fix.py", "output", "api-classical", "build", "",
     "fix only changes the noise-model U_error format passed to the simulator")
cand(f"{T0}/8", f"{T0}/8/buggy.py", f"{T0}/8/fixed.py", "output", "api-classical", "exclude",
     "rule 1: needs non-mechanical port: fixed line 4 qc.iden(q) (iden removed; iden -> id is not on the mechanical list)",
     "REVIEW: if iden -> id were accepted as mechanical the pair would differ (empty circuit vs one id gate) although the id is a semantic no-op added to work around an empty-circuit simulator error")
cand(f"{T0}/9", f"{T0}/9/buggy.py", "", "output", "api-classical", "exclude", NOFIX,
     "compile() for an IBMQ backend; " + NF_KIND)
cand(f"{T0}/10", f"{T0}/10/buggy.py", f"{T0}/10/fix.py", "output", "api-classical", "exclude",
     "rule 1: buggy line 3 QuantumCircuit(q3, c3) raises NameError (q3/c3 undefined); repairing it is not mechanical",
     "the reported bug is draw(output='latex') vs 'text'; gates are otherwise identical; buggy.py has no imports")
cand(f"{T0}/11", f"{T0}/11/buggy.py", f"{T0}/11/fix.py", "operation", "api-classical", "build", "",
     "from_qasm_str called on an instance (result discarded) vs as a constructor")
cand(f"{T0}/12", f"{T0}/12/buggy.py", "", "output", "api-classical", "exclude", NOFIX,
     "IBMQ.load_accounts + noisy compile; never executed (credentials); " + NF_KIND)
cand(f"{T0}/13", f"{T0}/13/buggy.py", f"{T0}/13/fix.py", "operation", "api-classical", "build", "",
     "fix adds ExtendLayout/EnlargeWithAncilla transpiler passes; pass manager needs an undefined `backend` and is not part of the circuit")
cand(f"{T0}/14", f"{T0}/14/buggy.py", "", "operation", "api-classical", "exclude", NOFIX,
     "gate labels / UnitaryGate display; " + NF_KIND)
cand(f"{T0}/15", f"{T0}/15/buggy.py", "", "output", "api-classical", "exclude", NOFIX,
     "drawing of a measure-then-gate circuit; " + NF_KIND)
cand(f"{T0}/16", f"{T0}/16/buggy.py", f"{T0}/16/fix.py", "operation", "api-classical", "exclude",
     "rule 1: no QuantumCircuit built: pulse CmdDef on an IBMQ backend (IBMQ.load_accounts, credentials)",
     "never executed; fix changes CmdDef.get keyword -> positional parameters")
cand(f"{T0}/17", f"{T0}/17/buggy.py", "", "operation", "api-classical", "exclude", NOFIX,
     "parameter_binds with several circuits; " + NF_KIND)
cand(f"{T0}/18", f"{T0}/18/buggy.py", "", "operation", "api-classical", "exclude", NOFIX,
     "sorting Qubit objects; no circuit; " + NF_KIND)
cand(f"{T0}/19", f"{T0}/19/buggy.py", "", "operation", "api-classical", "exclude", NOFIX,
     "transpile of parameterised circuit (script also has typos); " + NF_KIND)
cand(f"{T0}/20", f"{T0}/20/buggy.py", "", "operation", "api-classical", "exclude", NOFIX,
     "complex rotation angle accepted by rx; " + NF_KIND)
cand(f"{T0}/21", f"{T0}/21/buggy.py", "", "input", "api-classical", "exclude", NOFIX,
     "initial-layout execution on ibmq_burlington (provider, cloud); " + NF_KIND)
cand(f"{T0}/22", f"{T0}/22/buggy.py", f"{T0}/22/fix.py", "operation", "circuit-semantic", "build", "",
     "DAG substitution of a controlled gate's base gate; circuit taken is dag_to_circuit(dag) at line 35 (the script's final output); "
     "REVIEW: the change is in DAG-manipulation code (qargs of apply_operation_back), not in gate-append calls")
cand(f"{T0}/23", f"{T0}/23/buggy.py", "", "output", "api-classical", "exclude", NOFIX,
     "mpl drawing of a register name with underscores; " + NF_KIND)
cand(f"{T0}/24", f"{T0}/24/buggy.py", f"{T0}/24/fix.py", "operation", "api-classical", "exclude",
     "rule 1: fixed version is not valid Python (fix.py lines 10-11: positional argument follows keyword argument)",
     "transpile() argument usage; circuit itself is identical (cx(0,2))")

# --- Terra-4001-6000 ---------------------------------------------------------
cand(f"{T4}/Bug_1", f"{T4}/Bug_1/buggy.py", "", "input", "api-classical", "exclude", NOFIX,
     "inverse() of initialize; " + NF_KIND)
cand(f"{T4}/Bug_2", f"{T4}/Bug_2/buggy.py", "", "operation", "api-classical", "exclude", NOFIX,
     "u2 call; " + NF_KIND)
cand(f"{T4}/Bug_3", f"{T4}/Bug_3/buggy.py", "", "input", "api-classical", "exclude", NOFIX,
     "measure into a 1-bit register; undefined statepreparation/feature_train; " + NF_KIND)
cand(f"{T4}/Bug_4", f"{T4}/Bug_4/buggy.py", "", "output", "api-classical", "exclude", NOFIX,
     "unitary_simulator output; " + NF_KIND)
cand(f"{T4}/Bug_5", f"{T4}/Bug_5/buggy.py", f"{T4}/Bug_5/fixed.py", "operation", "circuit-semantic", "build", "",
     "crz control/target operands swapped inside a sub-circuit that is turned into an Operator and appended as one 3-qubit 'unitary'; "
     "the program's circuit qc therefore has one opaque instruction. REVIEW: degenerate for slicing (1 instruction)")
cand(f"{T4}/Bug_6", f"{T4}/Bug_6/buggy.py", "", "operation", "api-classical", "exclude", NOFIX,
     "transpile to ecr basis; undefined backend; " + NF_KIND)
cand(f"{T4}/Bug_7", f"{T4}/Bug_7/buggy.py", "", "output", "api-classical", "exclude", NOFIX,
     "IBMQ.load_account + get_memory; never executed (credentials); " + NF_KIND)
cand(f"{T4}/Bug_8", f"{T4}/Bug_8/buggy.py", f"{T4}/Bug_8/fixed.py", "operation", "api-classical", "exclude",
     "rule 1: no QuantumCircuit built: pulse schedule (pulse.ShiftPhase vs pulse.shift_phase); qiskit.pulse and qiskit.test.mock removed",
     "")
cand(f"{T4}/Bug_9", f"{T4}/Bug_9/buggy.py", "", "operation", "api-classical", "exclude", NOFIX,
     "undefined names i / PI; " + NF_KIND)
cand(f"{T4}/Bug_10", f"{T4}/Bug_10/buggy.py", "", "output", "api-classical", "exclude", NOFIX,
     "statevector plotting; " + NF_KIND)
cand(f"{T4}/Bug_11", f"{T4}/Bug_11/buggy.py", f"{T4}/Bug_11/fixed.py", "operation", "api-classical", "build", "",
     "decompose() vs transpile() for display; the transpile result is discarded so the circuit is unchanged")

# --- Terra-6000-7100 ---------------------------------------------------------
cand(f"{T6}/6255_Bug", f"{T6}/6255_Bug/bug_version.py", f"{T6}/6255_Fixed/fixed_version.py", "output", "api-classical", "build", "",
     "fix wraps the opflow expectation in PauliExpectation before CircuitSampler; opflow removed in 2.x but the state circuit builds without it")
cand(f"{T6}/6521_Bug", f"{T6}/6521_Bug/bug_version.py", "", "input", "api-classical", "exclude", NOFIX,
     "controlled-RY state preparation drawn with mpl; undefined feature_train1; " + NF_KIND)
cand(f"{T6}/6540_Bug", f"{T6}/6540_Bug/bug_version.py", f"{T6}/6540_Fixed/fixed_version.py", "operation", "api-classical", "build", "",
     "control() of a circuit containing a nested sub-circuit instruction vs a Gate")
cand(f"{T6}/6571_Bug", f"{T6}/6571_Bug/bug_version.py", f"{T6}/6571_Fixed/fixed_version.py", "output", "circuit-semantic", "build", "",
     "measure_all() adds a new 'meas' register vs measuring into the existing register")
cand(f"{T6}/6604_Bug", f"{T6}/6604_Bug/bug_version.py", f"{T6}/6604_Fixed/fixed_version.py", "output", "api-classical", "exclude",
     "rule 1: no QuantumCircuit built: opflow operator-precedence expression (3*(I^0)^...) only",
     "observable construction; no circuit in either script")
cand(f"{T6}/6777_Bug", f"{T6}/6777_Bug/bug_version.py", "", "operation", "api-classical", "exclude", NOFIX,
     "qiskit_nature/aqua VQE construction; " + NF_KIND)
cand(f"{T6}/6860_Bug", f"{T6}/6860_Bug/bug_version.py", f"{T6}/6860_Fixed/fixed_version.py", "operation", "api-classical", "exclude",
     "rule 1: needs non-mechanical port: fixed line 11 uses QuantumCircuit.transform_registers, which does not exist in qiskit 2.3; buggy overwrites private _qubits",
     "register bookkeeping, not gates")
cand(f"{T6}/6892_Bug", f"{T6}/6892_Bug/bug_version.py", f"{T6}/6892_Fixed/fixed_version.py", "operation", "api-classical", "build", "",
     "assign_parameters inplace=True vs inplace=False for a global-phase parameter; fixed circuit taken = bound_circuit (line 7)")
cand(f"{T6}/6927_Bug", f"{T6}/6927_Bug/bug_version.py", f"{T6}/6927_Fixed/fixed_version.py", "output", "api-classical", "build", "",
     "fix adds transpile() before run (and still runs the untranspiled qc); circuit unchanged")
cand(f"{T6}/7032_Bug", f"{T6}/7032_Bug/bug_version.py", f"{T6}/7032_Fixed/fixed_version.py", "operation", "api-classical", "exclude",
     "rule 1: needs non-mechanical port: the circuit's only consumer is qiskit.opflow.gradients.Gradient (removed algorithm library); "
     "the fix (.decompose(), line 6) exists only to satisfy that API",
     "REVIEW: RealAmplitudes itself builds in 2.3; read literally, the prepared circuits differ only in decomposition level "
     "(1 'RealAmplitudes' instruction vs its ry gates, same unitary) and the pair would pass rules 2-4")
cand(f"{T6}/7069_Fixed", "", f"{T6}/7069_Fixed/fixed_version.py", "operation", "api-classical", "exclude", NOBUGGY,
     "QNSPSA/VQE with removed QuantumInstance")

# --- Aer ---------------------------------------------------------------------
cand("Aer/bug_1", "Aer/bug_1/buggy.py", "Aer/bug_1/fixed.py", "output", "circuit-semantic", "build", "",
     "fix removes the final measurements before taking a statevector; README lists a modify.py that is absent")
cand("Aer/bug_7", "Aer/bug_7/buggy.py", "Aer/bug_7/fixed.py", "output", "circuit-semantic", "build", "",
     "measurement qubit->clbit mapping changed")
cand("Aer/bug_10", "Aer/bug_10/buggy.py", "Aer/bug_10/fixed.py", "output", "api-classical", "build", "",
     "fix adds subsystem_list to PulseSystemModel.from_backend; pulse/ignis/test.mock code dropped as execution")

# --- Program (single issue-reproduction scripts, no fix) ------------------------
cand("Program/1999", "Program/1999.py", "", "operation", "api-classical", "exclude", NOFIX,
     "dag.num_tensor_factors on a 20-qubit QV circuit; removed qiskit.mapper APIs; " + NF_KIND)
cand("Program/2009", "Program/2009.py", "", "operation", "api-classical", "exclude", NOFIX,
     "two_qubit_kak on a random circuit; " + NF_KIND)
cand("Program/2036", "Program/2036.py", "", "operation", "api-classical", "exclude", NOFIX,
     "transpile with tuple-keyed initial_layout; " + NF_KIND)
cand("Program/2373", "Program/2373.py", "", "output", "api-classical", "exclude", NOFIX,
     "T1 experiment on ibmq_16_melbourne (IBMQ.load_accounts, credentials); never executed; " + NF_KIND)
cand("Program/3410", "Program/3410.py", "", "operation", "api-classical", "exclude",
     "rule 1: no code (file contains only a comment and an issue URL)", "")
cand("Program/5839", "Program/5839.py", "", "output", "api-classical", "exclude", NOFIX,
     "Aer snapshots across transpilation; " + NF_KIND)

# --- StackExchange -------------------------------------------------------------
cand(f"{SE}/1", f"{SE}/1/buggy.py", f"{SE}/1/fix.py", "operation", "circuit-semantic", "exclude",
     "rule 1: buggy version is not valid Python (line 10 `qc.x(q[0]).c[0]_if(c[0], 0)`); repair requires guessing",
     "fix conditions on a 1-bit register; note fix.py line 9 (indented qc.h) applies H twice")
cand(f"{SE}/2", f"{SE}/2/buggy/times.py", "", "operation", "api-classical", "exclude", NOFIX,
     "QFT multiplier using register(Qconfig) credentials; never executed; " + NF_KIND)
cand(f"{SE}/3", f"{SE}/3/buggy.py", f"{SE}/3/fix.py", "operation", "api-classical", "exclude",
     "rule 1: needs non-mechanical port: buggy line 12 QuantumCircuit.wait / qiskit.extensions.simulator no longer exist (delay is a different instruction)",
     "fix replaces wait() by barrier;id;barrier (semantic no-op)")
cand(f"{SE}/4", f"{SE}/4/buggy.py", f"{SE}/4/fix.py", "operation", "circuit-semantic", "build", "",
     "Grover oracle: fix uncomputes ancillas instead of resetting them")
cand(f"{SE}/5", f"{SE}/5/buggy.py", f"{SE}/5/fix.py", "output", "circuit-semantic", "build", "",
     "second measurement into a separate classical register")
cand(f"{SE}/6", f"{SE}/6/buggy.py", f"{SE}/6/fix.py", "output", "api-classical", "build", "",
     "compile() removed -> transpile/assemble; 5 circuits compared pairwise")
cand(f"{SE}/7", f"{SE}/7/buggy.py", f"{SE}/7/fix.py", "output", "api-classical", "build", "",
     "statevector_simulator + get_statevector instead of counts")
cand(f"{SE}/8", f"{SE}/8/buggy.py", f"{SE}/8/fix.py", "output", "api-classical", "build", "",
     "execute(basis_gates=...) vs optimization_level=0")
cand(f"{SE}/9", f"{SE}/9/buggy.py", f"{SE}/9/fix.py", "output", "circuit-semantic", "build", "",
     "measurement clbit order reversed to match the expected bitstring")
cand(f"{SE}/10", f"{SE}/10/buggy.py", f"{SE}/10/fix.py", "operation", "circuit-semantic", "exclude",
     "rule 1: fixed version raises NameError at line 24 (`qc.measure([2],[2])`, qc undefined); repairing it is not on the mechanical list",
     "REVIEW: line 24 is a terminal measurement that preparation would drop anyway; with qc->circuit the pair (cx/cz vs c_if z/x teleport correction) would pass rules 1-4")
cand(f"{SE}/11", f"{SE}/11/buggy.py", "", "operation", "api-classical", "exclude", NOFIX,
     "HHL-style circuit re-executed in a loop; " + NF_KIND)
cand(f"{SE}/12", f"{SE}/12/buggy.py", f"{SE}/12/fix.py", "output", "api-classical", "exclude",
     "rule 1: needs non-mechanical port: line 12 `circ+meas` (QuantumCircuit.__add__ removed; compose is not on the list)",
     "fix only changes Aer max_parallel_threads; circuits identical")
cand(f"{SE}/13", f"{SE}/13/buggy.py", f"{SE}/13/fix.py", "output", "api-classical", "exclude",
     "rule 1: needs non-mechanical port: line 25 `middle + meas` (QuantumCircuit.__add__ removed)",
     "fix only drops execute(seed=8); circuits identical")
cand(f"{SE}/14", f"{SE}/14/buggy.py", f"{SE}/14/fix.py", "output", "api-classical", "exclude",
     "rule 1: needs non-mechanical port: lines 42-44 `pre + middle + meas_*` (QuantumCircuit.__add__ removed)",
     "fix only comments out print(counts); circuits identical")
cand(f"{SE}/15", f"{SE}/15/buggy.py", f"{SE}/15/fix.py", "operation", "circuit-semantic", "build", "",
     "inverse-QFT ordering in QPE")
cand(f"{SE}/16", f"{SE}/16/buggy.py", f"{SE}/16/fix.py", "operation", "circuit-semantic", "build", "",
     "classical `if (q[1]==1)` on a Qubit object (always False) replaced by a Toffoli chain; fix is a rewrite with a different register layout (4 vs 5 qubits). REVIEW: fault-site alignment is weak")
cand(f"{SE}/17", f"{SE}/17/buggy.py", f"{SE}/17/fix.py", "operation", "api-classical", "exclude",
     "rule 1: buggy raises NameError at line 11 (`gates` undefined) and builds no gates; fixed is an unseeded random_circuit(10,10)",
     "")
cand(f"{SE}/18", f"{SE}/18/buggy.py", f"{SE}/18/fix.py", "operation", "circuit-semantic", "exclude",
     "rule 1: needs non-mechanical port: buggy uses qiskit.aqua.circuits.FourierTransformCircuits (removed) and undefined psi; indentation error at line 4",
     "fix uses library QFT(3, inverse=True).reverse_bits()")
cand(f"{SE}/19", f"{SE}/19/buggy.py", "", "operation", "api-classical", "exclude", NOFIX,
     "sympy expression as cu1 parameter; " + NF_KIND)
cand(f"{SE}/20", f"{SE}/20/buggy.py", f"{SE}/20/fix.py", "operation", "api-classical", "exclude",
     "rule 1: needs non-mechanical port: calibration circuits come from ignis complete_meas_cal (removed, not imported)",
     "fix changes a duplicated physical qubit in initial_layout (12 -> 10); a transpile argument, not a circuit change")

# --- StackExchange-page-1-25 -------------------------------------------------------
cand(f"{SP}/Bug_5", f"{SP}/Bug_5/bug_version.py", f"{SP}/Fixed_5/fixed_version.py", "output", "api-classical", "exclude",
     "rule 1: needs non-mechanical port: buggy lines 4,6,8 use Aer's save_statevector (qiskit_aer instruction, unavailable); fix uses Statevector.from_instruction",
     "without the save instructions both circuits are h; cx (identical)")
cand(f"{SP}/Bug_6", f"{SP}/Bug_6/bug_version.py", f"{SP}/Fixed_6/fixed_version.py", "output", "api-classical", "build", "",
     "noise-model definition changed (coherent error on h instead of u2/u3); Aer execution dropped")
cand(f"{SP}/Bug_7", f"{SP}/Bug_7/bug_version.py", f"{SP}/Fixed_7/fixed_version.py", "operation", "api-classical", "exclude",
     "rule 1: needs non-mechanical port: circuit is a qiskit_nature UCC ansatz (old qiskit_nature API, not installed)",
     "fix changes the excitation-list format")
cand(f"{SP}/Bug_9", f"{SP}/Bug_9/bug_version.py", f"{SP}/Fixed_9/fixed_version.py", "input", "circuit-semantic", "build", "",
     "missing initial Hadamard layer (README: Initialization)")
cand(f"{SP}/Bug_10", f"{SP}/Bug_10/bug_version.py", f"{SP}/Fixed_10/fixed_version.py", "operation", "api-classical", "exclude",
     "rule 1: no QuantumCircuit difference expressible: opflow Gradient/VQE (removed); fixed file is a one-line fragment",
     "")
cand(f"{SP}/Bug_13", f"{SP}/Bug_13/bug_version.py", f"{SP}/Fixed_13/fixed_version.py", "output", "api-classical", "exclude",
     "rule 1: no QuantumCircuit built: IBM job retrieval (provider, cloud); never executed",
     "")
cand(f"{SP}/Bug_14", f"{SP}/Bug_14/bug_version.py", f"{SP}/Fixed_14/fixed_version.py", "operation", "api-classical", "exclude",
     "rule 1: no QuantumCircuit built: `circuit` is undefined in both scripts; fix adds seed_transpiler",
     "")
cand(f"{SP}/Bug_15", f"{SP}/Bug_15/bug_version.py", f"{SP}/Fixed_15/fixed_version.py", "operation", "api-classical", "exclude",
     "rule 1: not runnable: buggy is an indented REPL fragment, fixed file is the single line `num_qubits=2`",
     "TwoLocal num_parameters_settable after compose")
cand(f"{SP}/Bug_17", f"{SP}/Bug_17/bug_version.py", "", "output", "api-classical", "exclude", NOFIX,
     "classifier post-processing of counts; IPython magic; " + NF_KIND)
cand(f"{SP}/Bug_18", f"{SP}/Bug_18/bug_version.py", f"{SP}/Fixed_18/fixed_version.py", "output", "api-classical", "exclude",
     "rule 1: no QuantumCircuit difference: opflow Hamiltonian operator precedence; fixed file is a fragment; VQE/QuantumInstance removed",
     "")
cand(f"{SP}/Bug_19", f"{SP}/Bug_19/bug_version.py", f"{SP}/Fixed_19/fixed_version.py", "input", "circuit-semantic", "build", "",
     "initialize(0,0) twice instead of initialize(1,1) on qubit 1")
cand(f"{SP}/Bug_20", f"{SP}/Bug_20/bug_version.py", f"{SP}/Fixed_20/fixed_version.py", "operation", "api-classical", "exclude",
     "rule 1: buggy line 21 qc.QFT(0) raises AttributeError; fixed line 21 `qc + QFT(1)` uses removed QuantumCircuit.__add__; both load an IBMQ account",
     "never executed (credentials)")
cand(f"{SP}/Bug_21", f"{SP}/Bug_21/bug_version.py", f"{SP}/Fixed_21/fixed_version.py", "operation", "api-classical", "build", "",
     "transpile basis choice + Solovay-Kitaev post-processing; the source circuit qc is unchanged")

# --- StackExchange_2 -----------------------------------------------------------------
cand(f"{S2}/bug_1", f"{S2}/bug_1/buggy.py", f"{S2}/bug_1/fixed.py", "operation", "api-classical", "exclude",
     "rule 1: needs non-mechanical port: buggy line 4 circuit.iden(0) (removed; iden -> id is not on the list)",
     "the fix IS the rename; with it the circuits would be identical")
cand(f"{S2}/bug_2", f"{S2}/bug_2/buggy.py", f"{S2}/bug_2/fixed.py", "input", "api-classical", "build", "",
     "initial Statevector label '01' vs '10' is outside the circuit; the circuit is unchanged")

# --- stackoverflow-1-5 -----------------------------------------------------------------
cand(f"{SO1}/1", f"{SO1}/1/buggy.py", f"{SO1}/1/Fix.py", "output", "circuit-semantic", "build", "",
     "REVIEW: documented cause is measure(2,2) appended after execute() (buggy lines 22-24); Fix.py is Qiskit's teleport example "
     "(different input state u(0.3,0.2,0.1) vs x, c_if corrections instead of cx/cz), so the diff also covers non-fault edits")
cand(f"{SO1}/Bug_2", f"{SO1}/Bug_2/bug_version.py", f"{SO1}/Fixed_2/fixed_version.py", "output", "api-classical", "build", "",
     "decompose() only inside draw(); circuit unchanged")
cand(f"{SO1}/Bug_3", f"{SO1}/Bug_3/bug_version.py", f"{SO1}/Fixed_3/fixed_version.py", "output", "api-classical", "build", "",
     "print(draw('mpl')) vs draw('mpl').show(); empty circuit")
cand(f"{SO1}/Bug_8", f"{SO1}/Bug_8/bug_version.py", f"{SO1}/Fixed_8/fixed_version.py", "output", "api-classical", "build", "",
     "assemble before run; empty circuit")
cand(f"{SO1}/Bug_11", f"{SO1}/Bug_11/bug_version.py", f"{SO1}/Fixed_11/fixed_version.py", "operation", "api-classical", "exclude",
     "rule 1: buggy line 9 circuit.h(qr(0)) raises TypeError (register is not callable); both files contain IPython magic `%matplotlib inline` (not valid Python)",
     "README row 4; Mod_4 holds its diff")

# --- stackoverflow-6-10 -----------------------------------------------------------------
cand(f"{SO6}/bug_1", f"{SO6}/bug_1/buggy.py", f"{SO6}/bug_1/fixed.py", "operation", "circuit-semantic", "build", "",
     "ccx control/target reversed (README: little-endian label convention)")
cand(f"{SO6}/bug_2", f"{SO6}/bug_2/buggy.py", f"{SO6}/bug_2/fixed.py", "operation", "circuit-semantic", "build", "",
     "h(1) should be x(1)")
cand(f"{SO6}/bug_3", f"{SO6}/bug_3/buggy.py", f"{SO6}/bug_3/fixed.py", "operation", "circuit-semantic", "build", "",
     "hand-written IQFT replaced by the inverse of that circuit composed in")

# --- out of scope ------------------------------------------------------------------------
for i, (st, kd) in enumerate([("operation", "circuit-semantic"), ("output", "api-classical"),
                              ("input", "api-classical"), ("operation", "circuit-semantic"),
                              ("output", "circuit-semantic"), ("operation", "api-classical"),
                              ("output", "api-classical")], start=1):
    cand(f"Cirq/{i}", f"Cirq/{i}/buggy.py", f"Cirq/{i}/fixed.py", st, kd, "exclude", OOS_CIRQ,
         "stage/kind classified informally from the scripts")
cand("Q#/1", "Q#/buggy.qs", "Q#/fixed.qs", "output", "api-classical", "exclude", OOS_QS,
     "amplitude retrieval via DumpMachine; classified informally")
cand("Q#/2", "Q#/2.ipynb", "Q#/2.ipynb", "operation", "api-classical", "exclude", OOS_QS,
     "namespace declaration scope error in a notebook cell; classified informally")

# ---------------------------------------------------------------------------
# ANCHORS: (file, 1-based line, substring) that the ports below rely on.
# ---------------------------------------------------------------------------
ANCHORS = {
    f"{T0}/7": [(f"{T0}/7/buggy.py", 12, "qc.measure(q, c)"), (f"{T0}/7/Fix.py", 12, "qc.measure(q, c)")],
    f"{T0}/11": [(f"{T0}/11/buggy.py", 10, "qc.from_qasm_str(qasm)"), (f"{T0}/11/fix.py", 9, "QuantumCircuit.from_qasm_str(qasm)")],
    f"{T0}/13": [(f"{T0}/13/buggy.py", 7, "qc.measure(q[1],c[1])"), (f"{T0}/13/fix.py", 8, "qc.measure(q[1],c[1])")],
    f"{T0}/22": [(f"{T0}/22/buggy.py", 30, "node.qargs[node.op.num_ctrl_qubits:]"), (f"{T0}/22/fix.py", 30, "qr[node.op.num_ctrl_qubits:]")],
    f"{T4}/Bug_5": [(f"{T4}/Bug_5/buggy.py", 8, "circ.crz(pi/2,2,0)"), (f"{T4}/Bug_5/fixed.py", 8, "circ.crz(pi/2,0,1)")],
    f"{T4}/Bug_11": [(f"{T4}/Bug_11/buggy.py", 3, "qc.u1(0.24,0)"), (f"{T4}/Bug_11/fixed.py", 3, "qc.u1(0.24,0)")],
    f"{T6}/6255_Bug": [(f"{T6}/6255_Bug/bug_version.py", 11, "state.h(1)"), (f"{T6}/6255_Fixed/fixed_version.py", 11, "state.h(1)")],
    f"{T6}/6540_Bug": [(f"{T6}/6540_Bug/bug_version.py", 7, "outer_level.append(inner_level, [0,1])"),
                       (f"{T6}/6540_Fixed/fixed_version.py", 7, "outer_level.append(inner_level.to_gate(), [0,1])")],
    f"{T6}/6571_Bug": [(f"{T6}/6571_Bug/bug_version.py", 6, "qc.measure_all()"), (f"{T6}/6571_Fixed/fixed_version.py", 6, "qc.measure(qc.qubits, qc.clbits)")],
    f"{T6}/6892_Bug": [(f"{T6}/6892_Bug/bug_version.py", 6, "inplace=True"), (f"{T6}/6892_Fixed/fixed_version.py", 7, "inplace=False")],
    f"{T6}/6927_Bug": [(f"{T6}/6927_Bug/bug_version.py", 9, "qc.measure(list(range(3)), list(range(3)))"),
                       (f"{T6}/6927_Fixed/fixed_version.py", 9, "qc.measure(list(range(3)), list(range(3)))")],
    "Aer/bug_1": [("Aer/bug_1/buggy.py", 13, "ghz.measure(qr,cr)"), ("Aer/bug_1/fixed.py", 12, "ghz.barrier(qr)")],
    "Aer/bug_7": [("Aer/bug_7/buggy.py", 8, "qc.measure([1, 0, 2], [1, 0, 2])"), ("Aer/bug_7/fixed.py", 9, "qc.measure([1, 0, 2], [0, 1, 2])")],
    "Aer/bug_10": [("Aer/bug_10/buggy.py", 31, "circ.measure([0, 1], [0, 1])"), ("Aer/bug_10/fixed.py", 31, "circ.measure([0, 1], [0, 1])")],
    f"{SE}/4": [(f"{SE}/4/buggy.py", 35, "circuit.reset(ancillaries)"), (f"{SE}/4/fix.py", 34, "circuit.ccx( search_register[0], search_register[1], ancillaries[2] )")],
    f"{SE}/5": [(f"{SE}/5/buggy.py", 13, "qc.measure(q,c)"), (f"{SE}/5/fix.py", 13, "qc.measure(q,c2)")],
    f"{SE}/6": [(f"{SE}/6/buggy.py", 12, "qc.measure(qr, cr)"), (f"{SE}/6/fix.py", 15, "qc.measure(qr, cr)")],
    f"{SE}/7": [(f"{SE}/7/buggy.py", 4, "circuit.cx(0, 1)"), (f"{SE}/7/fix.py", 4, "circuit.cx(0, 1)")],
    f"{SE}/8": [(f"{SE}/8/buggy.py", 19, "circ.measure(range(n_qubits), range(n_qubits))"), (f"{SE}/8/fix.py", 19, "circ.measure(range(n_qubits), range(n_qubits))")],
    f"{SE}/9": [(f"{SE}/9/buggy.py", 21, "circuit.measure([0,1,2], [0,1,2])"), (f"{SE}/9/fix.py", 21, "circuit.measure([0,1,2], [2,1,0])")],
    f"{SE}/15": [(f"{SE}/15/buggy.py", 11, "circ.cu1(-2*np.pi/2**(i - m + 1), q[i], q[m])"), (f"{SE}/15/fix.py", 6, "circ.cu1(-2*math.pi/2**m, q[i+m-1], q[i])")],
    f"{SE}/16": [(f"{SE}/16/buggy.py", 7, "if (q[1] ==1) :"), (f"{SE}/16/fix.py", 7, "qc.ccx(q[2],q[3],q[4])")],
    f"{SP}/Bug_6": [(f"{SP}/Bug_6/bug_version.py", 19, "circ.measure(0, 0)"), (f"{SP}/Fixed_6/fixed_version.py", 26, "circ.measure(0, 0)")],
    f"{SP}/Bug_9": [(f"{SP}/Bug_9/bug_version.py", 4, "qc.cx(3, 1)"), (f"{SP}/Fixed_9/fixed_version.py", 5, "qc.h(i)")],
    f"{SP}/Bug_19": [(f"{SP}/Bug_19/bug_version.py", 7, "qc.initialize(0,0)"), (f"{SP}/Fixed_19/fixed_version.py", 4, "qc.initialize(1,1)")],
    f"{SP}/Bug_21": [(f"{SP}/Bug_21/bug_version.py", 16, "qc.unitary(u, [0,1,2], label='u')"), (f"{SP}/Fixed_21/fixed_version.py", 15, "qc.unitary(u, [0,1,2], label='u')")],
    f"{S2}/bug_2": [(f"{S2}/bug_2/buggy.py", 5, "from_label('01')"), (f"{S2}/bug_2/fixed.py", 5, "from_label('10')")],
    f"{SO1}/1": [(f"{SO1}/1/buggy.py", 24, "qc.measure(2, 2)"), (f"{SO1}/1/Fix.py", 57, "qc.z(q[2]).c_if(c0, 1)")],
    f"{SO1}/Bug_2": [(f"{SO1}/Bug_2/bug_version.py", 2, "ZZFeatureMap(2, entanglement=\"full\", reps=2)"),
                     (f"{SO1}/Fixed_2/fixed_version.py", 3, "zz.decompose().draw(\"mpl\")")],
    f"{SO1}/Bug_3": [(f"{SO1}/Bug_3/bug_version.py", 6, "Qc = QuantumCircuit(qr,cr)"), (f"{SO1}/Fixed_3/fixed_version.py", 6, "Qc = QuantumCircuit(qr,cr)")],
    f"{SO1}/Bug_8": [(f"{SO1}/Bug_8/bug_version.py", 4, "c = QuantumCircuit(2)"), (f"{SO1}/Fixed_8/fixed_version.py", 5, "c = QuantumCircuit(2)")],
    f"{SO6}/bug_1": [(f"{SO6}/bug_1/buggy.py", 12, "circuit.ccx(0,1,2)"), (f"{SO6}/bug_1/fixed.py", 12, "circuit.ccx(2,1,0)")],
    f"{SO6}/bug_2": [(f"{SO6}/bug_2/buggy.py", 6, "circuit.h(1)"), (f"{SO6}/bug_2/fixed.py", 6, "circuit.x(1)")],
    f"{SO6}/bug_3": [(f"{SO6}/bug_3/buggy.py", 10, "circuit.cu1(-pi/ pow(2, j-i), qin[j], qin[i])"),
                     (f"{SO6}/bug_3/fixed.py", 39, "circuit.compose(iqft, inplace=True)")],
}

# ---------------------------------------------------------------------------
# PORTS: circuit-building code re-typed from the original scripts.  Each
# entry: buggy/fixed code (the circuit is bound to `var`), and the change log.
# Execution, printing, drawing, plotting and backend code are dropped; that is
# logged as "dropped execution" and is the mechanical update allowed by rule 1.
# ---------------------------------------------------------------------------
HDR = "from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister\n"

PORTS = {}

# Terra-0-4000/7: buggy.py lines 5-12 == Fix.py lines 5-12 (noise config + q_execute dropped)
_t7 = HDR + """
q = QuantumRegister(2, name='q')          # L5
c = ClassicalRegister(2, name='c')        # L6
qc = QuantumCircuit(q,c)                  # L7
qc.h(q[0])                                # L9
qc.h(q[1])                                # L10
qc.cx(q[0], q[1])                         # L11
qc.measure(q, c)                          # L12
"""
PORTS[f"{T0}/7"] = dict(var="qc", buggy=_t7, fixed=_t7,
                        changes=["dropped qiskit.wrapper imports (L2-3) and noise-config/q_execute execution (L13-26) in both"])

# Terra-0-4000/11
PORTS[f"{T0}/11"] = dict(var="qc", buggy=HDR + """
qasm = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q -> c;'''                        # L4-8
qc = QuantumCircuit()                     # L9
qc.from_qasm_str(qasm)                    # L10 (static method; result discarded -> qc stays empty)
""", fixed=HDR + """
qasm = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q -> c;'''                        # L4-8
qc = QuantumCircuit.from_qasm_str(qasm)   # L9
""", changes=["buggy: dropped removed imports Aer/compile/execute and Aer.get_backend (L1-2)",
              "both: dropped print(qc.qasm()) (QuantumCircuit.qasm removed; printing only)"])

# Terra-0-4000/13: buggy lines 1-7 have no imports; fix lines 1-8
_t13 = HDR + """
q = QuantumRegister(2,'q')                # L1
c = ClassicalRegister(2,'c')              # L2
qc = QuantumCircuit(q,c)                  # L3
qc.h(q[0])                                # L4
qc.cx(q[0], q[1])                         # L5
qc.measure(q[0],c[0])                     # L6
qc.measure(q[1],c[1])                     # L7
"""
PORTS[f"{T0}/13"] = dict(var="qc", buggy=_t13, fixed=_t13,
                         changes=["both: added missing qiskit circuit imports",
                                  "both: dropped PassManager/CouplingMap transpilation that needs an undefined `backend` (buggy L9-15, fix L9-21)"])

# Terra-0-4000/22: whole script except prints; circuit = dag_to_circuit(dag) (L35)
_t22 = """
from qiskit import QuantumRegister, QuantumCircuit
from qiskit.converters import dag_to_circuit, circuit_to_dag
from qiskit.circuit import ControlledGate
from qiskit.dagcircuit import DAGCircuit
qr = QuantumRegister(4, 'qr')                       # L6
ghz_circuit = QuantumCircuit(3, name='ghz')         # L7
ghz_circuit.h(0)
ghz_circuit.cx(0, 1)
ghz_circuit.cx(1, 2)
ghz = ghz_circuit.to_gate()
cghz = ghz.control(1)                               # L12
circuit = QuantumCircuit(qr)
circuit.append(cghz, [3, 1, 0, 2])                  # L14
dag = circuit_to_dag(circuit)                       # L18
for node in dag.topological_op_nodes():
    if isinstance(node.op, ControlledGate):
        controlled_qubits = node.qargs[:node.op.num_ctrl_qubits]
        unctl_dag = DAGCircuit()
        for qreg in dag.qregs.values():
            unctl_dag.add_qreg(qreg)
        unctl_dag = DAGCircuit()
        for qreg in dag.qregs.values():
            unctl_dag.add_qreg(qreg)
        unctl_dag.apply_operation_back(node.op.base_gate,
                                       %s,          # L30 (the fault)
                                       node.op.params)
        dag.substitute_node_with_dag(node, unctl_dag)   # L33
out = dag_to_circuit(dag)                           # L35
"""
PORTS[f"{T0}/22"] = dict(var="out", buggy=_t22 % "node.qargs[node.op.num_ctrl_qubits:]",
                         fixed=_t22 % "qr[node.op.num_ctrl_qubits:]",
                         changes=["both: dropped print statements (L16, L32, L35 print wrapper)"])

# Terra-4001-6000/Bug_5: lines 7-15
_b5 = """
from math import pi
from qiskit import QuantumCircuit, QuantumRegister
from qiskit.quantum_info.operators import Operator
circ = QuantumCircuit(3)                 # L7
circ.crz(pi/2,%s)                        # L8
circ.crz(pi/4,%s)                        # L9
U = Operator(circ)                       # L10
qae = QuantumRegister(2,'qae')           # L12
reg_b = QuantumRegister(2,'b')           # L13
qc = QuantumCircuit(qae,reg_b)           # L14
qc.append(U,[qae[0],reg_b[0],reg_b[1]])  # L15
"""
PORTS[f"{T4}/Bug_5"] = dict(var="qc", buggy=_b5 % ("2,0", "2,1"), fixed=_b5 % ("0,1", "0,2"),
                            changes=["both: dropped visualization imports, Operator(qc) print and draw (L4, L16-18)"])

# Terra-4001-6000/Bug_11
_b11 = HDR + """
qc = QuantumCircuit(1)                   # L2
qc.p(0.24,0)                             # L3: qc.u1(0.24,0)
"""
PORTS[f"{T4}/Bug_11"] = dict(var="qc", buggy=_b11, fixed=_b11,
                             changes=["both: u1 -> p (L3)",
                                      "buggy: dropped print(qc.decompose()) (L4); fixed: dropped transpile(...) whose result is discarded and print (L4-5)"])

# Terra-6000-7100/6255: state circuit, lines 6-11 in both
_t6255 = HDR + """
state = QuantumCircuit(2)                # L6
state.h(1)
state.sdg(1)
state.cz(0, 1)
state.h(1)                               # L11
"""
PORTS[f"{T6}/6255_Bug"] = dict(var="state", buggy=_t6255, fixed=_t6255,
                               changes=["both: dropped Aer import and qiskit.opflow/QuantumInstance expectation evaluation (L1-4, L12-22)"])

# Terra-6000-7100/6540: whole scripts (already 2.x API)
_t6540 = HDR + """
qc = QuantumCircuit(3)                                  # L2
outer_level = QuantumCircuit(2, name='outer')           # L4
inner_level = QuantumCircuit(2, name='inner')           # L5
inner_level.x(0)                                        # L6
outer_level.append(%s, [0,1])                           # L7
qc.append(outer_level.control(), [0,1,2])               # L9
"""
PORTS[f"{T6}/6540_Bug"] = dict(var="qc", buggy=_t6540 % "inner_level", fixed=_t6540 % "inner_level.to_gate()",
                               changes=["none (scripts run as written)"])

# Terra-6000-7100/6571
_t6571 = HDR + """
qr = QuantumRegister(2, name='qreg')     # L2
cr = ClassicalRegister(2, name='creg')   # L3
qc = QuantumCircuit(qr,cr)               # L4
qc.h(qr)                                 # L5
%s                                       # L6
"""
PORTS[f"{T6}/6571_Bug"] = dict(var="qc", buggy=_t6571 % "qc.measure_all()", fixed=_t6571 % "qc.measure(qc.qubits, qc.clbits)",
                               changes=["both: dropped Aer backend/execute (L8-10)"])

# Terra-6000-7100/6892
PORTS[f"{T6}/6892_Bug"] = dict(var="circuit", buggy="""
from qiskit.circuit import QuantumCircuit, Parameter
from qiskit.circuit.library import EfficientSU2
circuit = EfficientSU2(1)                                 # L3
x = Parameter("x")
circuit.global_phase = x
circuit.assign_parameters({x: 0.001}, inplace=True)       # L6
""", fixed="""
from qiskit.circuit import QuantumCircuit, Parameter
from qiskit.circuit.library import EfficientSU2
circ0 = EfficientSU2(1)                                   # L4 (named `circuit` in the original)
x = Parameter("x")
circ0.global_phase = x
circuit = circ0.assign_parameters({x: 0.001}, inplace=False)   # L7 (`bound_circuit` in the original)
""", changes=["both: dropped prints", "fixed: the bound circuit (bound_circuit, L7) is taken as the fixed circuit"])

# Terra-6000-7100/6927
_t6927 = """
from qiskit import QuantumCircuit
from qiskit.circuit.library import PhaseEstimation
qc= QuantumCircuit(3,3)                                   # L3
unitary_circuit = QuantumCircuit(1)
unitary_circuit.h(0)
qc.append(PhaseEstimation(2, unitary_circuit), list(range(3)))   # L8
qc.measure(list(range(3)), list(range(3)))               # L9
"""
PORTS[f"{T6}/6927_Bug"] = dict(var="qc", buggy=_t6927, fixed=_t6927,
                               changes=["both: dropped Aer import/backend.run (L1, L10-11); fixed: dropped transpile whose result is unused (L11)"])

# Aer/bug_1
_a1 = HDR + """
qr = QuantumRegister(5,'qr')             # L3
cr = ClassicalRegister(5, 'cr')
ghz = QuantumCircuit(qr, cr)
ghz.h(qr[0])
ghz.cx(qr[0],qr[1])
ghz.cx(qr[1],qr[2])
ghz.cx(qr[2],qr[3])
ghz.cx(qr[3],qr[4])
ghz.barrier(qr)                          # L12
%s
"""
PORTS["Aer/bug_1"] = dict(var="ghz", buggy=_a1 % "ghz.measure(qr,cr)  # L13", fixed=_a1 % "",
                          changes=["both: dropped draw and BasicAer/execute statevector run"])

# Aer/bug_7
_a7 = HDR + """
n = 3
q = QuantumRegister(n)
c = ClassicalRegister(n)
qc = QuantumCircuit(q, c, name="circuit")
qc.x(0)
qc.measure([1, 0, 2], %s)
"""
PORTS["Aer/bug_7"] = dict(var="qc", buggy=_a7 % "[1, 0, 2]", fixed=_a7 % "[0, 1, 2]",
                          changes=["both: dropped qiskit.providers.aer import and execute (L2, L9-11)"])

# Aer/bug_10
_a10 = HDR + """
circ = QuantumCircuit(2, 2)              # L27
circ.x(0)
circ.x(0)
circ.x(1)
circ.measure([0, 1], [0, 1])             # L31
"""
PORTS["Aer/bug_10"] = dict(var="circ", buggy=_a10, fixed=_a10,
                           changes=["both: dropped test.mock/ignis/pulse/Aer imports, scheduling, assemble and PulseSimulator (L1-25, L33-48)"])

# StackExchange/4: buggy L3-50, fix L3-56
_se4_head = HDR + """
m_qubit = QuantumRegister(1)
search_register = QuantumRegister(4)
result_register = ClassicalRegister(4)
ancillaries = QuantumRegister(3)
circuit = QuantumCircuit(search_register, result_register, m_qubit, ancillaries)
circuit.x(m_qubit)
circuit.h(m_qubit)
circuit.h(search_register)
"""
PORTS[f"{SE}/4"] = dict(var="circuit", buggy=_se4_head + """
for _ in range(2):                                                      # L17
    circuit.x( search_register[2] )
    circuit.ccx( search_register[1], search_register[2], ancillaries[0] )
    circuit.ccx( search_register[3], ancillaries[0], ancillaries[1] )
    circuit.x( search_register[2] )                                     # L23
    circuit.ccx( search_register[0], search_register[1], ancillaries[2] )
    circuit.x(ancillaries)
    circuit.ccx( ancillaries[1], ancillaries[2], m_qubit[0] )
    circuit.x(ancillaries)                                              # L31
    circuit.x(m_qubit)
    circuit.reset(ancillaries)                                          # L35
    circuit.h(search_register)
    circuit.x(search_register)
    circuit.ccx( search_register[0], search_register[1], ancillaries[0] )
    circuit.ccx( search_register[2], ancillaries[0], ancillaries[1] )
    circuit.ccx( search_register[3], ancillaries[1], m_qubit[0] )
    circuit.x(search_register)
    circuit.x(m_qubit)
    circuit.h(search_register)
    circuit.reset(ancillaries)                                          # L48
circuit.measure(search_register, result_register)                       # L50
""", fixed=_se4_head + """
for _ in range(2):                                                      # L17
    circuit.x( search_register[2] )
    circuit.ccx( search_register[1], search_register[2], ancillaries[0] )
    circuit.ccx( search_register[3], ancillaries[0], ancillaries[1] )
    circuit.ccx( search_register[0], search_register[1], ancillaries[2] )   # L25
    circuit.x(ancillaries)
    circuit.ccx( ancillaries[1], ancillaries[2], m_qubit[0] )
    circuit.x(m_qubit)
    circuit.x(ancillaries)                                              # L33
    circuit.ccx( search_register[0], search_register[1], ancillaries[2] )
    circuit.ccx( search_register[3], ancillaries[0], ancillaries[1] )
    circuit.ccx( search_register[1], search_register[2], ancillaries[0] )
    circuit.x( search_register[2] )                                     # L37
    circuit.h(search_register)
    circuit.x(search_register)
    circuit.ccx( search_register[0], search_register[1], ancillaries[0] )
    circuit.ccx( search_register[2], ancillaries[0], ancillaries[1] )
    circuit.ccx( search_register[3], ancillaries[1], m_qubit[0] )
    circuit.x(search_register)
    circuit.x(m_qubit)
    circuit.ccx( search_register[2], ancillaries[0], ancillaries[1] )   # L49
    circuit.ccx( search_register[0], search_register[1], ancillaries[0] )
    circuit.h(search_register)
    circuit.reset(ancillaries)                                          # L54
circuit.measure(search_register, result_register)                       # L56
""", changes=["both: dropped Aer/execute import names and execution (L1, L52-59 / L58-65)"])

# StackExchange/5: buggy L3-13, fix L3-13 (simulator undefined in fix, only used by execute)
PORTS[f"{SE}/5"] = dict(var="qc", buggy=HDR + """
q = QuantumRegister(2)
c = ClassicalRegister(2)
qc = QuantumCircuit(q, c)
qc.h(q[0])
qc.cx(q[0], q[1])
qc.measure(q,c)          # L9
qc.cx(q[0], q[1])        # L12
qc.measure(q,c)          # L13
""", fixed=HDR + """
q = QuantumRegister(2)
c1 = ClassicalRegister(2)
c2 = ClassicalRegister(2)
qc = QuantumCircuit(q, c1,c2)
qc.h(q[0])
qc.cx(q[0], q[1])
qc.measure(q,c1)         # L9
qc.cx(q[0], q[1])        # L12
qc.measure(q,c2)         # L13
""", changes=["both: dropped qiskit.providers.aer import and the two execute() calls (L10-11, L14-15); fixed's undefined `simulator` was only used there"])

# StackExchange/6: 5 circuits in a list
_se6 = HDR + """
n_qubits = 5
qc_list = []
for i in range(n_qubits):
    qr = QuantumRegister(n_qubits)
    cr = ClassicalRegister(n_qubits)
    qc = QuantumCircuit(qr, cr)
    qc.x(qr[i])
    qc.measure(qr, cr)
    qc_list.append(qc)
"""
PORTS[f"{SE}/6"] = dict(var="qc_list", buggy=_se6, fixed=_se6,
                        changes=["both: dropped Aer/compile/JOB_FINAL_STATES (buggy) and transpile/assemble (fixed) execution"])

# StackExchange/7
_se7 = HDR + """
circuit = QuantumCircuit(2)
circuit.h(0)
circuit.cx(0, 1)
"""
PORTS[f"{SE}/7"] = dict(var="circuit", buggy=_se7, fixed=_se7, changes=["both: dropped execute/Aer"])

# StackExchange/8
_se8 = HDR + """
import numpy as np
n_qubits = 2
circ = QuantumCircuit(n_qubits, n_qubits)    # L12
circ.h(0)
circ.rx(np.pi/4,1)
circ.cz(0,1)
circ.rz(np.pi,0)
circ.measure(range(n_qubits), range(n_qubits))  # L19
"""
PORTS[f"{SE}/8"] = dict(var="circ", buggy=_se8, fixed=_se8, changes=["both: dropped Aer noise model and execute (L2-8, L21-49)"])

# StackExchange/9
_se9 = HDR + """
circuit = QuantumCircuit(3, 3)
circuit.x(0)
circuit.cx(0, 1)
circuit.barrier()
circuit.measure([0,1,2], %s)    # L21
"""
PORTS[f"{SE}/9"] = dict(var="circuit", buggy=_se9 % "[0,1,2]", fixed=_se9 % "[2,1,0]",
                        changes=["both: dropped execute/Aer import names and execution"])

# StackExchange/15
_se15_tail = """
def n_hadamard(circ, q, n):
    for i in range(n):
        circ.h(q[i])
def build_state_vector(circ, inp, s):
    for i, e in enumerate(inp):
        if e == '1':
            circ.x(s[i])
nancilla = 3
theta = 0.78
q = QuantumRegister(nancilla, 'q')
s = QuantumRegister(1, 's')
c = ClassicalRegister(nancilla, 'c')
qpe = QuantumCircuit(q, s, c)
build_state_vector(qpe, '1', s)
n_hadamard(qpe, q, nancilla)
for i in range(nancilla):
    qpe.cp(2*math.pi*theta*2**(nancilla-i-1), q[i], s[0])     # buggy L37 / fix L33: cu1 -> cp
qft_dagger(qpe, q, nancilla)
for i in range(nancilla):
    qpe.measure(q[i],c[i])
"""
PORTS[f"{SE}/15"] = dict(var="qpe", buggy=HDR + "import math\nimport numpy as np\n" + """
def qft_dagger(circ, q, n):            # L2
    for i in range(n//2):
        circ.swap(q[i], q[n - i - 1])
    for i in reversed(range(n)):
        circ.h(q[i])
        for m in reversed(range(i)):
            circ.cp(-2*np.pi/2**(i - m + 1), q[i], q[m])     # L11: cu1 -> cp
        circ.barrier()
""" + _se15_tail, fixed=HDR + "import math\n" + """
def qft_dagger(circ, q, n):            # L2
    for i in range(n-1,-1,-1):
        for m in range(n-i,1,-1):
            circ.cp(-2*math.pi/2**m, q[i+m-1], q[i])         # L6: cu1 -> cp
        circ.h(q[i])
        circ.barrier()
""" + _se15_tail, changes=["both: cu1 -> cp (controlled form of the listed u1 -> p rename)",
                          "buggy: added missing `import math` and `import numpy as np` (used at L11/L37, never imported); fixed: added missing `import math`",
                          "both: dropped BasicAer/execute"])

# StackExchange/16
PORTS[f"{SE}/16"] = dict(var="qc", buggy=HDR + """
q = QuantumRegister(2)
subnode = QuantumRegister(2)
qc = QuantumCircuit(q,subnode)
qc.ccx(subnode[0], subnode[1], q[1])
if (q[1] ==1) :          # L7: Python comparison of a Qubit object, always False
    qc.x(q[0])
qc.x(q[1])
qc.ccx(subnode[0], subnode[1], q[1])
""", fixed=HDR + """
q = QuantumRegister(5)
c = ClassicalRegister(5)
qc = QuantumCircuit(q,c)
qc.ccx(q[0],q[1],q[3])
qc.ccx(q[2],q[3],q[4])
qc.ccx(q[0],q[1],q[3])
""", changes=["both: dropped qc.draw()"])

# StackExchange-page-1-25/Bug_6
_sp6 = HDR + """
circ = QuantumCircuit(1, 1)
circ.h(0)
circ.h(0)
circ.measure(0, 0)
"""
PORTS[f"{SP}/Bug_6"] = dict(var="circ", buggy=_sp6, fixed=_sp6,
                            changes=["both: dropped Aer AerSimulator/NoiseModel construction, transpile and run (buggy L3-14, L22-26; fixed L3-21, L28-31)"])

# StackExchange-page-1-25/Bug_9
_sp9_body = """
qc.cx(3, 1)
qc.cx(1, 0)
qc.cx(0, 1)
qc.ccx(3, 2, 1)
qc.cx(1, 2)
qc.cx(3, 2)
qc.measure(0, 0)
qc.measure(1, 1)
qc.measure(2, 2)
qc.measure(3, 3)
"""
PORTS[f"{SP}/Bug_9"] = dict(var="qc", buggy=HDR + "qc = QuantumCircuit(4, 4)\n" + _sp9_body,
                            fixed=HDR + "qc = QuantumCircuit(4, 4)\nfor i in range(4):\n    qc.h(i)\n" + _sp9_body,
                            changes=["both: dropped execute/Aer/plot_histogram"])

# StackExchange-page-1-25/Bug_19
_sp19_tail = """
qc.h(0)
qc.h(1)
qc.cx(0,1)
qc.h(0)
qc.h(1)
"""
PORTS[f"{SP}/Bug_19"] = dict(var="qc", buggy=HDR + """
qc=QuantumCircuit(2)
qc.initialize(0,0)      # L6
qc.initialize(0,0)      # L7
""" + _sp19_tail, fixed=HDR + """
qc = QuantumCircuit(2)
qc.initialize(0,0)      # L3
qc.initialize(1,1)      # L4
""" + _sp19_tail, changes=["both: dropped unitary_simulator/assemble/array_to_latex (and transpile/draw in fixed)"])

# StackExchange-page-1-25/Bug_21
_sp21 = """
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator
u = Operator([[0, 0, 1, 0, 0, 0, 0, 0],
              [1, 0, 0, 0, 0, 0, 0, 0],
              [0, 1, 0, 0, 0, 0, 0, 0],
              [0, 0, 0, 1, 0, 0, 0, 0],
              [0, 0, 0, 0, 0, 0, 0, 1],
              [0, 0, 0, 0, 0, 1, 0, 0],
              [0, 0, 0, 0, 0, 0, 1, 0],
              [0, 0, 0, 0, 1, 0, 0, 0]])
qc = QuantumCircuit(3)
qc.unitary(u, [0,1,2], label='u')
"""
PORTS[f"{SP}/Bug_21"] = dict(var="qc", buggy=_sp21, fixed=_sp21,
                             changes=["both: dropped transpile/draw (buggy L18-19) and transpile + Solovay-Kitaev post-processing (fixed L17-25)"])

# StackExchange_2/bug_2
_s22 = HDR + """
mycircuit = QuantumCircuit(2)
mycircuit.h(0)
mycircuit.cx(0,1)
"""
PORTS[f"{S2}/bug_2"] = dict(var="mycircuit", buggy=_s22, fixed=_s22,
                            changes=["both: dropped Statevector.from_label/evolve and plot_state_qsphere (L5, L9-10)"])

# stackoverflow-1-5/1
PORTS[f"{SO1}/1"] = dict(var="qc", buggy=HDR + """
qc = QuantumCircuit(3, 3)     # L3
qc.x(0)
qc.barrier()
qc.h(1)
qc.cx(1, 2)
qc.barrier()
qc.cx(0, 1)
qc.h(0)
qc.barrier()
qc.measure(0, 0)
qc.measure(1, 1)
qc.cx(1, 2)
qc.cz(0, 2)                   # L19
qc.measure(2, 2)              # L24 (appended after execute() in the original)
""", fixed=HDR + """
q = QuantumRegister(3, "q")            # L33
c0 = ClassicalRegister(1, "c0")
c1 = ClassicalRegister(1, "c1")
c2 = ClassicalRegister(1, "c2")
qc = QuantumCircuit(q, c0, c1, c2, name="teleport")
qc.u(0.3, 0.2, 0.1, q[0])              # L40
qc.h(q[1])
qc.cx(q[1], q[2])
qc.barrier(q)
qc.cx(q[0], q[1])
qc.h(q[0])
qc.measure(q[0], c0[0])
qc.measure(q[1], c1[0])
qc.barrier(q)
with qc.if_test((c0, 1)):              # L57: qc.z(q[2]).c_if(c0, 1)
    qc.z(q[2])
with qc.if_test((c1, 1)):              # L58: qc.x(q[2]).c_if(c1, 1)
    qc.x(q[2])
qc.measure(q[2], c2[0])                # L59
""", changes=["buggy: dropped Aer/execute/get_memory/draw (L21-23, L25-26)",
              "fixed: c_if(c0,1) -> with qc.if_test((c0,1)) (L57); c_if(c1,1) -> with qc.if_test((c1,1)) (L58)",
              "fixed: dropped BasicAer/execute with coupling_map/initial_layout (L21-28, L66-79)"])

# stackoverflow-1-5/Bug_2
_so2 = """
from qiskit.circuit.library import ZZFeatureMap
zz = ZZFeatureMap(2, entanglement="full", reps=2)
"""
PORTS[f"{SO1}/Bug_2"] = dict(var="zz", buggy=_so2, fixed=_so2,
                             changes=["both: dropped draw('mpl'); fixed's decompose() is only inside the draw call (L3)"])

# stackoverflow-1-5/Bug_3
_so3 = HDR + """
qr = QuantumRegister(2)
cr = ClassicalRegister(2)
Qc = QuantumCircuit(qr,cr)
"""
PORTS[f"{SO1}/Bug_3"] = dict(var="Qc", buggy=_so3, fixed=_so3, changes=["both: dropped printing/drawing"])

# stackoverflow-1-5/Bug_8
_so8 = HDR + "c = QuantumCircuit(2)\n"
PORTS[f"{SO1}/Bug_8"] = dict(var="c", buggy=_so8, fixed=_so8,
                             changes=["both: dropped Aer import, transpile(c, simulator), assemble and run"])

# stackoverflow-6-10/bug_1
_so61 = HDR + """
bit = 3
bit_lst = list(range(bit))
circuit = QuantumCircuit(bit, bit)
circuit.reset(0)
circuit.reset(1)
circuit.reset(2)
circuit.x(0)
circuit.x(1)
circuit.ccx(%s)          # L12
circuit.barrier()
circuit.measure(bit_lst,bit_lst)
"""
PORTS[f"{SO6}/bug_1"] = dict(var="circuit", buggy=_so61 % "0,1,2", fixed=_so61 % "2,1,0",
                             changes=["both: dropped Aer/assemble runs, file output and plotting (L15-26)"])

# stackoverflow-6-10/bug_2
_so62 = HDR + """
circuit = QuantumCircuit(2)
circuit.h(0)
circuit.%s(1)            # L6
circuit.cx(0,1)
circuit.measure_all()
"""
PORTS[f"{SO6}/bug_2"] = dict(var="circuit", buggy=_so62 % "h", fixed=_so62 % "x",
                             changes=["both: dropped QasmSimulator import, transpile/run and prints (L2, L10-16)"])

# stackoverflow-6-10/bug_3
PORTS[f"{SO6}/bug_3"] = dict(var="circuit", buggy=HDR + """
from math import pi, pow
def IQFT(circuit, qin, n):
    for i in range (int(n/2)):
        circuit.swap(qin[i], qin[n -1 -i])
    for i in range (n):
        circuit.h(qin[i])
        for j in range (i +1, n, 1):
            circuit.cp(-pi/ pow(2, j-i), qin[j], qin[i])     # L10: cu1 -> cp
n = 3
qin = QuantumRegister(n)
cr = ClassicalRegister(n)
circuit = QuantumCircuit(qin, cr, name="Inverse_Quantum_Fourier_Transform")
circuit.h(qin)
circuit.z(qin[2])
circuit.s(qin[1])
circuit.z(qin[0])
circuit.t(qin[0])
IQFT(circuit, qin, n)
circuit.measure (qin, cr)       # L24
""", fixed=HDR + """
from math import pi, pow
def QFT(n, inverse=False):
    circuit = QuantumCircuit(n, name='IQFT' if inverse else 'QFT')
    for i in range(int(n/2)):
        circuit.swap(i, n - 1 - i)
    for i in range(n):
        circuit.h(i)
        for j in range(i + 1, n, 1):
            circuit.cp(-pi / pow(2, j - i), j, i)            # L17: cu1 -> cp
    if inverse:
        circuit = circuit.inverse()
    return circuit
n = 3
qin = QuantumRegister(n)
cr = ClassicalRegister(n)
circuit = QuantumCircuit(qin, cr)
circuit.h(qin)
circuit.z(qin[2])
circuit.s(qin[1])
circuit.z(qin[0])
circuit.t(qin[0])
iqft = QFT(n, inverse=True)
circuit.compose(iqft, inplace=True)   # L39
circuit.measure (qin, cr)       # L41
""", changes=["both: cu1 -> cp (controlled form of the listed u1 -> p rename)",
              "both: dropped BasicAer/execute import names and execution"])


# ---------------------------------------------------------------------------
# Preparation, signatures, diff
# ---------------------------------------------------------------------------
def _num(x):
    if isinstance(x, ParameterExpression):
        try:
            return _num(complex(x))
        except Exception:
            return ("expr", str(x))
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return round(float(x), 6) + 0.0
    if isinstance(x, (complex, np.complexfloating)):
        z = complex(x)
        if abs(z.imag) < 1e-12:
            return round(z.real, 6) + 0.0
        return (round(z.real, 6) + 0.0, round(z.imag, 6) + 0.0)
    if isinstance(x, np.ndarray):
        return ("array", x.shape, tuple(_num(v) for v in x.flatten()))
    if isinstance(x, QuantumCircuit):
        return ("block", tuple(sig(ci, x) for ci in x.data))
    return ("obj", str(x))


def _cond(op, qc):
    cond = getattr(op, "condition", None)
    if cond is None:
        return None
    tgt, val = cond if isinstance(cond, tuple) else (cond, None)
    if isinstance(tgt, Clbit):
        return ("clbit", qc.find_bit(tgt).index, val)
    if isinstance(tgt, ClassicalRegister):
        return ("creg", tuple(qc.find_bit(b).index for b in tgt), val)
    return ("expr", str(tgt), val)


def sig(ci, qc, with_clbits=False):
    op = ci.operation
    s = (op.name, tuple(qc.find_bit(q).index for q in ci.qubits),
         tuple(_num(p) for p in op.params), _cond(op, qc))
    if with_clbits:
        s = s + (tuple(qc.find_bit(c).index for c in ci.clbits),)
    return s


def _iter_names(qc):
    for ci in qc.data:
        yield ci.operation.name
        for b in getattr(ci.operation, "blocks", ()) or ():
            yield from _iter_names(b)


def prepare(qc):
    """drop barriers; decompose gates wider than 8 qubits; drop terminal measurements."""
    work = qc.copy_empty_like()
    for ci in qc.data:
        if ci.operation.name != "barrier":
            work.append(ci.operation, ci.qubits, ci.clbits, copy=False)
    for _ in range(20):
        wide = {ci.operation.name for ci in work.data
                if ci.operation.num_qubits > WIDE_GATE and ci.operation.name not in ("measure", "barrier")
                and not getattr(ci.operation, "blocks", None)}
        if not wide:
            break
        work = work.decompose(gates_to_decompose=list(wide))
    data = list(work.data)
    keep = [True] * len(data)
    changed = True
    while changed:  # fixpoint: a measurement followed only by dropped measurements is terminal
        changed = False
        for i, ci in enumerate(data):
            if not keep[i] or ci.operation.name != "measure":
                continue
            q, b = ci.qubits[0], ci.clbits[0]
            later = [data[j] for j in range(i + 1, len(data)) if keep[j]]
            touches_q = any(q in lj.qubits for lj in later)
            reads_b = any(b in lj.clbits for lj in later if lj.operation.name != "measure")
            if not touches_q and not reads_b:
                keep[i] = False
                changed = True
    out = work.copy_empty_like()
    for k, ci in zip(keep, data):
        if k:
            out.append(ci.operation, ci.qubits, ci.clbits, copy=False)
    return out


def fault_sites(pb, pf):
    sb = [sig(ci, pb) for ci in pb.data]
    sf = [sig(ci, pf) for ci in pf.data]
    sm = difflib.SequenceMatcher(None, sb, sf, autojunk=False)
    pos = set()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag in ("replace", "delete"):
            pos.update(range(i1, i2))
        else:  # pure insertion in the fix
            for j in range(j1, j2):
                for qi in sf[j][1]:
                    before = [k for k in range(0, i1) if qi in sb[k][1]]
                    after = [k for k in range(i1, len(sb)) if qi in sb[k][1]]
                    if before:
                        pos.add(before[-1])
                    if after:
                        pos.add(after[0])
    return sorted(pos), sm.get_opcodes()


def build(code, var):
    ns = {"__name__": "bugs4q_port"}
    exec(compile(code, "<port>", "exec"), ns)
    return ns[var]


def check_anchors(root, bug_id):
    for rel, line, text in ANCHORS.get(bug_id, []):
        with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
        if line > len(lines) or text not in lines[line - 1]:
            raise RuntimeError(f"anchor mismatch {rel}:{line}: expected {text!r}")


def write_pair(out_dir, bug_id, pb, pf):
    stem = os.path.join(out_dir, "circuits", bug_id.replace("/", "__"))
    try:
        qb, qf = qasm2.dumps(pb), qasm2.dumps(pf)
        lci = qasm2.LEGACY_CUSTOM_INSTRUCTIONS  # how Qiskit-exported OpenQASM 2 is read back
        rb, rf = qasm2.loads(qb, custom_instructions=lci), qasm2.loads(qf, custom_instructions=lci)  # round trip must parse and keep the length
        if len(rb.data) != len(pb.data) or len(rf.data) != len(pf.data):
            raise ValueError("qasm2 round trip changed the instruction count")
        for ext, txt in (("buggy", qb), ("fixed", qf)):
            with open(f"{stem}.{ext}.qasm", "w") as fh:
                fh.write(txt)
        return "qasm2"
    except Exception as exc:  # noqa: BLE001
        for ext, circ in (("buggy", pb), ("fixed", pf)):
            with open(f"{stem}.{ext}.qpy", "wb") as fh:
                qpy.dump(circ, fh)
        return f"qpy (qasm2 cannot express it: {type(exc).__name__}: {str(exc).splitlines()[0][:120]})"


def main():
    root, out_dir = sys.argv[1], sys.argv[2]
    assert qiskit.__version__ == "2.3.0", qiskit.__version__
    os.makedirs(os.path.join(out_dir, "circuits"), exist_ok=True)
    for f in os.listdir(os.path.join(out_dir, "circuits")):  # start clean
        if f.endswith((".qasm", ".qpy")):
            os.remove(os.path.join(out_dir, "circuits", f))
    for c in C:
        for k in ("buggy_file", "fixed_file"):
            if c[k] and not os.path.exists(os.path.join(root, c[k])):
                raise FileNotFoundError(c[k])
    rows = []
    for c in C:
        row = dict(bug_id=c["bug_id"], buggy_file=c["buggy_file"], fixed_file=c["fixed_file"],
                   stage=c["stage"], kind=c["kind"], included=0, reason=c["reason"], api_changes="",
                   n_qubits="", n_instructions_buggy="", n_instructions_fixed="",
                   fault_site_positions="", notes=c["notes"])
        if c["action"] == "build":
            p = PORTS[c["bug_id"]]
            row["api_changes"] = ";".join(p["changes"])
            check_anchors(root, c["bug_id"])
            notes = [c["notes"]] if c["notes"] else []
            try:
                cb = build(p["buggy"], p["var"])
            except Exception as exc:  # noqa: BLE001
                row["reason"] = f"rule 1: buggy version raises {type(exc).__name__} while building the circuit under qiskit 2.3 ({str(exc).splitlines()[0][:100]})"
                rows.append(row)
                continue
            try:
                cf = build(p["fixed"], p["var"])
            except Exception as exc:  # noqa: BLE001
                row["reason"] = f"rule 1: fixed version raises {type(exc).__name__} while building the circuit under qiskit 2.3 ({str(exc).splitlines()[0][:100]})"
                rows.append(row)
                continue
            lb = cb if isinstance(cb, list) else [cb]
            lf = cf if isinstance(cf, list) else [cf]
            pbs, pfs = [prepare(x) for x in lb], [prepare(x) for x in lf]
            nq = max(x.num_qubits for x in pbs + pfs)
            nqb, nqf = max(x.num_qubits for x in pbs), max(x.num_qubits for x in pfs)
            row["n_qubits"] = nq
            row["n_instructions_buggy"] = ";".join(str(len(x.data)) for x in pbs)
            row["n_instructions_fixed"] = ";".join(str(len(x.data)) for x in pfs)
            if [x.num_qubits for x in pbs] != [x.num_qubits for x in pfs] and nqb == nqf:
                notes.append("buggy and fixed circuits have different widths")
            if nqb != nqf:
                notes.append(f"buggy has {nqb} qubits, fixed has {nqf}; n_qubits is the max")
            same = len(pbs) == len(pfs) and all(
                [sig(ci, a) for ci in a.data] == [sig(ci, b) for ci in b.data]
                for a, b in zip(pbs, pfs))
            same_full = len(pbs) == len(pfs) and all(
                [sig(ci, a, True) for ci in a.data] == [sig(ci, b, True) for ci in b.data] for a, b in zip(pbs, pfs))
            raw_same = len(lb) == len(lf) and all(
                [sig(ci, a, True) for ci in a.data] == [sig(ci, b, True) for ci in b.data] for a, b in zip(lb, lf))
            names = set()
            for x in pbs + pfs:
                names.update(_iter_names(x))
            bad_cf = names & FORBIDDEN_CF
            if nq > MAX_QUBITS or max(len(x.data) for x in pbs + pfs) > MAX_INSTR:
                row["reason"] = f"rule 2: too large after preparation ({nq} qubits, {max(len(x.data) for x in pbs + pfs)} instructions)"
            elif same:
                row["reason"] = IDENT
                if not raw_same:
                    notes.append("the unprepared circuits differ, but only in barriers/terminal measurements")
                if not same_full:
                    notes.append("they differ only in measurement clbit targets, which the pre-registered signature ignores")
            elif bad_cf:
                row["reason"] = f"rule 4: unsupported control flow {sorted(bad_cf)}"
            else:
                row["included"] = 1
                row["reason"] = ""
                fs, _ = fault_sites(pbs[0], pfs[0])
                row["fault_site_positions"] = ";".join(map(str, fs))
                fmt = write_pair(out_dir, c["bug_id"], pbs[0], pfs[0])
                notes.append(f"saved as {fmt}")
            row["notes"] = " | ".join(n for n in notes if n)
        rows.append(row)
    cols = ["bug_id", "buggy_file", "fixed_file", "stage", "kind", "included", "reason", "api_changes",
            "n_qubits", "n_instructions_buggy", "n_instructions_fixed", "fault_site_positions", "notes"]
    with open(os.path.join(out_dir, "triage.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    inc = [r for r in rows if r["included"]]
    print(f"{len(rows)} candidates, {len(inc)} included")
    for r in inc:
        print(r["bug_id"], r["n_qubits"], r["n_instructions_buggy"], r["n_instructions_fixed"], r["fault_site_positions"])


if __name__ == "__main__":
    main()
