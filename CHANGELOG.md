# Changelog

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

## 2.0.0 — 2026-09-28 (revised manuscript)

### Added
- `wpr_faults.py`: failure tables holding node **and** link failures; the recording
  criteria of Algorithms 5–6 (including the bookkeeping that turns a fully isolated
  node into a node record); the notification of Algorithms 7–8 simulated in
  synchronous rounds, so that several failures can be notified concurrently
  (`concurrent` model) or one after the other (`sequential` model); the two
  forwarding rules — `original` (Algorithms 11–12 as originally submitted) and
  `trace` (the revised rule: the header carries the set of failures the current path
  avoids, and a node recomputes only when its table is not contained in it) — and a
  greedy failure-oblivious baseline reproducing the behaviour of RPS and GRWMS.
- `wpr_experiments.py`: the experiments of the revised paper — `two-failures`
  (exhaustive, sequential and concurrent, node or node+link), `k-failures` (random
  concurrent node or link failures), `mitigation` (affected set, blind-spot radius
  ρ*, probe radius and courtesy hops), `large` (10^4 to 3.6×10^5 nodes), `borel` (the
  RCRR scenario on B(47,23) with 5–35 % of the links failed), `greedy`, and
  `self-test` (recomputes the quick tables and compares them with `results/`).
- `wda_cost.g` and `run_wda.py`: size of the shortLex automatic structure (word
  acceptor, word-difference automata, general multiplier) of every family, computed
  with GAP/kbmag, with the computation time.
- `results/`: CSV files behind every table of the paper (`link_failures/` and
  `extra_families/` hold the runs mentioned in the text but not tabulated), plus
  `wda_cost.csv` / `wda_cost.txt`.
- `LICENSE` (MIT, as declared on Zenodo), `CITATION.cff`, `.zenodo.json`.

### Changed
- `README.md`: documents the new scripts, the two forwarding rules, the meaning of
  the criterion set vs. the notified set, and corrects the claim about `--radius 2
  --courtesy-hops 1` (the probe radius must be at least the blind-spot radius ρ*,
  which is 2 for Bubble-sort graphs and m/2−2 for the m×m torus).

### Unchanged
- `wpr_verify.py` (single node failure; Tables 5, 8 and 9) and
  `edge_transitivity.g`. Under a single failure the two forwarding rules visit the
  same nodes, so the published single-failure figures are unaffected.

### Known limitations
- The `original` rule is kept only to reproduce the comparison; it is not loop-free
  with two or more failures (see Remark 1 of the paper).
- kbmag's `gpaxioms` overflows its file-name buffers with long relators and long
  temporary paths; `run_wda.py` uses a short temporary directory and, for the
  100×100 torus, a `gpaxioms` rebuilt with larger buffers (see `results/wda_cost.txt`).
  The Star and Pancake graphs of Sym_8 did not complete within a ten-minute cap.

## 1.0 (tag `wpr`) — 2026-08-14
- Initial deposit: `wpr_verify.py`, `edge_transitivity.g`, `README.md`.
