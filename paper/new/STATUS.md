# Paper A status (30 October 2026, commit 052b675)

**Title.** What Must a Quantum Slice Keep? Slicing Quantum Programs for Comprehension
**Venue.** ICPC 2027 research track, double-anonymous; paper due 5 November 2026 AoE, 10 pages + 2 of references.
**RP.** #EA0C9 (saved after every change with `../_rp_tools/save_to_rp_v2.py`).

## Done
- Every section written and reviewed: abstract and keywords, I Introduction, II example (Fig. 1), III related work
  (Table I), IV semantics, write-all rule and Algorithm 1 (backward and forward pass), V design, VI results with the
  scorecard and an answer to each RQ, VII implications, VIII threats, IX conclusion.
- Four-agent review applied (cuts/REVIEW_2026-10-29.md); two reading maps applied (second map
  https://claude.ai/artifact/34yivudVSpgT2ouGgvmPnK, in the current claude.ai organization).
- Definition 4 states the bit treatment the study used; the one-pass algorithm equals the study's graph on 784 of 784
  pairs (backward) and 3,156 of 3,156 operations (forward), Deviation I-28.
- RQ4 compares the QDG and the QPDG as graphs (22 ms against 21.7 s at depth 380); the one-pass cost is reported
  separately; the timing machine is named in Section V.
- Replication package: `sh tools/build_package_a.sh` -> build/package-a; private GitHub repo
  alomarhw/quantum-slice-semantics (clone in ../paper-a-artifact); anonymous link
  https://anonymous.4open.science/r/quantum-slice-semantics-7CAF, in the Introduction. After every paper change:
  rebuild, check names, rsync into the clone, commit as Anonymous Authors, push.

## Open
1. **Length.** Body 11.73 pages (measured to the end of the Conclusion); about 1.9 pages to cut. Candidates: Fig. 2 at
   column width (~0.35), drop the language-model study (~0.3), repeated text (~0.2), proof sketches to the package
   (~0.15), then sentence-level tightening. The author chooses.
2. **Source comment** in core.tex about a general necessity proposition (Beckman et al. 2001): keep or remove before
   submission (it shows in the package's LaTeX source, not in the PDF).
3. **HotCRP.** Title and abstract registered by the author; update them there if they change.
