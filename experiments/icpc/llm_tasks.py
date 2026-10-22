"""LLM tasks T1 and T2 (PROTOCOL_ICPC.md section 6; Deviation I-3).

Three subcommands:
  items  build the fixed item files (prompts + ground truth); run with the experiment venv
         T1: results/llm/t1_items.jsonl   T2: results/llm/t2_items.jsonl (needs the RQ3 run)
  run    send the prompts of one task to one or more arms; append every call to
         results/llm/<task>__<arm>.jsonl; already answered calls are skipped (resume)
  score  parse and score every logged call: results/llm/<task>_scores.csv

Fixed details (section 6 and Deviation I-3, which this file implements):
  - circuit text: qiskit.qasm2.dumps of the prepared circuit, each instruction line suffixed
    "// [k]"; a slice keeps the header and only the instruction lines of its positions. Circuits
    with a single-bit condition, which OpenQASM 2 cannot write, are shown with each classical bit in
    its own one-bit register (same instructions, same indices).
  - the qubit is named as in the QASM text (register name and index), e.g. q[3].
  - T1 sample: 200 corpus-A pairs, proportional to each corpus's pairs (largest remainder), seed
    20261025; plus every catalogue entry. Development items: K1, K2, K3 and two corpus-A pairs drawn
    from the rest with the same seed; they are logged but never scored.
  - T2 sample: primary RQ3 units (killed mutants, Z-wrong qubit), 30 per operator (all when fewer),
    seed 20261026. Context string (d'Aloisio et al., ESEM 2024): "The name of the algorithm is:
    <file stem>. The code includes <n> qubits."
  - consistency subset: 50 scored items per task (seed "<task seed>:consistency"); T1 all inputs,
    T2 inputs full and q with context; runs 1..3. Primary run is run 0.
  - Claude arms: default sampling, adaptive thinking, effort medium, max_tokens 16000, no refusal
    fallback. Open arms (OpenAI-compatible vLLM server): temperature 0 for run 0, 0.8 with seed =
    run for runs 1..3, max_tokens 2048.
  - Claude calls are ordered item-major (item, arm, input, context) so that a run stopped by the
    budget cap covers a random subset of items on every arm.

Usage:
  python icpc/llm_tasks.py items --task t1 --data-root ../data --eval-code ../selection
  python icpc/llm_tasks.py items --task t2 --data-root ../data --rq3 results/icpc/rq3
  python icpc/llm_tasks.py run --task t1 --arms claude-haiku-5-5 --split dev
  python icpc/llm_tasks.py run --task t1 --arms claude-opus-5-5,claude-sonnet-5-5 --budget-usd 40
  python icpc/llm_tasks.py run --task t1 --arms O-mid --base-url http://127.0.0.1:8000/v1
  python icpc/llm_tasks.py score --task t1
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
OUT = HERE / "results" / "llm"

T1_SEED, T2_SEED, T1_N, T2_PER_OPERATOR, CONSISTENCY_N, CONSISTENCY_RUNS = 20261025, 20261026, 200, 30, 50, 3
DEV_CATALOGUE = ("K1", "K2", "K3")

T1_PROMPT = ("Here is a quantum circuit in OpenQASM 2. Each instruction ends with its index as `// [k]`.\n"
             "{circuit}\n"
             "Which instructions can affect the final quantum state of qubit {qubit} (its reduced density "
             "matrix at the end of the circuit)? Answer with a JSON list of instruction indices and nothing else.")
T2_PROMPT = ("This quantum circuit has a bug: the measured distribution of qubit {qubit} is wrong.{context}\n"
             "{circuit}\n"
             "Which instruction is most likely the faulty one? Answer with a JSON list of up to 3 instruction "
             "indices, most likely first, and nothing else.")
T2_CONTEXT = " The name of the algorithm is: {name}. The code includes {n} qubits."

CLAUDE = {  # model id -> USD per 1e6 input / output tokens (Deviation I-3 item 6)
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}
OPEN = {"O-mid": "Qwen/Qwen2.5-Coder-32B-Instruct", "O-small": "Qwen/Qwen2.5-Coder-1.5B-Instruct"}
CLAUDE_MAX_TOKENS, CLAUDE_EFFORT, OPEN_MAX_TOKENS = 16000, "medium", 2048
RETRY_ROUNDS = 3


def _rng(tag: str):
    import numpy as np
    return np.random.default_rng(int(hashlib.sha256(tag.encode()).hexdigest()[:12], 16))


# ---------------------------------------------------------------------------- circuit text

def _split_registers(qc):
    """Equivalent circuit with every classical bit in its own one-bit register (for single-bit
    conditions, which OpenQASM 2 cannot write). Instruction order and indices are unchanged."""
    from qiskit import ClassicalRegister, QuantumCircuit
    from qiskit.circuit import Clbit
    from qiskit.circuit.controlflow import IfElseOp
    regs = [ClassicalRegister(1, f"c{i}") for i in range(qc.num_clbits)]
    out = QuantumCircuit(*qc.qregs, *regs)
    if len(out.qubits) != len(qc.qubits):
        raise ValueError("loose qubits")
    cmap = {b: regs[i][0] for i, b in enumerate(qc.clbits)}
    for inst in qc.data:
        op = inst.operation
        if op.name == "if_else":
            tgt, val = op.condition
            if isinstance(tgt, Clbit):
                op = IfElseOp((regs[qc.find_bit(tgt).index], int(val)), *op.blocks)
        out.append(op, inst.qubits, [cmap[c] for c in inst.clbits])
    return out


def qasm_lines(qc):
    """(header lines, instruction lines in position order). Raises ValueError when the labels
    cannot be placed exactly (Deviation I-3 item 5)."""
    from qiskit import qasm2
    try:
        text = qasm2.dumps(qc)
    except qasm2.QASM2ExportError:
        text = qasm2.dumps(_split_registers(qc))
    lines = [ln for ln in text.splitlines() if ln.strip()]
    head_kw = ("OPENQASM", "include", "gate ", "opaque ", "qreg ", "creg ")
    n_head = 0
    while n_head < len(lines) and lines[n_head].startswith(head_kw):
        n_head += 1
    body = lines[n_head:]
    if len(body) != len(qc.data) or any(ln.startswith(head_kw) for ln in body):
        raise ValueError(f"{len(body)} instruction lines for {len(qc.data)} instructions")
    return lines[:n_head], body


def render(qc, positions=None) -> str:
    head, body = qasm_lines(qc)
    keep = range(len(body)) if positions is None else sorted(positions)
    return "\n".join(head + [f"{body[k]} // [{k}]" for k in keep])


def qubit_name(qc, t: int) -> str:
    loc = qc.find_bit(qc.qubits[t])
    reg, idx = loc.registers[0]
    return f"{reg.name}[{idx}]"


# ---------------------------------------------------------------------------- items

def _t1_truth(job):
    """Ground truth for the T1 pairs of one circuit: influence set, S-lc, category of each
    influencing instruction (rq1_run.classify_miss)."""
    kind, key, targets, data_root = job
    from common.corpus import load
    from icpc.influence import influence, influence_sets
    from icpc.rq1_run import classify_miss
    from slicers.registry import Slicers
    if kind == "catalogue":
        from tests.dependence_catalogue import CATALOGUE
        build = next(b for kid, _, b, t, _ in CATALOGUE if kid == key[0] and t == key[1])
        qc, name = build(), key[0]
    else:
        qc, name = load(Path(data_root) / key), Path(key).stem
    inf = influence_sets(influence(qc), qc.num_qubits)
    s = Slicers(qc, name)
    out = []
    for t in targets:
        try:
            circuit = render(qc)
        except ValueError as exc:
            out.append({"key": key, "target": t, "excluded": f"labels: {exc}"})
            continue
        out.append({"key": key, "target": t, "circuit": circuit, "qubit": qubit_name(qc, t),
                    "n_qubits": qc.num_qubits, "n_ops": len(qc.data), "influence": sorted(inf[t]),
                    "lc": sorted(s.lc(t)),
                    "category": {str(k): classify_miss(qc, k, t) for k in sorted(inf[t])}})
    return out


def items_t1(data_root: Path, eval_code: Path, workers: int):
    from tests.dependence_catalogue import CATALOGUE
    pairs = list(csv.DictReader(open(HERE / "results" / "icpc" / "rq1" / "pairs.csv")))
    by_corpus = defaultdict(list)
    for p in pairs:
        by_corpus[p["corpus"]].append((p["path"], int(p["target"])))
    rng = _rng(f"{T1_SEED}:t1")
    quota = {c: T1_N * len(v) / len(pairs) for c, v in by_corpus.items()}
    alloc = {c: int(q) for c, q in quota.items()}
    for c in sorted(quota, key=lambda c: -(quota[c] - alloc[c]))[: T1_N - sum(alloc.values())]:
        alloc[c] += 1
    chosen, rest = [], []
    for c in sorted(by_corpus):
        v = by_corpus[c]
        pick = set(rng.choice(len(v), size=alloc[c], replace=False).tolist())
        chosen += [(c, *v[i]) for i in sorted(pick)]
        rest += [(c, *v[i]) for i in range(len(v)) if i not in pick]
    dev = [rest[i] for i in sorted(rng.choice(len(rest), size=2, replace=False).tolist())]
    sel = [(c, p, t, "score") for c, p, t in chosen] + [(c, p, t, "dev") for c, p, t in dev]
    jobs = defaultdict(list)
    for c, p, t, _ in sel:
        jobs[("corpus", p)].append(t)
    for kid, _, _, t, _ in CATALOGUE:
        jobs[("catalogue", (kid, t))].append(t)
    res = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for rows in ex.map(_t1_truth, [(k[0], k[1], ts, str(data_root)) for k, ts in jobs.items()]):
            for r in rows:
                res[(r["key"] if isinstance(r["key"], str) else tuple(r["key"]), r["target"])] = r
    items, excluded = [], []
    for c, p, t, split in sel:
        items.append(("corpus", c, p, t, split, res[(p, t)]))
    for kid, kind, _, t, _ in CATALOGUE:
        items.append(("catalogue", "catalogue", kid, t, "dev" if kid in DEV_CATALOGUE else "score", res[((kid, t), t)]))
    out = []
    for source, corpus, key, t, split, r in items:
        iid = f"t1:{key}:q{t}"
        if "excluded" in r:
            excluded.append({"id": iid, "reason": r["excluded"]})
            continue
        out.append({"id": iid, "task": "t1", "source": source, "corpus": corpus, "key": key, "target": t,
                    "split": split, "qubit": r["qubit"], "n_qubits": r["n_qubits"], "n_ops": r["n_ops"],
                    "influence": r["influence"], "lc": r["lc"], "category": r["category"],
                    "inputs": {"full": {"none": T1_PROMPT.format(circuit=r["circuit"], qubit=r["qubit"])}}})
    return out, excluded


def items_t2(data_root: Path, rq3: Path):
    from common.corpus import load
    from icpc.mutate import OPERATORS, mutants
    from slicers.registry import Slicers
    units = [u for u in csv.DictReader(open(rq3 / "units.csv")) if u["analysis"] == "primary"]
    by_op = defaultdict(list)
    for u in units:
        by_op[u["operator"]].append(u)
    rng = _rng(f"{T2_SEED}:t2")
    chosen = []
    for op in OPERATORS:
        v = sorted(by_op.get(op, []), key=lambda u: (u["mutant"], int(u["target"])))
        if v:
            chosen += [v[i] for i in sorted(rng.choice(len(v), size=min(T2_PER_OPERATOR, len(v)), replace=False).tolist())]
    # section 6.5: five development units for the format check, drawn from the primary units outside
    # the sample (same seed); logged but never scored
    chosen_ids = {(u["mutant"], u["target"]) for u in chosen}
    rest = sorted((u for u in units if (u["mutant"], u["target"]) not in chosen_ids), key=lambda u: (u["mutant"], int(u["target"])))
    dev = [rest[i] for i in sorted(rng.choice(len(rest), size=5, replace=False).tolist())]
    dev_ids = {(u["mutant"], u["target"]) for u in dev}
    cache, out, excluded = {}, [], []
    for u in chosen + dev:
        rel, mi, t = u["path"], int(u["mutant"].rsplit("#", 1)[1]), int(u["target"])
        if rel not in cache:
            cache[rel] = mutants(load(data_root / rel), rel)
        m = cache[rel][mi]
        iid = f"t2:{u['mutant']}:q{t}"
        if len(m.circuit.data) != int(u["n_ops"]) or ";".join(map(str, sorted(m.fault_site))) != u["fault_site"]:
            excluded.append({"id": iid, "reason": "mutant does not regenerate as in units.csv"})
            continue
        qc = m.circuit
        # the extra register of an inserted measurement is named "mut" by icpc/mutate.py; it is shown
        # under a neutral name so the name does not point at the fault
        if any(r.name == "mut" for r in qc.cregs):
            from qiskit import QuantumCircuit
            qc2 = QuantumCircuit(*qc.qregs, *[r if r.name != "mut" else type(r)(r.size, "c_extra") for r in qc.cregs])
            bmap = dict(zip(qc.clbits, qc2.clbits))
            for inst in qc.data:
                qc2.append(inst.operation, inst.qubits, [bmap[c] for c in inst.clbits])
            qc = qc2
        s = Slicers(qc, Path(rel).stem)
        slices = {"full": None, "lc": s.lc(t), "q": s.q(t), "du": s.du(t)}
        try:
            texts = {k: render(qc, v) for k, v in slices.items()}
        except ValueError as exc:
            excluded.append({"id": iid, "reason": f"labels: {exc}"})
            continue
        qn = qubit_name(qc, t)
        ctx = T2_CONTEXT.format(name=Path(rel).stem, n=qc.num_qubits)
        inputs = {k: {"context": T2_PROMPT.format(qubit=qn, context=ctx, circuit=texts[k])} for k in slices}
        for k in ("full", "q"):
            inputs[k]["none"] = T2_PROMPT.format(qubit=qn, context="", circuit=texts[k])
        out.append({"id": iid, "task": "t2", "source": "mutant", "corpus": u["corpus"], "key": u["mutant"],
                    "operator": u["operator"], "target": t,
                    "split": "dev" if (u["mutant"], u["target"]) in dev_ids else "score", "qubit": qn,
                    "n_qubits": qc.num_qubits, "n_ops": len(qc.data),
                    "fault_site": sorted(m.fault_site), "slices": {k: sorted(v) for k, v in slices.items() if v is not None},
                    "inputs": inputs})
    return out, excluded


def cmd_items(a) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if a.task == "t1":
        items, excluded = items_t1(Path(a.data_root).resolve(), Path(a.eval_code), a.workers)
    else:
        items, excluded = items_t2(Path(a.data_root).resolve(), Path(a.rq3))
    scored = [it["id"] for it in items if it["split"] == "score"]
    rng = _rng(f"{T1_SEED if a.task == 't1' else T2_SEED}:consistency")
    cons = {scored[i] for i in rng.choice(len(scored), size=min(CONSISTENCY_N, len(scored)), replace=False).tolist()}
    order = rng.permutation(len(items)).tolist()
    for rank, i in enumerate(order):
        items[i]["order"] = rank
    for it in items:
        it["consistency"] = int(it["id"] in cons)
    path = OUT / f"{a.task}_items.jsonl"
    with open(path, "w") as fh:
        for it in sorted(items, key=lambda it: it["order"]):
            fh.write(json.dumps(it) + "\n")
    (OUT / f"{a.task}_items_excluded.json").write_text(json.dumps(excluded, indent=2))
    n_calls = sum(len(c) for it in items for c in it["inputs"].values())
    print(f"{len(items)} items ({len(scored)} scored, {sum(it['split'] == 'dev' for it in items)} dev), "
          f"{len(excluded)} excluded, {n_calls} prompts per arm in run 0; wrote {path}")
    return 0


# ---------------------------------------------------------------------------- calls

class Budget:
    def __init__(self, cap, spent):
        self.cap, self.spent, self.lock = cap, spent, threading.Lock()

    def add(self, usd):
        with self.lock:
            self.spent += usd

    def exhausted(self):
        return self.cap is not None and self.spent >= self.cap


def _claude_call(client, model, prompt):
    with client.messages.stream(model=model, max_tokens=CLAUDE_MAX_TOKENS, thinking={"type": "adaptive"},
                                output_config={"effort": CLAUDE_EFFORT},
                                messages=[{"role": "user", "content": prompt}]) as stream:
        msg = stream.get_final_message()
    pin, pout = CLAUDE[model]
    u = msg.usage
    return {"model_returned": msg.model, "stop_reason": msg.stop_reason,
            "text": "".join(b.text for b in msg.content if b.type == "text"),
            "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
            "cost_usd": (u.input_tokens * pin + u.output_tokens * pout) / 1e6}


def _open_call(client, model, prompt, run):
    kw = {"temperature": 0.0} if run == 0 else {"temperature": 0.8, "seed": run}
    r = client.chat.completions.create(model=model, max_tokens=OPEN_MAX_TOKENS,
                                       messages=[{"role": "user", "content": prompt}], **kw)
    return {"model_returned": r.model, "stop_reason": r.choices[0].finish_reason,
            "text": r.choices[0].message.content or "", "input_tokens": r.usage.prompt_tokens,
            "output_tokens": r.usage.completion_tokens, "cost_usd": 0.0}


def _done(path: Path):
    keys, spent = set(), 0.0
    if path.exists():
        for ln in open(path):
            r = json.loads(ln)
            spent += r.get("cost_usd") or 0.0
            if not r.get("error"):
                keys.add((r["item"], r["input"], r["context"], r["run"]))
    return keys, spent


def cmd_run(a) -> int:
    items = [json.loads(ln) for ln in open(OUT / f"{a.task}_items.jsonl")]
    items = [it for it in items if it["split"] == a.split]
    arms = a.arms.split(",")
    runs = [0] if not a.consistency else list(range(1, CONSISTENCY_RUNS + 1))
    if a.consistency:
        items = [it for it in items if it["consistency"]]
    if a.limit:
        items = items[: a.limit]
    clients, logs, done = {}, {}, {}
    for arm in arms:
        if arm in CLAUDE:
            import anthropic
            clients[arm] = anthropic.Anthropic(max_retries=8, timeout=180)  # a stalled stream fails after 180 s idle
        elif arm in OPEN:
            import openai
            clients[arm] = openai.OpenAI(api_key="EMPTY", base_url=a.base_url, max_retries=4, timeout=600)
        else:
            raise SystemExit(f"unknown arm {arm}")
        logs[arm] = OUT / f"{a.task}__{arm}.jsonl"
        done[arm], _ = _done(logs[arm])
    spent = sum(_done(OUT / f"{a.task}__{m}.jsonl")[1] for m in CLAUDE)  # the cap covers every Claude arm
    if any(arm in CLAUDE for arm in arms) and a.split == "score" and a.budget_usd is None:
        raise SystemExit("a scored Claude run needs --budget-usd (section 6.4: the author fixes the cap before the run)")
    budget = Budget(a.budget_usd, spent)
    jobs = []
    for it in items:  # item-major order (items are stored in their seeded order)
        for arm in arms:
            for inp, ctxs in it["inputs"].items():
                for ctx, prompt in ctxs.items():
                    if a.consistency and a.task == "t2" and not (inp in ("full", "q") and ctx == "context"):
                        continue
                    for run in runs:
                        if (it["id"], inp, ctx, run) not in done[arm]:
                            jobs.append((it["id"], arm, inp, ctx, run, prompt))
    print(f"{len(jobs)} calls to make; spent so far ${spent:.2f}" + (f" of ${a.budget_usd:.2f}" if a.budget_usd else ""), flush=True)
    locks = {arm: threading.Lock() for arm in arms}
    counts = defaultdict(int)

    def work(job):
        iid, arm, inp, ctx, run, prompt = job
        if arm in CLAUDE and budget.exhausted():
            return "skipped"
        rec = {"task": a.task, "item": iid, "arm": arm, "input": inp, "context": ctx, "run": run,
               "split": a.split, "prompt": prompt, "timestamp": datetime.now(timezone.utc).isoformat()}
        t0 = time.time()
        try:
            res = _claude_call(clients[arm], arm, prompt) if arm in CLAUDE else _open_call(clients[arm], OPEN[arm], prompt, run)
            rec |= res
            rec["refusal"] = int(res["stop_reason"] == "refusal")
        except Exception as exc:  # logged and retried on the next invocation
            rec |= {"error": f"{type(exc).__name__}: {str(exc)[:500]}", "cost_usd": 0.0}
        rec["seconds"] = round(time.time() - t0, 2)
        if arm in CLAUDE:
            budget.add(rec.get("cost_usd") or 0.0)
        with locks[arm]:
            with open(logs[arm], "a") as fh:
                fh.write(json.dumps(rec) + "\n")
        return "error" if rec.get("error") else "ok"

    t0, skipped_any = time.time(), False
    for rnd in range(1 + RETRY_ROUNDS):  # failed calls are logged, then retried in the next round
        counts = defaultdict(int)
        with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
            statuses = list(ex.map(work, jobs))
        for st in statuses:
            counts[st] += 1
        skipped_any = skipped_any or counts["skipped"] > 0
        print(f"  round {rnd}: {len(jobs)} calls {dict(counts)} ${budget.spent:.2f} {time.time() - t0:.0f}s", flush=True)
        jobs = [j for j, st in zip(jobs, statuses) if st == "error"]
        if not jobs:
            break
    partial = skipped_any
    print(("PARTIAL: budget cap reached; " if partial else "") + f"done {dict(counts)}; still failing {len(jobs)}; spent ${budget.spent:.2f}")
    return 0


# ---------------------------------------------------------------------------- scoring

_ARRAY = re.compile(r"\[[0-9,\s]*\]")


def parse_answer(text: str):
    """Deviation I-3 item 4: json.loads of the stripped text, else the last integer array in it."""
    t = (text or "").strip()
    try:
        v = json.loads(t)
        if isinstance(v, list) and all(isinstance(x, int) and not isinstance(x, bool) for x in v):
            return v
    except ValueError:
        pass
    found = _ARRAY.findall(t)
    if found:
        return json.loads(found[-1])
    return None


def _top_level_lists(t: str):
    out, depth, start = [], 0, None
    for i, ch in enumerate(t):
        if ch == "[":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "]" and depth:
            depth -= 1
            if depth == 0:
                out.append(t[start:i + 1])
    return out


def parse_answer_lenient(text: str):
    """Deviation I-4 (post hoc, sensitivity only): json.loads of the stripped text, else the last
    top-level list whose elements are all indices written as 7, "7", [7] or "[7]" (never a list nested
    inside another one, unlike parse_answer's fallback)."""
    t = (text or "").strip()
    try:
        v = json.loads(t)
        if isinstance(v, list) and all(isinstance(x, int) and not isinstance(x, bool) for x in v):
            return v
    except ValueError:
        pass
    elem = re.compile(r'\s*"?\[?\s*(\d+)\s*\]?"?\s*')
    for cand in reversed(_top_level_lists(t)):
        inner = cand[1:-1]
        parts = [] if not inner.strip() else inner.split(",")
        ms = [elem.fullmatch(x) for x in parts]
        if all(ms):
            return [int(m.group(1)) for m in ms]
    return None


_ELEM = re.compile(r'\s*"?\[?\s*(\d+)\s*\]?"?\s*')


def parse_answer_line(text: str):
    """Deviation I-8 (primary): json.loads of the reply with code fences removed; else the reply's LAST
    non-empty line, with Markdown emphasis stripped, if it is exactly a list whose elements are all
    indices (7, "7", [7] or "[7]"). A bracket inside prose or an identifier such as q[3] never counts."""
    t = re.sub(r"```(?:json)?", "", text or "").strip()
    try:
        v = json.loads(t)
        if isinstance(v, list) and all(isinstance(x, int) and not isinstance(x, bool) for x in v):
            return v
    except ValueError:
        pass
    lines = [ln.strip().strip("*_`").strip() for ln in t.splitlines() if ln.strip()]
    if lines and lines[-1].startswith("[") and lines[-1].endswith("]"):
        inner = lines[-1][1:-1]
        parts = [] if not inner.strip() else inner.split(",")
        ms = [_ELEM.fullmatch(x) for x in parts]
        if all(ms):
            return [int(m.group(1)) for m in ms]
    return None


PARSERS = {"line": (parse_answer_line, ""), "frozen": (parse_answer, "_frozen"), "lenient": (parse_answer_lenient, "_lenient")}


def cmd_score(a) -> int:
    items = {it["id"]: it for it in map(json.loads, open(OUT / f"{a.task}_items.jsonl"))}
    rows = []
    for log in sorted(OUT.glob(f"{a.task}__*.jsonl")):
        latest = {}
        for r in map(json.loads, open(log)):
            if not r.get("error"):
                latest[(r["item"], r["input"], r["context"], r["run"])] = r
        for r in latest.values():
            it = items[r["item"]]
            parser = PARSERS[a.parser][0]
            ans = parser(r["text"]) if not r.get("refusal") else None
            row = {"task": a.task, "arm": r["arm"], "model_returned": r["model_returned"], "item": r["item"],
                   "split": it["split"], "source": it["source"], "corpus": it["corpus"], "input": r["input"],
                   "context": r["context"], "run": r["run"], "consistency": it["consistency"],
                   "n_ops": it["n_ops"], "stop_reason": r["stop_reason"], "refusal": r.get("refusal", 0),
                   "parsed": int(ans is not None), "input_tokens": r["input_tokens"],
                   "output_tokens": r["output_tokens"], "cost_usd": r["cost_usd"]}
            valid = set(range(it["n_ops"])) if r["input"] == "full" else set(it.get("slices", {}).get(r["input"], range(it["n_ops"])))
            answer = [x for x in (ans or []) if x in valid]
            row["dropped_indices"] = len(ans or []) - len(answer)
            row["answer"] = json.dumps(answer if ans is not None else None)
            if a.task == "t1":
                got, inf, lc = set(answer), set(it["influence"]), set(it["lc"])
                hit = len(got & inf)
                row |= {"n_influencing": len(inf), "n_answer": len(got),
                        "recall": hit / len(inf) if inf else 1.0,
                        "precision": (hit / len(got) if got else (1.0 if not inf else 0.0)) if ans is not None else 0.0,
                        "recall_lc": len(got & lc) / len(lc) if lc else 1.0,
                        "outside_lc": len(got - lc)}
                if ans is None:
                    row["recall"] = row["recall_lc"] = 0.0
                p, rc = row["precision"], row["recall"]
                row["f1"] = 2 * p * rc / (p + rc) if p + rc else 0.0
                for cat in ("same-wire", "feedback", "written-operand", "kickback"):
                    ks = {int(k) for k, v in it["category"].items() if v == cat}
                    row[f"recall_{cat}"] = (len(got & ks) / len(ks)) if ks else ""
            else:
                fault = set(it["fault_site"])
                row |= {"operator": it["operator"], "top1": int(bool(answer[:1]) and answer[0] in fault),
                        "top3": int(bool(set(answer[:3]) & fault)),
                        "fault_in_input": int(bool(fault & valid))}
            rows.append(row)
    rows.sort(key=lambda r: (r["arm"], r["item"], r["input"], r["context"], r["run"]))
    path = OUT / f"{a.task}_scores{PARSERS[a.parser][1]}.csv"
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} scored calls; wrote {path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("items")
    p.add_argument("--task", choices=["t1", "t2"], required=True)
    p.add_argument("--data-root", required=True)
    p.add_argument("--eval-code", default="../selection")
    p.add_argument("--rq3", default=str(HERE / "results" / "icpc" / "rq3"))
    p.add_argument("--workers", type=int, default=8)
    p = sub.add_parser("run")
    p.add_argument("--task", choices=["t1", "t2"], required=True)
    p.add_argument("--arms", required=True, help=f"comma-separated: {', '.join(list(CLAUDE) + list(OPEN))}")
    p.add_argument("--split", choices=["dev", "score"], default="score")
    p.add_argument("--consistency", action="store_true", help="runs 1..3 on the consistency subset")
    p.add_argument("--budget-usd", type=float, default=None, help="cap on Claude spend logged for this task")
    p.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--limit", type=int, default=None)
    p = sub.add_parser("score")
    p.add_argument("--task", choices=["t1", "t2"], required=True)
    p.add_argument("--parser", choices=list(PARSERS), default="line",
                   help="line: Deviation I-8 primary; frozen: the pre-registered rule (sensitivity); lenient: Deviation I-4")
    a = ap.parse_args()
    return {"items": cmd_items, "run": cmd_run, "score": cmd_score}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
