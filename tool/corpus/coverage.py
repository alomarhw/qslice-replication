"""T3-style coverage of the tool on a corpus of Qiskit programs, statically (no program is executed).
Per file: srcML parse, circuits, operations of the largest circuit, may-operations, notes by kind, crash, time.
Usage: python -m tool.corpus.coverage CORPUS_DIR OUT.csv [--limit N] [--timeout S]"""
import argparse, csv, re, signal, sys, time, traceback
from collections import Counter
from pathlib import Path

from tool import srcml as X
from tool.interp import Interpreter
from tool.slicer import wire_slice


class Timeout(Exception):
    pass


def _alarm(*_):
    raise Timeout()


def kind(note: str) -> str:
    return re.sub(r"\d+", "N", note.split(":")[0])[:80]


def one(path: Path, timeout: int):
    row = {"file": str(path), "parsed": 0, "uses_qiskit": 0, "circuits": 0, "ops": 0, "qubits": 0, "may_ops": 0,
           "unresolved_qubit_ops": 0, "notes": 0, "unsound_notes": 0, "crash": "", "seconds": 0.0, "slice_ok": 0}
    src = path.read_text(errors="replace")
    row["uses_qiskit"] = int("qiskit" in src)
    t0 = time.perf_counter()
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(timeout)
    kinds = Counter()
    try:
        unit = X.parse_file(path)
        row["parsed"] = 1
        tr = Interpreter(str(path)).run(unit)
        c = tr.main_circuit()
        row["circuits"] = len(tr.circuits)
        row["notes"] = len(tr.notes)
        row["unsound_notes"] = sum("not traced" in m for _, m in tr.notes)
        kinds.update(kind(m) for _, m in tr.notes)
        if c is not None and c.ops:
            row["ops"] = len(c.ops)
            row["qubits"] = c.n("q")
            row["may_ops"] = sum(o.may for o in c.ops)
            row["unresolved_qubit_ops"] = sum(any(len(s) != 1 for s in o.qubits) for o in c.ops)
            for q in range(min(c.n("q"), 64)):
                wire_slice(c, [q])
            row["slice_ok"] = 1
    except Timeout:
        row["crash"] = "timeout"
    except Exception as exc:
        row["crash"] = f"{type(exc).__name__}: {exc}"[:200] + " @ " + traceback.extract_tb(exc.__traceback__)[-1].name
    finally:
        signal.alarm(0)
    row["seconds"] = round(time.perf_counter() - t0, 3)
    row["note_kinds"] = "; ".join(f"{k} x{v}" for k, v in kinds.most_common())
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("out")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    files = sorted(p for p in Path(a.corpus).rglob("*.py") if "__MACOSX" not in str(p))
    if a.limit:
        files = files[: a.limit]
    rows = []
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for i, r in enumerate(ex.map(one, files, [a.timeout] * len(files), chunksize=1), 1):
            rows.append(r)
            if i % 500 == 0:
                print(f"  {i}/{len(files)}", flush=True)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    q = [r for r in rows if r["uses_qiskit"]]
    print(f"files {len(rows)}; mention qiskit {len(q)}; parsed {sum(r['parsed'] for r in q)}; with a circuit "
          f"{sum(r['ops'] > 0 for r in q)}; sliced {sum(r['slice_ok'] for r in q)}; crashes {sum(bool(r['crash']) for r in q)}; "
          f"with unsound notes {sum(r['unsound_notes'] > 0 for r in q)}")


if __name__ == "__main__":
    main()
