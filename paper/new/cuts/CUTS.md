# Cuts to Paper A (for length)

The full text before each cut is kept verbatim in the dated folder, so anything can be restored.

## 2026-10-29, Tiers 1 and 2 (author decision), snapshot in 2026-10-29-precut/
Body before: 13.61 pages; after: 11.63 pages (measured to the end of the Conclusion).

| Section | Cut |
|---|---|
| II | Five "Relation and reuse" paragraphs merged into the gaps paragraph; entanglement analysis folded into II-B; debugging tools and detectors halved (Ramalho's slicing remark, Oldfield's testing limit, bug patterns cite dropped here) |
| III | Background paragraph halved |
| IV | Table II (three kinds) replaced by inline examples; "Why the write set cannot be smaller" reduced to two sentences; Proposition (forward/backward duality) reduced to one sentence |
| V | Subjects table replaced by text; MBFL design shortened (backward-order ranking dropped) |
| VI | RQ1 QPDG paragraph condensed (precision numbers left to Table VI); noise paragraph condensed (sampled-run maximum dropped); MBFL results condensed; language-model results condensed and Fig. llm removed; Fig. cost removed; VI-E (QDG vs QPDG, Table VIII) removed, its size-control point moved into RQ3 |
| VII | Implications halved, all four points kept |
| VIII | Threats tightened |

## 2026-10-29, contributions as a paragraph (author request)
The numbered list of four contributions in the Introduction became one paragraph (278 -> 196 words). Dropped from it,
still in the body: the 99.7% figure, the count of 21 gates, distributivity over criteria and the 55.4% of state-based
slices. The list is in 2026-10-29-precut/intro.tex.

## 2026-10-29, sentence-level tightening and duplicates (author request)
Body 11.53 -> 10.18 pages, no claim, number, definition, proof or citation removed. Duplicates removed: the "light
cone is known" claim (kept in the Introduction and before Theorem 1; dropped from the gaps paragraph and after
Proposition 2); the P1 walkthrough (shortened, Section III tells it); the QDG's 17.5-point size-controlled gain (stated
twice in RQ3); the outcome-histogram argument (kept in the Introduction and RQ1, a reference in Implications); H1/H2
known in advance (kept in Section V, shortened in Threats). Every section's text before this pass is recoverable from
git (commit 799befe).
