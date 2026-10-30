# Material moved from Paper A to Paper B

Paper A (RP #EA0C9, paper/new/) keeps the question "what must a quantum slice keep, and which rule produces it?".
Paper B (its own RP project, paper/b/) takes "can quantum programs be sliced statically, at scale, on the source
developers write?". Everything removed from A is copied here verbatim under inbox/ as raw material, with the commit
it came from. B's prose is written fresh: no sentence of A is reused, since the two may be reviewed together.

| Date | Item | From (A, file and commit) | Into (inbox/ file) | Notes |
|---|---|---|---|---|
| 2026-10-29 | The approach section in full: why srcML and srcSlice, E1 with the role table (Table IV), E2-E5, two front ends, faithfulness, coverage, the overview figure | new/sections/approach.tex, f96523f | inbox/approach.tex | A keeps one paragraph on how slices reach source lines (IV-E) |
| 2026-10-29 | Related work with the original Table I (tool row, srcML/srcSlice subsections) | new/sections/related.tex, f96523f | inbox/related_with_table1.tex | A's related work is re-centred on dependence models; Table I is now a table of dependence models |
| 2026-10-29 | Circuit loops: subsection, Proposition 5, its proof and the exact check on the control-flow programs | new/sections/core.tex 300-331, f96523f | inbox/core_circuit_loops.tex | A states that device loops are outside its model |
| 2026-10-29 | Qubit slice profile: Definition 5 and the BV profile of q0 | new/sections/core.tex 354-370, f96523f | inbox/core_qubit_profile.tex | |
| 2026-10-29 | srcSlice-Q's scalability (Fig. scale, its paragraph) and Table VIII's "Largest circuit" row | new/sections/results.tex 226-254, 279, f96523f | inbox/results_scalability.tex | A's RQ4 is the cost of the rules only |
| 2026-10-29 | srcSlice-Q on LintQ's data (Table IX and its section) | new/sections/results.tex 306-342, f96523f | inbox/results_lintq.tex | |
| 2026-10-29 | Program rows of the subjects table, the tool's timing settings and the LintQ comparison design | new/sections/design.tex 27-90, 137-150, f96523f | inbox/design_programs_and_tool.tex | A's subjects table lists circuits only |
| 2026-10-29 | Fig. 1 caption crediting the tool with the slices | new/sections/example.tex 3-12, f96523f | inbox/example_fig1_caption.tex | Fig. 1 itself stays in A; B uses its own example |
