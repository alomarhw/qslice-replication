"""OpenQASM 3 to srcML, following the markup Behler et al. specified for OpenQASM, for the subset slicing needs.

The grammar is the official one (data/openqasm3_grammar/qasm3Parser.g4). The front end parses the statements that
decide which operations act on which qubits under which conditions: declarations (qubit, bit, qreg/creg, classical
scalars, const, input/output), assignments, gate definitions, gate calls with the modifiers ctrl, negctrl, inv and
pow, gphase, measure in both forms, reset, barrier, if/else, for, while, break, continue, end, switch, and scopes. The
other statements of the grammar (def, return, let, delay, nop, extern, cal, defcal, defcalgrammar, pragma,
annotations) are marked up losslessly as <unsupported> elements that the quantum layer reports instead of reading.
Qiskit's exporter writes `for i in [a:b]` without the loop variable's type, which the grammar requires; it is accepted.

    statement                           element (Behler et al. where they define it)
    OPENQASM 3.0;  include "f";         <version>, <include>
    qubit[n] q;  bit[n] c;  int x = e;  <decl_stmt><decl><type>..</type> <name>..</name> [= <init>]</decl>
    x = e;  c[0] = measure q[0];        <expr_stmt><expr> .. </expr>; measure is <measure> inside it
    measure q -> c;                     <measure>
    ctrl @ g(..) a, b;                  <expr_stmt><expr><call> with <specifier> per modifier, <argument_list>,
                                        <argument_list type="quantum">
    gate g(p) a, b { .. }               <gate> with <parameter_list>, <parameter_list type="quantum">, <block>
    reset q;  barrier q;                <reset>, <barrier>
    if (e) s else s                     <if_stmt><if>if <condition>..</condition> <block>..</block></if>
                                        <else>else <block>..</block></else></if_stmt>
    for [t] i in r s                    <for>for <control>.. <range>in ..</range></control> <block>
    while (e) s                         <while>while <condition>..</condition> <block>
    switch (e) { case 1, 2 {..} .. }    <switch>switch <condition>..</condition> <block> <case>, <default>
    break; continue; end;               <break>, <continue>, <end>
    // ..  /* .. */                     <comment type="line"> / <comment type="block">

Parsing errors raise QasmSyntaxError with the line and column; nothing is guessed.
"""

from __future__ import annotations

import re
from collections import deque
from typing import Iterator, List, Optional

from tool.qasm_srcml import NS, POS, Node, QasmSyntaxError, Tok, _Pos, _build, _emit, _gap, _lc  # noqa: F401

_TOKEN = re.compile((r"""
    (?P<ws>[ \t\r\n]+)
  | (?P<comment>//[^\n]*|/\*.*?\*/)
  | (?P<timing>(?:<<F>>|<<D>>)[ \t]*(?:dt|ns|us|µs|ms|s)(?![A-Za-z0-9_]))
  | (?P<real>(?:<<F>>|<<D>>)[ \t]*im(?![A-Za-z0-9_])|<<F>>)
  | (?P<int>0[bB][01](?:_?[01])*|0[oO][0-7](?:_?[0-7])*|0[xX][0-9a-fA-F](?:_?[0-9a-fA-F])*|<<D>>)(?![A-Za-z0-9_])
  | (?P<string>"[^"\n]*"|'[^'\n]*')
  | (?P<hw>\$[0-9]+)
  | (?P<id>[A-Za-z_\u0080-\uffff][A-Za-z0-9_\u0080-\uffff]*)
  | (?P<id2>\#[A-Za-z]+)
  | (?P<op>->|\+\+|\*\*|<<=|>>=|<<|>>|<=|>=|==|!=|&&|\|\||[+\-*/%&|^]=|[;,()\[\]{}+\-*/%^&|~!<>=:@])
""".replace("<<F>>", r"(?:(?:[0-9](?:_?[0-9])*\.(?:[0-9](?:_?[0-9])*)?|\.[0-9](?:_?[0-9])*)(?:[eE][-+]?[0-9](?:_?[0-9])*)?"
                    r"|[0-9](?:_?[0-9])*[eE][-+]?[0-9](?:_?[0-9])*)")
     .replace("<<D>>", r"[0-9](?:_?[0-9])*")), re.X | re.S)

SCALAR = {"bit", "int", "uint", "float", "angle", "bool", "duration", "stretch", "complex"}
MODIFIERS = {"ctrl", "negctrl", "inv", "pow"}
UNSUPPORTED = {"def", "return", "let", "delay", "nop", "extern", "cal", "defcal", "defcalgrammar", "pragma",
               "#pragma"}
KEYWORDS = {"OPENQASM", "include", "qubit", "qreg", "creg", "const", "input", "output", "gate", "measure", "reset",
            "barrier", "if", "else", "for", "in", "while", "break", "continue", "end", "switch", "case", "default",
            "gphase"} | SCALAR | MODIFIERS | UNSUPPORTED
# binary operators by precedence, lowest first (qasm3Parser.g4, `expression`)
BINARY = [("||",), ("&&",), ("|",), ("^",), ("&",), ("==", "!="), ("<", "<=", ">", ">="), ("<<", ">>"),
          ("+", "-"), ("*", "/", "%")]
ASSIGN = {"=", "+=", "-=", "*=", "/=", "&=", "|=", "^=", "<<=", ">>=", "%="}


def _lexer(text: str, i: int = 0) -> Iterator[Tok]:
    while i < len(text):
        m = _TOKEN.match(text, i)
        if not m:
            raise QasmSyntaxError(f"{_lc(text, i)}: unexpected character {text[i]!r}")
        k = "id" if m.lastgroup == "id2" else m.lastgroup
        yield Tok(k, m.group(), i, m.end())
        i = m.end()


def _raw_block_end(text: str, i: int) -> int:
    """The offset just after the brace that closes a calibration block opened before offset i."""
    depth = 1
    while i < len(text):
        depth += text[i] == "{"
        depth -= text[i] == "}"
        i += 1
        if depth == 0:
            return i
    raise QasmSyntaxError(f"{_lc(text, i)}: calibration block is not closed")


class _Parser:
    def __init__(self, text: str):
        self.text = text
        self._lex = _lexer(text)
        self.buf = deque()
        self.comments: List[Tok] = []
        self.last_end = 0

    # -- tokens
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

    def at(self, *texts, d=0) -> bool:
        t = self.peek(d)
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

    def ident(self) -> Tok:
        t = self.peek()
        if t is None or t.kind != "id" or t.text in KEYWORDS - {"measure"} and t.text not in ("gphase",):
            raise QasmSyntaxError(f"{_lc(self.text, t.start if t else len(self.text))}: identifier expected, "
                                  f"found {t.text if t else 'end of file'!r}")
        return self.take()

    def leaf(self, tag, t, attrs=()):
        return Node(tag, t.start, t.end, attrs)

    # -- program
    def program(self) -> Iterator[Node]:
        if self.at("OPENQASM"):
            a = self.take()
            v = self.take()
            if not v.text.startswith("3"):
                raise QasmSyntaxError(f"{_lc(self.text, v.start)}: OpenQASM {v.text} is not OpenQASM 3")
            e = self.take(";")
            yield Node("version", a.start, e.end, (), [self.leaf("literal", v, (("type", "number"),))])
        while self.peek() is not None:
            yield self.statement()

    def statement(self) -> Node:
        t = self.peek()
        x = t.text
        if x == "OPENQASM":
            raise QasmSyntaxError(f"{_lc(self.text, t.start)}: the version statement may appear only first")
        if x == "{":
            return self.scope("block")
        if x == ";":
            raise QasmSyntaxError(f"{_lc(self.text, t.start)}: OpenQASM 3 has no empty statement")
        if x == "include":
            a = self.take()
            f = self.take(kind="string")
            e = self.take(";")
            return Node("include", a.start, e.end, (), [self.leaf("literal", f, (("type", "string"),))])
        if x in ("qubit", "qreg", "creg") or x in ("const", "input", "output") or \
                ((x in SCALAR or x == "array") and not self._is_cast()):
            return self.decl()
        if x == "gate":
            return self.gate()
        if x == "box":                                  # a timed scope: its statements are read in place
            a = self.take()
            kids = [self.designator()] if self.at("[") else []
            kids.append(self.scope())
            return Node("box", a.start, kids[-1].end, (), kids)
        if x == "if":
            return self.if_stmt()
        if x == "for":
            return self.for_stmt()
        if x == "while":
            return self.while_stmt()
        if x == "switch":
            return self.switch_stmt()
        if x in ("break", "continue", "end"):
            a = self.take()
            e = self.take(";")
            return Node(x, a.start, e.end)
        if x == "measure":
            return self.measure_stmt()
        if x == "reset":
            a = self.take()
            q = self.operand()
            e = self.take(";")
            return Node("reset", a.start, e.end, (), [q])
        if x == "barrier":
            a = self.take()
            kids = [self.operand_list()] if not self.at(";") else []
            e = self.take(";")
            return Node("barrier", a.start, e.end, (), kids)
        if x in UNSUPPORTED or x.startswith("@") or (x == "#" ):
            return self.unsupported()
        if t.kind == "op" and t.text == "@":
            return self.unsupported()
        if x in MODIFIERS or x == "gphase" or self._is_gate_call():
            return self.gate_call()
        return self.expr_stmt()

    def _is_cast(self) -> bool:
        """`int(x)` and `float[32](x)` start an expression, not a declaration."""
        if self.at("(", d=1):
            return True
        if self.at("[", d=1):
            depth, d = 0, 1
            while True:
                t = self.peek(d)
                if t is None:
                    return False
                depth += t.text == "["
                depth -= t.text == "]"
                d += 1
                if depth == 0:
                    return self.at("(", d=d)
        return False

    def _is_gate_call(self) -> bool:
        """An identifier followed by operands (an identifier or $n), possibly after (params) and [designator]."""
        if self.peek().kind != "id":
            return False
        d = 1
        for opener, closer in (("(", ")"), ("[", "]")):
            if self.at(opener, d=d):
                depth = 0
                while True:
                    t = self.peek(d)
                    if t is None:
                        return False
                    depth += t.text == opener
                    depth -= t.text == closer
                    d += 1
                    if depth == 0:
                        break
        t = self.peek(d)
        return t is not None and (t.kind == "hw" or (t.kind == "id" and t.text not in KEYWORDS))

    def scope(self, tag="block") -> Node:
        lb = self.take("{")
        kids = []
        while not self.at("}"):
            if self.peek() is None:
                raise QasmSyntaxError(f"{_lc(self.text, lb.start)}: scope is not closed")
            kids.append(self.statement())
        rb = self.take("}")
        return Node(tag, lb.start, rb.end, (), [Node("block_content", lb.end, rb.start, (), kids)])

    def body(self) -> Node:
        """A statement or a scope, as a block (a pseudo block for a single statement, as srcML marks it up)."""
        if self.at("{"):
            return self.scope()
        s = self.statement()
        return Node("block", s.start, s.end, (("type", "pseudo"),), [Node("block_content", s.start, s.end, (), [s])])

    # -- declarations and assignments
    def designator(self) -> Node:
        lb = self.take("[")
        e = self.expression()
        rb = self.take("]")
        return Node("index", lb.start, rb.end, (), [e])

    def type_(self) -> Node:
        t = self.take()
        if t.text not in SCALAR and t.text not in ("qubit", "array"):
            raise QasmSyntaxError(f"{_lc(self.text, t.start)}: type expected, found {t.text!r}")
        kids = [self.leaf("name", t)]
        if t.text == "array":
            lb = self.take("[")
            inner = [self.type_()]
            while self.at(","):
                self.take(",")
                if self.at("]"):
                    break
                inner.append(self.expression())
            rb = self.take("]")
            kids.append(Node("index", lb.start, rb.end, (), inner))
            return Node("type", t.start, rb.end, (), kids)
        if t.text == "bool" and self.at("["):
            raise QasmSyntaxError(f"{_lc(self.text, self.peek().start)}: bool takes no designator")
        if t.text == "complex" and self.at("["):
            if self.peek(1) is None or self.peek(1).text not in SCALAR:
                raise QasmSyntaxError(f"{_lc(self.text, self.peek().start)}: complex[...] takes a scalar type")
            lb = self.take("[")
            inner = self.type_()
            rb = self.take("]")
            kids.append(Node("index", lb.start, rb.end, (), [inner]))
        elif self.at("["):
            kids.append(self.designator())
        return Node("type", t.start, kids[-1].end, (), kids)

    def decl(self) -> Node:
        start = self.peek().start
        specs = []
        spec = None
        if self.at("const", "input", "output"):
            s = self.take()
            spec = s.text
            specs.append(self.leaf("specifier", s))
            if self.at("const", "input", "output", "qreg", "creg", "qubit"):
                raise QasmSyntaxError(f"{_lc(self.text, self.peek().start)}: {self.peek().text!r} cannot follow {spec!r}")
        if self.at("qreg", "creg"):
            kw = self.take()
            n = self.ident()
            kids = [Node("type", kw.start, kw.end, (), [self.leaf("name", kw)])]
            if self.at("["):
                ix = self.designator()
                kids.append(Node("name", n.start, ix.end, (), [self.leaf("name", n), ix]))
            else:
                kids.append(self.leaf("name", n))
            e = self.take(";")
            return Node("decl_stmt", start, e.end, (), [Node("decl", start, kids[-1].end, (), kids)])
        typ = self.type_()
        n = self.ident()
        kids = specs + [typ, self.leaf("name", n)]
        if self.at("=") and spec in ("input", "output"):
            raise QasmSyntaxError(f"{_lc(self.text, self.peek().start)}: an {spec} declaration takes no value")
        if self.at("="):
            eq = self.take("=")
            val = self.measure_expr() if self.at("measure") else self.array_literal() if self.at("{") else self.expression()
            kids.append(Node("init", eq.start, val.end, (), [val]))
        elif spec == "const":
            raise QasmSyntaxError(f"{_lc(self.text, n.end)}: a const declaration needs a value")
        e = self.take(";")
        return Node("decl_stmt", start, e.end, (), [Node("decl", start, kids[-1].end, (), kids)])

    def expr_stmt(self) -> Node:
        lhs = self.expression()
        t = self.peek()
        if t is not None and t.text in ASSIGN:
            op = self.take()
            rhs = self.measure_expr() if self.at("measure") else self.array_literal() if self.at("{") else self.expression()
            e = self.take(";")
            ex = Node("expr", lhs.start, rhs.end, (), [lhs, self.leaf("operator", op), rhs])
            return Node("expr_stmt", lhs.start, e.end, (), [ex])
        e = self.take(";")
        return Node("expr_stmt", lhs.start, e.end, (), [lhs])

    def measure_expr(self) -> Node:
        a = self.take("measure")
        q = self.operand()
        return Node("measure", a.start, q.end, (), [q])

    def measure_stmt(self) -> Node:
        m = self.measure_expr()
        kids = [m]
        if self.at("->"):
            ar = self.take("->")
            kids += [self.leaf("operator", ar), self.operand()]
        e = self.take(";")
        return Node("measure", m.start, e.end, (), m.children + kids[1:]) if len(kids) > 1 else \
            Node("measure", m.start, e.end, (), m.children)

    # -- gates
    def idlist(self, quantum: bool, paren: bool) -> Node:
        start = self.peek().start
        kids = []
        if paren:
            self.take("(")
            if self.at(")"):
                end = self.take(")").end
                return Node("parameter_list", start, end, (), [])
        while True:
            t = self.ident()
            kids.append(Node("parameter", t.start, t.end, (), [self.leaf("name", t)]))
            if not self.at(","):
                break
            self.take(",")
            if (paren and self.at(")")) or (not paren and (self.peek() is None or self.peek().kind != "id")):
                break
        end = self.take(")").end if paren else kids[-1].end
        return Node("parameter_list", start, end, (("type", "quantum"),) if quantum else (), kids)

    def gate(self) -> Node:
        a = self.take("gate")
        n = self.ident()
        kids = [self.leaf("name", n)]
        if self.at("("):
            kids.append(self.idlist(False, True))
        kids.append(self.idlist(True, False))
        kids.append(self.scope())
        return Node("gate", a.start, kids[-1].end, (), kids)

    def gate_call(self) -> Node:
        start = self.peek().start
        kids = []
        while self.at(*MODIFIERS):
            m = self.take()
            mk = [self.leaf("name", m)]
            if m.text == "pow" and not self.at("("):
                raise QasmSyntaxError(f"{_lc(self.text, m.end)}: pow needs an argument")
            if m.text == "inv" and self.at("("):
                raise QasmSyntaxError(f"{_lc(self.text, m.end)}: inv takes no argument")
            if self.at("("):
                lp = self.take("(")
                e = self.expression()
                rp = self.take(")")
                mk.append(Node("argument_list", lp.start, rp.end, (), [Node("argument", e.start, e.end, (), [e])]))
            at = self.take("@")
            kids.append(Node("specifier", m.start, at.end, (), mk))
        n = self.take(kind="id")
        kids.append(self.leaf("name", n))
        if self.at("("):
            kids.append(self.explist())
        if self.at("["):
            kids.append(self.designator())
        if not self.at(";"):
            kids.append(self.operand_list())
        e = self.take(";")
        call = Node("call", start, kids[-1].end, (), kids)
        return Node("expr_stmt", start, e.end, (), [Node("expr", start, call.end, (), [call])])

    def operand(self) -> Node:
        t = self.peek()
        if t is not None and t.kind == "hw":
            self.take()
            lit = self.leaf("literal", t, (("type", "qubit"),))
            return Node("expr", t.start, t.end, (), [lit])
        n = self.ident()
        nm = self.leaf("name", n)
        idx = []
        while self.at("["):
            idx.append(self.index())
        if idx:
            nm = Node("name", n.start, idx[-1].end, (), [nm] + idx)
        return Node("expr", nm.start, nm.end, (), [nm])

    def operand_list(self) -> Node:
        kids = []
        while True:
            e = self.operand()
            kids.append(Node("argument", e.start, e.end, (), [e]))
            if not self.at(","):
                break
            self.take(",")
            t = self.peek()
            if t is None or (t.kind not in ("id", "hw")):
                break
        return Node("argument_list", kids[0].start, kids[-1].end, (("type", "quantum"),), kids)

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

    # -- control flow
    def condition(self) -> Node:
        lp = self.take("(")
        e = self.expression()
        rp = self.take(")")
        return Node("condition", lp.start, rp.end, (), [e])

    def if_stmt(self) -> Node:
        a = self.take("if")
        c = self.condition()
        b = self.body()
        kids = [Node("if", a.start, b.end, (), [c, b])]
        if self.at("else"):
            el = self.take("else")
            eb = self.body()
            kids.append(Node("else", el.start, eb.end, (), [eb]))
        return Node("if_stmt", a.start, kids[-1].end, (), kids)

    def for_stmt(self) -> Node:
        a = self.take("for")
        ctl = []
        if self.peek() is not None and self.peek().text in SCALAR:
            ctl.append(self.type_())
        v = self.ident()
        ctl.append(self.leaf("name", v))
        kw = self.take("in")
        if self.at("["):
            lb = self.take("[")
            r = self.range_expr()
            rb = self.take("]")
            rng = Node("range", kw.start, rb.end, (), [Node("index", lb.start, rb.end, (), [r])])
        elif self.at("{"):
            s = self.set_expr()
            rng = Node("range", kw.start, s.end, (), [s])
        else:
            e = self.expression()
            rng = Node("range", kw.start, e.end, (), [e])
        ctl.append(rng)
        control = Node("control", ctl[0].start, rng.end, (), ctl)
        b = self.body()
        return Node("for", a.start, b.end, (), [control, b])

    def while_stmt(self) -> Node:
        a = self.take("while")
        c = self.condition()
        b = self.body()
        return Node("while", a.start, b.end, (), [c, b])

    def switch_stmt(self) -> Node:
        a = self.take("switch")
        c = self.condition()
        lb = self.take("{")
        cases = []
        while not self.at("}"):
            if self.at("case"):
                k = self.take("case")
                vals = [self.expression()]
                while self.at(","):
                    self.take(",")
                    if self.at("{"):
                        break
                    vals.append(self.expression())
                expr = Node("expr", vals[0].start, vals[-1].end, (), vals)
                s = self.scope()
                cases.append(Node("case", k.start, s.end, (), [expr, s]))
            elif self.at("default"):
                k = self.take("default")
                s = self.scope()
                cases.append(Node("default", k.start, s.end, (), [s]))
            else:
                t = self.peek()
                raise QasmSyntaxError(f"{_lc(self.text, t.start if t else len(self.text))}: 'case' or 'default' expected")
        rb = self.take("}")
        blk = Node("block", lb.start, rb.end, (), [Node("block_content", lb.end, rb.start, (), cases)])
        return Node("switch", a.start, rb.end, (), [c, blk])

    def unsupported(self) -> Node:
        """A statement outside the subset: kept whole, with its kind, up to its ';' or its closing brace."""
        t = self.peek()
        start, depth = t.start, 0
        kind = t.text.lstrip("#@") or "annotation"
        while True:
            u = self.peek()
            if u is None:
                raise QasmSyntaxError(f"{_lc(self.text, start)}: statement is not closed")
            self.take()
            if u.text == "{" and kind in ("cal", "defcal") and depth == 0:
                close = _raw_block_end(self.text, u.end)   # calibration code is raw text (CalibrationBlock)
                self.buf.clear()
                self._lex = _lexer(self.text, close)
                self.last_end = close
                break
            if u.text == "{":
                depth += 1
            elif u.text == "}":
                depth -= 1
                # a scope ends the statement (box, def, cal, defcal); braces inside an expression do not
                if depth == 0 and not self.at("else", ";", "]", ")", ",", "+", "-", "*", "/", "**", "]", "%"):
                    break
            elif u.text == ";" and depth == 0:
                break
            if kind in ("pragma", "annotation") and self._line_end(u):
                break
        return Node("unsupported", start, self.last_end, (("kind", kind),))

    def _line_end(self, u: Tok) -> bool:
        nxt = self.peek()
        return nxt is None or "\n" in self.text[u.end:nxt.start]

    # -- expressions
    def range_expr(self) -> Node:
        start = self.peek().start
        kids = []
        if not self.at(":"):
            kids.append(self.expression())
        while self.at(":"):
            kids.append(self.leaf("operator", self.take(":")))
            if not self.at(":", "]", ","):
                kids.append(self.expression())
        return Node("expr", start, self.last_end, (), kids)

    def array_literal(self) -> Node:
        lb = self.take("{")
        kids = []
        while not self.at("}"):
            kids.append(self.array_literal() if self.at("{") else self.expression())
            if self.at(","):
                self.take(",")
            elif not self.at("}"):
                t = self.peek()
                raise QasmSyntaxError(f"{_lc(self.text, t.start if t else len(self.text))}: ',' or '}}' expected")
        rb = self.take("}")
        return Node("expr", lb.start, rb.end, (("type", "array"),), kids)

    def set_expr(self) -> Node:
        lb = self.take("{")
        kids = []
        while not self.at("}"):
            kids.append(self.expression())
            if self.at(","):
                self.take(",")
        rb = self.take("}")
        return Node("expr", lb.start, rb.end, (("type", "set"),), kids)

    def index(self) -> Node:
        lb = self.take("[")
        kids = []
        if self.at("{"):
            kids.append(self.set_expr())
        else:
            while not self.at("]"):
                kids.append(self.range_expr())
                if self.at(","):
                    self.take(",")
        rb = self.take("]")
        return Node("index", lb.start, rb.end, (), kids)

    def expression(self) -> Node:
        start = self.peek().start if self.peek() else len(self.text)
        out: List[Node] = []
        self._binary(0, out)
        return Node("expr", start, self.last_end, (), out)

    def _binary(self, level, out):
        if level == len(BINARY):
            self._unary(out)
            return
        self._binary(level + 1, out)
        while self.peek() is not None and self.peek().text in BINARY[level]:
            out.append(self.leaf("operator", self.take()))
            self._binary(level + 1, out)

    def _unary(self, out):
        if self.at("-", "~", "!"):
            out.append(self.leaf("operator", self.take()))
            self._unary(out)
            return
        self._power(out)

    def _power(self, out):
        self._postfix(out)
        if self.at("**"):
            out.append(self.leaf("operator", self.take()))
            self._unary(out)

    def _postfix(self, out):
        self._atom(out)
        while self.at("["):
            ix = self.index()
            last = out.pop()
            out.append(Node("name", last.start, ix.end, (), [last, ix]))

    def _atom(self, out):
        t = self.peek()
        if t is None:
            raise QasmSyntaxError(f"{_lc(self.text, len(self.text))}: expression expected")
        if t.kind in ("real", "int", "timing"):
            out.append(self.leaf("literal", self.take(), (("type", "number"),)))
        elif t.kind == "string":
            out.append(self.leaf("literal", self.take(), (("type", "bitstring"),)))
        elif t.kind == "hw":
            out.append(self.leaf("literal", self.take(), (("type", "qubit"),)))
        elif t.text in ("true", "false"):
            out.append(self.leaf("literal", self.take(), (("type", "boolean"),)))
        elif t.text == "(":
            self.take("(")
            self._binary(0, out)
            self.take(")")
        elif t.kind == "id" and (t.text in SCALAR) and (self.at("(", d=1) or self.at("[", d=1)):
            ty = self.type_()
            lp = self.take("(")
            inner: List[Node] = []
            s = self.peek().start
            self._binary(0, inner)
            rp = self.take(")")
            out.append(Node("call", ty.start, rp.end, (), [ty, Node("argument_list", lp.start, rp.end, (), [
                Node("argument", s, self.toks_end(), (), [Node("expr", s, self.toks_end(), (), inner)])])]))
        elif t.text == "durationof" and self.at("(", d=1):
            n = self.take()
            lp = self.take("(")
            sc = self.scope()
            rp = self.take(")")
            out.append(Node("call", n.start, rp.end, (), [self.leaf("name", n), Node("argument_list", lp.start, rp.end, (), [
                Node("argument", sc.start, sc.end, (), [sc])])]))
        elif t.kind == "id" and self.at("(", d=1):
            n = self.take()
            al = self.explist()
            out.append(Node("call", n.start, al.end, (), [self.leaf("name", n), al]))
        elif t.kind == "id" and t.text not in KEYWORDS - {"pi"}:
            out.append(self.leaf("name", self.take()))
        else:
            raise QasmSyntaxError(f"{_lc(self.text, t.start)}: unexpected {t.text!r} in an expression")

    def toks_end(self) -> int:
        return self.last_end


# -- emission, as the OpenQASM 2 front end

def unit_parts(text: str, filename: str = "") -> Iterator[str]:
    from xml.sax.saxutils import quoteattr
    p = _Parser(text)
    pos = _Pos(text)
    yield ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           f'<unit xmlns="{NS}" xmlns:pos="{POS}" revision="1.1.0" language="OpenQASM" '
           f'filename={quoteattr(filename)} pos:tabs="8">')
    cur = 0
    for s in p.program():
        p.peek()
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


def unit_elements(text: str) -> Iterator:
    p = _Parser(text)
    pos = _Pos(text)
    for s in p.program():
        p.peek()
        mine = [c for c in p.comments if c.start < s.end]
        p.comments = [c for c in p.comments if c.start >= s.end]
        yield _build(text, s, pos, [c for c in mine if c.start >= s.start])
