# Changelog

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
