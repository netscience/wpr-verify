## 2.1.0 — 2026-09-30 (revised manuscript, final rule)

### Changed
- `wpr_faults.py`: the revised forwarding rule `trace` now adds to the failure
  trace only the failures that block the path still to be followed (a node it
  visits or a link it traverses), instead of the node's whole table. A node
  recomputes only when one of its recorded failures lies on that path, and
  iterates until the new path avoids its whole table; the source starts from the
  failure-free shortLex path. The delivery guarantee (Theorem 1) is unchanged:
  every recomputation still adds a new failure to the trace. Headers become much
  smaller (mean trace 0.04–0.5 labels with 2–12 node failures, against 0.8–9.5 with
  the whole-table rule) and the number of path computations per message drops
  from 1.3–3.2 to 1.04–1.5; the fraction of non-minimal routes rises slightly.
  The whole-table rule of 2.0.0 is kept as `trace-full`.
- `route()` returns the size of the trace on arrival (`trace`); `audit()`
  accumulates it (`trace_sum`), and `wpr_experiments.py` reports its mean
  (`trace mean`) in `two-failures`, `k-failures` and `borel`.
- `results/`: `two_failures.csv`, `k_failures.csv`, `borel.csv` (now the full sweep,
  20 failure sets and 5000 pairs per level) and `link_failures/` regenerated with the
  new rule. The single-failure tables
  (`greedy`, `mitigation`, `large`, and those of `wpr_verify.py`) are unaffected:
  under one failure both rules follow the same routes.
