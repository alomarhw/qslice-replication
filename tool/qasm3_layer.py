"""The quantum layer over the srcML of an OpenQASM 3 program (tool.qasm3_srcml), for the subset it marks up.

OpenQASM 3 decides at run time what Qiskit decides in Python and on the device, so the layer applies E2 as it does to
a Qiskit program (tool.interp), with the same rules:
  - a classical value the layer can compute is computed (declarations, assignments, loop variables); a value read from
    a measured bit, an input, or a construct outside the subset is unknown, and carries the bits it was read from;
  - an `if` or `while` whose condition reads measured bits runs on the device: every operation under it is
    conditioned on those bits, as an if_test is; a `while`, and a `for` over an unknown range, is repeated until no
    new dependence appears, as may-operations (tool.interp.Interpreter.unknown_loop); a `switch` conditions every case
    on the bits of its target;
  - an `if`, `for` or `while` over values the layer knows is followed exactly: the branch taken, the iterations
    unrolled with their index recorded;
  - a condition the layer cannot decide and that reads no measured bit makes every branch a may-operation;
  - a qubit operand it cannot resolve acts on every qubit it may denote, as a may-operation.
Gate calls are one operation on their qubits, controls from ctrl and negctrl first; a gate definition is a
role-table entry, as for OpenQASM 2. Statements outside the subset are reported in the trace's notes.

    read(path) -> Trace          ops(path) -> iterator of Op
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterator, List, Optional, Tuple

from tool.interp import Circuit, Op, Reg, Trace
from tool.qasm3_srcml import _lexer, unit_elements
from tool.qasm_srcml import NS, POS

S = "{%s}" % NS
E: FrozenSet[int] = frozenset()
UNK = object()
MAX_ITER = 10_000
MAX_COPIES = 65
# stdgates.inc of the OpenQASM 3 specification: name -> (parameters, qubits); U and gphase are built in
STDGATES = {"p": (1, 1), "x": (0, 1), "y": (0, 1), "z": (0, 1), "h": (0, 1), "s": (0, 1), "sdg": (0, 1),
            "t": (0, 1), "tdg": (0, 1), "sx": (0, 1), "rx": (1, 1), "ry": (1, 1), "rz": (1, 1), "cx": (0, 2),
            "cy": (0, 2), "cz": (0, 2), "cp": (1, 2), "crx": (1, 2), "cry": (1, 2), "crz": (1, 2), "ch": (0, 2),
            "swap": (0, 2), "ccx": (0, 3), "cswap": (0, 3), "cu": (4, 2), "CX": (0, 2), "phase": (1, 1),
            "cphase": (1, 2), "id": (0, 1), "u1": (1, 1), "u2": (2, 1), "u3": (3, 1)}
CONTROLS = {"cx": 1, "cy": 1, "cz": 1, "cp": 1, "crx": 1, "cry": 1, "crz": 1, "ch": 1, "cswap": 1, "ccx": 2,
            "cu": 1, "CX": 1, "cphase": 1}
CONST = {"pi": math.pi, "π": math.pi, "tau": 2 * math.pi, "τ": 2 * math.pi, "euler": math.e, "ℇ": math.e}
FUNCS = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "arcsin": math.asin, "arccos": math.acos,
         "arctan": math.atan, "exp": math.exp, "log": math.log, "sqrt": math.sqrt, "abs": abs, "floor": math.floor,
         "ceiling": math.ceil}


class Qasm3Error(Exception):
    pass


class _Stop(Exception):
    pass


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


def tag(e) -> str:
    return e.tag.replace(S, "")


def text(e) -> str:
    return "".join(e.itertext()) if e is not None else ""


def line(e) -> int:
    return int(e.get("{%s}start" % POS).split(":")[0])


class V:
    """A classical value: the value, or UNK, and the measured bits it was computed from."""
    __slots__ = ("v", "bits")

    def __init__(self, v, bits=E):
        self.v, self.bits = v, frozenset(bits)


class _Layer:
    def __init__(self, path: Path):
        self.path = path
        self.q: Dict[str, Tuple[int, int, int]] = {}     # qubit register -> (offset, size, declaration line)
        self.c: Dict[str, Tuple[int, int, int]] = {}     # bit register
        self.nq = self.nc = 0
        self.vars: Dict[str, V] = {}
        self.gates: Dict[str, Tuple[int, int]] = {}
        self.user: set = set()
        self.ops: List[Op] = []
        self.notes: List[Tuple[int, str]] = []
        self.ctx: List[Tuple[str, Any]] = []               # ("cond", bits) | ("for", (line, i)) | ("may", None)
        self.hw: Dict[int, int] = {}
        self.subs: Dict[str, int] = {}                     # def subroutines (outside the subset): name -> line

    def note(self, ln, msg):
        if (ln, msg) not in self.notes:
            self.notes.append((ln, msg))

    # ------------------------------------------------------------------ expressions
    def ev(self, e) -> V:
        """The value of an <expr> (or <init>) element, from its text, which srcML keeps exactly."""
        if e is None:
            return V(UNK)
        self._ln = line(e) if e.get("{%s}start" % POS) else getattr(self, "_ln", 0)
        if tag(e) == "measure":
            return V(UNK, self._measure(e, None))
        toks = [t for t in _lexer(text(e)) if t.kind not in ("ws", "comment")]
        self._t, self._k = toks, 0
        try:
            out = self._or()
            return out if self._k == len(toks) else V(UNK, out.bits)
        except (IndexError, ValueError, TypeError, ZeroDivisionError, OverflowError):
            return V(UNK, self._bits_in(toks))

    def _bits_in(self, toks) -> FrozenSet[int]:
        b = set()
        for t in toks:
            if t.text in self.c:
                off, size, _ = self.c[t.text]
                b |= set(range(off, off + size))
            elif t.text in self.vars:
                b |= self.vars[t.text].bits
        return frozenset(b)

    def _peek(self):
        return self._t[self._k].text if self._k < len(self._t) else None

    def _next(self):
        self._k += 1
        return self._t[self._k - 1]

    def _bin(self, ops, sub, fn):
        a = sub()
        while self._peek() in ops:
            o = self._next().text
            b = sub()
            a = V(UNK if a.v is UNK or b.v is UNK else fn(o, a.v, b.v), a.bits | b.bits)
        return a

    def _or(self):
        return self._bin(("||",), self._and, lambda o, a, b: bool(a) or bool(b))

    def _and(self):
        return self._bin(("&&",), self._bor, lambda o, a, b: bool(a) and bool(b))

    def _bor(self):
        return self._bin(("|",), self._xor, lambda o, a, b: int(a) | int(b))

    def _xor(self):
        return self._bin(("^",), self._band, lambda o, a, b: int(a) ^ int(b))

    def _band(self):
        return self._bin(("&",), self._eq, lambda o, a, b: int(a) & int(b))

    def _eq(self):
        return self._bin(("==", "!="), self._cmp, lambda o, a, b: (a == b) if o == "==" else (a != b))

    def _cmp(self):
        f = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b}
        return self._bin(tuple(f), self._shift, lambda o, a, b: f[o](a, b))

    def _shift(self):
        return self._bin(("<<", ">>"), self._add, lambda o, a, b: int(a) << int(b) if o == "<<" else int(a) >> int(b))

    def _add(self):
        return self._bin(("+", "-"), self._mul, lambda o, a, b: a + b if o == "+" else a - b)

    def _mul(self):
        def f(o, a, b):
            if o == "*":
                return a * b
            if o == "%":
                return a % b
            return a // b if isinstance(a, int) and isinstance(b, int) else a / b
        return self._bin(("*", "/", "%"), self._unary, f)

    def _unary(self):
        if self._peek() in ("-", "~", "!"):
            o = self._next().text
            a = self._unary()
            if a.v is UNK:
                return a
            return V(-a.v if o == "-" else (~int(a.v) if o == "~" else (not a.v)), a.bits)
        return self._pow()

    def _pow(self):
        a = self._atom()
        if self._peek() == "**":
            self._next()
            b = self._unary()
            return V(UNK if a.v is UNK or b.v is UNK else a.v ** b.v, a.bits | b.bits)
        return a

    def _atom(self) -> V:
        t = self._next()
        x = t.text
        if t.kind == "int":
            s = x.replace("_", "")
            return V(int(s, 0) if s[:2].lower() in ("0b", "0o", "0x") else int(s))
        if t.kind == "real":
            s = x.replace("_", "").replace(" ", "")
            return V(complex(0, float(s[:-2])) if s.endswith("im") else float(s))
        if t.kind == "timing":
            return V(UNK)
        if t.kind == "string":
            return V(int(x.strip("\"'").replace("_", ""), 2))
        if x in ("true", "false"):
            return V(x == "true")
        if x == "(":
            v = self._or()
            self._next()
            return v
        if x in FUNCS and self._peek() == "(":
            self._next()
            a = self._or()
            self._next()
            return V(UNK if a.v is UNK else FUNCS[x](a.v), a.bits)
        if x in self.subs and self._peek() == "(":
            self._next()
            depth, start = 1, self._k
            while depth:
                depth += self._peek() == "("
                depth -= self._peek() == ")"
                self._next()
            names = [u for u in self._t[start:self._k - 1] if u.kind in ("id", "hw")]
            ops = [ET.fromstring(f'<expr xmlns="{NS}" xmlns:pos="{POS}" pos:start="{self._ln}:1"><name pos:start="{self._ln}:1">'
                                 f'{u.text}</name></expr>') if u.kind == "id" else
                   ET.fromstring(f'<expr xmlns="{NS}" xmlns:pos="{POS}" pos:start="{self._ln}:1"><literal type="qubit">'
                                 f'{u.text}</literal></expr>') for u in names if u.kind == "hw" or u.text in self.q]
            return V(UNK, self.sub_call(x, ops, self._ln))
        if self._peek() == "(" :                          # a cast or another call: its argument's bits
            self._next()
            depth, start = 1, self._k
            while depth:
                depth += self._peek() == "("
                depth -= self._peek() == ")"
                self._next()
            inner = self._t[start:self._k - 1]
            return V(UNK, self._bits_in(inner))
        if x in CONST and x not in self.vars:
            return self._index(V(CONST[x]))
        if x in self.c:
            off, size, _ = self.c[x]
            if self._peek() == "[":
                return self._bit_index(off, size)
            return V(UNK, range(off, off + size))
        if x in self.vars:
            return self._index(self.vars[x])
        if x in self.q:
            return V(UNK)
        return self._index(V(UNK))

    def _index(self, v: V) -> V:
        while self._peek() == "[":
            self._next()
            depth = 1
            while depth:
                depth += self._peek() == "["
                depth -= self._peek() == "]"
                self._next()
            v = V(UNK, v.bits)
        return v

    def _bit_index(self, off, size) -> V:
        self._next()
        i = self._or()
        self._next()
        if isinstance(i.v, int) and 0 <= i.v < size:
            return V(UNK, {off + i.v} | i.bits)
        return V(UNK, set(range(off, off + size)) | i.bits)

    # ------------------------------------------------------------------ operands
    def indices(self, idx_el, size: int) -> Tuple[Optional[List[int]], bool]:
        """The indices an <index> denotes, inclusive ranges as OpenQASM 3 defines them; None when unknown."""
        parts = list(idx_el)
        if len(parts) == 1 and parts[0].get("type") == "set":
            vals = [self.ev(x).v for x in parts[0]]
            return (None, True) if any(not isinstance(v, int) for v in vals) else ([v % size if v < 0 else v for v in vals], False)
        out = []
        for p in parts:
            src = text(p)
            if ":" in src:
                pieces = [self.ev(ET.fromstring(f'<expr xmlns="{NS}">{x}</expr>')).v if x.strip() else None
                          for x in _split_colon(src)]
                if any(x is not None and not isinstance(x, int) for x in pieces):
                    return None, True
                if len(pieces) == 2:
                    a, b, st = pieces[0], pieces[1], 1
                else:
                    a, st, b = pieces
                a = 0 if a is None else a
                b = size - 1 if b is None else b
                st = st or 1
                a, b = (a % size if a < 0 else a), (b % size if b < 0 else b)
                out += list(range(a, b + (1 if st > 0 else -1), st))
            else:
                v = self.ev(p).v
                if not isinstance(v, int):
                    return None, True
                out.append(v % size if v < 0 else v)
        return out, False

    def qubits(self, operand) -> Tuple[List[FrozenSet[int]], bool]:
        """The qubits an operand denotes, one set per qubit (a may-set when unknown), and whether it is unknown."""
        lit = operand.find(f".//{S}literal")
        if lit is not None and lit.get("type") == "qubit":
            n = int(text(lit)[1:])
            if n not in self.hw:
                self.hw[n] = self.nq
                self.nq += 1
            return [frozenset([self.hw[n]])], False
        nm = operand.find(S + "name")
        inner = nm.find(S + "name")
        reg = text(inner if inner is not None else nm).strip()
        if reg not in self.q:
            self.note(line(operand), f"qubit operand {reg!r} is not a declared register (a construct outside the "
                                     f"subset may have named it): read as any qubit")
            return [frozenset(range(self.nq))], True
        off, size, _ = self.q[reg]
        idx = nm.find(S + "index")
        if idx is None:
            return [frozenset([off + i]) for i in range(size)], False
        got, unknown = self.indices(idx, size)
        if unknown:
            return [frozenset(range(off, off + size))], True
        if any(i >= size for i in got):
            raise Qasm3Error(f"{self.path}:{line(operand)}: index out of range for {reg}[{size}]")
        return [frozenset([off + i]) for i in got], False

    def bits_of(self, operand) -> List[FrozenSet[int]]:
        nm = operand.find(f".//{S}name")
        inner = nm.find(S + "name")
        reg = text(inner if inner is not None else nm).strip()
        if reg in self.vars:                     # a bit of a classical variable, such as an angle
            b = self.nc
            self.nc += 1
            self.vars[reg] = V(UNK, self.vars[reg].bits | {b})
            return [frozenset([b])]
        if reg not in self.c:
            raise Qasm3Error(f"{self.path}:{line(operand)}: {reg!r} is not a declared bit register")
        off, size, _ = self.c[reg]
        idx = nm.find(S + "index")
        if idx is None:
            return [frozenset([off + i]) for i in range(size)]
        got, unknown = self.indices(idx, size)
        return [frozenset(range(off, off + size))] if unknown else [frozenset([off + i]) for i in got]

    # ------------------------------------------------------------------ operations
    def emit(self, name, qubits, ln, clbits=(), may=False, nctrl=0):
        cond = frozenset(b for k, x in self.ctx if k == "cond" for b in x)
        iters = tuple(x for k, x in self.ctx if k == "for")
        may = may or any(k == "may" for k, _ in self.ctx)
        self.ops.append(Op(name=name, qubits=tuple(qubits), clbits=tuple(clbits), cond=cond, line=ln, calls=(),
                           iters=iters, deps=E, may=may, nctrl=nctrl))

    def _measure(self, m, target_el) -> FrozenSet[int]:
        """A measurement; target_el is the bit operand or None (the caller assigns). Returns the bits written."""
        q_el = m.find(S + "expr")
        qs, unk = self.qubits(q_el)
        return frozenset(qs[0]) if qs else E  # placeholder, the caller emits

    def measure(self, q_el, targets: List[FrozenSet[int]], ln):
        qs, unk = self.qubits(q_el)
        if len(targets) == 1 and len(qs) > 1 and len(targets[0]) == len(qs):
            targets = [frozenset([b]) for b in sorted(targets[0])]
        if len(qs) != len(targets):
            raise Qasm3Error(f"{self.path}:{ln}: measure: {len(qs)} qubits into {len(targets)} bits")
        for qb, cb in zip(qs, targets):
            self.emit("measure", [qb], ln, clbits=(cb,), may=unk)
        return frozenset(b for t in targets for b in t)

    def gate_call(self, call, ln):
        mods = call.findall(S + "specifier")
        name = text(call.find(S + "name")).strip()
        lists = call.findall(S + "argument_list")
        angles = [l for l in lists if l.get("type") != "quantum"]
        qlist = [l for l in lists if l.get("type") == "quantum"]
        nctrl = 0
        for m in mods:
            mn = text(m.find(S + "name")).strip()
            if mn in ("ctrl", "negctrl"):
                al = m.find(S + "argument_list")
                k = self.ev(al.find(f"{S}argument/{S}expr")).v if al is not None else 1
                if not isinstance(k, int):
                    raise Qasm3Error(f"{self.path}:{ln}: {mn}(n) needs a known n")
                nctrl += k
        if name in self.subs:
            args = qlist[0].findall(S + "argument") if qlist else []
            self.sub_call(name, [a.find(S + "expr") for a in args], ln)
            return
        if name == "gphase":
            if not qlist:
                return                                     # a global phase on no qubit
            nq = nctrl
        elif name == "U":
            nq = 1 + nctrl
        elif name in self.gates:
            nq = self.gates[name][1] + nctrl
        else:
            raise Qasm3Error(f"{self.path}:{ln}: gate {name!r} is not defined")
        args = qlist[0].findall(S + "argument") if qlist else []
        if len(args) != nq:
            raise Qasm3Error(f"{self.path}:{ln}: {name} with {len(mods)} modifiers acts on {nq} qubits, {len(args)} given")
        per, unk = [], False
        for a in args:
            qs, u = self.qubits(a.find(S + "expr"))
            per.append(qs)
            unk |= u
        width = max(len(p) for p in per)
        if any(len(p) not in (1, width) for p in per):
            raise Qasm3Error(f"{self.path}:{ln}: {name}: registers of different sizes in one application")
        base_ctrl = CONTROLS.get(name, 0) if name not in self.user else 0
        for i in range(width):
            qb = [p[i] if len(p) > 1 else p[0] for p in per]
            singles = [next(iter(s)) for s in qb if len(s) == 1]
            if len(singles) != len(set(singles)) and not unk:
                raise Qasm3Error(f"{self.path}:{ln}: {name} is applied to the same qubit twice")
            self.emit(name if name != "U" else "u", qb, ln, may=unk, nctrl=nctrl + base_ctrl)

    def sub_call(self, name, operands, ln) -> FrozenSet[int]:
        """A call to a def subroutine, which the subset does not read: a subroutine reaches only the qubits passed
        to it, so the call is one operation on all of them; its result is a fresh bit the operation writes, so a
        condition on the result depends on the call."""
        qs, unk = [], False
        for o in operands:
            got, u = self.qubits(o)
            qs += got
            unk |= u
        b = self.nc
        self.nc += 1
        self.emit(name, qs, ln, clbits=(frozenset([b]),), may=unk)
        return frozenset([b])

    # ------------------------------------------------------------------ statements
    def block(self, blk):
        """A scope: what it declares goes out of scope at its end (the bits it used stay distinct)."""
        before = (set(self.c), set(self.vars))
        try:
            for st in blk.find(S + "block_content"):
                self.stmt(st)
        finally:
            for k in set(self.c) - before[0]:
                del self.c[k]
            for k in set(self.vars) - before[1]:
                del self.vars[k]

    def stmt(self, e):
        t = tag(e)
        ln = line(e)
        if t in ("version", "comment"):
            return
        if t == "include":
            f = text(e.find(S + "literal")).strip("\"'")
            if f == "stdgates.inc":
                self.gates.update(STDGATES)
            else:
                p = self.path.parent / f
                if not p.exists():
                    raise Qasm3Error(f"{self.path}:{ln}: include file {f!r} not found")
                for st in unit_elements(p.read_text(errors="replace")):
                    if tag(st) == "gate":
                        self.gate_def(st)
            return
        if t == "decl_stmt":
            return self.decl(e.find(S + "decl"), ln)
        if t == "gate":
            return self.gate_def(e)
        if t == "measure":
            q_el = e.find(S + "expr")
            target = e.findall(S + "expr")[1] if len(e.findall(S + "expr")) > 1 else None
            if target is None:
                self.note(ln, "measure without a target: the outcome is discarded")
                qs, unk = self.qubits(q_el)
                for qb in qs:
                    self.emit("measure", [qb], ln, may=unk)
                return
            self.measure(q_el, self.bits_of(target), ln)
            return
        if t == "reset":
            qs, unk = self.qubits(e.find(S + "expr"))
            for qb in qs:
                self.emit("reset", [qb], ln, may=unk)
            return
        if t == "barrier":
            al = e.find(S + "argument_list")
            if al is None:
                qs = [frozenset([i]) for i in range(self.nq)]
            else:
                qs = [s for a in al.findall(S + "argument") for s in self.qubits(a.find(S + "expr"))[0]]
            self.emit("barrier", qs, ln)
            return
        if t == "expr_stmt":
            return self.expr_stmt(e, ln)
        if t == "if_stmt":
            return self.if_stmt(e, ln)
        if t == "for":
            return self.for_stmt(e, ln)
        if t == "while":
            return self.while_stmt(e, ln)
        if t == "switch":
            return self.switch_stmt(e, ln)
        if t == "block":
            return self.block(e)
        if t == "break":
            raise _Break()
        if t == "continue":
            raise _Continue()
        if t == "end":
            raise _Stop()
        if t == "unsupported":
            if e.get("kind") == "def":
                m = re.match(r"\s*def\s+([A-Za-z_]\w*)", text(e))
                if m:
                    self.subs[m.group(1)] = ln
                    self.note(ln, f"def {m.group(1)}: outside the subset; a call is one operation on its qubit arguments")
                    return
            self.note(ln, f"{e.get('kind')}: outside the OpenQASM 3 subset, not read")
            return
        raise Qasm3Error(f"{self.path}:{ln}: <{t}> is not read")

    def decl(self, d, ln):
        typ = text(d.find(S + "type")).strip()
        names = d.findall(S + "name")
        nm = names[-1] if names else None
        inner = nm.find(S + "name") if nm is not None else None
        name = text(inner if inner is not None else nm).strip()
        kind = typ.split("[")[0].strip()
        size = 1
        ix = nm.find(S + "index") if inner is not None else None
        if ix is None:
            ix = d.find(f"{S}type/{S}index")
        if ix is not None and kind in ("qubit", "qreg", "bit", "creg"):
            v = self.ev(list(ix)[0]).v
            if not isinstance(v, int):
                raise Qasm3Error(f"{self.path}:{ln}: the size of {name!r} must be known")
            size = v
        if name in self.q or name in self.c:
            raise Qasm3Error(f"{self.path}:{ln}: {name!r} declared twice")
        if name in self.vars:
            self.note(ln, f"{name!r} declared again: the new declaration is read")
            del self.vars[name]
        if kind in ("qubit", "qreg"):
            self.q[name] = (self.nq, size, ln)
            self.nq += size
            return
        init = d.find(S + "init")
        if kind in ("bit", "creg"):
            self.c[name] = (self.nc, size, ln)
            self.nc += size
            if init is not None:
                val = list(init)[0]
                if tag(val) == "measure":
                    self.measure(val.find(S + "expr"), [frozenset(range(self.nc - size, self.nc))], ln)
            return
        spec = d.find(S + "specifier")
        if spec is not None and text(spec).strip() == "input":
            self.vars[name] = V(UNK)
            self.note(ln, f"input {name!r}: unknown until run time")
            return
        if init is None:
            self.vars[name] = V(0 if kind in ("int", "uint", "bool", "angle", "float") else UNK)
            return
        val = list(init)[0]
        if tag(val) == "measure":
            bits = self.measure_into_var(val, ln)
            self.vars[name] = V(UNK, bits)
            return
        self.vars[name] = self.ev(val)

    def measure_into_var(self, m, ln) -> FrozenSet[int]:
        """`int x = measure q;` measures into an anonymous result; its bits are fresh, beyond the declared ones."""
        qs, unk = self.qubits(m.find(S + "expr"))
        bits = []
        for qb in qs:
            b = self.nc
            self.nc += 1
            self.emit("measure", [qb], ln, clbits=(frozenset([b]),), may=unk)
            bits.append(b)
        return frozenset(bits)

    def gate_def(self, g):
        name = text(g.find(S + "name")).strip()
        lists = g.findall(S + "parameter_list")
        params = [l for l in lists if l.get("type") != "quantum"]
        qargs = [l for l in lists if l.get("type") == "quantum"][0]
        if name in self.user:
            raise Qasm3Error(f"{self.path}:{line(g)}: gate {name!r} defined twice")
        self.gates[name] = (len(params[0].findall(S + "parameter")) if params else 0, len(qargs.findall(S + "parameter")))
        self.user.add(name)

    def expr_stmt(self, e, ln):
        ex = e.find(S + "expr")
        kids = list(ex)
        if len(kids) == 1 and tag(kids[0]) == "call" and (kids[0].find(S + "argument_list[@type='quantum']") is not None
                                                          or kids[0].find(S + "specifier") is not None
                                                          or text(kids[0].find(S + "name")).strip() == "gphase"):
            return self.gate_call(kids[0], ln)
        if len(kids) == 3 and tag(kids[1]) == "operator":
            lhs, op, rhs = kids
            target = text(lhs).strip()
            reg = target.split("[")[0].strip()
            if tag(rhs) == "measure":
                if reg in self.c:
                    self.measure(rhs.find(S + "expr"), self.bits_of(lhs), ln)
                    return
                bits = self.measure_into_var(rhs, ln)
                self.vars[reg] = V(UNK, bits)
                return
            val = self.ev(rhs)
            if reg in self.c:
                return                                       # a bit assigned a classical value: no operation
            old = self.vars.get(reg, V(UNK))
            o = text(op).strip()
            if "[" in target:
                self.vars[reg] = V(UNK, old.bits | val.bits)
            elif o == "=":
                self.vars[reg] = val if not any(k == "may" for k, _ in self.ctx) else V(UNK, val.bits | old.bits)
            else:
                self.vars[reg] = V(UNK, old.bits | val.bits)
            return
        self.note(ln, "expression statement: evaluated for its value only")

    # ------------------------------------------------------------------ control flow
    def _cond(self, el) -> V:
        return self.ev(el.find(f"{S}condition/{S}expr"))

    def _under(self, kind, x, f):
        self.ctx.append((kind, x))
        try:
            f()
        finally:
            self.ctx.pop()

    def if_stmt(self, e, ln):
        iff = e.find(S + "if")
        c = self._cond(iff)
        then = iff.find(S + "block")
        els = e.find(f"{S}else/{S}block")
        if c.v is not UNK and not c.bits:
            if c.v:
                self.block(then)
            elif els is not None:
                self.block(els)
            return
        kind, x = ("cond", c.bits) if c.bits else ("may", None)
        if not c.bits:
            self.note(ln, "if with an unknown condition: every branch read, as may-operations")
        self._under(kind, x, lambda: self.block(then))
        if els is not None:
            self._under(kind, x, lambda: self.block(els))

    def loop_values(self, rng) -> Optional[List[Any]]:
        inner = list(rng)
        if inner and tag(inner[0]) == "index":
            src = text(list(inner[0])[0])
            parts = [self.ev(ET.fromstring(f'<expr xmlns="{NS}">{x}</expr>')).v if x.strip() else None
                     for x in _split_colon(src)]
            if len(parts) < 2 or any(not isinstance(p, int) for p in parts):
                return None
            a, b, st = (parts[0], parts[1], 1) if len(parts) == 2 else (parts[0], parts[2], parts[1])
            if st == 0:
                return None
            return list(range(a, b + (1 if st > 0 else -1), st))
        if inner and inner[0].get("type") == "set":
            vals = [self.ev(x).v for x in inner[0]]
            return None if any(v is UNK for v in vals) else vals
        return None

    def for_stmt(self, e, ln):
        ctl = e.find(S + "control")
        var = text(ctl.find(S + "name")).strip()
        vals = self.loop_values(ctl.find(S + "range"))
        body = e.find(S + "block")
        saved = self.vars.get(var)
        if vals is None or len(vals) > MAX_ITER:
            self.vars[var] = V(UNK)
            self.unknown_loop(ln, "for", lambda: self.block(body))
        else:
            for i, v in enumerate(vals):
                self.vars[var] = V(v)
                try:
                    self._under("for", (ln, i), lambda: self.block(body))
                except _Break:
                    break
                except _Continue:
                    continue
        if saved is None:
            self.vars.pop(var, None)
        else:
            self.vars[var] = saved

    def while_stmt(self, e, ln):
        body = e.find(S + "block")
        c = self._cond(e)
        if c.v is not UNK and not c.bits:
            n = 0
            while True:
                c = self._cond(e)
                if c.v is UNK or c.bits:
                    break
                if not c.v:
                    return
                n += 1
                if n > MAX_ITER:
                    self.note(ln, "while loop stopped at the iteration limit")
                    return
                try:
                    self._under("for", (ln, n - 1), lambda: self.block(body))
                except _Break:
                    return
                except _Continue:
                    continue
        if c.bits:
            self._under("cond", c.bits, lambda: self.unknown_loop(ln, "while", lambda: self.block(body)))
        else:
            self.unknown_loop(ln, "while", lambda: self.block(body))

    def unknown_loop(self, ln, kind, body_once):
        """As tool.interp's unknown_loop: len(touched) + 1 copies of the body (at least two), as may-operations."""
        self.note(ln, f"{kind} with an unknown iteration count: body repeated to cover every dependence chain, as "
                      f"may-operations")
        i, touched, need = 0, set(), 2
        saved = dict(self.vars)
        while i < need and i < MAX_COPIES:
            before = len(self.ops)
            self.ctx.append(("may", None))
            try:
                body_once()
            except (_Break, _Continue):
                pass
            finally:
                self.ctx.pop()
            for op in self.ops[before:]:
                touched |= {q for s in op.qubits for q in s}
                touched |= {("c", b) for s in op.clbits for b in s} | {("c", b) for b in op.cond}
            need = max(2, len(touched) + 1)
            i += 1
        if need > MAX_COPIES:
            self.note(ln, "loop copies capped: dependences through more iterations are not traced")
        for k, v in list(self.vars.items()):
            old = saved.get(k)
            if old is None or old.v != v.v:
                self.vars[k] = V(UNK, v.bits | (old.bits if old else E))

    def switch_stmt(self, e, ln):
        target = self._cond(e)
        cases = list(e.find(f"{S}block/{S}block_content"))
        if target.v is not UNK and not target.bits:
            for cs in cases:
                if tag(cs) == "case" and any(self.ev(v).v == target.v for v in cs.find(S + "expr")):
                    return self.block(cs.find(S + "block"))
            for cs in cases:
                if tag(cs) == "default":
                    return self.block(cs.find(S + "block"))
            return
        kind, x = ("cond", target.bits) if target.bits else ("may", None)
        for cs in cases:
            if tag(cs) in ("case", "default"):
                self._under(kind, x, lambda cs=cs: self.block(cs.find(S + "block")))

    def run(self):
        try:
            for st in unit_elements(self.path.read_text(errors="replace")):
                self.stmt(st)
        except _Stop:
            pass
        return self.ops


def _split_colon(src: str) -> List[str]:
    """`a:b:c` into its parts, at the colons outside brackets."""
    out, depth, cur = [], 0, ""
    for ch in src:
        depth += ch in "([{"
        depth -= ch in ")]}"
        if ch == ":" and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def ops(path) -> List[Op]:
    return _Layer(Path(path)).run()


def read(path) -> Trace:
    path = Path(path)
    lay = _Layer(path)
    lay.run()
    uid = 0
    qregs = [Reg("q", k, v[1], (uid := uid + 1)) for k, v in sorted(lay.q.items(), key=lambda kv: kv[1][0])]
    cregs = [Reg("c", k, v[1], (uid := uid + 1)) for k, v in sorted(lay.c.items(), key=lambda kv: kv[1][0])]
    circ = Circuit(0, 1, qregs, cregs, lay.ops, path.stem, frozenset(v[2] for v in list(lay.q.values()) + list(lay.c.values())))
    return Trace(str(path), [circ], lay.notes)
