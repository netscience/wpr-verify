# Verification code for the WPR routing scheme

Companion code for

> D. Aguirre-Guerrero, L. Fàbrega, P. Vilà,
> *Word-Processing-based Routing: A Fault-tolerant Routing Scheme for Cayley
> Graphs*.

It reproduces every figure reported in the tables of the paper.

Version 2.1.0 (revised manuscript). Earlier versions are archived on Zenodo
(version 2.0.0: [10.5281/zenodo.23005545](https://doi.org/10.5281/zenodo.23005545);
concept DOI for all versions:
[10.5281/zenodo.21929581](https://doi.org/10.5281/zenodo.21929581)); see
`CITATION.cff` for how to cite the code and the paper, and `CHANGELOG.md` for
what changed since version 1.

## Contents

| File | Purpose | Requires |
|---|---|---|
| `wpr_verify.py` | Single node failure: locality of failure records, exhaustive routing verification and control-plane cost (Tables 5, 8 and 9) | Python ≥ 3.6, standard library only |
| `wpr_faults.py` | Library: failure tables for node **and** link failures, notification of Algorithms 5–8 simulated in synchronous rounds (sequential or concurrent failures), the two forwarding rules (`original`: the table-only rule of Remark 1 of the paper; `trace`: the rule with failure trace of Algorithms 11–12) and a greedy failure-oblivious baseline | Python ≥ 3.6 |
| `wpr_experiments.py` | The experiments added in the revision: two failures (exhaustive), *k* concurrent failures, minimality mitigation (affected set, blind-spot radius, probe radius, courtesy hops), large instances, the RCRR scenario on the Borel graph, greedy baseline | Python ≥ 3.6 |
| `edge_transitivity.g` | Rigorous edge-transitivity check via automorphism groups | GAP ≥ 4.15 with GRAPE |
| `wda_cost.g` | Size of the shortLex automatic structure (word acceptor, word-difference automata) of each group, and the time to compute it | GAP ≥ 4.15 with kbmag |

## Running

No packages need to be installed for the Python scripts: they import only from
the standard library, which keeps them reproducible for reviewers and readers.

```bash
python3 wpr_verify.py --self-test      # verify Tables 5, 8, 9 against the published figures
python3 wpr_verify.py                  # print those tables
python3 wpr_verify.py --latex          # emit LaTeX tabular rows

python3 wpr_experiments.py two-failures            # Table: two node failures, exhaustive
python3 wpr_experiments.py two-failures --links    # a node and a link failure
python3 wpr_experiments.py k-failures --sets 20    # Table: k concurrent node failures
python3 wpr_experiments.py k-failures --links      # k concurrent link failures
python3 wpr_experiments.py mitigation              # Table: affected set, rho*, radius / courtesy hops
python3 wpr_experiments.py large --pairs 10000 --destinations 50   # Table: 10^4 - 3.6x10^5 nodes
python3 wpr_experiments.py borel --sets 20 --pairs 5000 --destinations 100   # Table: RCRR scenario
python3 wpr_experiments.py greedy                  # Table: WPR vs greedy, single failure
```

Every experiment accepts `--csv DIR` (write a CSV next to the text table),
`--latex` (LaTeX rows), `--families ...` (restrict to some graphs) and
`--seed` (the sampled experiments are pseudo-random with a fixed default
seed, so they are reproducible). The single-failure self-test finishes in a
few seconds; the complete set of experiments of the paper takes about one hour
on a laptop, the Borel sweep being the longest.

## What is verified

**Single failure (`wpr_verify.py`).** For each Cayley graph a single node
failure is introduced. The notification process of Algorithms 7–8 runs, with
each notified node applying the recording criterion of Algorithm 5 and
relaying only when its own table changes. Then **every ordered pair** of
surviving nodes is routed with Algorithms 11–12, and the hop count is compared
against the true distance in Γ \ F. No sampling is involved — for `BS(5)` and
`ST(5)` that is 14 042 pairs each. Because Cayley graphs are vertex-transitive,
and the shortLex order is invariant under left translation, the result does
not depend on which node fails; the identity is used throughout. Under a
single failure the table-only rule and the rule with failure trace visit exactly the same nodes, so these tables are
unaffected by the revision.

**Several failures (`wpr_faults.py`, `wpr_experiments.py`).** Failure elements
are nodes and links. Each node keeps a table of both; a notification is
processed with Algorithms 5–6 (node and link criteria, including the
bookkeeping that turns a fully isolated node into a node record) and relayed
with Algorithms 7–8, including the lines by which a node that records a
failure also evaluates the failures known to its notifier. The notification is
simulated in synchronous rounds, so that the notifications of several
failures can overlap (`concurrent` model) or be run one after the other
(`sequential` model). Messages are then routed with

* `original`: the table-only rule (Remark 1 of the paper; version 1 of this code) — a node with a
  non-empty table recomputes the path from its own table;
* `trace`: the revised rule (Algorithms 11–12 of the revised paper) — the
  header carries a failure trace *B*. A node (the source included, which
  starts from the failure-free shortLex path with *B* = ∅) acts only if some
  element of its table *T* lies on the path still to be followed (a node it
  visits or a link it traverses); it then adds those blocking elements, and
  only those, to *B*, recomputes the path avoiding *B*, and repeats until the
  path avoids *T*. Failures that do not affect the path never enter the header;
* `trace-full`: a variant, kept for comparison, in which a node recomputes
  whenever *T* is not contained in *B* and adds its whole table to *B*. It
  follows the same routes far more often than not but carries larger headers
  and computes more paths (this was the rule of version 2.0.0).

and, for reference, with a failure-oblivious greedy rule (forward to the alive
neighbour closest to the destination in the failure-free graph, i.e. the
behaviour of the RPS and GRWMS schemes). Loops are detected by state
repetition; a hop into a failed element counts as a loss.

The `mitigation` experiment computes, for a single failure, the set of
*affected* nodes (those whose first hop towards some destination changes),
the *blind-spot radius* ρ\* (the smallest probe radius that lets every affected
node see a witness), the criterion set and the notified set, and it re-runs
the notification with a wider probe radius (`--radius`) and courtesy hops
(`--courtesy-hops`, extra relays past the last updating node). Minimal routing
for every pair holds exactly when the notified set contains the affected set
(Proposition 1 of the paper). Note that ρ\* = 2 in the Bubble-sort graphs and
grows with the side length in square tori (ρ\* = 5 for 14×14), so
`--radius 2 --courtesy-hops 1` restores minimality on the eleven families of
Table 8 but not on every family: `--radius` must be at least ρ\*.

## Edge-transitivity

`wpr_verify.py` does not decide edge-transitivity; it only routes messages. The
edge-transitivity column of the paper is settled by `edge_transitivity.g`,
which computes the full automorphism group of each graph with GRAPE (calling
nauty) and tests whether it acts transitively on the edge set:

```bash
gap -q edge_transitivity.g
```

This is a separate tool on purpose. Aut(Γ) can be strictly larger than the
group of automorphisms of G preserving S, so a group-theoretic shortcut would
not be sound.

## Automaton sizes

`wda_cost.g` builds the finitely presented group behind each Cayley graph,
computes its shortLex automatic structure with kbmag and reports the number of
states of the word acceptor, of the first and second word-difference automata
and of the general multiplier, together with the computation time (Table on
the cost of the WDA in the paper). `run_wda.py` drives it case by case with a
wall-clock cap and collects `results/wda_cost.csv` / `results/wda_cost.txt`:

```bash
python3 run_wda.py            # or: gap -q -b wda_cost.g < /dev/null
```

Two practical notes. kbmag writes its temporary files under the path given by
GAP's temporary directory; with a long path (about 70 characters, the macOS
default) the `gpaxioms` program overflows its fixed 100-byte file-name buffers
on relators of more than ~25 letters and `AutomaticStructure` returns `false`.
The driver therefore points kbmag to the short relative directory `wdatmp/`.
For the largest relators (the $100\times100$ torus, whose relators have 100
letters) `gpaxioms` had to be rebuilt from the package sources with larger
buffers; the runs affected are marked in `wda_cost.txt`. The word-difference
automaton used by the path-computation algorithms is the second one
(`SecondWordDifferenceAutomaton`, kbmag file `.diff2`); every group order was
checked against the number of words accepted by the word acceptor.

## Adding a family

Graph constructors in `wpr_verify.py` return a `CayleyGraph` and compose
freely: give the list of group elements and, for each generator in alphabet
order, the function that applies it. The generator order *is* the
lexicographic order used by shortLex.
