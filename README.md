# Verification code for the WPR routing scheme

Companion code for

> D. Aguirre-Guerrero, L. Fàbrega, P. Vilà,
> *Word-Processing-based Routing: A Fault-tolerant Routing Scheme for Cayley
> Graphs*.

It reproduces results reported in tables 8 and 9 of the paper.

## Contents

| File | Purpose | Requires |
|---|---|---|
| `wpr_verify.py` | Exhaustive verification of the routing scheme; regenerates both tables | Python ≥ 3.6, standard library only |
| `edge_transitivity.g` | Rigorous edge-transitivity check via automorphism groups | GAP ≥ 4.15 with GRAPE |

## Running
#### Python version

`wpr_verify.py` needs **Python 3.6 or later**.

No packages need to be installed: the script imports only from the standard
library, which keeps it reproducible for reviewers and readers.

```bash
python3 wpr_verify.py --self-test      # verify against the published figures
python3 wpr_verify.py                  # print both tables
python3 wpr_verify.py --table locality
python3 wpr_verify.py --table verification
python3 wpr_verify.py --latex          # emit LaTeX tabular rows
```

The self-test finishes in well under a second and prints
`published figures reproduced` when the computed values match those in the
paper. Two further options explore the strengthened control plane discussed in
the paper:

```bash
python3 wpr_verify.py --table verification --radius 2 --courtesy-hops 1
```

`--radius 2` widens the recording criterion of Algorithm 5 to destinations
within distance two of the failure; `--courtesy-hops 1` relays each
notification one hop past the last updating node. Together they restore
minimal routing on every family tested, at a modest cost in failure-table size.

## What is verified

For each Cayley graph a single node failure is introduced. The notification
process of Algorithms 7–8 runs, with each notified node applying the recording
criterion of Algorithm 5 and relaying only when its own table changes. Then
**every ordered pair** of surviving nodes is routed with Algorithms 11–12, and
the hop count is compared against the true distance in $\Gamma\setminus F$. No sampling is
involved — for `BS(5)` and `ST(5)` that is $14042$ pairs each.

Because Cayley graphs are vertex-transitive, and the shortLex order is
invariant under left translation (the word joining `u` and `v` depends only on
`u⁻¹v`), the result does not depend on which node is chosen to fail. The
identity is used throughout.

## Edge-transitivity

`wpr_verify.py` does not decide edge-transitivity; it only routes messages. The
edge-transitivity column of the paper is settled by `edge_transitivity.g`,
which computes the full automorphism group of each graph with GRAPE (calling
nauty) and tests whether it acts transitively on the edge set:

```bash
gap -q edge_transitivity.g
```

This is a separate tool on purpose. $Aut(\Gamma)$ can be strictly larger than the
group of automorphisms of G preserving S, so a group-theoretic shortcut would
not be sound, and a local invariant such as counting short cycles per edge can
only ever certify *non*-equivalence, never equivalence.

## Adding a family

Graph constructors return a `CayleyGraph` and compose freely:

```python
from wpr_verify import CayleyGraph, verification

def my_graph(n):
    return CayleyGraph("MyCG(%d)" % n, list(range(n)),
                       [lambda g: (g + 1) % n, lambda g: (g - 1) % n])

print(verification(my_graph(30)))
```

Generator index order **is** the alphabet order used by shortLex, so listing
the actions in a different order gives a different (equally valid) shortLex
language.
