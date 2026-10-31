"""OpenQASM 2 front end of srcSlice-Q (Deviation I-22): read() and compact() build the trace through srcML
(tool.qasm_srcml, Behler et al.'s markup) and the quantum layer over it (tool.qasm_layer). The line reader below is
kept as read_lines() and compact_lines(), the baseline the srcML front end is compared and timed against.

srcML 1.1 has no OpenQASM language, and the markup Behler et al. specified has no released parser, so OpenQASM 2
files are read here, statement by statement, into the operation trace that the Qiskit front end builds from srcML
(tool.interp). In OpenQASM the quantum roles of E1 are in the syntax and the execution order of E2 is the statement
order, so E3 to E5 apply unchanged. Every operation records the line its statement starts on, and its classical
lines are the lines that declare its registers.

Covered: OPENQASM/include headers, qreg/creg, gate and opaque definitions (a defined gate is one operation, as
qiskit.qasm2.load makes it), gate applications with register broadcast, measure, reset, barrier and if(c==n).

Two forms of the trace:
  read(path) -> Trace          the Op-based trace of tool.interp, for slicing, profiles and the command line;
  compact(path) -> Compact     flat arrays (operation kinds, qubits, bits, lines) for circuits with millions of
                               operations, sliced by tool.slicer.compact_slice and compact_all_qubits.
"""

from __future__ import annotations

import re
from array import array
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

from tool.interp import Circuit, Op, Reg, Trace

E = frozenset()
STMT_END = re.compile(r";")
DECL = re.compile(r"^(qreg|creg)\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]$")
COND = re.compile(r"^if\s*\(\s*([A-Za-z_]\w*)\s*==\s*(\d+)\s*\)\s*(.*)$", re.S)
MEAS = re.compile(r"^measure\s+(.+?)\s*->\s*(.+)$", re.S)
APP = re.compile(r"^([A-Za-z_]\w*)\s*(\((.*)\))?\s*(.*)$", re.S)
ARG = re.compile(r"^([A-Za-z_]\w*)\s*(\[\s*(\d+)\s*\])?$")
BUILTIN = {"U": "u", "CX": "cx"}
CONTROLS = {"cx": 1, "cy": 1, "cz": 1, "ch": 1, "crx": 1, "cry": 1, "crz": 1, "cu1": 1, "cu3": 1, "cu": 1,
            "cp": 1, "csx": 1, "cswap": 1, "ccx": 2, "c3x": 3, "c3sqrtx": 3, "c4x": 4, "rccx": 2, "rc3x": 3}


class QasmError(Exception):
    pass


def statements(text: str) -> Iterator[Tuple[int, str]]:
    """(line where the statement starts, statement text without ';') for every top-level statement; gate and
    opaque definitions are yielded whole, with their body."""
    text = re.sub(r"//[^\n]*", "", text)
    i, n, line = 0, len(text), 1
    while i < n:
        while i < n and text[i] in " \t\r\n":
            line += text[i] == "\n"
            i += 1
        if i >= n:
            break
        start_line = line
        if re.match(r"gate\s", text[i:i + 5]):
            j = text.find("}", i) + 1
            if j == 0:
                raise QasmError(f"line {start_line}: gate definition without a body")
        else:
            j = text.index(";", i) + 1
        stmt = text[i:j]
        line += stmt.count("\n")
        i = j
        yield start_line, stmt.rstrip(";").strip()


@dataclass
class Compact:
    """A trace as flat arrays. Operation k acts on qubits qs[qoff[k]:qoff[k+1]], measures into bit mbit[k] (-1 if
    none), is conditioned on bits cs[coff[k]:coff[k+1]], and starts on source line line[k]. kind[k] is 0 for a
    gate, 1 for a measurement, 2 for a reset and 3 for a barrier."""
    n_qubits: int
    n_bits: int
    kind: array = field(default_factory=lambda: array("b"))
    qoff: array = field(default_factory=lambda: array("q", [0]))
    qs: array = field(default_factory=lambda: array("i"))
    mbit: array = field(default_factory=lambda: array("i"))
    coff: array = field(default_factory=lambda: array("q", [0]))
    cs: array = field(default_factory=lambda: array("i"))
    line: array = field(default_factory=lambda: array("i"))
    names: List[str] = field(default_factory=list)
    name_of: array = field(default_factory=lambda: array("i"))

    def __len__(self):
        return len(self.kind)


class _Reader:
    def __init__(self, path: Path):
        self.path = path
        self.q: Dict[str, Tuple[int, int, int]] = {}   # register -> (offset, size, declaration line)
        self.c: Dict[str, Tuple[int, int, int]] = {}
        self.nq = self.nc = 0
        self.gates: Dict[str, int] = {}

    def bits(self, arg: str, regs) -> List[Tuple[int, int]]:
        """(global index, declaration line) for every bit an argument denotes: one, or a whole register."""
        m = ARG.match(arg.strip())
        if not m or m.group(1) not in regs:
            raise QasmError(f"{self.path}: unknown argument {arg!r}")
        off, size, ln = regs[m.group(1)]
        if m.group(3) is not None:
            return [(off + int(m.group(3)), ln)]
        return [(off + i, ln) for i in range(size)]

    def run(self) -> Iterator[Tuple]:
        """Yields (name, [qubits], measured bit or -1, [condition bits], line, declaration lines) per operation."""
        for ln, st in statements(self.path.read_text(errors="replace")):
            if not st or st.startswith("OPENQASM") or st.startswith("include"):
                continue
            gd = re.match(r"^(gate|opaque)\s+([A-Za-z_]\w*)", st)
            if gd:
                name = gd.group(2)
                self.gates[name] = ln
                continue
            m = DECL.match(st)
            if m:
                regs = self.q if m.group(1) == "qreg" else self.c
                size = int(m.group(3))
                if m.group(1) == "qreg":
                    regs[m.group(2)] = (self.nq, size, ln)
                    self.nq += size
                else:
                    regs[m.group(2)] = (self.nc, size, ln)
                    self.nc += size
                continue
            cond, deps0 = [], set()
            m = COND.match(st)
            if m:
                if m.group(1) not in self.c:
                    raise QasmError(f"{self.path}:{ln}: unknown register in condition")
                off, size, dl = self.c[m.group(1)]
                cond, st = list(range(off, off + size)), m.group(3).strip()
                deps0.add(dl)
            m = MEAS.match(st)
            if m:
                qa, ca = self.bits(m.group(1), self.q), self.bits(m.group(2), self.c)
                if len(qa) != len(ca):
                    raise QasmError(f"{self.path}:{ln}: measure sizes differ")
                for (qb, ql), (cb, cl) in zip(qa, ca):
                    yield "measure", [qb], cb, cond, ln, frozenset(deps0 | {ql, cl})
                continue
            m = APP.match(st)
            if not m:
                raise QasmError(f"{self.path}:{ln}: cannot read {st[:60]!r}")
            name = BUILTIN.get(m.group(1), m.group(1))
            args = [a for a in m.group(4).split(",") if a.strip()]
            if name == "barrier":
                qb = sorted({b for a in args for b, _ in self.bits(a, self.q)})
                yield "barrier", qb, -1, [], ln, frozenset()
                continue
            arg_bits = [self.bits(a, self.q) for a in args]
            width = max((len(b) for b in arg_bits), default=1)
            if any(len(b) not in (1, width) for b in arg_bits):
                raise QasmError(f"{self.path}:{ln}: broadcast sizes differ")
            for i in range(width):
                qb, dl = [], set(deps0)
                for b in arg_bits:
                    g, l = b[i] if len(b) > 1 else b[0]
                    qb.append(g)
                    dl.add(l)
                if name in self.gates:
                    dl.add(self.gates[name])
                yield name, qb, -1, cond, ln, frozenset(dl)


def openqasm_version(text: str) -> int:
    """3 for an OpenQASM 3 program: its version line says 3, or it has none and includes stdgates.inc or is not
    valid OpenQASM 2 (OpenQASM 3 reads every OpenQASM 2 program, so a file without a version line is read as
    OpenQASM 2 when it can be). 2 otherwise."""
    head = text[:2000]
    if re.search(r"OPENQASM\s+3", head) or re.search(r'include\s+"stdgates\.inc"', head):
        return 3
    if re.search(r"OPENQASM\s+2", head):
        return 2
    from tool.qasm_srcml import QasmSyntaxError, unit_elements  # noqa: PLC0415
    try:
        for _ in unit_elements(text):
            pass
        return 2
    except QasmSyntaxError:
        return 3


def read(path) -> Trace:
    """The trace, built by the quantum layer from the program's srcML (tool.qasm_srcml, tool.qasm_layer)."""
    from tool import qasm_layer  # noqa: PLC0415
    return qasm_layer.read(path)


def compact(path) -> Compact:
    """The compact trace, built by the quantum layer from the program's srcML, statement by statement."""
    from tool import qasm_layer  # noqa: PLC0415
    lay = qasm_layer._Layer(Path(path))
    return _compact(lay, ((n, qb, mb, cond, ln) for n, qb, mb, cond, ln, _ in lay.run()))


def read_lines(path) -> Trace:
    """The trace from the earlier line reader (_Reader), kept as a baseline for the srcML front end."""
    path = Path(path)
    r = _Reader(path)
    ops: List[Op] = []
    for name, qb, mb, cond, ln, dl in r.run():
        ops.append(Op(name=name, qubits=tuple(frozenset([q]) for q in qb),
                      clbits=(frozenset([mb]),) if mb >= 0 else (), cond=frozenset(cond), line=ln, calls=(), iters=(),
                      deps=dl, nctrl=CONTROLS.get(name, 0) if name not in r.gates else 0))
    uid = 0
    qregs = [Reg("q", k, v[1], (uid := uid + 1)) for k, v in sorted(r.q.items(), key=lambda kv: kv[1][0])]
    cregs = [Reg("c", k, v[1], (uid := uid + 1)) for k, v in sorted(r.c.items(), key=lambda kv: kv[1][0])]
    circ = Circuit(0, 1, qregs, cregs, ops, path.stem, frozenset(v[2] for v in list(r.q.values()) + list(r.c.values())))
    return Trace(str(path), [circ], [])


def compact_lines(path) -> Compact:
    """The compact trace from the earlier line reader, the baseline for timing the srcML front end."""
    r = _Reader(Path(path))
    return _compact(r, ((n, qb, mb, cond, ln) for n, qb, mb, cond, ln, _ in r.run()))


def _compact(r, it) -> Compact:
    kinds = {"measure": 1, "reset": 2, "barrier": 3}
    out = None
    names: Dict[str, int] = {}
    buf = []
    for row in it:
        buf.append(row)
        if len(buf) >= 65536:
            out = _flush(out, r, buf, names, kinds)
            buf = []
    out = _flush(out, r, buf, names, kinds)
    out.n_qubits, out.n_bits = r.nq, r.nc
    out.names = [k for k, _ in sorted(names.items(), key=lambda kv: kv[1])]
    return out


def _flush(out, r, buf, names, kinds):
    if out is None:
        out = Compact(r.nq, r.nc)
    for name, qb, mb, cond, ln in buf:
        out.kind.append(kinds.get(name, 0))
        out.qs.extend(qb)
        out.qoff.append(len(out.qs))
        out.mbit.append(mb)
        out.cs.extend(cond)
        out.coff.append(len(out.cs))
        out.line.append(ln)
        out.name_of.append(names.setdefault(name, len(names)))
    return out
