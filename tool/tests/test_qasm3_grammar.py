"""The OpenQASM 3 front end against the official grammar test suite (data/openqasm3_grammar/tests, read as data).

  reference  each case's source is marked up losslessly, and its top-level statements are, in order, those of the
             case's reference parse tree, statement for statement (a statement outside the subset is an
             <unsupported> element of that kind);
  invalid    each line of tests/invalid/statements/*.qasm is an invalid statement on its own: the front end rejects
             it, or, for a statement outside the subset, keeps it whole as <unsupported>, which the layer reports.
Usage (workspace root): python -m tool.tests.test_qasm3_grammar
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from tool.qasm3_srcml import to_srcml
from tool.qasm_srcml import QasmSyntaxError

ROOT = Path(__file__).resolve().parents[2] / "data" / "openqasm3_grammar" / "tests"
S = "{http://www.srcML.org/srcML/src}"
# grammar statement rule -> srcML element of the subset (None: outside the subset, an <unsupported> element)
RULE = {"whileStatement": "while", "forStatement": "for", "ifStatement": "if_stmt", "switchStatement": "switch",
        "gateCallStatement": "expr_stmt", "expressionStatement": "expr_stmt", "assignmentStatement": "expr_stmt",
        "classicalDeclarationStatement": "decl_stmt", "constDeclarationStatement": "decl_stmt",
        "ioDeclarationStatement": "decl_stmt", "oldStyleDeclarationStatement": "decl_stmt",
        "quantumDeclarationStatement": "decl_stmt", "gateStatement": "gate", "includeStatement": "include",
        "resetStatement": "reset", "barrierStatement": "barrier", "breakStatement": "break",
        "continueStatement": "continue", "endStatement": "end", "measureArrowAssignmentStatement": "measure",
        "version": "version", "scope": "block", "boxStatement": "box"}


def cases():
    for f in sorted(ROOT.glob("reference/**/*.yaml")):
        text = f.read_text()
        m = re.search(r"^source: \|\n((?:  .*\n|\n)*)", text, re.M)
        r = re.search(r"^reference: \|\n((?:  .*\n|\n)*)", text, re.M)
        if not m or not r:
            continue
        src = "".join(l[2:] if l.startswith("  ") else l for l in m.group(1).splitlines(True))
        yield f, src.rstrip("\n") + "\n", r.group(1)


def expected(tree: str):
    """The top-level statements of a reference parse tree: the version, then the rule under each `statementOrScope`
    of `program` (annotations, which precede a statement, are left out)."""
    out, lines = [], tree.splitlines()
    ind = lambda l: len(l) - len(l.lstrip())  # noqa: E731
    for i, l in enumerate(lines):
        if ind(l) == 4 and l.strip() == "version":
            out.append("version")
        if ind(l) != 4 or l.strip() != "statementOrScope":
            continue
        nxt = lines[i + 1]
        if nxt.strip() != "statement":
            out.append(nxt.strip())
            continue
        for m in lines[i + 2:]:
            if ind(m) <= ind(nxt):
                break
            if ind(m) == ind(nxt) + 2 and m.strip() != "annotation" and not m.strip().startswith("@"):
                out.append(m.strip())
                break
    return out


def got(src: str):
    root = ET.fromstring(to_srcml(src).encode())
    assert "".join(root.itertext()) == src, "markup is not lossless"
    return [(e.tag.replace(S, ""), e.get("kind")) for e in root
            if e.tag.replace(S, "") != "comment" and e.get("kind") != "annotation"]


def main():
    ok = bad = 0
    for f, src, tree in cases():
        exp = expected(tree)
        try:
            g = got(src)
            same = len(g) == len(exp) and all(RULE.get(e) == t or (RULE.get(e) is None and t == "unsupported")
                                              for e, (t, _) in zip(exp, g))
        except QasmSyntaxError as e:
            same, g = False, str(e)
        if same:
            ok += 1
        else:
            bad += 1
            print("REFERENCE MISMATCH", f.relative_to(ROOT), "| expected", exp, "| got", g)
    print(f"reference: {ok} of {ok + bad} cases match")
    rej = kept = acc = 0
    for f in sorted(ROOT.glob("invalid/statements/*.qasm")):
        for l in f.read_text().splitlines():
            if not l.strip() or l.strip().startswith("//"):
                continue
            try:
                g = got(l + "\n")
                if any(t == "unsupported" for t, _ in g):
                    kept += 1
                else:
                    acc += 1
                    print("ACCEPTED INVALID", f.name, "|", l)
            except QasmSyntaxError:
                rej += 1
            except Exception as e:                 # anything else is a bug
                acc += 1
                print("ERROR", f.name, "|", l, "|", type(e).__name__)
    print(f"invalid: {rej} rejected, {kept} kept whole as unsupported, {acc} accepted")


if __name__ == "__main__":
    main()
