"""Classical lines of a slice from srcSlice (Deviation I-20).

srcSlice reads the program's srcML and prints one slice profile per variable: its definition and use lines, the
variables that depend on it (dvars), its aliases, and the functions it is passed to with the argument position
(cfuncs). srcSlice knows nothing of qubits, so the quantum lines come from the QDG on the operation trace
(tool.slicer); this module adds the classical lines that compute them.

For a set of quantum lines, the start lines are those lines and the headers of the loops, conditions and with
blocks that enclose them. A profile is seeded when its use set holds a start line. The closure adds a profile's
definition lines, every profile whose dvars hold its name (in the same function or global), and, for a parameter at
position k of f, every profile whose cfuncs hold f{k}. The classical lines are the closure's lines minus the
quantum lines.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, Set, Tuple

from tool import srcml as X

SRCSLICE = "srcslice"
ROW = re.compile(r"^(?P<file>[^,]*),(?P<fn>[^,]*),(?P<var>[^,]*),def\{(?P<defs>[^}]*)\},use\{(?P<uses>[^}]*)\},"
                 r"dvars\{(?P<dvars>[^}]*)\},pointers\{(?P<ptrs>[^}]*)\},cfuncs\{(?P<cfuncs>.*)\}$")
CFUNC = re.compile(r"([^,{}]+)\{(\d+)\}")
HEADERS = {"for", "while", "if", "elseif", "else", "with", "if_stmt"}


@dataclass(frozen=True)
class Profile:
    fn: str                        # enclosing function, or GLOBAL
    var: str
    defs: FrozenSet[int]
    uses: FrozenSet[int]
    dvars: FrozenSet[str]
    ptrs: FrozenSet[str]
    cfuncs: FrozenSet[Tuple[str, int]]


def _ints(s: str) -> FrozenSet[int]:
    return frozenset(int(x) for x in s.split(",") if x.strip().isdigit())


def _names(s: str) -> FrozenSet[str]:
    return frozenset(x.strip() for x in s.split(",") if x.strip())


def profiles(path: Path) -> Tuple[List[Profile], float]:
    """srcSlice's profiles of one Python file, and srcSlice's time in seconds (srcML included)."""
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as d:
        xml = Path(d) / "unit.xml"
        r = subprocess.run(["srcml", "--src-encoding=UTF-8", "--position", "-l", "Python", str(path), "-o", str(xml)], capture_output=True,
                           text=True)
        if r.returncode != 0:
            raise X.SrcMLError(r.stderr.strip()[:300])
        out = subprocess.run([SRCSLICE, str(xml)], capture_output=True, text=True, timeout=120).stdout
    took = time.perf_counter() - t0
    rows = []
    for ln in out.splitlines():
        m = ROW.match(ln.strip())
        if not m:
            continue
        rows.append(Profile(m["fn"], m["var"], _ints(m["defs"]), _ints(m["uses"]), _names(m["dvars"]),
                            _names(m["ptrs"]), frozenset((f.strip(), int(k)) for f, k in CFUNC.findall(m["cfuncs"]))))
    return rows, took


def structure(root: ET.Element):
    """Per line, the header lines of the blocks that enclose it; per function, its header line and parameters."""
    parent = {c: p for p in root.iter() for c in p}
    enclosing: Dict[int, Set[int]] = {}
    for e in root.iter():
        L = X.line(e) if e.get("{%s}start" % X.POS) else None
        if L is None or L in enclosing:
            continue
        hs, p = set(), parent.get(e)
        while p is not None:
            if X.tag(p) in HEADERS and p.get("{%s}start" % X.POS):
                h = X.line(p)
                if h != L:
                    hs.add(h)
            p = parent.get(p)
        enclosing[L] = hs
    params: Dict[str, Tuple[int, List[str]]] = {}
    for f in root.iter(X.S + "function"):
        name = f.find(X.S + "name")
        plist = f.find(X.S + "parameter_list")
        if name is None or plist is None:
            continue
        ps = []
        for p in plist.findall(X.S + "parameter"):
            n = p.find(".//" + X.S + "name")
            ps.append(X.text(n).strip() if n is not None else "")
        if ps and ps[0] in ("self", "cls"):
            ps = ps[1:]
        params[X.text(name).strip()] = (X.line(f), ps)
    return enclosing, params


def classical_lines(path: Path, quantum_lines: Iterable[int], prof: List[Profile] = None,
                    root: ET.Element = None) -> Set[int]:
    quantum = set(quantum_lines)
    if prof is None:
        prof, _ = profiles(path)
    if root is None:
        root = X.parse_file(path)
    enclosing, params = structure(root)
    start = set(quantum)
    for L in quantum:
        start |= enclosing.get(L, set())
    by_name: Dict[str, List[Profile]] = {}
    for p in prof:
        by_name.setdefault(p.var, []).append(p)
    todo = [p for p in prof if p.uses & start]
    seen: Set[Profile] = set()
    lines: Set[int] = start - quantum  # the headers of the blocks that enclose a quantum line
    while todo:
        p = todo.pop()
        if p in seen:
            continue
        seen.add(p)
        lines |= p.defs
        for q in prof:  # profiles this one depends on: q's dvars hold p's name
            if p.var in q.dvars and (q.fn == p.fn or q.fn == "GLOBAL"):
                todo.append(q)
        if p.fn in params:  # a parameter: the arguments passed at its position
            hdr, ps = params[p.fn]
            if p.var in ps:
                k = ps.index(p.var) + 1
                todo.extend(q for q in prof if (p.fn, k) in q.cfuncs)
        for L in p.defs:  # the headers enclosing a definition, and what they use
            for h in enclosing.get(L, set()) - lines:
                lines.add(h)
                todo.extend(q for q in prof if h in q.uses)
    return lines - quantum
