"""Steps 3 to 5 of the OpenQASM 2 front-end validation.

  grammar   one program per production of Appendix A of the specification (Cross et al., arXiv:1707.03429), each
            marked up losslessly and read by the layer into the circuit qiskit.qasm2.load builds;
  invalid   programs that break a rule of the grammar or of Section 2: the front end rejects each, as Qiskit's strict
            mode does;
  spec      the example programs of Section 3 of the specification (tool/tests/qasm2/spec_*.qasm);
  behler    the elements Behler et al. use in their hand-marked OpenQASM files (QStatic's examples) for the constructs
            OpenQASM 2 shares: include, register declaration, gate call, quantum argument list, gate definition.
Usage (workspace root): python -m tool.tests.test_qasm_srcml   (or with pytest)
"""
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import pytest
except ImportError:            # the runner at the bottom needs no pytest
    pytest = None
from qiskit import qasm2

from tool import qasm_layer
from tool.qasm_srcml import QasmSyntaxError, to_srcml, unit_elements
from tool.tests.check_qasm_layer import compare

HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'

VALID = {
    "version only": "OPENQASM 2.0;\n",
    "no version (Qiskit relaxation)": 'include "qelib1.inc";\nqreg q[1];\nh q[0];\n',
    "comment before version": "// header\nOPENQASM 2.0;\nqreg q[1];\n",
    "qreg creg": "OPENQASM 2.0;\nqreg q[2];\ncreg c[2];\n",
    "U builtin, expression": "OPENQASM 2.0;\nqreg q[1];\nU(pi/2, 0, -pi) q[0];\n",
    "CX builtin": "OPENQASM 2.0;\nqreg q[2];\nCX q[0],q[1];\n",
    "CX register broadcast": "OPENQASM 2.0;\nqreg a[2];\nqreg b[2];\nCX a,b;\n",
    "CX qubit to register": "OPENQASM 2.0;\nqreg a[1];\nqreg b[3];\nCX a[0],b;\n",
    "U on register": "OPENQASM 2.0;\nqreg q[3];\nU(0,0,0) q;\n",
    "qelib gate with params": HEAD + "qreg q[2];\ncu1(pi/4) q[0],q[1];\nu3(0.1,0.2,0.3) q[1];\n",
    "functions and power": HEAD + "qreg q[1];\nu1(sin(pi/4)^2 + cos(0.5) - sqrt(2)*exp(1)/ln(3) + tan(0.1)) q[0];\n",
    "scientific notation": HEAD + "qreg q[1];\nrz(1.5e-3) q[0];\nrz(.5E+2) q[0];\nrz(2.) q[0];\n",
    "unary minus nested": HEAD + "qreg q[1];\nrx(-(-pi)) q[0];\n",
    "gate with params": HEAD + "gate g(a,b) x,y\n{\n  u1(a) x;\n  cx x,y;\n  u1(-b/2) y;\n}\nqreg q[2];\ng(0.1,0.2) q[0],q[1];\n",
    "gate empty parens": HEAD + "gate g() x { h x; }\nqreg q[1];\ng() q[0];\ng q[0];\n",
    "empty gate body": HEAD + "gate id2 a { }\nqreg q[1];\nid2 q[0];\n",
    "gate calls gate": HEAD + "gate a1 x { h x; }\ngate a2 x,y { a1 x; cx x,y; a1 y; }\nqreg q[2];\na2 q[0],q[1];\n",
    "gate body barrier": HEAD + "gate g a,b { h a; barrier a,b; cx a,b; }\nqreg q[2];\ng q[0],q[1];\n",
    "user gate broadcast": HEAD + "gate g a,b { cx a,b; }\nqreg qa[1];\nqreg qb[3];\ng qa[0],qb;\n",
    "opaque": HEAD + "opaque o(t) a,b;\nqreg q[2];\n",
    "measure qubit": HEAD + "qreg q[1];\ncreg c[1];\nmeasure q[0] -> c[0];\n",
    "measure register": HEAD + "qreg q[3];\ncreg c[3];\nmeasure q -> c;\n",
    "reset": HEAD + "qreg q[2];\nreset q[0];\nreset q;\n",
    "barrier mixed": HEAD + "qreg q[2];\nqreg r[2];\nbarrier q,r[0];\n",
    "if gate": HEAD + "qreg q[1];\ncreg c[2];\nmeasure q[0] -> c[0];\nif(c==1) x q[0];\n",
    "if measure": HEAD + "qreg q[1];\ncreg c[1];\nif(c==0) measure q[0] -> c[0];\n",
    "if reset": HEAD + "qreg q[1];\ncreg c[1];\nif(c==1) reset q[0];\n",
    "if spaced": HEAD + "qreg q[1];\ncreg c[1];\nif ( c == 1 ) x q[0];\n",
    "several statements per line": HEAD + "qreg q[2]; creg c[2]; h q[0]; cx q[0],q[1]; measure q -> c;\n",
    "statement across lines": HEAD + "qreg q[2];\ncx\n  q[0],\n  q[1];\n",
    "trailing comments": HEAD + "qreg q[1]; // the register\nh q[0]; // a gate\n",
    "empty statements": HEAD + "qreg q[1];;\n;\nh q[0];\n",
    "trailing comma (Qiskit relaxation)": HEAD + "qreg q[2];\ncx q[0],q[1],;\n",
    "legacy qelib gate": HEAD + "qreg q[4];\nc3x q[0],q[1],q[2],q[3];\nrzz(0.3) q[0],q[1];\n",
    "no trailing newline": HEAD + "qreg q[1];\nh q[0];",
    "crlf line ends": "OPENQASM 2.0;\r\ninclude \"qelib1.inc\";\r\nqreg q[1];\r\nh q[0];\r\n",
}

INVALID = {
    "missing semicolon": HEAD + "qreg q[1]\nh q[0];\n",
    "undeclared register": HEAD + "qreg q[1];\nh r[0];\n",
    "index out of range": HEAD + "qreg q[2];\nh q[2];\n",
    "undefined gate": HEAD + "qreg q[1];\nfoo q[0];\n",
    "wrong arity": HEAD + "qreg q[2];\ncx q[0];\n",
    "wrong parameter count": HEAD + "qreg q[1];\nu1 q[0];\n",
    "same qubit twice": HEAD + "qreg q[2];\ncx q[0],q[0];\n",
    "broadcast sizes differ": HEAD + "qreg a[2];\nqreg b[3];\ncx a,b;\n",
    "measure sizes differ": HEAD + "qreg q[2];\ncreg c[3];\nmeasure q -> c;\n",
    "indexed argument in gate body": HEAD + "gate g a { h a[0]; }\nqreg q[1];\n",
    "gate calls itself": HEAD + "gate g a { g a; }\n",
    "gate used before definition": HEAD + "gate g a { k a; }\ngate k a { h a; }\n",
    "if on undeclared register": HEAD + "qreg q[1];\nif(d==1) x q[0];\n",
    "if around barrier": HEAD + "qreg q[1];\ncreg c[1];\nif(c==1) barrier q;\n",
    "measure in gate body": HEAD + "gate g a { measure a -> a; }\n",
    "declaration in gate body": HEAD + "gate g a { qreg r[1]; }\n",
    "version twice": "OPENQASM 2.0;\nOPENQASM 2.0;\n",
    "version 3": "OPENQASM 3.0;\nqubit q;\n",
    "unclosed gate": HEAD + "gate g a { h a;\n",
    "bad character": HEAD + "qreg q[1];\nh q[0] @;\n",
    "register declared twice": HEAD + "qreg q[1];\nqreg q[2];\n",
}

BAD = (QasmSyntaxError, qasm_layer.QasmSemanticError)


def _file(text: str) -> Path:
    d = Path(tempfile.mkdtemp())
    p = d / "t.qasm"
    p.write_bytes(text.encode())
    return p


def test_valid(name):
    text = VALID[name]
    root = ET.fromstring(to_srcml(text).encode())
    assert "".join(root.itertext()) == text, "markup is not lossless"
    ok, note = compare(_file(text))
    assert ok, note


def test_invalid(name):
    p = _file(INVALID[name])
    try:
        list(qasm_layer.ops(p))
    except BAD:
        pass
    else:
        raise AssertionError("the front end accepted it")
    try:
        qasm2.load(str(p), custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS, strict=True)
    except Exception:
        return
    raise AssertionError("Qiskit accepts it")


SPEC = sorted(Path(__file__).parent.joinpath("qasm2").glob("spec_*.qasm"))


def test_spec_examples(path):
    text = path.read_text()
    assert "".join(ET.fromstring(to_srcml(text).encode()).itertext()) == text
    ok, note = compare(path)
    assert ok, note


def _same(a, b):
    assert (a.tag, dict(a.attrib), a.text or "", a.tail or "") == (b.tag, dict(b.attrib), b.text or "", b.tail or ""), (a.tag, b.tag)
    assert len(a) == len(b)
    for x, y in zip(a, b):
        _same(x, y)


def test_tree_equals_text(text):
    """The element tree the layer reads is the tree the written srcML parses to, statement by statement (comments
    between statements belong to the unit and are not built)."""
    parsed = [e for e in ET.fromstring(to_srcml(text).encode()) if not e.tag.endswith("}comment")]
    built = list(unit_elements(text))
    assert len(parsed) == len(built)
    for a, b in zip(parsed, built):
        b.tail = a.tail                           # text between statements belongs to the unit, not the statement
        _same(a, b)


def test_behler_elements():
    """The markup of the constructs both languages share uses Behler et al.'s elements and attributes."""
    x = to_srcml(HEAD + "gate hadamard_cnot a, b {\n    h a;\n    cx a, b;\n}\nqreg q[2];\nx q[0];\n")
    S = "{http://www.srcML.org/srcML/src}"
    r = ET.fromstring(x.encode())
    assert r.find(S + "include/" + S + "literal").get("type") == "string"
    g = r.find(S + "gate")
    assert [p.get("type") for p in g.findall(S + "parameter_list")] == ["quantum"]
    assert g.find(S + "block/" + S + "block_content/" + S + "expr_stmt/" + S + "expr/" + S + "call") is not None
    d = r.find(S + "decl_stmt/" + S + "decl")
    assert d.find(S + "type/" + S + "name").text == "qreg"
    call = r.findall(S + "expr_stmt")[-1].find(S + "expr/" + S + "call")
    al = call.find(S + "argument_list")
    assert al.get("type") == "quantum"
    assert al.find(S + "argument/" + S + "expr/" + S + "name/" + S + "index/" + S + "expr/" + S + "literal").get("type") == "number"


if __name__ == "__main__":
    cases = [(f"valid: {n}", test_valid, n) for n in sorted(VALID)] + \
            [(f"invalid: {n}", test_invalid, n) for n in sorted(INVALID)] + \
            [(f"spec: {p.stem}", test_spec_examples, p) for p in SPEC] + [("behler elements", test_behler_elements, None)] + \
            [(f"tree = text: {n}", test_tree_equals_text, VALID[n]) for n in sorted(VALID)] + \
            [(f"tree = text: {p.stem}", test_tree_equals_text, p.read_text()) for p in SPEC]
    failed = 0
    for label, fn, arg in cases:
        try:
            fn(arg) if arg is not None else fn()
        except Exception as e:
            failed += 1
            print("FAIL", label, "|", type(e).__name__, str(e)[:160])
    print(f"{len(cases) - failed} of {len(cases)} passed")
