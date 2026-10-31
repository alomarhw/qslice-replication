"""OpenQASM 2 to srcML, following the markup Behler et al. specified for OpenQASM.

srcML 1.1 has no OpenQASM language, and Behler et al. specified a srcML markup for OpenQASM 3 (QCE 2024) without
releasing a parser; their analyses ran on files marked up by hand. This module produces that markup automatically for
OpenQASM 2, which OpenQASM 3 is backward compatible with, in srcML 1.1's own format: the srcML namespace, pos:start and
pos:end positions as `srcml --position` writes them, and every character of the source kept, so the markup converts
back to the exact file.

The grammar is Appendix A of Cross et al., Open Quantum Assembly Language (arXiv:1707.03429), with the relaxations
Qiskit's loader accepts by default: a missing version statement, empty statements, trailing commas in lists, and the
functions asin, acos and atan. Every statement form of the specification's Table 1 is covered.

    statement form                      element (Behler et al. where they define it)
    OPENQASM 2.0;                       <version>
    include "f";                        <include>, the file name a <literal type="string">
    qreg q[n]; creg c[n];               <decl_stmt><decl><type><name>qreg</name></type> <name><name>q</name><index>
    gate g(p) a,b { body }              <gate> with <parameter_list>, <parameter_list type="quantum">, <block>
    opaque g(p) a,b;                    <gate_decl>
    U(..) a;  CX a,b;  g(..) a,b;       <expr_stmt><expr><call> with <argument_list> and <argument_list type="quantum">
    measure a -> b;                     <measure>
    reset a;                            <reset>
    barrier a,b;                        <barrier> with <argument_list type="quantum">
    if(c==n) qop;                       <if_stmt><if>if <condition>(..)</condition> <block type="pseudo">
    // text                             <comment type="line">
    ;                                   <empty_stmt>

Parameter expressions are marked up as srcML marks up C expressions: one <expr> holding <literal>, <name>,
<operator> and <call> elements, parentheses kept as text. A program that does not follow the grammar raises
QasmSyntaxError with its line and column; nothing is guessed.

    to_srcml(text, filename) -> str            the whole unit
    unit_parts(text, filename) -> iterator      the unit's opening tag, then one string per top-level statement or
                                                gap, then its closing tag, for files too large to hold as one tree
"""

from __future__ import annotations

import bisect
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Tuple
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

NS = "http://www.srcML.org/srcML/src"
POS = "http://www.srcML.org/srcML/position"
FUNCS = {"sin", "cos", "tan", "exp", "ln", "sqrt", "asin", "acos", "atan"}

_TOKEN = re.compile(r"""
    (?P<ws>[ \t\r\n]+)
  | (?P<comment>//[^\n]*)
  | (?P<real>(?:[0-9]+\.[0-9]*|[0-9]*\.[0-9]+)(?:[eE][-+]?[0-9]+)?|[0-9]+[eE][-+]?[0-9]+)
  | (?P<int>[0-9]+)
  | (?P<string>"[^"\n]*")
  | (?P<id>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>->|==|[;,()\[\]{}+\-*/^])
""", re.X)


class QasmSyntaxError(Exception):
    pass


@dataclass
class Tok:
    kind: str
    text: str
    start: int
    end: int          # exclusive


@dataclass
class Node:
    tag: str
    start: int
    end: int          # exclusive
    attrs: Tuple[Tuple[str, str], ...] = ()
    children: List["Node"] = field(default_factory=list)


def _lexer(text: str) -> Iterator[Tok]:
    i = 0
    while i < len(text):
        m = _TOKEN.match(text, i)
        if not m:
            raise QasmSyntaxError(f"{_lc(text, i)}: unexpected character {text[i]!r}")
        yield Tok(m.lastgroup, m.group(), i, m.end())
        i = m.end()


def _lc(text: str, off: int) -> str:
    line = text.count("\n", 0, off) + 1
    return f"line {line}, column {off - (text.rfind(chr(10), 0, off) + 1) + 1}"


class _Parser:
    """Recursive descent over the significant tokens; nodes keep source offsets, so the markup is lossless."""

    def __init__(self, text: str):
        self.text = text
        self._lex = _lexer(text)
        self.buf = deque()                # significant tokens read ahead
        self.comments: List[Tok] = []     # comments lexed so far and not yet emitted
        self.last_end = 0

    # -- token access
    def peek(self, d=0) -> Optional[Tok]:
        while len(self.buf) <= d:
            t = next(self._lex, None)
            if t is None:
                return None
            if t.kind == "comment":
                self.comments.append(t)
            elif t.kind != "ws":
                self.buf.append(t)
        return self.buf[d]

    def at(self, *texts) -> bool:
        t = self.peek()
        return t is not None and t.text in texts

    def take(self, text=None, kind=None) -> Tok:
        t = self.peek()
        if t is None:
            raise QasmSyntaxError(f"{_lc(self.text, len(self.text))}: unexpected end of file"
                                  + (f", expected {text or kind!r}" if text or kind else ""))
        if (text is not None and t.text != text) or (kind is not None and t.kind != kind):
            raise QasmSyntaxError(f"{_lc(self.text, t.start)}: expected {text or kind!r}, found {t.text!r}")
        self.buf.popleft()
        self.last_end = t.end
        return t

    # -- leaves
    def name(self, t: Tok) -> Node:
        return Node("name", t.start, t.end)

    def literal(self, t: Tok, typ: str) -> Node:
        return Node("literal", t.start, t.end, (("type", typ),))

    def op(self, t: Tok) -> Node:
        return Node("operator", t.start, t.end)

    # -- program
    def program(self) -> Iterator[Node]:
        if self.at("OPENQASM"):
            yield self.version()
        while self.peek() is not None:
            yield self.statement(top=True)

    def version(self) -> Node:
        a = self.take("OPENQASM")
        v = self.peek()
        if v is None or v.kind not in ("real", "int"):
            raise QasmSyntaxError(f"{_lc(self.text, a.end)}: version number expected")
        self.take()
        if v.text not in ("2.0", "2"):
            raise QasmSyntaxError(f"{_lc(self.text, v.start)}: OpenQASM {v.text} is not OpenQASM 2")
        e = self.take(";")
        return Node("version", a.start, e.end, (), [self.literal(v, "number")])

    def statement(self, top=False) -> Node:
        t = self.peek()
        if t.text == ";":
            self.take()
            return Node("empty_stmt", t.start, t.end)
        if t.text == "OPENQASM":
            raise QasmSyntaxError(f"{_lc(self.text, t.start)}: the version statement may appear only first")
        if top and t.text == "include":
            return self.include()
        if top and t.text in ("qreg", "creg"):
            return self.decl()
        if top and t.text == "gate":
            return self.gate()
        if top and t.text == "opaque":
            return self.opaque()
        if top and t.text == "if":
            return self.if_stmt()
        if t.text == "barrier":
            return self.barrier()
        return self.qop()

    def include(self) -> Node:
        a = self.take("include")
        f = self.take(kind="string")
        e = self.take(";")
        return Node("include", a.start, e.end, (), [self.literal(f, "string")])

    def decl(self) -> Node:
        kw = self.take()
        n = self.take(kind="id")
        lb = self.take("[")
        size = self.take(kind="int")
        rb = self.take("]")
        e = self.take(";")
        index = Node("index", lb.start, rb.end, (), [Node("expr", size.start, size.end, (), [self.literal(size, "number")])])
        nm = Node("name", n.start, rb.end, (), [self.name(n), index])
        typ = Node("type", kw.start, kw.end, (), [self.name(kw)])
        d = Node("decl", kw.start, rb.end, (), [typ, nm])
        return Node("decl_stmt", kw.start, e.end, (), [d])

    def idlist(self, quantum: bool, opener: Optional[str] = None) -> Node:
        """A parameter list of identifiers: (a, b) for parameters, or a bare list for qubit arguments."""
        start = self.peek().start
        kids = []
        if opener:
            self.take("(")
            if self.at(")"):
                end = self.take(")").end
                return Node("parameter_list", start, end, (), [])
        while True:
            t = self.take(kind="id")
            kids.append(Node("parameter", t.start, t.end, (), [self.name(t)]))
            if not self.at(","):
                break
            self.take(",")
            if opener and self.at(")"):            # trailing comma, as Qiskit accepts
                break
            if not opener and self.peek() is not None and self.peek().kind != "id":
                break
        end = self.take(")").end if opener else kids[-1].end
        return Node("parameter_list", start, end, (("type", "quantum"),) if quantum else (), kids)

    def gate(self) -> Node:
        a = self.take("gate")
        n = self.take(kind="id")
        kids = [self.name(n)]
        if self.at("("):
            kids.append(self.idlist(False, "("))
        kids.append(self.idlist(True))
        lb = self.take("{")
        body = []
        while not self.at("}"):
            if self.peek() is None:
                raise QasmSyntaxError(f"{_lc(self.text, lb.start)}: gate body is not closed")
            body.append(self.barrier() if self.at("barrier") else self.uop())
        rb = self.take("}")
        bc = Node("block_content", lb.end, rb.start, (), body)
        kids.append(Node("block", lb.start, rb.end, (), [bc]))
        return Node("gate", a.start, rb.end, (), kids)

    def opaque(self) -> Node:
        a = self.take("opaque")
        n = self.take(kind="id")
        kids = [self.name(n)]
        if self.at("("):
            kids.append(self.idlist(False, "("))
        kids.append(self.idlist(True))
        e = self.take(";")
        return Node("gate_decl", a.start, e.end, (), kids)

    def if_stmt(self) -> Node:
        a = self.take("if")
        lp = self.take("(")
        c = self.take(kind="id")
        eq = self.take("==")
        v = self.take(kind="int")
        rp = self.take(")")
        cond = Node("condition", lp.start, rp.end, (), [
            Node("expr", c.start, v.end, (), [self.name(c), self.op(eq), self.literal(v, "number")])])
        q = self.qop()
        blk = Node("block", q.start, q.end, (("type", "pseudo"),), [Node("block_content", q.start, q.end, (), [q])])
        iff = Node("if", a.start, q.end, (), [cond, blk])
        return Node("if_stmt", a.start, q.end, (), [iff])

    def qop(self) -> Node:
        if self.at("measure"):
            a = self.take("measure")
            q = self.argument_expr()
            ar = self.take("->")
            c = self.argument_expr()
            e = self.take(";")
            return Node("measure", a.start, e.end, (), [q, self.op(ar), c])
        if self.at("reset"):
            a = self.take("reset")
            q = self.argument_expr()
            e = self.take(";")
            return Node("reset", a.start, e.end, (), [q])
        return self.uop()

    def barrier(self) -> Node:
        a = self.take("barrier")
        al = self.arglist()
        e = self.take(";")
        return Node("barrier", a.start, e.end, (), [al])

    def uop(self) -> Node:
        n = self.take(kind="id")
        if n.text in ("measure", "reset", "barrier", "if", "gate", "opaque", "qreg", "creg", "include"):
            raise QasmSyntaxError(f"{_lc(self.text, n.start)}: {n.text!r} cannot appear here")
        kids = [self.name(n)]
        if self.at("("):
            kids.append(self.explist())
        kids.append(self.arglist())
        e = self.take(";")
        call = Node("call", n.start, kids[-1].end, (), kids)
        return Node("expr_stmt", n.start, e.end, (), [Node("expr", n.start, call.end, (), [call])])

    # -- arguments
    def argument_expr(self) -> Node:
        n = self.take(kind="id")
        if self.at("["):
            lb = self.take("[")
            i = self.take(kind="int")
            rb = self.take("]")
            idx = Node("index", lb.start, rb.end, (), [Node("expr", i.start, i.end, (), [self.literal(i, "number")])])
            nm = Node("name", n.start, rb.end, (), [self.name(n), idx])
        else:
            nm = self.name(n)
        return Node("expr", nm.start, nm.end, (), [nm])

    def arglist(self) -> Node:
        """The qubit arguments of a gate or barrier: <argument_list type="quantum">."""
        first = self.peek()
        kids = []
        while True:
            e = self.argument_expr()
            kids.append(Node("argument", e.start, e.end, (), [e]))
            if not self.at(","):
                break
            self.take(",")
            if self.peek() is None or self.peek().kind != "id":   # trailing comma
                break
        if first is None:
            raise QasmSyntaxError("qubit argument expected")
        return Node("argument_list", kids[0].start, kids[-1].end, (("type", "quantum"),), kids)

    # -- parameter expressions
    def explist(self) -> Node:
        lp = self.take("(")
        kids = []
        while not self.at(")"):
            e = self.expression()
            kids.append(Node("argument", e.start, e.end, (), [e]))
            if self.at(","):
                self.take(",")
            elif not self.at(")"):
                t = self.peek()
                raise QasmSyntaxError(f"{_lc(self.text, t.start if t else len(self.text))}: ',' or ')' expected")
        rp = self.take(")")
        return Node("argument_list", lp.start, rp.end, (), kids)

    def expression(self) -> Node:
        leaves: List[Node] = []
        start = self.peek().start if self.peek() else len(self.text)
        self._sum(leaves)
        end = self.last_end
        return Node("expr", start, end, (), leaves)

    def _sum(self, out):
        self._product(out)
        while self.at("+", "-"):
            out.append(self.op(self.take()))
            self._product(out)

    def _product(self, out):
        self._unary(out)
        while self.at("*", "/"):
            out.append(self.op(self.take()))
            self._unary(out)

    def _unary(self, out):
        if self.at("-", "+"):
            out.append(self.op(self.take()))
            self._unary(out)
            return
        self._power(out)

    def _power(self, out):
        self._atom(out)
        if self.at("^"):
            out.append(self.op(self.take()))
            self._unary(out)                       # right associative

    def _atom(self, out):
        t = self.peek()
        if t is None:
            raise QasmSyntaxError(f"{_lc(self.text, len(self.text))}: expression expected")
        if t.kind in ("real", "int"):
            out.append(self.literal(self.take(), "number"))
        elif t.text == "(":
            self.take("(")
            self._sum(out)
            self.take(")")
        elif t.kind == "id" and t.text in FUNCS and self.peek(1) is not None and self.peek(1).text == "(":
            n = self.take()
            lp = self.take("(")
            inner: List[Node] = []
            s = self.peek().start if self.peek() else lp.end
            self._sum(inner)
            arg = Node("argument", s, self.last_end, (), [Node("expr", s, self.last_end, (), inner)])
            rp = self.take(")")
            out.append(Node("call", n.start, rp.end, (), [self.name(n), Node("argument_list", lp.start, rp.end, (), [arg])]))
        elif t.kind == "id":
            out.append(self.name(self.take()))
        else:
            raise QasmSyntaxError(f"{_lc(self.text, t.start)}: unexpected {t.text!r} in an expression")


# -- emission

class _Pos:
    def __init__(self, text: str):
        self.starts = [0] + [m.end() for m in re.finditer("\n", text)]
        self._i = 0

    def lc(self, off: int) -> str:
        i = self._i
        st = self.starts
        if not (st[i] <= off and (i + 1 == len(st) or off < st[i + 1])):
            i = self._i = bisect.bisect_right(st, off) - 1
        return f"{i + 1}:{off - st[i] + 1}"


def _emit(text: str, node: Node, pos: _Pos, comments: List[Tok], out: List[str]):
    attrs = "".join(f" {k}={quoteattr(v)}" for k, v in node.attrs)
    end = node.end - 1 if node.end > node.start else node.start
    out.append(f'<{node.tag}{attrs} pos:start="{pos.lc(node.start)}" pos:end="{pos.lc(end)}">')
    cur = node.start
    for c in node.children:
        _gap(text, cur, c.start, pos, comments, out)
        _emit(text, c, pos, comments, out)
        cur = c.end
    _gap(text, cur, node.end, pos, comments, out)
    out.append(f"</{node.tag}>")


def _esc(s: str) -> str:
    """XML-escaped text that survives an XML parser: a carriage return is a character reference, since parsers
    normalize line ends."""
    return escape(s).replace("\r", "&#13;")


def _gap(text: str, a: int, b: int, pos: _Pos, comments: List[Tok], out: List[str]):
    """Source text between elements, with any comment in it marked up."""
    for c in comments:
        if a <= c.start < b:
            out.append(_esc(text[a:c.start]))
            out.append(f'<comment type="line" pos:start="{pos.lc(c.start)}" pos:end="{pos.lc(c.end - 1)}">'
                       f"{_esc(c.text)}</comment>")
            a = c.end
    out.append(_esc(text[a:b]))


def unit_parts(text: str, filename: str = "") -> Iterator[str]:
    p = _Parser(text)
    pos = _Pos(text)
    yield ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           f'<unit xmlns="{NS}" xmlns:pos="{POS}" revision="1.1.0" language="OpenQASM" '
           f'filename={quoteattr(filename)} pos:tabs="8">')
    cur = 0
    for s in p.program():
        p.peek()                                   # lex past the statement, so its comments are queued
        mine = [c for c in p.comments if c.start < s.end]
        p.comments = [c for c in p.comments if c.start >= s.end]
        out: List[str] = []
        _gap(text, cur, s.start, pos, [c for c in mine if c.start < s.start], out)
        _emit(text, s, pos, [c for c in mine if c.start >= s.start], out)
        cur = s.end
        yield "".join(out)
    tail: List[str] = []
    _gap(text, cur, len(text), pos, p.comments, tail)
    yield "".join(tail) + "</unit>"


def to_srcml(text: str, filename: str = "") -> str:
    return "".join(unit_parts(text, filename))

# -- the same markup as an element tree, for the quantum layer: no XML text is written or parsed

_T = "{%s}" % NS
_PS, _PE = "{%s}start" % POS, "{%s}end" % POS


def _build(text: str, node: Node, pos: _Pos, comments: List[Tok]) -> ET.Element:
    e = ET.Element(_T + node.tag, dict(node.attrs))
    end = node.end - 1 if node.end > node.start else node.start
    e.set(_PS, pos.lc(node.start))
    e.set(_PE, pos.lc(end))
    last = None                                  # where the next gap text goes: e.text, or the tail of `last`
    cur = node.start

    def gap(a, b):
        nonlocal last
        if not comments:
            if a < b:
                _put(e, last, text[a:b])
            return
        for c in comments:
            if a <= c.start < b:
                _put(e, last, text[a:c.start])
                ce = ET.SubElement(e, _T + "comment", {"type": "line", _PS: pos.lc(c.start), _PE: pos.lc(c.end - 1)})
                ce.text = c.text
                last = ce
                a = c.end
        _put(e, last, text[a:b])

    for ch in node.children:
        gap(cur, ch.start)
        ce = _build(text, ch, pos, comments)
        e.append(ce)
        last = ce
        cur = ch.end
    gap(cur, node.end)
    return e


def _put(parent: ET.Element, last, s: str):
    if not s:
        return
    if last is None:
        parent.text = (parent.text or "") + s
    else:
        last.tail = (last.tail or "") + s


def unit_elements(text: str) -> Iterator[ET.Element]:
    """The top-level statement elements of the unit, built in memory: the tree unit_parts' text parses to, with the
    text between statements left out."""
    p = _Parser(text)
    pos = _Pos(text)
    for s in p.program():
        p.peek()
        mine = [c for c in p.comments if c.start < s.end]
        p.comments = [c for c in p.comments if c.start >= s.end]
        yield _build(text, s, pos, [c for c in mine if c.start >= s.start])

