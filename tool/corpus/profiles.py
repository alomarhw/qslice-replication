"""Qubit slice profiles over a corpus (Deviation I-17), statically (no program is executed).
Per qubit of each file's largest circuit: defs/uses, names, functions, dependents, measured bits, conditioned lines,
and the line counts of its backward and forward slices (tool.profile). A name is the identifier an argument starts
with (qr in qr[0], qubit in qubit); literals and other expressions are not names, and neither is an integer index
(an identifier the file uses as a subscript, binds by a loop over range(...), or assigns a number, as i in
qc.h(i)), and an argument that calls a function (range(n)) names no single qubit.
Usage: python -m tool.corpus.profiles CORPUS_DIR OUT.csv [--sample N --seed S] [--timeout S] [--max-qubits Q]"""
import argparse, ast, csv, random, re, signal
from pathlib import Path

from tool.interp import Interpreter
from tool import srcml as X
from tool.profile import qubit_arg_texts, slice_profile

NAME = re.compile(r"^([A-Za-z_]\w*)")


class Timeout(Exception):
    pass


def _alarm(*_):
    raise Timeout()


def int_indices(path: Path):
    """Identifiers used as integer indices: subscripts (x[i]) and targets of loops over range(...)."""
    try:
        tree = ast.parse(path.read_text(errors="replace"))
    except SyntaxError:
        return set()
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Subscript):
            out |= {m.id for m in ast.walk(n.slice) if isinstance(m, ast.Name)}
        elif isinstance(n, (ast.For, ast.comprehension)) and isinstance(n.iter, ast.Call) and \
                getattr(n.iter.func, "id", "") == "range":
            out |= {m.id for m in ast.walk(n.target) if isinstance(m, ast.Name)}
        elif isinstance(n, ast.Assign) and numeric(n.value):
            out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
    return out


def numeric(v) -> bool:
    if isinstance(v, ast.Constant):
        return isinstance(v.value, int) and not isinstance(v.value, bool)
    if isinstance(v, ast.BinOp):
        return numeric(v.left) or numeric(v.right)
    return isinstance(v, ast.Call) and getattr(v.func, "id", "") in ("len", "int")


def names(texts, index):
    out = set()
    for t in texts:
        m = NAME.match(t)
        if "(" in t:
            continue
        if m and m.group(1) not in ("True", "False", "None") and not (m.group(0) == t and t in index):
            out.add(m.group(1))
    return out


def one(path: Path, root: Path, timeout: int, max_qubits: int):
    rel = str(path.relative_to(root))
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(timeout)
    try:
        c = Interpreter(str(path)).run(X.parse_file(path)).main_circuit()
        if c is None or not c.ops:
            return [{"file": rel, "qubit": -1, "error": "no circuit"}]
        args = qubit_arg_texts(path)
        index = int_indices(path)
        rows = []
        for q in range(min(c.n("q"), max_qubits)):
            p = slice_profile(c, q, args)
            if not p.defs_uses:
                continue
            nm = names(p.names, index)
            rows.append({"file": rel, "qubit": q, "n_qubits": c.n("q"), "def_use_lines": len(p.defs_uses),
                         "names": len(nm), "name_texts": " | ".join(sorted(nm))[:200], "in_function": int(bool(p.functions)),
                         "dependents": len(p.dependents), "bits": len(p.bits), "conditioned_lines": len(p.conditioned_lines),
                         "bwd_lines": len(p.backward_lines), "fwd_lines": len(p.forward_lines), "error": ""})
        return rows or [{"file": rel, "qubit": -1, "error": "no qubit acted on"}]
    except Timeout:
        return [{"file": rel, "qubit": -1, "error": "timeout"}]
    except Exception as exc:  # recorded as a result, as in coverage.py
        return [{"file": rel, "qubit": -1, "error": type(exc).__name__}]
    finally:
        signal.alarm(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("out")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--seed", type=int, default=20261026)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--max-qubits", type=int, default=64)
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    root = Path(a.corpus)
    files = sorted(p for p in root.rglob("*.py") if "__MACOSX" not in str(p) and "qiskit" in p.read_text(errors="replace"))
    if a.sample and a.sample < len(files):
        files = sorted(random.Random(a.seed).sample(files, a.sample))
    rows = []
    from concurrent.futures import ProcessPoolExecutor
    n = len(files)
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for r in ex.map(one, files, [root] * n, [a.timeout] * n, [a.max_qubits] * n, chunksize=1):
            rows.extend(r)
    keys = ["file", "qubit", "n_qubits", "def_use_lines", "names", "name_texts", "in_function", "dependents", "bits",
            "conditioned_lines", "bwd_lines", "fwd_lines", "error"]
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    ok = [r for r in rows if not r["error"]]
    print(f"files {n}; with a circuit {len({r['file'] for r in ok})}; qubits {len(ok)}; "
          f"timeouts {sum(r['error'] == 'timeout' for r in rows)}; crashes {sum(r['error'] not in ('', 'timeout', 'no circuit', 'no qubit acted on') for r in rows)}")


if __name__ == "__main__":
    main()
