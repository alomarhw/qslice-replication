"""Static interpretation of a Qiskit program into an operation trace, without executing it.

srcML gives the program's statements, blocks and positions. The exact text of each simple statement (srcML
preserves it) is parsed into a Python syntax tree and interpreted over an abstract domain:
  - known Python values (numbers, strings, lists, tuples, ranges), and UNK for anything not computable
    statically (random numbers, I/O, unknown library calls);
  - quantum objects: registers, bits, circuits, gate objects, user functions.
Every value carries the source lines that computed it (its provenance), so the classical lines a sliced
operation depends on are known exactly.

Soundness when something is not resolved (the wire rule never kills a qubit location, so adding operations
or widening their qubit sets can only enlarge a slice):
  - an unknown qubit index makes the operation act on every qubit it may denote (a may-operation);
  - an unknown condition runs both branches; an unknown loop runs its body twice (may-operations);
  - a circuit passed to a function the tool cannot see is reported as unsound coverage.
Every such case is recorded in Trace.notes.
"""

from __future__ import annotations

import ast
import math
import textwrap
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from tool import srcml as X
from tool.gates import GATES, NOT_SLICED

MAX_OPS = 200_000
MAX_ITER = 10_000
E: FrozenSet[int] = frozenset()


class _Unknown:
    def __repr__(self):
        return "UNK"


UNK = _Unknown()


@dataclass
class Reg:
    kind: str           # "q" or "c"
    name: str
    size: Optional[int]
    uid: int


@dataclass(frozen=True)
class Bit:
    reg: Reg
    index: Optional[int]  # None: unknown index within the register

    def __hash__(self):
        return hash((self.reg.uid, self.index))

    def __eq__(self, o):
        return isinstance(o, Bit) and o.reg.uid == self.reg.uid and o.index == self.index


@dataclass
class Op:
    name: str
    qubits: Tuple[FrozenSet[int], ...]   # per qubit argument, the global qubit indices it may denote
    clbits: Tuple[FrozenSet[int], ...]
    cond: FrozenSet[int]                 # classical bits read by a condition (if_test, c_if)
    line: int
    calls: Tuple[int, ...]               # call-site lines of inlined functions, outermost first
    iters: Tuple[Tuple[int, int], ...]   # (for-statement line, iteration) of enclosing loops
    deps: FrozenSet[int]                 # classical provenance: lines computing qubits, bits, angles, conditions
    may: bool = False                    # under an unknown condition or loop, or with an unresolved qubit
    params: Tuple[Any, ...] = ()
    nctrl: int = 0                       # leading qubit operands that are controls (for the classical-PDG rule)

    @property
    def touched(self) -> FrozenSet[int]:
        return frozenset().union(*self.qubits) if self.qubits else frozenset()


@dataclass
class Circuit:
    uid: int
    line: int
    qregs: List[Reg] = field(default_factory=list)
    cregs: List[Reg] = field(default_factory=list)
    ops: List[Op] = field(default_factory=list)
    name: str = ""
    lines: FrozenSet[int] = E  # provenance of its construction (circuit and register lines)

    def offset(self, reg: Reg) -> Optional[int]:
        regs = self.qregs if reg.kind == "q" else self.cregs
        off = 0
        for r in regs:
            if r.uid == reg.uid:
                return off
            off += r.size or 0
        return None

    def n(self, kind="q") -> int:
        return sum(r.size or 0 for r in (self.qregs if kind == "q" else self.cregs))


@dataclass
class GateVal:
    name: str
    nq: Optional[int]
    params: Tuple[Any, ...] = ()


@dataclass
class Func:
    node: Any        # srcML <function> element
    params: List[Tuple[str, Optional[str]]]
    env: "Env"


@dataclass
class InstrSet:
    ops: List[Op]
    circ: Circuit


class _Return(Exception):
    def __init__(self, v):
        self.v = v


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


class Env:
    def __init__(self, parent: Optional["Env"] = None):
        self.vars: Dict[str, Tuple[Any, FrozenSet[int]]] = {}
        self.parent = parent

    def get(self, k):
        e = self
        while e is not None:
            if k in e.vars:
                return e.vars[k]
            e = e.parent
        return None

    def set(self, k, v, lines):
        self.vars[k] = (v, frozenset(lines))


@dataclass
class Trace:
    path: str
    circuits: List[Circuit]
    notes: List[Tuple[int, str]]

    def main_circuit(self) -> Optional[Circuit]:
        return max(self.circuits, key=lambda c: len(c.ops), default=None)


SAFE_MATH = {"sqrt", "sin", "cos", "tan", "arcsin", "arccos", "arctan", "asin", "acos", "atan", "exp", "log", "log2",
             "floor", "ceil", "pi", "e"}


class Interpreter:
    def __init__(self, path: str):
        self.path = path
        self.circuits: List[Circuit] = []
        self.notes: List[Tuple[int, str]] = []
        self.uid = 0
        self.ctx: List[Tuple[str, int, FrozenSet[int], Any]] = []  # (kind, line, lines, extra): for/if/while/with
        self.calls: List[int] = []
        self.may = 0
        self.nops = 0
        self.globals = Env()
        self.aliases: Dict[str, str] = {}
        self.star: List[str] = []
        self.base = 0

    # ---------------------------------------------------------------- helpers
    def _new(self):
        self.uid += 1
        return self.uid

    def note(self, line, msg):
        if (line, msg) not in self.notes:
            self.notes.append((line, msg))

    def ctx_lines(self) -> FrozenSet[int]:
        out = set()
        for _, ln, lines, _ in self.ctx:
            out.add(ln)
            out |= lines
        return frozenset(out) | frozenset(self.calls)

    def iters(self):
        return tuple((ln, extra) for k, ln, _, extra in self.ctx if k == "for")

    def cond_bits(self, circ: Circuit) -> Tuple[FrozenSet[int], FrozenSet[int]]:
        bits, lines = set(), set()
        for k, _, ln, extra in self.ctx:
            if k == "if_test" and extra is not None and extra[0] is circ:
                bits |= extra[1]
                lines |= ln
        return frozenset(bits), frozenset(lines)

    # ---------------------------------------------------------------- statements
    def run(self, unit) -> Trace:
        try:
            self.block(unit, self.globals)
        except _Return:
            pass
        return Trace(self.path, self.circuits, self.notes)

    def block(self, blk, env):
        for st in X.statements(blk):
            self.stmt(st, env)

    def stmt(self, st, env):
        t = X.tag(st)
        ln = X.line(st)
        if t in ("expr_stmt", "expr"):
            self.simple(X.text(st), ln, env)
        elif t == "import":
            self.do_import(X.text(st), ln)
        elif t == "for":
            self.do_for(st, env)
        elif t == "while":
            self.do_while(st, env)
        elif t == "if_stmt":
            self.do_if(st, env)
        elif t == "function":
            self.do_def(st, env)
        elif t == "return":
            src = X.text(st).strip()[len("return"):].strip()
            v = self.eval_text(src, ln, env) if src else (None, E)
            raise _Return(v)
        elif t == "with":
            self.do_with(st, env)
        elif t == "try":
            blk = X.child(st, "block")
            if blk is not None:
                self.block(blk, env)
            self.note(ln, "try: only the try block is interpreted")
        elif t == "break":
            raise _Break()
        elif t == "continue":
            raise _Continue()
        elif t in ("pass", "assert", "comment", "empty_stmt", "decl_stmt"):
            pass
        elif t == "throw":
            raise _Return((None, E))
        elif t == "class":
            self.note(ln, "class definitions are not interpreted")
        else:
            self.note(ln, f"statement <{t}> not interpreted")

    def simple(self, src, ln, env):
        try:
            tree = ast.parse(textwrap.dedent(src))
        except SyntaxError:
            self.note(ln, "statement text not parseable")
            return
        for node in tree.body:
            self.py_stmt(node, ln, env)

    def py_stmt(self, node, ln, env):
        L = ln + node.lineno - 1
        self.base = ln
        if isinstance(node, ast.Expr):
            self.ev(node.value, L, env)
        elif isinstance(node, ast.Assign):
            v = self.ev(node.value, L, env)
            for tg in node.targets:
                self.assign(tg, v, L, env)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            self.assign(node.target, self.ev(node.value, L, env), L, env)
        elif isinstance(node, ast.AugAssign):
            cur = self.ev(node.target, L, env)
            rhs = self.ev(node.value, L, env)
            self.assign(node.target, self.binop(node.op, cur, rhs), L, env)
        else:
            self.note(L, f"Python statement {type(node).__name__} not interpreted")

    def assign(self, tg, v, L, env):
        val, lines = v
        lines = frozenset(lines) | {L} | self.ctx_lines()
        if isinstance(tg, ast.Name):
            env.set(tg.id, val, lines)
        elif isinstance(tg, (ast.Tuple, ast.List)):
            if isinstance(val, (list, tuple)) and len(val) == len(tg.elts):
                for t2, x in zip(tg.elts, val):
                    self.assign(t2, (x, lines), L, env)
            else:
                for t2 in tg.elts:
                    self.assign(t2, (UNK, lines), L, env)
        elif isinstance(tg, ast.Subscript):
            obj, ol = self.ev(tg.value, L, env)
            idx, il = self.ev(tg.slice, L, env)
            if isinstance(obj, list) and isinstance(idx, int) and -len(obj) <= idx < len(obj):
                obj[idx] = val
            elif isinstance(obj, dict) and idx is not UNK:
                obj[idx] = val
        elif isinstance(tg, ast.Attribute):
            pass
        else:
            self.note(L, "assignment target not interpreted")

    def do_import(self, src, ln):
        try:
            tree = ast.parse(src.strip())
        except SyntaxError:
            return
        for node in tree.body:
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.aliases[a.asname or a.name.split(".")[0]] = a.name
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    if a.name == "*":
                        self.star.append(node.module or "")
                    else:
                        self.aliases[a.asname or a.name] = f"{node.module}.{a.name}"

    def _control(self, st):
        ctl = X.child(st, "control")
        tgt = X.text(ctl.find(X.S + "expr")) if ctl is not None and ctl.find(X.S + "expr") is not None else ""
        rng = ctl.find(X.S + "range") if ctl is not None else None
        it = X.text(rng).strip()
        if it.startswith("in"):
            it = it[2:]
        return tgt.strip(), it.strip()

    def do_for(self, st, env):
        ln = X.line(st)
        tgt, it = self._control(st)
        blk = X.child(st, "block")
        try:
            target = ast.parse(tgt, mode="eval").body
        except SyntaxError:
            self.note(ln, "for target not parseable")
            return
        seq, sl = self.eval_text(it, ln, env)
        items = self.iterate(seq)
        if items is None:
            self.note(ln, "loop over an unknown sequence: body interpreted twice, as may-operations")
            self.may += 1
            for i in range(2):
                self.assign(target, (UNK, sl), ln, env)
                self.ctx.append(("for", ln, frozenset(sl), i))
                try:
                    self.block(blk, env)
                except (_Break, _Continue):
                    pass
                finally:
                    self.ctx.pop()
            self.may -= 1
            return
        for i, x in enumerate(items):
            self.assign(target, (x, sl), ln, env)
            self.ctx.append(("for", ln, frozenset(sl), i))
            try:
                self.block(blk, env)
            except _Continue:
                pass
            except _Break:
                self.ctx.pop()
                break
            self.ctx.pop()
        else:
            return

    def iterate(self, seq):
        if isinstance(seq, (list, tuple, range)):
            return list(seq)[:MAX_ITER]
        if isinstance(seq, Reg):
            return [Bit(seq, i) for i in range(seq.size)] if seq.size is not None else None
        if isinstance(seq, dict):
            return list(seq)
        if isinstance(seq, str):
            return list(seq)
        return None

    def do_while(self, st, env):
        ln = X.line(st)
        cond = X.text(X.child(st, "condition")).strip()
        blk = X.child(st, "block")
        n = 0
        while n < MAX_ITER:
            c, cl = self.eval_text(cond, ln, env)
            if c is UNK:
                self.note(ln, "while loop with an unknown condition: body interpreted twice, as may-operations")
                self.may += 1
                for i in range(2):
                    self.ctx.append(("while", ln, frozenset(cl), i))
                    try:
                        self.block(blk, env)
                    except (_Break, _Continue):
                        pass
                    finally:
                        self.ctx.pop()
                self.may -= 1
                return
            if not c:
                return
            self.ctx.append(("while", ln, frozenset(cl), n))
            try:
                self.block(blk, env)
            except _Continue:
                pass
            except _Break:
                self.ctx.pop()
                return
            self.ctx.pop()
            n += 1
        self.note(ln, "while loop stopped at the iteration limit")

    def do_if(self, st, env):
        branches = []  # (condition text or None, block, line)
        for c in st:
            t = X.tag(c)
            if t in ("if", "elseif"):
                branches.append((X.text(X.child(c, "condition")).strip(), X.child(c, "block"), X.line(c)))
            elif t == "else":
                branches.append((None, X.child(c, "block"), X.line(c)))
        taken_unknown = False
        lines = set()
        for cond, blk, ln in branches:
            if cond is None:
                self.ctx.append(("if", ln, frozenset(lines), None))
                try:
                    if taken_unknown:
                        self.may += 1
                    self.block(blk, env)
                finally:
                    if taken_unknown:
                        self.may -= 1
                    self.ctx.pop()
                return
            c, cl = self.eval_text(cond, ln, env)
            lines |= set(cl) | {ln}
            if c is UNK or taken_unknown:
                if not taken_unknown:
                    self.note(ln, "unknown condition: every branch interpreted, as may-operations")
                taken_unknown = True
                self.ctx.append(("if", ln, frozenset(lines), None))
                self.may += 1
                try:
                    self.block(blk, env)
                finally:
                    self.may -= 1
                    self.ctx.pop()
                continue
            if c:
                self.ctx.append(("if", ln, frozenset(lines), None))
                try:
                    self.block(blk, env)
                finally:
                    self.ctx.pop()
                return

    def do_def(self, st, env):
        name = X.text(X.child(st, "name")).strip()
        params = []
        pl = X.child(st, "parameter_list")
        for p in (X.children(pl, "parameter") if pl is not None else []):
            ptxt = X.text(p).strip()
            if ptxt in ("self",) or ptxt.startswith("*"):
                params.append((ptxt.lstrip("*"), None))
                continue
            nm, _, dflt = ptxt.partition("=")
            nm = nm.split(":")[0].strip()
            params.append((nm, dflt.strip() or None))
        env.set(name, Func(st, params, env), {X.line(st)})

    def do_with(self, st, env):
        ln = X.line(st)
        expr = st.find(X.S + "expr")
        src = X.text(expr).strip() if expr is not None else ""
        blk = X.child(st, "block")
        try:
            node = ast.parse(src.split(" as ")[0], mode="eval").body
        except SyntaxError:
            node = None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "if_test":
            circ, _ = self.ev(node.func.value, ln, env)
            cond, cl = self.ev(node.args[0], ln, env) if node.args else (UNK, E)
            if isinstance(circ, Circuit):
                bits = self.cbits_of(circ, cond[0] if isinstance(cond, tuple) and cond else cond, ln)
                self.ctx.append(("if_test", ln, frozenset(cl) | {ln}, (circ, bits)))
                try:
                    self.block(blk, env)
                finally:
                    self.ctx.pop()
                return
        self.ctx.append(("with", ln, E, None))
        try:
            self.block(blk, env)
        finally:
            self.ctx.pop()

    # ---------------------------------------------------------------- expressions
    def eval_text(self, src, ln, env):
        self.base = ln
        try:
            node = ast.parse(textwrap.dedent(src).strip(), mode="eval").body
        except SyntaxError:
            self.note(ln, "expression not parseable")
            return UNK, E
        return self.ev(node, ln, env)

    def ev(self, n, L, env) -> Tuple[Any, FrozenSet[int]]:
        m = getattr(self, "ev_" + type(n).__name__, None)
        if m is None:
            return UNK, E
        return m(n, L, env)

    def ev_Constant(self, n, L, env):
        return n.value, E

    def ev_Name(self, n, L, env):
        got = env.get(n.id)
        if got is not None:
            return got
        if n.id in ("True", "False", "None"):
            return {"True": True, "False": False, "None": None}[n.id], E
        if n.id in self.aliases or n.id in BUILTINS:
            return ("__name__", self.aliases.get(n.id, n.id)), E
        if self.star:  # from <module> import *: an undefined name may come from it
            return ("__name__", f"{self.star[-1]}.{n.id}"), E
        return UNK, E

    def ev_Attribute(self, n, L, env):
        obj, ol = self.ev(n.value, L, env)
        a = n.attr
        if isinstance(obj, tuple) and len(obj) == 2 and obj[0] == "__name__":
            full = f"{obj[1]}.{a}"
            if a in ("pi",) and obj[1].split(".")[0] in ("numpy", "math", "np"):
                return math.pi, ol
            return ("__name__", full), ol
        if isinstance(obj, Circuit):
            if a == "qubits":
                return [Bit(r, i) for r in obj.qregs for i in range(r.size or 0)], ol | obj.lines
            if a == "clbits":
                return [Bit(r, i) for r in obj.cregs for i in range(r.size or 0)], ol | obj.lines
            if a in ("num_qubits", "width"):
                return obj.n("q"), ol | obj.lines
            if a == "num_clbits":
                return obj.n("c"), ol | obj.lines
            return ("__method__", obj, a), ol
        if isinstance(obj, Reg):
            if a == "size":
                return (obj.size if obj.size is not None else UNK), ol
            if a == "name":
                return obj.name, ol
        if isinstance(obj, (InstrSet, list, dict, GateVal)):
            return ("__method__", obj, a), ol
        return ("__method__", obj, a), ol

    def ev_Subscript(self, n, L, env):
        obj, ol = self.ev(n.value, L, env)
        if isinstance(n.slice, ast.Slice):
            lo = self.ev(n.slice.lower, L, env) if n.slice.lower else (None, E)
            hi = self.ev(n.slice.upper, L, env) if n.slice.upper else (None, E)
            st = self.ev(n.slice.step, L, env) if n.slice.step else (None, E)
            lines = ol | lo[1] | hi[1] | st[1]
            if UNK in (lo[0], hi[0], st[0]):
                seq = self.iterate(obj)
                return (UNK if seq is None else [Bit(obj, None)] if isinstance(obj, Reg) else UNK), lines
            seq = self.iterate(obj)
            if seq is None or not all(v is None or (isinstance(v, int) and not isinstance(v, bool)) for v in (lo[0], hi[0], st[0])):
                return UNK, lines
            return seq[slice(lo[0], hi[0], st[0])], lines
        idx, il = self.ev(n.slice, L, env)
        lines = ol | il
        if isinstance(obj, Reg):
            if isinstance(idx, int) and obj.size is not None:
                return Bit(obj, idx % obj.size if idx < 0 else idx), lines
            return Bit(obj, None), lines
        if isinstance(obj, (list, tuple, range, str)):
            if isinstance(idx, int) and -len(obj) <= idx < len(obj):
                return obj[idx], lines
            if all(isinstance(x, Bit) for x in obj) and obj:
                return [b for b in obj], lines  # unknown index into a list of bits: any of them
            return UNK, lines
        if isinstance(obj, dict) and idx is not UNK:
            try:
                return obj.get(idx, UNK), lines
            except TypeError:
                return UNK, lines
        if isinstance(obj, tuple) and obj[:1] == ("__name__",):
            return obj, lines
        return UNK, lines

    def ev_BinOp(self, n, L, env):
        return self.binop(n.op, self.ev(n.left, L, env), self.ev(n.right, L, env))

    def binop(self, op, a, b):
        (x, xl), (y, yl) = a, b
        lines = xl | yl
        if x is UNK or y is UNK or isinstance(x, (Bit, Reg, Circuit)) or isinstance(y, (Bit, Reg, Circuit)):
            if isinstance(x, list) and isinstance(y, list) and isinstance(op, ast.Add):
                return x + y, lines
            return UNK, lines
        if not self._small_enough(op, x, y):
            return UNK, lines
        try:
            f = {ast.Add: lambda p, q: p + q, ast.Sub: lambda p, q: p - q, ast.Mult: lambda p, q: p * q,
                 ast.Div: lambda p, q: p / q, ast.FloorDiv: lambda p, q: p // q, ast.Mod: lambda p, q: p % q,
                 ast.Pow: lambda p, q: p ** q, ast.BitAnd: lambda p, q: p & q, ast.BitOr: lambda p, q: p | q,
                 ast.BitXor: lambda p, q: p ^ q, ast.LShift: lambda p, q: p << q, ast.RShift: lambda p, q: p >> q}[type(op)]
            r = f(x, y)
            if isinstance(r, (list, str)) and len(r) > 100_000:
                return UNK, lines
            return r, lines
        except Exception:
            return UNK, lines

    @staticmethod
    def _small_enough(op, x, y) -> bool:
        """Refuse operations whose result could be huge (they run in C and cannot be interrupted): large powers,
        shifts and sequence repetitions. The result is then UNK, which is sound."""
        def big(v, lim):
            return isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v) > lim
        if isinstance(op, ast.Pow):
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                if big(y, 64) or (big(x, 2 ** 20) and not (isinstance(y, (int, float)) and abs(y) <= 1)):
                    return False
        if isinstance(op, (ast.LShift,)) and big(y, 64):
            return False
        if isinstance(op, ast.Mult):
            for a_, b_ in ((x, y), (y, x)):
                if isinstance(a_, (list, tuple, str)) and isinstance(b_, int) and len(a_) * abs(b_) > 100_000:
                    return False
            if big(x, 10 ** 300) or big(y, 10 ** 300):
                return False
        return True

    def ev_UnaryOp(self, n, L, env):
        x, xl = self.ev(n.operand, L, env)
        if x is UNK:
            return UNK, xl
        try:
            return {ast.USub: lambda p: -p, ast.UAdd: lambda p: +p, ast.Not: lambda p: not p,
                    ast.Invert: lambda p: ~p}[type(n.op)](x), xl
        except Exception:
            return UNK, xl

    def ev_BoolOp(self, n, L, env):
        vals = [self.ev(v, L, env) for v in n.values]
        lines = frozenset().union(*[l for _, l in vals])
        xs = [v for v, _ in vals]
        if any(v is UNK for v in xs):
            return UNK, lines
        try:
            return (all(xs) if isinstance(n.op, ast.And) else any(xs)), lines
        except Exception:
            return UNK, lines

    def ev_Compare(self, n, L, env):
        left, ll = self.ev(n.left, L, env)
        lines, res = set(ll), True
        for op, c in zip(n.ops, n.comparators):
            r, rl = self.ev(c, L, env)
            lines |= rl
            if left is UNK or r is UNK:
                return UNK, frozenset(lines)
            try:
                ok = {ast.Eq: lambda p, q: p == q, ast.NotEq: lambda p, q: p != q, ast.Lt: lambda p, q: p < q,
                      ast.LtE: lambda p, q: p <= q, ast.Gt: lambda p, q: p > q, ast.GtE: lambda p, q: p >= q,
                      ast.In: lambda p, q: p in q, ast.NotIn: lambda p, q: p not in q,
                      ast.Is: lambda p, q: p is q, ast.IsNot: lambda p, q: p is not q}[type(op)](left, r)
            except Exception:
                return UNK, frozenset(lines)
            res = res and ok
            left = r
        return res, frozenset(lines)

    def ev_IfExp(self, n, L, env):
        c, cl = self.ev(n.test, L, env)
        if c is UNK:
            a, al = self.ev(n.body, L, env)
            b, bl = self.ev(n.orelse, L, env)
            return (a if a == b else UNK), cl | al | bl
        v, vl = self.ev(n.body if c else n.orelse, L, env)
        return v, cl | vl

    def ev_List(self, n, L, env):
        vals = [self.ev(e, L, env) for e in n.elts]
        return [v for v, _ in vals], frozenset().union(*[l for _, l in vals]) if vals else E

    def ev_Tuple(self, n, L, env):
        v, l = self.ev_List(n, L, env)
        return tuple(v), l

    ev_Set = ev_List

    def ev_Dict(self, n, L, env):
        out, lines = {}, set()
        for k, v in zip(n.keys, n.values):
            kv, kl = self.ev(k, L, env) if k is not None else (UNK, E)
            vv, vl = self.ev(v, L, env)
            lines |= kl | vl
            try:
                if kv is not UNK:
                    out[kv] = vv
            except TypeError:
                pass
        return out, frozenset(lines)

    def ev_JoinedStr(self, n, L, env):
        return UNK, E

    def ev_ListComp(self, n, L, env):
        if len(n.generators) != 1 or n.generators[0].ifs and False:
            pass
        out, lines = [], set()

        def rec(gi, e):
            if gi == len(n.generators):
                v, vl = self.ev(n.elt, L, e)
                out.append(v)
                lines.update(vl)
                return True
            g = n.generators[gi]
            seq, sl = self.ev(g.iter, L, e)
            lines.update(sl)
            items = self.iterate(seq)
            if items is None:
                return False
            for x in items:
                e2 = Env(e)
                self.assign(g.target, (x, sl), L, e2)
                ok = True
                for cond in g.ifs:
                    c, cl = self.ev(cond, L, e2)
                    lines.update(cl)
                    if c is UNK:
                        return False
                    ok = ok and bool(c)
                if ok and not rec(gi + 1, e2):
                    return False
            return True
        if not rec(0, env):
            return UNK, frozenset(lines)
        return out, frozenset(lines)

    ev_GeneratorExp = ev_ListComp

    def ev_Lambda(self, n, L, env):
        return UNK, E

    def ev_Starred(self, n, L, env):
        return self.ev(n.value, L, env)

    # ---------------------------------------------------------------- calls
    def ev_Call(self, n, L, env):
        L = self.base + getattr(n, "lineno", 1) - 1 if self.base else L
        f, fl = self.ev(n.func, L, env)
        args, lines = [], set(fl)
        for a in n.args:
            v, vl = self.ev(a, L, env)
            lines |= vl
            if isinstance(a, ast.Starred):
                seq = self.iterate(v)
                args.extend(seq if seq is not None else [UNK])
            else:
                args.append(v)
        kw = {}
        for k in n.keywords:
            v, vl = self.ev(k.value, L, env)
            lines |= vl
            if k.arg:
                kw[k.arg] = v
        lines = frozenset(lines)
        if isinstance(f, Func):
            return self.call_func(f, n, L, env)
        if isinstance(f, tuple) and f[:1] == ("__method__",):
            return self.method(f[1], f[2], args, kw, lines, L, n, env)
        if isinstance(f, tuple) and f[:1] == ("__name__",):
            return self.named_call(f[1], args, kw, lines, L)
        callee = f[1].split(".")[-1] if isinstance(f, tuple) and f[:1] == ("__name__",) else ""
        if callee in OPAQUE:
            self.note(L, f"{callee}: the circuit is converted to a DAG; operations rewritten there are not traced")
        elif callee not in READ_ONLY:
            for v in list(args) + list(kw.values()):
                if isinstance(v, Circuit):
                    self.note(L, "a circuit is passed to a function the tool cannot see: its operations there are not traced")
        return UNK, lines

    def call_func(self, f: Func, n, L, env):
        if len(self.calls) > 40:
            self.note(L, "call depth limit reached")
            return UNK, E
        fe = Env(f.env)
        argv = [self.ev(a, L, env) for a in n.args]
        kwv = {k.arg: self.ev(k.value, L, env) for k in n.keywords if k.arg}
        for i, (pn, dflt) in enumerate(f.params):
            if i < len(argv):
                v = argv[i]
            elif pn in kwv:
                v = kwv[pn]
            elif dflt is not None:
                v = self.eval_text(dflt, X.line(f.node), f.env)
            else:
                v = (UNK, E)
            fe.set(pn, v[0], v[1] | {L})
        self.calls.append(L)
        try:
            self.block(X.child(f.node, "block"), fe)
            ret = (None, E)
        except _Return as r:
            ret = r.v
        finally:
            self.calls.pop()
        return ret[0], frozenset(ret[1]) | {L}

    def named_call(self, full, args, kw, lines, L):
        short = full.split(".")[-1]
        if short in OPAQUE and any(isinstance(v, Circuit) for v in list(args) + list(kw.values())):
            self.note(L, f"{short}: the circuit is converted to a DAG; operations rewritten there are not traced")
            return UNK, lines
        try:
            if short == "range" and all(isinstance(a, int) for a in args):
                return range(*args), lines
            if short == "len":
                a = args[0] if args else UNK
                if isinstance(a, Reg):
                    return (a.size if a.size is not None else UNK), lines
                if isinstance(a, Circuit):
                    return len(a.ops), lines
                return (len(a) if isinstance(a, (list, tuple, range, str, dict)) else UNK), lines
            if short in ("list", "tuple", "sorted", "reversed", "set"):
                seq = self.iterate(args[0]) if args else []
                if seq is None:
                    return UNK, lines
                r = {"list": list, "tuple": tuple, "sorted": sorted, "reversed": lambda s: list(reversed(s)),
                     "set": list}[short](seq)
                return r, lines
            if short == "zip":
                seqs = [self.iterate(a) for a in args]
                return (UNK if any(s is None for s in seqs) else [tuple(t) for t in zip(*seqs)]), lines
            if short == "enumerate":
                seq = self.iterate(args[0])
                return (UNK if seq is None else list(enumerate(seq))), lines
            if short in ("int", "float", "abs", "round", "min", "max", "sum", "bool", "str", "pow") and not any(a is UNK for a in args):
                return getattr(__builtins__, short, None)(*args) if not isinstance(__builtins__, dict) else __builtins__[short](*args), lines
            if short in SAFE_MATH and full.split(".")[0] in ("math", "numpy", "np", "cmath"):
                if any(a is UNK for a in args):
                    return UNK, lines
                return getattr(math, {"arcsin": "asin", "arccos": "acos", "arctan": "atan"}.get(short, short))(*args), lines
            if short == "print":
                return None, lines
            if short == "getattr" and len(args) >= 2 and isinstance(args[1], str):
                return ("__method__", args[0], args[1]), lines
            if short == "isinstance":
                return UNK, lines
        except Exception:
            return UNK, lines
        if short in ("QuantumRegister", "ClassicalRegister", "AncillaRegister"):
            size = args[0] if args else kw.get("size", UNK)
            name = args[1] if len(args) > 1 else kw.get("name", short[0].lower())
            r = Reg("c" if short == "ClassicalRegister" else "q", name if isinstance(name, str) else "?",
                    size if isinstance(size, int) else None, self._new())
            if r.size is None:
                self.note(L, f"{short} of unknown size")
            return r, lines | {L}
        if short == "QuantumCircuit":
            c = Circuit(self._new(), L, lines=lines | {L} | self.ctx_lines())
            ints = [a for a in args if isinstance(a, int)]
            for a in args:
                if isinstance(a, Reg):
                    (c.qregs if a.kind == "q" else c.cregs).append(a)
                elif isinstance(a, list) and a and all(isinstance(b, Bit) for b in a):
                    self.note(L, "QuantumCircuit built from a list of bits: treated as one register")
            if ints:
                c.qregs.append(Reg("q", "q", ints[0], self._new()))
                if len(ints) > 1:
                    c.cregs.append(Reg("c", "c", ints[1], self._new()))
            if any(a is UNK for a in args):
                self.note(L, "QuantumCircuit of unknown size")
                c.qregs.append(Reg("q", "q", None, self._new()))
            self.circuits.append(c)
            return c, lines | {L}
        if short.endswith("Gate") or short in ("Measure", "Reset", "Barrier", "Initialize", "QFT", "Isometry",
                                                "UnitaryGate", "Diagonal", "GroverOperator", "PhaseOracle"):
            return GateVal(short, self._gate_arity(full, args, kw), tuple(args)), lines | {L}
        if short in ("execute", "transpile", "assemble", "plot_histogram", "get_backend", "run"):
            return UNK, lines
        return UNK, lines

    def _gate_arity(self, full, args, kw):
        try:
            import qiskit.circuit.library as lib
            cls = getattr(lib, full.split(".")[-1], None)
            if cls is None:
                return None
            safe = [a if isinstance(a, (int, float)) else 0.5 for a in args]
            return cls(*safe).num_qubits
        except Exception:
            n = kw.get("num_qubits") if isinstance(kw.get("num_qubits"), int) else (args[0] if args and isinstance(args[0], int) else None)
            return n

    # ---------------------------------------------------------------- circuit methods
    def method(self, obj, name, args, kw, lines, L, n, env):
        if isinstance(obj, Circuit):
            return self.circuit_method(obj, name, args, kw, lines, L)
        if isinstance(obj, InstrSet):
            if name == "c_if" and args:
                bits = self.cbits_of(obj.circ, args[0], L)
                for i, op in enumerate(obj.ops):
                    obj.ops[i].__dict__  # Op is a mutable dataclass
                    op.cond = op.cond | bits
                    op.deps = op.deps | lines | {L}
                return obj, lines
            return obj, lines
        if isinstance(obj, list):
            if name == "append" and args:
                obj.append(args[0])
                return None, lines
            if name == "extend" and args:
                seq = self.iterate(args[0])
                obj.extend(seq if seq is not None else [UNK])
                return None, lines
            if name == "pop":
                return (obj.pop() if obj else UNK), lines
            if name == "index" and args and args[0] in obj:
                return obj.index(args[0]), lines
            if name == "reverse":
                obj.reverse()
                return None, lines
            return UNK, lines
        if isinstance(obj, GateVal):
            if name in ("control",):
                k = args[0] if args and isinstance(args[0], int) else 1
                return GateVal("c" + obj.name, (obj.nq + k) if obj.nq is not None else None), lines
            if name in ("inverse", "power", "to_gate", "to_instruction", "copy"):
                return obj, lines
            return UNK, lines
        if isinstance(obj, tuple) and obj[:1] == ("__name__",):
            return self.named_call(f"{obj[1]}.{name}", args, kw, lines, L)
        if name not in READ_ONLY:
            for v in list(args) + list(kw.values()):
                if isinstance(v, Circuit):
                    self.note(L, "a circuit is passed to a method the tool cannot see: its operations there are not traced")
        return UNK, lines

    def qubit_sets(self, circ: Circuit, v, L) -> Optional[List[FrozenSet[int]]]:
        """A qubit argument as a list (broadcast) of sets of global qubit indices."""
        allq = frozenset(range(circ.n("q")))
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            if 0 <= v < circ.n("q") or v < 0 and -v <= circ.n("q"):
                return [frozenset({v % circ.n("q")})]
            self.note(L, f"qubit index {v} out of range")
            return [allq]
        if isinstance(v, Bit):
            off = circ.offset(v.reg)
            if off is None:
                self.note(L, "a qubit of a register not in this circuit")
                return [allq]
            if v.index is None or v.reg.size is None:
                return [frozenset(range(off, off + (v.reg.size or 0))) or allq]
            return [frozenset({off + v.index})]
        if isinstance(v, Reg):
            off = circ.offset(v)
            if off is None or v.size is None:
                return [allq]
            return [frozenset({off + i}) for i in range(v.size)]
        if isinstance(v, (list, tuple, range)):
            out = []
            for x in v:
                s = self.qubit_sets(circ, x, L)
                if s is None:
                    return None
                out.extend(s)
            return out
        return [allq]  # UNK or anything else: any qubit (a may-operation)

    def cbits_of(self, circ: Circuit, v, L) -> FrozenSet[int]:
        if isinstance(v, int) and not isinstance(v, bool):
            return frozenset({v}) if 0 <= v < circ.n("c") else frozenset(range(circ.n("c")))
        if isinstance(v, Bit):
            off = circ.offset(v.reg)
            if off is None or v.index is None:
                return frozenset(range(circ.n("c")))
            return frozenset({off + v.index})
        if isinstance(v, Reg):
            off = circ.offset(v)
            return frozenset(range(off, off + (v.size or 0))) if off is not None else frozenset(range(circ.n("c")))
        if isinstance(v, (list, tuple)):
            return frozenset().union(*[self.cbits_of(circ, x, L) for x in v]) if v else frozenset()
        return frozenset(range(circ.n("c")))

    def emit(self, circ: Circuit, name, qsets: List[FrozenSet[int]], csets, lines, L, params=(), nctrl=0):
        if self.nops >= MAX_OPS:
            self.note(L, "operation limit reached")
            return None
        cond, cl = self.cond_bits(circ)
        unresolved = any(len(s) != 1 for s in qsets)
        op = Op(name, tuple(qsets), tuple(csets), cond, L, tuple(self.calls), self.iters(),
                frozenset(lines) | cl | self.ctx_lines() | circ.lines, self.may > 0 or unresolved, tuple(params), nctrl)
        circ.ops.append(op)
        self.nops += 1
        return op

    def circuit_method(self, circ: Circuit, name, args, kw, lines, L):
        if name in ("measure_all", "measure_active"):
            nq = circ.n("q")
            reg = Reg("c", "meas", nq, self._new())
            circ.cregs.append(reg)
            off = circ.offset(reg)
            ops = [self.emit(circ, "measure", [frozenset({q})], [frozenset({off + q})], lines, L) for q in range(nq)]
            return InstrSet([o for o in ops if o], circ), lines
        if name == "add_register":
            for a in args:
                if isinstance(a, Reg):
                    (circ.qregs if a.kind == "q" else circ.cregs).append(a)
            return None, lines
        if name in ("append", "compose"):
            return self.append_or_compose(circ, name, args, kw, lines, L)
        if name in ("copy",):
            c2 = Circuit(self._new(), L, list(circ.qregs), list(circ.cregs), list(circ.ops), lines=circ.lines | {L})
            self.circuits.append(c2)
            return c2, lines | {L}
        if name in ("inverse", "reverse_ops", "power", "repeat", "decompose", "assign_parameters", "bind_parameters"):
            if name == "decompose":
                return circ, lines
            self.note(L, f"QuantumCircuit.{name}: result treated as unknown")
            return UNK, lines
        if name in ("to_gate", "to_instruction"):
            return GateVal("circuit", circ.n("q")), lines | {L}
        if name == "if_test":
            self.note(L, "if_test outside a with statement is not interpreted")
            return UNK, lines
        sig = GATES.get(name)
        if sig is None:
            if name not in ("draw", "count_ops", "size", "depth", "width", "qasm", "num_qubits", "remove_final_measurements",
                            "barrier", "save_statevector", "snapshot", "save_state"):
                self.note(L, f"QuantumCircuit.{name} is not modelled")
            return UNK, lines
        # bind arguments to the signature
        bound = {}
        names = [p for p, _ in sig.args]
        for i, a in enumerate(args):
            if i < len(names):
                bound[names[i]] = a
        for k, v in kw.items():
            bound[k] = v
        qargs, cargs, params = [], [], []
        for p, k in sig.args:
            if p not in bound:
                continue
            if k == "q":
                if name == "barrier" and p == "qargs":
                    pass
                s = self.qubit_sets(circ, bound[p], L)
                if s is None:
                    self.note(L, f"argument {p} of {name} not understood")
                    s = [frozenset(range(circ.n("q")))]
                qargs.append((p, s))
            elif k == "c":
                v = bound[p]
                seq = self.iterate(v) if isinstance(v, (list, tuple, range, Reg)) else [v]
                cargs.append([self.cbits_of(circ, x, L) for x in (seq if seq is not None else [UNK])])
            elif k == "angle":
                params.append(bound[p])
        if name == "barrier":
            return InstrSet([], circ), lines
        if name == "measure" and not cargs:
            cargs = [[frozenset(range(circ.n("c")))]]
        # broadcast: argument lists of length 1 are repeated
        # plural parameters (control_qubits, qubits, ...) are one operand list of a single operation, not a broadcast
        plural = [(p, s) for p, s in qargs if p in PLURAL]
        qargs = [(p, s) for p, s in qargs if p not in PLURAL]
        lens = [len(s) for _, s in qargs] + [len(c) for c in cargs]
        width = max(lens) if lens else 1
        ops = []
        if all(x in (1, width) for x in lens):
            nctrl = sum(len(s) for p, s in plural if p.startswith("control")) + sum(1 for p, _ in qargs if p.startswith("control"))
            for i in range(width):
                qs = [x for _, s in plural for x in s] + [s[i if len(s) > 1 else 0] for _, s in qargs]
                cs = [c[i if len(c) > 1 else 0] for c in cargs]
                ops.append(self.emit(circ, name, qs, cs, lines, L, params, nctrl))
        else:
            self.note(L, f"{name}: argument lengths do not broadcast; one may-operation on all named qubits")
            qs = [x for _, s in plural for x in s] + [frozenset().union(*s) for _, s in qargs]
            cs = [frozenset().union(*c) for c in cargs]
            op = self.emit(circ, name, qs, cs, lines, L, params)
            if op:
                op.may = True
            ops.append(op)
        if name in NOT_SLICED:
            pass
        return InstrSet([o for o in ops if o], circ), lines

    def append_or_compose(self, circ, name, args, kw, lines, L):
        inst = args[0] if args else kw.get("instruction", kw.get("other", UNK))
        qv = args[1] if len(args) > 1 else kw.get("qargs", kw.get("qubits", None))
        cv = args[2] if len(args) > 2 else kw.get("cargs", kw.get("clbits", None))
        if name == "compose" and isinstance(inst, Circuit):
            target = circ
            if not kw.get("inplace", False):
                target = Circuit(self._new(), L, list(circ.qregs), list(circ.cregs), list(circ.ops), lines=circ.lines | {L})
                self.circuits.append(target)
            if qv is None:
                qmap = list(range(inst.n("q")))
            else:
                s = self.qubit_sets(target, qv, L) or []
                qmap = [next(iter(x)) if len(x) == 1 else None for x in s]
            for op in inst.ops:
                qs = []
                for qset in op.qubits:
                    m = set()
                    for q in qset:
                        t = qmap[q] if q < len(qmap) else None
                        m |= {t} if t is not None else set(range(target.n("q")))
                    qs.append(frozenset(m))
                new = Op(op.name, tuple(qs), op.clbits, op.cond, op.line, op.calls + (L,), op.iters,
                         op.deps | lines | {L}, op.may or any(len(x) != 1 for x in qs), op.params)
                target.ops.append(new)
            return (InstrSet([], target) if kw.get("inplace", False) else target), lines | {L}
        nq = inst.nq if isinstance(inst, GateVal) else inst.n("q") if isinstance(inst, Circuit) else None
        gname = inst.name if isinstance(inst, GateVal) else "circuit" if isinstance(inst, Circuit) else "unknown"
        s = self.qubit_sets(circ, qv, L) if qv is not None else None
        if s is None:
            self.note(L, f"{name}: qubits not resolved; may-operation on all qubits")
            s = [frozenset(range(circ.n("q")))]
        if nq is not None and len(s) != nq:
            self.note(L, f"{name}: {len(s)} qubits given for a {nq}-qubit operation")
        cs = []
        if cv is not None:
            seq = self.iterate(cv) if isinstance(cv, (list, tuple, range, Reg)) else [cv]
            cs = [self.cbits_of(circ, x, L) for x in (seq or [UNK])]
        if gname.lower() in ("measure",):
            gname = "measure"
        op = self.emit(circ, gname.lower().replace("gate", "") or "unknown", s, cs, lines, L,
                       inst.params if isinstance(inst, GateVal) else ())
        return InstrSet([op] if op else [], circ), lines


# Calls that turn a circuit into another representation the tool does not follow (rewrites there are not traced)
OPAQUE = {"circuit_to_dag", "dag_to_circuit", "substitute_node_with_dag", "apply_operation_back", "apply_operation_front"}
# Functions and methods that only read a circuit they are given (simulation, compilation, display, analysis).
READ_ONLY = {"execute", "transpile", "assemble", "run", "plot_histogram", "plot_state_city", "plot_bloch_multivector",
             "plot_state_qsphere", "plot_circuit_layout", "plot_gate_map", "circuit_drawer", "draw", "print", "display",
             "Statevector", "DensityMatrix", "Operator", "from_instruction", "from_label", "evolve", "simulate",
             "circuit_to_instruction", "circuit_to_gate", "dumps", "dump", "qasm",
             "qasm2", "qasm3", "count_ops", "depth", "size", "width", "len", "str", "repr", "Sampler", "Estimator",
             "SamplerV2", "EstimatorV2", "result", "get_counts", "get_statevector", "save", "append_to_list",
             "assertEqual", "assertTrue", "assertIsInstance", "submit", "job", "isinstance", "copy", "deepcopy"}
PLURAL = {"control_qubits", "ancilla_qubits", "target_qubits", "qubits", "qargs"}
BUILTINS = {"range", "len", "list", "tuple", "zip", "enumerate", "int", "float", "abs", "round", "min", "max", "sum",
            "sorted", "reversed", "print", "bool", "str", "set", "pow", "getattr", "isinstance"}


def trace_file(path) -> Trace:
    from pathlib import Path
    unit = X.parse_file(Path(path))
    return Interpreter(str(path)).run(unit)
