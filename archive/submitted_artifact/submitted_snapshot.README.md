# submitted_snapshot/

The replication artifact exactly as it was available to reviewers (July 7, 2026), so that what was
reviewed can be inspected. It is unchanged except for one redaction, `"user_id"` in the 18
`data/ibm_cleveland_jobs/*-info.json` files. Version-control history is not included.

Its own README and `reproduce.sh` are the submitted versions and make the claims the paper makes.
Where those claims differ from what the code does, `../PROVENANCE.md` is authoritative. In
particular, the snapshot's `results/TAB_ablation.csv` (Table VI) has no generating code (D2), and its
Isabelle claim is withdrawn (D3).

Large corpus archives that were omitted from the submitted artifact are omitted here too (see
`data/QASMBench-master.zip.OMITTED.txt`); `../fetch_data.py` fetches QASMBench at the pinned commit.
