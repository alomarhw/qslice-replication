# srcSlice as QSlice uses it

QSlice takes the classical lines of a slice from srcSlice (`tool/srcslice.py`, Deviation I-20 of
`experiments/PROTOCOL_ICPC.md`). It uses upstream srcSlice at commit `ce86ef8` with the patch in this
folder, `srcslice-python.diff`.

## What the patch changes

The accuracy fixes apply to every language srcSlice supports:
- call arguments are linked in `return` statements and in `if`, `while`, `for` and `switch` headers;
- each nested call gets its own argument counter;
- `sizeof`, `alignof`, `typeof` and `decltype` create no links;
- a member name after `.` or `->` is not matched to a local variable;
- a call site no longer overwrites a parameter's index;
- `return x;` no longer leaks into the next assignment;
- `int r = f(x)` makes `r` depend on `x`;
- a compound assignment also uses its left-hand side;
- names are printed on one line;
- `--help` and `--version` work.

It also adds Python support:
- keyword arguments;
- the `self` and `cls` offset;
- `for`, `with`, tuple and comprehension targets;
- annotations, decorators, nested scopes, lambdas and f-strings.

`tests/regression/run.sh` in the patched tree runs its regression suite.

## Build

```sh
git clone --recursive https://github.com/srcML/srcSlice.git
cd srcSlice
git checkout ce86ef8
git submodule update --init --recursive
git apply ../srcslice-python.diff   # this file
mkdir ../build && cd ../build
cmake ../srcSlice && make
```

Put the resulting `srcslice` on the `PATH`. srcML 1.1.0 must be installed.
