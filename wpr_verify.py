               #!/usr/bin/env python3
"""
wpr_verify.py -- Exhaustive verification of the Word-Processing-based Routing
(WPR) scheme on Cayley Graphs.

Reproduces every figure reported in the tables of

    D. Aguirre-Guerrero, L. Fabrega, P. Vila,
    "Word-Processing-based Routing: A Fault-tolerant Routing Scheme for
     Cayley Graphs".

Requirements: Python 3.6 or later. Standard library only -- no dependencies.

Usage
-----
    python3 wpr_verify.py                # both tables (default families)
    python3 wpr_verify.py --table locality
    python3 wpr_verify.py --table verification
    python3 wpr_verify.py --latex        # emit LaTeX tabular bodies
    python3 wpr_verify.py --self-test    # check against published figures

What is verified
----------------
For each Cayley Graph a single node failure is introduced. The failure
notification of Algorithms 7-8 is executed, with each notified node applying
the recording criterion of Algorithm 5 and relaying only when its own table
changes. Then EVERY ordered pair of surviving nodes is routed using
Algorithms 11-12 and the resulting hop count is compared against the true
distance in Gamma \\ F. No sampling is involved.

By vertex-transitivity of Cayley Graphs, and because the shortLex order is
invariant under left translation (the word joining u and v depends only on
u^{-1} v), the outcome does not depend on which node is chosen to fail.
The identity is used throughout.
"""

from __future__ import print_function

import argparse
import sys
from collections import deque
import random
from itertools import combinations, permutations

if sys.version_info < (3, 6):
    sys.exit("This script requires Python 3.6 or later (found %d.%d). "
             "See README.md." % sys.version_info[:2])

INF = float("inf")


# ---------------------------------------------------------------------------
# Cayley graph construction
# ---------------------------------------------------------------------------

class CayleyGraph(object):
    """A Cayley graph stored as an adjacency table indexed by generator.

    adj[u][i] is the node reached from u through the generator of index i.
    Generator indices are the alphabet A of the paper, ordered a < b < c < ...
    so that index order IS the lexicographic order used by shortLex.
    """

    def __init__(self, name, elements, actions):
        self.name = name
        index = {e: i for i, e in enumerate(elements)}
        self.deg = len(actions)
        self.n = len(elements)
        self.adj = [[0] * self.deg for _ in range(self.n)]
        for e in elements:
            u = index[e]
            for i, act in enumerate(actions):
                self.adj[u][i] = index[act(e)]

    # -- basic graph queries -------------------------------------------------

    def bfs(self, source, banned=()):
        """Distances from `source`, treating nodes in `banned` as removed."""
        banned = set(banned)
        dist = [INF] * self.n
        if source in banned:
            return dist
        dist[source] = 0
        queue = deque([source])
        while queue:
            x = queue.popleft()
            dx = dist[x] + 1
            for y in self.adj[x]:
                if y not in banned and dist[y] == INF:
                    dist[y] = dx
                    queue.append(y)
        return dist

    def neighbours(self, u):
        return self.adj[u]

    def diameter(self):
        return max(d for d in self.bfs(0) if d != INF)


def _compose(g, s):
    return tuple(g[s[i]] for i in range(len(g)))


def _transposition(p, i, j):
    t = list(range(p))
    t[i], t[j] = t[j], t[i]
    return tuple(t)


def _prefix_reversal(p, k):
    return tuple(list(range(k - 1, -1, -1)) + list(range(k, p)))


def _from_permutations(name, p, gens):
    return CayleyGraph(name, list(permutations(range(p))),
                       [(lambda g, s=s: _compose(g, s)) for s in gens])


def bubble_sort(p):
    """BS(p): Sym_p with adjacent transpositions s_1 < ... < s_{p-1}."""
    return _from_permutations("BS(%d)" % p, p,
                              [_transposition(p, i, i + 1) for i in range(p - 1)])


def star(p):
    """ST(p): Sym_p with the star transpositions (1 i)."""
    return _from_permutations("ST(%d)" % p, p,
                              [_transposition(p, 0, i) for i in range(1, p)])


def complete_transposition(p):
    """CT(p): Sym_p with all transpositions."""
    return _from_permutations("CT(%d)" % p, p,
                              [_transposition(p, i, j)
                               for i, j in combinations(range(p), 2)])


def pancake(p):
    """PC(p): Sym_p with prefix reversals."""
    return _from_permutations("PC(%d)" % p, p,
                              [_prefix_reversal(p, k) for k in range(2, p + 1)])


def hypercube(k):
    """Q_k: (Z/2Z)^k with the standard basis."""
    return CayleyGraph("Q_%d" % k, list(range(1 << k)),
                       [(lambda g, i=i: g ^ (1 << i)) for i in range(k)])


def torus(m, k=None):
    """Z_m x Z_k with generators (+1,0), (0,+1), (-1,0), (0,-1)."""
    k = m if k is None else k
    deltas = [(1, 0), (0, 1), (-1, 0), (0, -1)]
    return CayleyGraph("Torus %dx%d" % (m, k),
                       [(x, y) for x in range(m) for y in range(k)],
                       [(lambda g, d=d: ((g[0] + d[0]) % m, (g[1] + d[1]) % k))
                        for d in deltas])


def borel(p, k, connectors=None):
    """Borel Cayley graph: the group of matrices [[a,b],[0,1]] over Z_p with a
    ranging over the subgroup of order k of Z_p^*, so that n = p*k.

    These are the graphs on which the only previously published fault-tolerant
    routing scheme for Cayley graphs was evaluated; p=47, k=23 gives the
    1081-node instance used there.
    """
    g = None
    for cand in range(2, p):
        order, x = 1, cand
        while x != 1:
            x = (x * cand) % p
            order += 1
        if order == k:
            g = cand
            break
    if g is None:
        raise ValueError("Z_%d^* has no subgroup of order %d" % (p, k))

    subgroup, x = [], 1
    for _ in range(k):
        subgroup.append(x)
        x = (x * g) % p
    elements = [(a, b) for a in subgroup for b in range(p)]

    def mul(u, v):
        return ((u[0] * v[0]) % p, (u[0] * v[1] + u[1]) % p)

    def inv(u):
        ai = pow(u[0], p - 2, p)
        return (ai, (-ai * u[1]) % p)

    if connectors is None:
        connectors = [(g, 0), (1, 1)]
    gens = []
    for c in connectors:
        gens.append(c)
        gens.append(inv(c))
    return CayleyGraph("Borel(%d,%d)" % (p, k), elements,
                       [(lambda u, c=c: mul(u, c)) for c in gens])


def circulant(n, connectors):
    """Z_n with S = {+/- c : c in connectors}."""
    shifts = []
    for c in connectors:
        shifts += [c, -c]
    return CayleyGraph("C_%d(%s)" % (n, ",".join(map(str, connectors))),
                       list(range(n)),
                       [(lambda g, s=s: (g + s) % n) for s in shifts])


# ---------------------------------------------------------------------------
# shortLex machinery
# ---------------------------------------------------------------------------

class ShortLex(object):
    """Cached shortLex path computation for a fixed failure set.

    A shortLex path minimises length first and lexicographic order second, so
    it is obtained greedily on the shortest-path DAG: from the current node,
    take the smallest generator index that decreases the distance to the
    target. Distances are cached per target, which is what makes exhaustive
    all-pairs verification tractable.
    """

    def __init__(self, graph, banned=()):
        self.g = graph
        self.banned = frozenset(banned)
        self._dist = {}

    def dist_to(self, target):
        d = self._dist.get(target)
        if d is None:
            d = self.g.bfs(target, self.banned)
            self._dist[target] = d
        return d

    def distance(self, u, v):
        return self.dist_to(v)[u]

    def first_letter(self, u, v):
        """Index of the first generator of the shortLex path u -> v.

        Returns None if no path exists (the symbol bot of the paper), and
        EMPTY if u == v (the empty path e_A).
        """
        if u in self.banned or v in self.banned:
            return None
        d = self.dist_to(v)
        if d[u] == INF:
            return None
        if u == v:
            return EMPTY
        du = d[u]
        for i, y in enumerate(self.g.adj[u]):
            if y not in self.banned and d[y] == du - 1:
                return i
        return None

    def path(self, u, v):
        """The shortLex word from u to v, as a tuple of generator indices."""
        if u in self.banned or v in self.banned:
            return None
        d = self.dist_to(v)
        if d[u] == INF:
            return None
        word, cur = [], u
        while cur != v:
            dc = d[cur]
            for i, y in enumerate(self.g.adj[cur]):
                if y not in self.banned and d[y] == dc - 1:
                    word.append(i)
                    cur = y
                    break
        return tuple(word)


EMPTY = "e_A"


def walk(graph, u, word):
    for i in word:
        u = graph.adj[u][i]
    return u


# ---------------------------------------------------------------------------
# The WPR control plane
# ---------------------------------------------------------------------------

def ball(graph, centre, radius):
    d = graph.bfs(centre)
    return [v for v in range(graph.n) if 0 < d[v] <= radius]


def records_failure(graph, u, f, clean, faulty, radius=1):
    """Recording criterion of Algorithm 5, for a node failure f.

    `clean` and `faulty` are ShortLex objects for the failure sets {} and {f}.
    A node records f when, for some destination v within `radius` of f, either
    no path to v survives, or the first hop towards v changes.
    """
    if u == f:
        return False
    if u in graph.neighbours(f):
        return True                      # unconditional: Algorithm 7, step 1
    for v in ball(graph, f, radius):
        if v == u:
            continue
        w1 = faulty.first_letter(u, v)
        w2 = clean.first_letter(u, v)
        if w1 is None or w1 != w2:
            return True
    return False


def notify(graph, f, clean, faulty, radius=1, courtesy_hops=0):
    """Failure notification of Algorithms 7-8.

    Starts at the neighbours of f and relays outward. A node that does not
    update its table stops the process, except that `courtesy_hops` extra
    relays are allowed past the last updating node.

    Returns (recorded, messages, rounds): the set of nodes holding f in
    their failure table, the number of notification messages emitted, and the
    number of propagation rounds until convergence. A node emits one message
    per active port other than the one it was notified through, hence deg - 1
    messages per relaying node.
    """
    recorded, seen, frontier = set(), set(), []
    for v in graph.neighbours(f):
        if v != f:
            recorded.add(v)
            seen.add(v)
            frontier.append((v, 0))
    messages = len(set(graph.neighbours(f)) - {f}) * (graph.deg - 1)
    rounds = 0
    while frontier:
        rounds += 1
        nxt = []
        for z, slack in frontier:
            for u in graph.neighbours(z):
                if u == f or u in seen:
                    continue
                seen.add(u)
                if records_failure(graph, u, f, clean, faulty, radius):
                    recorded.add(u)
                    nxt.append((u, 0))
                elif slack < courtesy_hops:
                    nxt.append((u, slack + 1))
        messages += len(nxt) * (graph.deg - 1)
        frontier = nxt
    return recorded, messages, rounds


def route(graph, src, dst, f, recorded, clean, faulty, max_hops=None):
    """Forwarding of Algorithms 11-12. Returns (status, hops).

    status is "ok", "lost" or "loop". A node with a non-empty failure table
    recomputes an avoiding path (Algorithm 11); otherwise it follows the
    header written upstream (Algorithm 4 via Algorithm 12).
    """
    max_hops = max_hops or 4 * graph.n
    view = lambda u: faulty if u in recorded else clean

    word = view(src).path(src, dst)
    if word is None:
        return "lost", 0
    cur, header, hops = graph.adj[src][word[0]], word[1:], 1
    history = set()
    while hops < max_hops:
        if not header:
            return "ok", hops
        if cur not in recorded:                      # static forwarding
            cur, header = graph.adj[cur][header[0]], header[1:]
        else:                                        # recompute (Algorithm 11)
            target = walk(graph, cur, header)
            word = faulty.path(cur, target)
            if word is None:
                return "lost", hops
            cur, header = graph.adj[cur][word[0]], word[1:]
        hops += 1
        state = (cur, header)
        if state in history:
            return "loop", hops
        history.add(state)
    return "loop", hops


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------

def locality(graph, radius=1):
    """Number and spread of the nodes satisfying the recording criterion."""
    f = 0
    clean, faulty = ShortLex(graph), ShortLex(graph, {f})
    dist = graph.bfs(f)
    rec = [u for u in range(graph.n)
           if u != f and records_failure(graph, u, f, clean, faulty, radius)]
    return dict(name=graph.name, n=graph.n, deg=graph.deg,
                diameter=graph.diameter(), recorders=len(rec),
                fraction=100.0 * len(rec) / (graph.n - 1),
                max_distance=max((dist[u] for u in rec), default=0))


def verification(graph, radius=1, courtesy_hops=0, sample=0, seed=12345):
    """Route every ordered pair of surviving nodes and audit the outcome.

    With sample > 0, route that many uniformly random pairs instead. Sampling
    is only intended for graphs too large for the exhaustive sweep; the figures
    reported in the paper are exhaustive unless stated otherwise.
    """
    f = 0
    clean, faulty = ShortLex(graph), ShortLex(graph, {f})
    recorded, _, _ = notify(graph, f, clean, faulty, radius, courtesy_hops)
    lost = loops = non_minimal = pairs = 0

    if sample:
        rng = random.Random(seed)
        survivors = [u for u in range(graph.n) if u != f]
        todo = []
        while len(todo) < sample:
            a, b = rng.choice(survivors), rng.choice(survivors)
            if a != b:
                todo.append((a, b))
    else:
        todo = ((a, b) for a in range(graph.n) if a != f
                for b in range(graph.n) if b != f and b != a)

    for s, t in todo:
            pairs += 1
            status, hops = route(graph, s, t, f, recorded, clean, faulty)
            if status == "lost":
                lost += 1
            elif status == "loop":
                loops += 1
            elif hops > faulty.distance(s, t):
                non_minimal += 1
    return dict(name=graph.name, n=graph.n, deg=graph.deg,
                diameter=graph.diameter(), recorders=len(recorded),
                pairs=pairs, lost=lost, loops=loops, non_minimal=non_minimal)


def overhead(graph, radius=1, courtesy_hops=0):
    """Control-plane cost of a single node failure.

    The reference point is a network-wide flood, in which every surviving node
    relays the notification once through each of its other ports.
    """
    f = 0
    clean, faulty = ShortLex(graph), ShortLex(graph, {f})
    recorded, messages, rounds = notify(graph, f, clean, faulty,
                                        radius, courtesy_hops)
    flood = (graph.n - 1) * (graph.deg - 1)
    return dict(name=graph.name, n=graph.n, deg=graph.deg,
                diameter=graph.diameter(), recorders=len(recorded),
                messages=messages, rounds=rounds, flood=flood,
                share=100.0 * messages / flood)


# ---------------------------------------------------------------------------
# Families and reporting
# ---------------------------------------------------------------------------

LOCALITY_FAMILIES = [bubble_sort(4), bubble_sort(5), bubble_sort(6),
                     hypercube(4), hypercube(6), hypercube(8),
                     torus(4), torus(8)]

VERIFICATION_FAMILIES = [bubble_sort(4), bubble_sort(5),bubble_sort(6),
                         star(4), star(5), complete_transposition(4),
                         pancake(4), pancake(5),
                         hypercube(4), torus(6), torus(4, 16),
                         circulant(20, [1, 2])]

OVERHEAD_FAMILIES = [bubble_sort(4), bubble_sort(5), bubble_sort(6),
                     bubble_sort(7), hypercube(4), hypercube(6), hypercube(8),
                     hypercube(10), torus(6), torus(14),
                     star(5), pancake(5)]

# figures published in the paper, checked by --self-test
PUBLISHED = {
    "locality": {"BS(4)": (10, 4), "BS(5)": (30, 6), "BS(6)": (79, 9),
                 "Q_4": (4, 1), "Q_6": (6, 1), "Q_8": (8, 1),
                 "Torus 4x4": (4, 1), "Torus 8x8": (17, 3)},
    "overhead": {"BS(4)": (16, 3), "BS(5)": (84, 6), "BS(7)": (710, 10),
                 "Q_4": (12, 1), "Q_10": (90, 1), "Torus 6x6": (30, 2)},
    "verification": {"BS(4)": (0, 0, 4), "BS(5)": (0, 0, 6),
                     "ST(4)": (0, 0, 0), "ST(5)": (0, 0, 0),
                     "PC(4)": (0, 0, 0), "PC(5)": (0, 0, 0),
                     "Q_4": (0, 0, 0), "Torus 6x6": (0, 0, 0)},
}


def report_locality(rows, latex=False):
    if latex:
        for r in rows:
            print("$%s$ & %d & %d & %d & %d & %.1f\\%% & %d\\\\"
                  % (r["name"], r["n"], r["deg"], r["diameter"],
                     r["recorders"], r["fraction"], r["max_distance"]))
        return
    print("\n%-14s %7s %4s %4s %8s %8s %7s"
          % ("Cayley graph", "n", "deg", "D", "record.", "share", "max d"))
    print("-" * 56)
    for r in rows:
        print("%-14s %7d %4d %4d %8d %7.1f%% %7d"
              % (r["name"], r["n"], r["deg"], r["diameter"],
                 r["recorders"], r["fraction"], r["max_distance"]))


def report_overhead(rows, latex=False):
    if latex:
        for r in rows:
            print("%s & %d & %d & %d & %d & %d & %d & %.1f\\%%\\\\"
                  % (r["name"], r["n"], r["deg"], r["recorders"],
                     r["messages"], r["rounds"], r["flood"], r["share"]))
        return
    print("\n%-14s %7s %4s %8s %9s %7s %9s %8s"
          % ("Cayley graph", "n", "deg", "record.", "messages", "rounds",
             "flood", "share"))
    print("-" * 68)
    for r in rows:
        print("%-14s %7d %4d %8d %9d %7d %9d %7.1f%%"
              % (r["name"], r["n"], r["deg"], r["recorders"], r["messages"],
                 r["rounds"], r["flood"], r["share"]))


def report_verification(rows, latex=False):
    if latex:
        for r in rows:
            print("%s & %d & %d & %d & %d & %d & %d / %d & %d\\\\"
                  % (r["name"], r["n"], r["deg"], r["diameter"],
                     r["recorders"], r["pairs"], r["lost"], r["loops"],
                     r["non_minimal"]))
        return
    print("\n%-14s %7s %4s %4s %8s %8s %6s %6s %8s"
          % ("Cayley graph", "n", "deg", "D", "record.", "pairs",
             "lost", "loops", "non-min."))
    print("-" * 72)
    for r in rows:
        print("%-14s %7d %4d %4d %8d %8d %6d %6d %8d"
              % (r["name"], r["n"], r["deg"], r["diameter"], r["recorders"],
                 r["pairs"], r["lost"], r["loops"], r["non_minimal"]))


def self_test():
    ok = True
    for r in (locality(g) for g in LOCALITY_FAMILIES):
        exp = PUBLISHED["locality"].get(r["name"])
        if exp and (r["recorders"], r["max_distance"]) != exp:
            print("MISMATCH locality %s: got %s expected %s"
                  % (r["name"], (r["recorders"], r["max_distance"]), exp))
            ok = False
    for r in (verification(g) for g in VERIFICATION_FAMILIES):
        exp = PUBLISHED["verification"].get(r["name"])
        got = (r["lost"], r["loops"], r["non_minimal"])
        if exp and got != exp:
            print("MISMATCH verification %s: got %s expected %s"
                  % (r["name"], got, exp))
            ok = False
    for r in (overhead(g) for g in OVERHEAD_FAMILIES):
        exp = PUBLISHED["overhead"].get(r["name"])
        got = (r["messages"], r["rounds"])
        if exp and got != exp:
            print("MISMATCH overhead %s: got %s expected %s"
                  % (r["name"], got, exp))
            ok = False
    print("self-test: %s" % ("all published figures reproduced" if ok
                             else "DISCREPANCIES FOUND"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--table",
                    choices=["locality", "verification", "overhead", "all"],
                    default="all")
    ap.add_argument("--latex", action="store_true",
                    help="emit LaTeX tabular rows instead of a text table")
    ap.add_argument("--self-test", action="store_true",
                    help="check the computed figures against the published ones")
    ap.add_argument("--radius", type=int, default=1,
                    help="radius of the recording criterion (1 = Algorithm 5 "
                         "as published; 2 = strengthened variant)")
    ap.add_argument("--courtesy-hops", type=int, default=0,
                    help="extra notification relays past the last updating node")
    ap.add_argument("--family",
                    choices=["bubble", "star", "complete-transposition",
                             "pancake", "hypercube", "torus", "circulant",
                             "borel"],
                    help="verify a single family instead of the default set")
    ap.add_argument("--order", type=int, nargs="+",
                    help="parameters of --family: p for bubble/star/pancake/"
                         "complete-transposition, k for hypercube, m [k] for "
                         "torus, n c1 c2 ... for circulant, p k for borel")
    ap.add_argument("--sample", type=int, default=0,
                    help="route this many random source-destination pairs "
                         "instead of all of them (0 = exhaustive)")
    args = ap.parse_args()

    if args.family:
        builders = {"bubble": bubble_sort, "star": star,
                    "complete-transposition": complete_transposition,
                    "pancake": pancake, "hypercube": hypercube,
                    "torus": torus, "borel": borel,
                    "circulant": lambda n, *c: circulant(n, list(c))}
        graph = builders[args.family](*(args.order or []))
        print(locality(graph, args.radius))
        print(verification(graph, args.radius, args.courtesy_hops,
                           sample=args.sample))
        print(overhead(graph, args.radius, args.courtesy_hops))
        return 0

    if args.self_test:
        return self_test()

    if args.table in ("locality", "all"):
        rows = [locality(g, args.radius) for g in LOCALITY_FAMILIES]
        report_locality(rows, args.latex)
    if args.table in ("verification", "all"):
        rows = [verification(g, args.radius, args.courtesy_hops)
                for g in VERIFICATION_FAMILIES]
        report_verification(rows, args.latex)
    if args.table in ("overhead", "all"):
        rows = [overhead(g, args.radius, args.courtesy_hops)
                for g in OVERHEAD_FAMILIES]
        report_overhead(rows, args.latex)
    return 0


if __name__ == "__main__":
    sys.exit(main())
