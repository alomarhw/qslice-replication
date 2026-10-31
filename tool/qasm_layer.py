"""The quantum layer over the srcML of an OpenQASM 2 program (tool.qasm_srcml).

The layer reads the markup statement by statement, as it reads the srcML of a Qiskit program, and builds the same
operation trace that tool.interp builds, so E3 to E5 apply unchanged.

    srcML element                       what the layer does                                         extension
    <include>                           qelib1.inc: the standard gates' roles, read from the       E1
                                        markup of qelib1.inc itself; another file: its gate and
                                        opaque definitions, read from its own markup
    <decl_stmt> qreg / creg             allocates qubits or bits; the declaration is a classical    E2, E4
                                        line of every operation on the register
    <gate>, <gate_decl>                 a role-table entry: parameter count, qubit count; the       E1, E4
                                        definition is a classical line of every application
    <expr_stmt><call>                   one operation per qubit tuple, broadcast over registers     E1, E2
                                        as the specification defines; U and CX are the built-ins
    <measure>, <reset>, <barrier>       writes the bits, resets the qubits, never sliced            E2
    <if_stmt>                           conditions the operation on every bit of the register       E2, E3
    pos:start                           the line of every operation                                 E2

The rules the specification states beyond its grammar are checked, and a violation raises QasmSemanticError:
declared names, register bounds, gate arity and parameter count, equal sizes in a broadcast, distinct qubits in one
application, gates defined before use and not recursive, and unindexed qubit arguments in a gate body.

    read(path) -> Trace         the Op-based trace of tool.interp
    ops(path) -> iterator       (name, qubits, measured bit or -1, condition bits, line, classical lines) per operation
    arg_texts(path) -> dict     line -> qubit-argument texts per application, the names of a qubit profile (E5)
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from tool.interp import Circuit, Op, Reg, Trace
from tool.qasm_srcml import NS, POS, unit_elements

S = "{%s}" % NS
QELIB = Path(__file__).resolve().parent / "data" / "qelib1.inc"
# Instructions Qiskit's loader adds to qelib1.inc as built-ins (qiskit.qasm2.LEGACY_CUSTOM_INSTRUCTIONS), with their
# parameter and qubit counts, for programs written against Qiskit's qelib1.inc.
LEGACY = {"u0": (1, 1), "u": (3, 1), "p": (1, 1), "sx": (0, 1), "sxdg": (0, 1), "swap": (0, 2), "cswap": (0, 3),
          "crx": (1, 2), "cry": (1, 2), "cp": (1, 2), "csx": (0, 2), "cu": (4, 2), "rxx": (1, 2), "rzz": (1, 2),
          "rccx": (0, 3), "rc3x": (0, 4), "c3x": (0, 4), "c3sqrtx": (0, 4), "c4x": (0, 5), "delay": (1, 1)}
BUILTIN = {"U": ("u", 3, 1), "CX": ("cx", 0, 2)}
CONTROLS = {"cx": 1, "cy": 1, "cz": 1, "ch": 1, "crx": 1, "cry": 1, "crz": 1, "cu1": 1, "cu3": 1, "cu": 1,
            "cp": 1, "csx": 1, "cswap": 1, "ccx": 2, "c3x": 3, "c3sqrtx": 3, "c4x": 4, "rccx": 2, "rc3x": 3}


class QasmSemanticError(Exception):
    pass


def tag(e) -> str:
    return e.tag.replace(S, "")


def text(e) -> str:
    return "".join(e.itertext())


def line(e) -> int:
    return int(e.get("{%s}start" % POS).split(":")[0])


def statements(path: Path) -> Iterator[ET.Element]:
    """The top-level statement elements of the program's srcML, parsed one at a time."""
    yield from unit_elements(path.read_text(errors="replace"))


@lru_cache(maxsize=None)
def _definitions(path: str) -> Dict[str, Tuple[int, int, Tuple[int, int]]]:
    """name -> (parameter count, qubit count, (first line, last line)) for the gate and opaque definitions of an
    include file, read from its own markup."""
    out = {}
    for e in statements(Path(path)):
        if tag(e) in ("gate", "gate_decl"):
            name, np_, nq = _signature(e)
            out[name] = (np_, nq, (line(e), int(e.get("{%s}end" % POS).split(":")[0])))
    return out


def _signature(e) -> Tuple[str, int, int]:
    name = text(e.find(S + "name")).strip()
    lists = e.findall(S + "parameter_list")
    params = [p for p in lists if p.get("type") != "quantum"]
    qargs = [p for p in lists if p.get("type") == "quantum"][0]
    return name, (len(params[0].findall(S + "parameter")) if params else 0), len(qargs.findall(S + "parameter"))


class _Layer:
    def __init__(self, path: Path):
        self.path = path
        self.q: Dict[str, Tuple[int, int, int]] = {}    # register -> (offset, size, declaration line)
        self.c: Dict[str, Tuple[int, int, int]] = {}
        self.nq = self.nc = 0
        self.gates: Dict[str, Tuple[int, int, Tuple[int, ...]]] = {}   # name -> (params, qubits, classical lines)
        self.user: set = set()
        self.args: Dict[int, List[List[str]]] = {}

    def err(self, e, msg):
        raise QasmSemanticError(f"{self.path}:{line(e)}: {msg}")

    # -- E1: the role table
    def include(self, e):
        f = text(e.find(S + "literal")).strip('"')
        ln = line(e)
        if f == "qelib1.inc":
            for name, (np_, nq, _) in _definitions(str(QELIB)).items():
                self.gates[name] = (np_, nq, (ln,))
            for name, (np_, nq) in LEGACY.items():
                self.gates.setdefault(name, (np_, nq, (ln,)))
            return
        p = (self.path.parent / f)
        if not p.exists():
            self.err(e, f"include file {f!r} not found")
        for name, (np_, nq, _) in _definitions(str(p.resolve())).items():
            self.gates[name] = (np_, nq, (ln,))

    def gate(self, e):
        name, np_, nq = _signature(e)
        if name in self.user:
            self.err(e, f"gate {name!r} defined twice")
        qnames = [text(p).strip() for p in [l for l in e.findall(S + "parameter_list") if l.get("type") == "quantum"][0]]
        if len(set(qnames)) != len(qnames):
            self.err(e, f"gate {name!r} repeats a qubit argument")
        blk = e.find(S + "block")
        if blk is not None:
            for st in blk.find(S + "block_content"):
                if tag(st) == "comment":
                    continue
                for nm in st.iter(S + "name"):
                    if nm.find(S + "index") is not None:
                        self.err(st, "a qubit argument cannot be indexed inside a gate body")
                if tag(st) == "expr_stmt":
                    callee = text(st.find(f"{S}expr/{S}call/{S}name")).strip()
                    if callee == name:
                        self.err(st, f"gate {name!r} cannot call itself")
                    if callee not in self.gates and callee not in BUILTIN:
                        self.err(st, f"gate {callee!r} used before its definition")
        end = int(e.get("{%s}end" % POS).split(":")[0])
        self.gates[name] = (np_, nq, tuple(range(line(e), end + 1)))
        self.user.add(name)

    # -- E2: registers and operations
    def decl(self, e):
        kind = text(e.find(f"{S}decl/{S}type")).strip()
        nm = e.find(f"{S}decl/{S}name")
        name = text(nm.find(S + "name")).strip()
        size = int(text(nm.find(f"{S}index/{S}expr")))
        if name in self.q or name in self.c:
            self.err(e, f"register {name!r} declared twice")
        if kind == "qreg":
            self.q[name] = (self.nq, size, line(e))
            self.nq += size
        else:
            self.c[name] = (self.nc, size, line(e))
            self.nc += size

    def bits(self, arg, regs, what) -> List[Tuple[int, int]]:
        """(global index, declaration line) for every qubit or bit an argument denotes."""
        nm = arg.find(f".//{S}name")
        inner = nm.find(S + "name")
        reg = text(inner if inner is not None else nm).strip()
        if reg not in regs:
            self.err(arg, f"{reg!r} is not a declared {what} register")
        off, size, ln = regs[reg]
        idx = nm.find(S + "index")
        if idx is not None:
            i = int(text(idx).strip("[] "))
            if i >= size:
                self.err(arg, f"index {i} is out of range for {reg}[{size}]")
            return [(off + i, ln)]
        return [(off + i, ln) for i in range(size)]

    def apply(self, e, cond, cdeps) -> Iterator[Tuple]:
        t = tag(e)
        ln = line(e)
        if t == "measure":
            qa, ca = (self.bits(x, r, w) for x, r, w in zip(e.findall(S + "expr"), (self.q, self.c), ("quantum", "classical")))
            if len(qa) != len(ca):
                self.err(e, "measure: the qubit and bit arguments differ in size")
            self.args.setdefault(ln, []).append([text(e.findall(S + "expr")[0]).strip()])
            for (qb, ql), (cb, cl) in zip(qa, ca):
                yield "measure", [qb], cb, cond, ln, frozenset(cdeps | {ql, cl})
            return
        if t == "reset":
            x = e.find(S + "expr")
            self.args.setdefault(ln, []).append([text(x).strip()])
            for qb, ql in self.bits(x, self.q, "quantum"):
                yield "reset", [qb], -1, cond, ln, frozenset(cdeps | {ql})
            return
        if t == "barrier":
            qs = sorted({b for a in e.find(S + "argument_list") for b, _ in self.bits(a, self.q, "quantum")})
            yield "barrier", qs, -1, [], ln, frozenset()
            return
        if t != "expr_stmt":
            self.err(e, f"<{t}> is not a quantum operation")
        call = e.find(f"{S}expr/{S}call")
        callee = text(call.find(S + "name")).strip()
        lists = call.findall(S + "argument_list")
        angles = [l for l in lists if l.get("type") != "quantum"]
        qlist = [l for l in lists if l.get("type") == "quantum"][0]
        if callee in BUILTIN:
            name, np_, nq = BUILTIN[callee]
            gdeps: Tuple[int, ...] = ()
        elif callee in self.gates:
            name = callee
            np_, nq, gdeps = self.gates[callee]
        else:
            self.err(e, f"gate {callee!r} is not defined")
        n_ang = len(angles[0].findall(S + "argument")) if angles else 0
        if n_ang != np_:
            self.err(e, f"{callee} takes {np_} parameters, {n_ang} given")
        args = qlist.findall(S + "argument")
        if len(args) != nq:
            self.err(e, f"{callee} acts on {nq} qubits, {len(args)} given")
        self.args.setdefault(ln, []).append([text(a).strip() for a in args])
        arg_bits = [self.bits(a, self.q, "quantum") for a in args]
        width = max(len(b) for b in arg_bits)
        if any(len(b) not in (1, width) for b in arg_bits):
            self.err(e, f"{callee}: registers of different sizes in one application")
        for i in range(width):
            qb, dl = [], set(cdeps) | set(gdeps)
            for b in arg_bits:
                g, l = b[i] if len(b) > 1 else b[0]
                qb.append(g)
                dl.add(l)
            if len(set(qb)) != len(qb):
                self.err(e, f"{callee} is applied to the same qubit twice")
            yield name, qb, -1, cond, ln, frozenset(dl)

    def run(self) -> Iterator[Tuple]:
        for e in statements(self.path):
            t = tag(e)
            if t in ("version", "comment", "empty_stmt"):
                continue
            if t == "include":
                self.include(e)
            elif t == "decl_stmt":
                self.decl(e)
            elif t in ("gate", "gate_decl"):
                self.gate(e)
            elif t == "if_stmt":
                c = e.find(f"{S}if/{S}condition/{S}expr")
                reg = text(c.find(S + "name")).strip()
                if reg not in self.c:
                    self.err(e, f"{reg!r} is not a declared classical register")
                off, size, dl = self.c[reg]
                inner = [x for x in e.find(f"{S}if/{S}block/{S}block_content") if tag(x) != "comment"][0]
                yield from self.apply(inner, list(range(off, off + size)), {dl, line(e)})
            else:
                yield from self.apply(e, [], set())


def ops(path) -> Iterator[Tuple]:
    yield from _Layer(Path(path)).run()


def read(path) -> Trace:
    path = Path(path)
    lay = _Layer(path)
    out: List[Op] = []
    for name, qb, mb, cond, ln, dl in lay.run():
        out.append(Op(name=name, qubits=tuple(frozenset([q]) for q in qb),
                      clbits=(frozenset([mb]),) if mb >= 0 else (), cond=frozenset(cond), line=ln, calls=(), iters=(),
                      deps=dl, nctrl=CONTROLS.get(name, 0) if name not in lay.user else 0))
    uid = 0
    qregs = [Reg("q", k, v[1], (uid := uid + 1)) for k, v in sorted(lay.q.items(), key=lambda kv: kv[1][0])]
    cregs = [Reg("c", k, v[1], (uid := uid + 1)) for k, v in sorted(lay.c.items(), key=lambda kv: kv[1][0])]
    circ = Circuit(0, 1, qregs, cregs, out, path.stem, frozenset(v[2] for v in list(lay.q.values()) + list(lay.c.values())))
    tr = Trace(str(path), [circ], [])
    tr.arg_texts = lay.args
    return tr


def arg_texts(path) -> Dict[int, List[List[str]]]:
    lay = _Layer(Path(path))
    for _ in lay.run():
        pass
    return lay.args
