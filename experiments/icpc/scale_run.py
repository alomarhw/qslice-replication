"""Scalability of srcSlice-Q (Deviation I-22), under RQ4 as descriptive.

S1  every file of LintQ's corpus (read, never executed): per-stage times of srcSlice-Q (srcML, interpretation E1+E2,
    the QDG slice of every qubit E3 up to 64 qubits, srcSlice's profiles E4, qubit profiles E5), with operation,
    qubit and code-line counts, and for comprehension the lines of each qubit's slice.
S2  QASMBench medium and large through the OpenQASM 2 front end: read, one slice (the qubit with most operations),
    and every qubit in one pass (compact_all_qubits). Baselines on the same file, each in its own process:
    qiskit.qasm2.load, DAG ancestors of the last operation on that qubit (the plain light cone), Qiskit's LightCone
    pass for that qubit (Z), and building the QPDG reimplementation (Slicers).
S3  our own parametric programs (QFT, GHZ, QAOA ring, repetition code), generated at growing sizes into
    results/icpc/scale/programs/: srcSlice-Q's stages, and, since these programs are ours and safe to run, Qiskit
    building the circuit by running the program followed by DAG ancestors.
Every input runs in its own process, killed at the wall-clock limit (tool.corpus.hardlimit).
Usage (workspace root):
  python experiments/icpc/scale_run.py s1 --data-root <data-root> [--workers 6]
  python experiments/icpc/scale_run.py s2 [--workers 2]
  python experiments/icpc/scale_run.py s3 [--workers 2]
"""
import argparse
import csv
import json
import os
import platform
import re
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tool import TOOL_NAME  # noqa: E402
from tool.corpus.hardlimit import run_all  # noqa: E402

OUT = ROOT / "experiments" / "results" / "icpc" / "scale"
LIMIT = 600
S1_LIMIT = 120
MAX_QUBITS = 64
QB = ROOT / "data" / "QASMBench-master" / "QASMBench-master"
SIZES = {"qft": [10, 30, 100, 300, 600], "ghz": [10, 100, 1000, 10000, 50000],
         "qaoa_ring": [10, 100, 1000, 5000, 20000], "repetition": [5, 25, 100, 400, 1000]}
TEMPLATES = {
    "qft": """import numpy as np
from qiskit import QuantumCircuit

n = {N}
qc = QuantumCircuit(n, n)
for j in range(n):
    qc.h(j)
    for k in range(j + 1, n):
        qc.cp(np.pi / 2 ** (k - j), k, j)
for j in range(n // 2):
    qc.swap(j, n - j - 1)
qc.measure(range(n), range(n))
""",
    "ghz": """from qiskit import QuantumCircuit

n = {N}
qc = QuantumCircuit(n, n)
qc.h(0)
for i in range(n - 1):
    qc.cx(i, i + 1)
qc.measure(range(n), range(n))
""",
    "qaoa_ring": """from qiskit import QuantumCircuit

n = {N}
p = 4
gammas = [0.1 * (k + 1) for k in range(p)]
betas = [0.8 - 0.1 * k for k in range(p)]
qc = QuantumCircuit(n)
qc.h(range(n))
for layer in range(p):
    for i in range(n):
        qc.rzz(2 * gammas[layer], i, (i + 1) % n)
    for i in range(n):
        qc.rx(2 * betas[layer], i)
qc.measure_all()
""",
    "repetition": """from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

d = {N}
rounds = 10
data = QuantumRegister(d, "data")
anc = QuantumRegister(d - 1, "anc")
syn = ClassicalRegister(d - 1, "syn")
qc = QuantumCircuit(data, anc, syn)
qc.x(data[0])
for r in range(rounds):
    for i in range(d - 1):
        qc.cx(data[i], anc[i])
        qc.cx(data[i + 1], anc[i])
    for i in range(d - 1):
        qc.measure(anc[i], syn[i])
        qc.reset(anc[i])
""",
}


class Timeout(Exception):
    pass


def _alarm(*_):
    raise Timeout()


def code_lines(path: Path) -> int:
    return sum(1 for ln in path.read_text(errors="replace").splitlines() if ln.strip() and not ln.strip().startswith("#"))


def busiest(c) -> int:
    """The qubit with most operations of a compact trace (ties: the smallest index)."""
    count = [0] * c.n_qubits
    for q in c.qs:
        count[q] += 1
    return max(range(c.n_qubits), key=lambda q: (count[q], -q)) if c.n_qubits else 0


# ---- S1 -------------------------------------------------------------------------------------------------------------
def s1_one(path: Path, rel: str):
    from tool import srcml as X, srcslice as S
    from tool.interp import Interpreter
    from tool.profile import qubit_arg_texts, slice_profile
    from tool.slicer import wire_slice
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(S1_LIMIT)
    row = {"file": rel, "code_lines": code_lines(path)}
    try:
        t = time.perf_counter()
        root = X.parse_file(path)
        row["t_srcml"] = time.perf_counter() - t
        t = time.perf_counter()
        c = Interpreter(str(path), S1_LIMIT).run(root).main_circuit()
        row["t_interp"] = time.perf_counter() - t
        if c is None or not c.ops:
            return row | {"error": "no circuit"}
        nq = c.n("q")
        row |= {"ops": len(c.ops), "qubits": nq, "may_ops": sum(o.may for o in c.ops),
                "ops_beyond_10th_iteration": sum(any(i >= 10 for _, i in o.iters) for o in c.ops),
                "max_iteration": max((i for o in c.ops for _, i in o.iters), default=-1)}
        crit = range(min(nq, MAX_QUBITS))
        t = time.perf_counter()
        slices = [wire_slice(c, [q]) for q in crit]
        row["t_slice"] = time.perf_counter() - t
        t = time.perf_counter()
        prof, _ = S.profiles(path)
        cls = [S.classical_lines(path, s.quantum_lines, prof, root) for s in slices]
        row["t_srcslice"] = time.perf_counter() - t
        t = time.perf_counter()
        args = qubit_arg_texts(path)
        for q in crit:
            slice_profile(c, q, args)
        row["t_profile"] = time.perf_counter() - t
        sizes = [len(s.quantum_lines | cl) for s, cl in zip(slices, cls) if s.ops]
        row |= {"sliced_qubits": len(sizes), "slice_lines": ";".join(map(str, sizes)), "error": ""}
        return row
    except Timeout:
        return row | {"error": "timeout"}
    except Exception as exc:  # recorded as a result
        return row | {"error": type(exc).__name__}
    finally:
        signal.alarm(0)


def s1_timeout(path, rel):
    return {"file": rel, "error": "timeout"}


def s1(data_root: Path, workers: int):
    corpus = data_root / "lintq" / "exp_v08" / "files_selected"
    files = sorted(corpus.glob("*.py"))
    rows = list(run_all(s1_one, [(p, p.name) for p in files], S1_LIMIT, s1_timeout, workers))
    write(OUT / "s1_lintq.csv", rows)
    print(f"S1: {len(rows)} files, {sum(not r.get('error') for r in rows)} sliced")


# ---- S2 -------------------------------------------------------------------------------------------------------------
def s2_srcsliceq(path: str):
    from tool import qasm, slicer
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(LIMIT)
    row = {"path": path, "tool": TOOL_NAME}
    try:
        t = time.perf_counter()
        c = qasm.compact(QB / path)
        row |= {"t_read": time.perf_counter() - t, "ops": len(c), "qubits": c.n_qubits}
        q = busiest(c)
        t = time.perf_counter()
        term = slicer.compact_terminal(c)
        row["t_terminal"] = time.perf_counter() - t
        t = time.perf_counter()
        one = slicer.compact_slice(c, [q], term)
        row |= {"t_one": time.perf_counter() - t, "criterion": q, "one_size": len(one)}
        t = time.perf_counter()
        total, _ = slicer.compact_all_qubits(c, term)
        row |= {"t_all": time.perf_counter() - t, "all_memberships": total, "error": ""}
        return row
    except Timeout:
        return row | {"error": "timeout"}
    except Exception as exc:
        return row | {"error": f"{type(exc).__name__}"}
    finally:
        signal.alarm(0)


def s2_baseline(path: str, which: str):
    from qiskit import qasm2
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(LIMIT)
    row = {"path": path, "tool": which}
    try:
        from tool import qasm
        q = busiest(qasm.compact(QB / path))
        t = time.perf_counter()
        qc = qasm2.load(str(QB / path), custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
        row["t_load"] = time.perf_counter() - t
        nb = qc.copy_empty_like()
        for inst in qc.data:
            if inst.operation.name != "barrier":
                nb.append(inst)
        t = time.perf_counter()
        if which == "qiskit-dag":
            from qiskit.converters import circuit_to_dag
            dag = circuit_to_dag(nb)
            row["t_build"] = time.perf_counter() - t
            t = time.perf_counter()
            wire = nb.qubits[q]
            last = [n for n in dag.nodes_on_wire(wire, only_ops=True)][-1]
            row["one_size"] = len(dag.ancestors(last)) + 1
        elif which == "qiskit-lightcone":
            from common.corpus import prepare  # as RQ2: barriers and terminal measurements dropped, which the pass needs
            from slicers.registry import Slicers
            s = Slicers.__new__(Slicers)
            t = time.perf_counter()
            s.qc = prepare(qc)
            row["t_build"] = time.perf_counter() - t
            t = time.perf_counter()
            row["one_size"] = len(s._lightcone(q, ("Z",)))
        elif which == "qpdg":
            from slicers.registry import Slicers
            s = Slicers(nb, path)
            row["t_build"] = time.perf_counter() - t
            t = time.perf_counter()
            row["one_size"] = len(s.yz(q))
        row |= {"t_one": time.perf_counter() - t, "error": ""}
        return row
    except Timeout:
        return row | {"error": "timeout"}
    except Exception as exc:
        return row | {"error": f"{type(exc).__name__}"}
    finally:
        signal.alarm(0)


def s2(workers: int, tools=None):
    files = []
    for p in sorted(QB.glob("*/*/*.qasm")):
        if p.parts[-3] in ("medium", "large"):
            files.append(str(p.relative_to(QB)))
    workers = max(workers, 4)
    files.sort(key=lambda f: (QB / f).stat().st_size)  # smallest first
    tools = tools or [TOOL_NAME, "qiskit-dag", "qiskit-lightcone", "qpdg"]
    kept = [r for r in csv.DictReader(open(OUT / "s2_qasmbench.csv")) if r["tool"] not in tools] \
        if (OUT / "s2_qasmbench.csv").exists() else []
    rows = kept
    if TOOL_NAME in tools:
        rows += list(run_all(s2_srcsliceq, [(f,) for f in files], LIMIT, lambda f: {"path": f, "tool": TOOL_NAME, "error": "timeout"}, workers))
    for which in [t for t in tools if t != TOOL_NAME]:
        # in batches by size; once every circuit of a batch hits the limit, the larger ones are not run
        stop = False
        for i in range(0, len(files), workers):
            batch = files[i:i + workers]
            if stop:
                rows += [{"path": f, "tool": which, "error": "skipped: larger than a batch that hit the limit"} for f in batch]
                continue
            got = list(run_all(s2_baseline, [(f, which) for f in batch], LIMIT,
                               lambda f, w: {"path": f, "tool": w, "error": "timeout"}, workers))
            rows += got
            stop = all(r["error"] == "timeout" for r in got)
    write(OUT / "s2_qasmbench.csv", rows)
    print(f"S2: {len(files)} circuits")


# ---- S3 -------------------------------------------------------------------------------------------------------------
def s3_one(prog: str, size: int):
    from tool import srcml as X, srcslice as S, slicer
    from tool.interp import Interpreter, MAX_OPS
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(LIMIT)
    path = OUT / "programs" / f"{prog}_{size}.py"
    row = {"program": prog, "size": size, "tool": TOOL_NAME, "code_lines": code_lines(path)}
    try:
        t = time.perf_counter()
        root = X.parse_file(path)
        row["t_srcml"] = time.perf_counter() - t
        t = time.perf_counter()
        c = Interpreter(str(path), LIMIT).run(root).main_circuit()
        row |= {"t_interp": time.perf_counter() - t, "ops": len(c.ops), "qubits": c.n("q"), "capped": len(c.ops) >= MAX_OPS}
        t = time.perf_counter()
        one = slicer.wire_slice(c, [0])
        row["t_one"] = time.perf_counter() - t
        t = time.perf_counter()
        cc = slicer.compact_from_circuit(c)
        total, _ = slicer.compact_all_qubits(cc)
        row |= {"t_all": time.perf_counter() - t, "all_memberships": total}
        t = time.perf_counter()
        prof, _ = S.profiles(path)
        S.classical_lines(path, one.quantum_lines, prof, root)
        row |= {"t_srcslice": time.perf_counter() - t, "error": ""}
        return row
    except Timeout:
        return row | {"error": "timeout"}
    except Exception as exc:
        return row | {"error": f"{type(exc).__name__}"}
    finally:
        signal.alarm(0)


def s3_run(prog: str, size: int):
    """Baseline on our own program: run it (Qiskit builds the circuit), then DAG ancestors of qubit 0's last op."""
    import runpy
    from qiskit import QuantumCircuit
    from qiskit.converters import circuit_to_dag
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(LIMIT)
    path = OUT / "programs" / f"{prog}_{size}.py"
    row = {"program": prog, "size": size, "tool": "qiskit-run-dag"}
    try:
        t = time.perf_counter()
        g = runpy.run_path(str(path))
        qc = max((v for v in g.values() if isinstance(v, QuantumCircuit)), key=lambda x: len(x.data))
        row["t_load"] = time.perf_counter() - t
        t = time.perf_counter()
        dag = circuit_to_dag(qc)
        row["t_build"] = time.perf_counter() - t
        t = time.perf_counter()
        ops = [n for n in dag.nodes_on_wire(qc.qubits[0], only_ops=True)]
        row |= {"one_size": len(dag.ancestors(ops[-1])) + 1 if ops else 0, "t_one": time.perf_counter() - t,
                "ops": len(qc.data), "error": ""}
        return row
    except Timeout:
        return row | {"error": "timeout"}
    except Exception as exc:
        return row | {"error": f"{type(exc).__name__}"}
    finally:
        signal.alarm(0)


def s3(workers: int):
    (OUT / "programs").mkdir(parents=True, exist_ok=True)
    jobs = []
    for prog, sizes in SIZES.items():
        for n in sizes:
            (OUT / "programs" / f"{prog}_{n}.py").write_text(TEMPLATES[prog].replace("{N}", str(n)))
            jobs.append((prog, n))
    rows = list(run_all(s3_one, jobs, LIMIT, lambda p, n: {"program": p, "size": n, "tool": TOOL_NAME, "error": "timeout"}, workers))
    rows += list(run_all(s3_run, jobs, LIMIT, lambda p, n: {"program": p, "size": n, "tool": "qiskit-run-dag", "error": "timeout"}, workers))
    write(OUT / "s3_parametric.csv", rows)
    print(f"S3: {len(jobs)} programs")


def write(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()})
    (OUT / "machine.json").write_text(json.dumps({"platform": platform.platform(), "machine": platform.machine(),
                                                  "cpu": "Intel Xeon W-2140B 3.2 GHz", "cpu_count": os.cpu_count(),
                                                  "memory_gib": 32, "python": platform.python_version(),
                                                  "limit_s": LIMIT, "s1_limit_s": S1_LIMIT}, indent=1) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["s1", "s2", "s3"])
    ap.add_argument("--data-root")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--tools", help="s2 only: comma-separated tools to (re)run; the other rows of the CSV are kept")
    a = ap.parse_args()
    if a.stage == "s1":
        s1(Path(a.data_root), a.workers)
    elif a.stage == "s2":
        s2(a.workers, a.tools.split(",") if a.tools else None)
    else:
        s3(a.workers)


if __name__ == "__main__":
    main()
