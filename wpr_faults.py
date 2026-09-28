#!/usr/bin/env python3
"""wpr_faults.py -- WPR control plane and forwarding under arbitrary failure
sets: several node and/or link failures, sequential or concurrent.

Companion to wpr_verify.py, which reproduces the single-failure tables of

    D. Aguirre-Guerrero, L. Fabrega, P. Vila,
    "Word-Processing-based Routing: A Fault-tolerant Routing Scheme for
     Cayley Graphs".

This module adds what the revised version of the paper needs:

  * failure elements: nodes (an int) and links (a pair (u, v) with u < v);
  * per-node failure tables holding both kinds of element, updated by the
    recording criteria of Algorithms 5-6 and relayed by Algorithms 7-8; the
    notification is simulated in synchronous rounds so that the notifications
    of several failures can overlap (concurrent failure model);
  * two forwarding rules: the published Algorithms 11-12 ("original"), and the
    revised rule in which the message header also carries the set A of
    failures avoided by the path it holds; a node recomputes only when its
    table is not contained in A and then avoids A := A U T_u ("trace");
  * a greedy, failure-oblivious baseline reproducing the behaviour of the RPS
    and GRWMS schemes (forward to the alive neighbour closest to the
    destination in the failure-free graph).

Requirements: Python 3.6 or later, standard library only.
"""
from collections import deque

from wpr_verify import INF  # noqa: F401  (re-exported for convenience)

EMPTY = "e_A"


# ---------------------------------------------------------------------------
# Failure elements
# ---------------------------------------------------------------------------

def link(u, v):
    """Canonical representation of the link between u and v."""
    return (u, v) if u < v else (v, u)


def is_link(x):
    return isinstance(x, tuple)


def split(failures):
    """(banned nodes, banned links) as frozensets."""
    return (frozenset(x for x in failures if not is_link(x)),
            frozenset(x for x in failures if is_link(x)))


# ---------------------------------------------------------------------------
# shortLex paths avoiding a failure set
# ---------------------------------------------------------------------------

class ShortLexF(object):
    """shortLex paths in Gamma \\ F for a fixed failure set F of nodes and
    links.  Distances to each target are computed once (BFS) and cached, so
    routing many messages towards the same destination is cheap.

    A shortLex path minimises length first and lexicographic order second, so
    it is obtained greedily on the shortest-path DAG: from the current node,
    take the smallest generator index whose (alive) link leads to a node one
    step closer to the target.  This is exactly the word returned by
    Algorithm D of the path-computation paper, without needing the automaton.
    """

    __slots__ = ("g", "nodes", "links", "_dist")

    def __init__(self, graph, failures=()):
        self.g = graph
        self.nodes, self.links = split(failures)
        self._dist = {}

    # -- distances -----------------------------------------------------------

    def dist_to(self, target):
        d = self._dist.get(target)
        if d is None:
            d = self._bfs(target)
            self._dist[target] = d
        return d

    def _bfs(self, source):
        g, nodes, links = self.g, self.nodes, self.links
        dist = [INF] * g.n
        if source in nodes:
            return dist
        dist[source] = 0
        queue = deque([source])
        if links:
            while queue:
                x = queue.popleft()
                dx = dist[x] + 1
                for y in g.adj[x]:
                    if (y not in nodes and dist[y] == INF
                            and link(x, y) not in links):
                        dist[y] = dx
                        queue.append(y)
        else:
            while queue:
                x = queue.popleft()
                dx = dist[x] + 1
                for y in g.adj[x]:
                    if y not in nodes and dist[y] == INF:
                        dist[y] = dx
                        queue.append(y)
        return dist

    def distance(self, u, v):
        return self.dist_to(v)[u]

    # -- shortLex words ------------------------------------------------------

    def _step(self, cur, d):
        """Smallest generator index leaving `cur` on a shortest path."""
        dc = d[cur] - 1
        links = self.links
        for i, y in enumerate(self.g.adj[cur]):
            if d[y] == dc and (not links or link(cur, y) not in links):
                return i, y
        return None, None

    def first_letter(self, u, v):
        """Index of the first generator of the shortLex path u -> v; None if
        no path exists (the symbol bot of the paper); EMPTY if u == v."""
        if u in self.nodes or v in self.nodes:
            return None
        d = self.dist_to(v)
        if d[u] == INF:
            return None
        if u == v:
            return EMPTY
        return self._step(u, d)[0]

    def path(self, u, v):
        """The shortLex word from u to v as a tuple of generator indices, or
        None if u and v are disconnected in Gamma \\ F."""
        if u in self.nodes or v in self.nodes:
            return None
        d = self.dist_to(v)
        if d[u] == INF:
            return None
        word, cur = [], u
        while cur != v:
            i, cur = self._step(cur, d)
            word.append(i)
        return tuple(word)


class Oracle(object):
    """Cache of ShortLexF objects, one per distinct failure set."""

    def __init__(self, graph):
        self.g = graph
        self.cache = {}

    def sl(self, failures):
        key = frozenset(failures)
        s = self.cache.get(key)
        if s is None:
            s = ShortLexF(self.g, key)
            self.cache[key] = s
        return s

    @property
    def clean(self):
        return self.sl(())


# ---------------------------------------------------------------------------
# Failure tables: the recording criteria of Algorithms 5 and 6
# ---------------------------------------------------------------------------

def add_failure(graph, table, x):
    """Insert x into a failure table with the bookkeeping of Algorithm 5
    (lines 3-7: a node failure supersedes the records of its links) and
    Algorithm 6 (lines 3-8: once every link of a node is recorded, the node
    itself is recorded instead)."""
    if is_link(x):
        table = table | {x}
        for v in x:
            incident = [y for y in table if is_link(y) and v in y]
            if len(incident) == graph.deg:
                table = (table - frozenset(incident)) | {v}
        return table
    incident = frozenset(y for y in table if is_link(y) and x in y)
    return (table - incident) | {x}


def ball(graph, centre, radius):
    """Nodes at distance 1..radius from `centre` in the failure-free graph."""
    if radius == 1:
        return [v for v in graph.adj[centre] if v != centre]
    d = ShortLexF(graph).dist_to(centre)
    return [v for v in range(graph.n) if 0 < d[v] <= radius]


def criterion(graph, oracle, u, x, table, radius=1):
    """Recording criterion at node u for the failure element x, given u's
    current table.  Algorithm 5 for a node failure, Algorithm 6 for a link
    failure.  `radius` widens the set of probed destinations from the
    neighbours of the failure (radius 1, as published) to every node within
    that distance of it (the strengthened criterion of the revision)."""
    if x in table:
        return False
    if is_link(x):
        if u in x:
            return True                      # incident: Algorithm 8, step 1
        probes = [v for v in x if v != u and v not in table]
    else:
        if u == x:
            return False
        if x in graph.adj[u]:
            return True                      # adjacent: Algorithm 7, step 1
        if any(is_link(y) and x in y for y in table):
            return True                      # Algorithm 5, lines 3-7
        probes = [v for v in ball(graph, x, radius)
                  if v != u and v not in table]
    base = oracle.sl(table)
    with_x = oracle.sl(table | {x})
    for v in probes:
        w1 = with_x.first_letter(u, v)
        w2 = base.first_letter(u, v)
        if w1 is None or w1 != w2:
            return True
    return False


def detectors(graph, x, alive_nodes=None):
    """Nodes that detect the failure of x directly (Algorithms 7-8, 'Upon')."""
    cand = list(x) if is_link(x) else [v for v in graph.adj[x] if v != x]
    if alive_nodes is not None:
        cand = [v for v in cand if v in alive_nodes]
    return sorted(set(cand))


# ---------------------------------------------------------------------------
# Notification (Algorithms 7-8), simulated in synchronous rounds
# ---------------------------------------------------------------------------

def notify(graph, oracle, failures, tables, all_failures=None, radius=1,
           courtesy=0, rng=None):
    """Run the notification of every element of `failures`, all detected at
    round 0 (so a list of several elements models CONCURRENT failures; call
    once per element, in order, for the SEQUENTIAL model).

    `tables` is a list of frozensets (one per node); a modified copy is
    returned.  `all_failures` is the set of elements that are actually down
    while the notification runs (messages sent to a failed node or over a
    failed link are lost); it defaults to `failures` plus every element already
    present in some table.  `rng`, when given, randomises the order in which
    the messages received in the same round are processed.

    Returns (tables, info) where info[x] = {"recorded": set of nodes holding
    x, "msgs": notification messages emitted for x, "rounds": rounds until x's
    notification converged} and info["rounds"] is the overall convergence
    time.
    """
    tables = list(tables)
    failures = list(failures)
    if all_failures is None:
        all_failures = set(failures)
        for t in tables:
            all_failures |= t
    down_nodes, down_links = split(all_failures)

    def alive_link(a, b):
        return b not in down_nodes and link(a, b) not in down_links

    seen = {x: set() for x in failures}
    recorded = {x: set() for x in failures}
    msgs = {x: 0 for x in failures}
    last_round = {x: 0 for x in failures}
    inbox = []
    for idx, x in enumerate(failures):
        for z in detectors(graph, x, alive_nodes=None):
            if z in down_nodes:
                continue
            tables[z] = add_failure(graph, tables[z], x)
            seen[x].add(z)
            recorded[x].add(z)
            for y in graph.adj[z]:
                if (is_link(x) and link(z, y) == x) or (not is_link(x) and y == x):
                    continue                 # not through the failed element
                msgs[x] += 1
                if alive_link(z, y):
                    inbox.append((idx, z, y, tables[z], 0))
    rounds = 0
    while inbox:
        rounds += 1
        if rng is not None:
            rng.shuffle(inbox)
        else:
            inbox.sort(key=lambda m: (m[0], m[1], m[2]))
        nxt = []
        for idx, z, u, tz, slack in inbox:
            x = failures[idx]
            last_round[x] = rounds           # a message about x was received
            if u in seen[x]:
                continue                     # repeated notification: ignored
            seen[x].add(u)
            update = criterion(graph, oracle, u, x, tables[u], radius)
            if update:
                tables[u] = add_failure(graph, tables[u], x)
                for y in sorted(tz - tables[u], key=repr):   # Alg. 7, lines 3-6
                    if criterion(graph, oracle, u, y, tables[u], radius):
                        tables[u] = add_failure(graph, tables[u], y)
                recorded[x].add(u)
                relay, new_slack = True, 0
            elif slack < courtesy:
                relay, new_slack = True, slack + 1
            else:
                relay = False
            if relay:
                for y in graph.adj[u]:
                    if y == z:
                        continue             # every port except the incoming one
                    msgs[x] += 1
                    if alive_link(u, y):
                        nxt.append((idx, u, y, tables[u], new_slack))
        inbox = nxt
    info = {x: dict(recorded=recorded[x], msgs=msgs[x], rounds=last_round[x])
            for x in failures}
    info["rounds"] = rounds
    return tables, info


def tables_after(graph, oracle, failures, model, radius=1, courtesy=0,
                 rng=None):
    """Failure tables once every notification has converged, under the
    'sequential' model (one failure at a time) or the 'concurrent' model (all
    at once)."""
    tables = [frozenset()] * graph.n
    if model == "sequential":
        for x in failures:
            tables, _ = notify(graph, oracle, [x], tables, radius=radius,
                               courtesy=courtesy, rng=rng)
        return tables
    tables, _ = notify(graph, oracle, list(failures), tables, radius=radius,
                       courtesy=courtesy, rng=rng)
    return tables


# ---------------------------------------------------------------------------
# Forwarding
# ---------------------------------------------------------------------------

def route(graph, oracle, src, dst, tables, failures, rule="trace",
          max_hops=None):
    """Forward one message from src to dst.

    rule = "original": Algorithms 11-12 as published (a node with a non-empty
                       table recomputes the path avoiding its own table).
    rule = "trace":    the header carries the set A of failures avoided by
                       the path it holds; a node recomputes only when its
                       table is not contained in A, and avoids A U T_u.

    Returns a dict with: status ("ok", "lost" or "loop"), hops, computations
    (number of shortLex computations, the source's included), and header_max
    (largest number of failure labels carried in the header).  "lost" covers
    a missing path and a hop into a failed element (dropped by the link
    layer).
    """
    max_hops = max_hops or 4 * graph.n
    down_nodes, down_links = split(failures)
    trace = (rule == "trace")

    def hop(cur, i):
        y = graph.adj[cur][i]
        if y in down_nodes or link(cur, y) in down_links:
            return None
        return y

    A = tables[src]
    word = oracle.sl(A).path(src, dst)
    computations, header_max = 1, len(A)
    if word is None:
        return dict(status="lost", hops=0, computations=computations,
                    header_max=header_max)
    nxt = hop(src, word[0])
    if nxt is None:
        return dict(status="lost", hops=1, computations=computations,
                    header_max=header_max)
    cur, header, hops = nxt, word[1:], 1
    history = set()
    while hops < max_hops:
        if not header:
            return dict(status="ok" if cur == dst else "lost", hops=hops,
                        computations=computations, header_max=header_max)
        t = tables[cur]
        if trace:
            recompute = not t <= A
            if recompute:
                A = A | t
        else:
            recompute = bool(t)
            if recompute:
                A = t
        if recompute:
            computations += 1
            header_max = max(header_max, len(A))
            word = oracle.sl(A).path(cur, dst)
            if word is None:
                return dict(status="lost", hops=hops, computations=computations,
                            header_max=header_max)
            i, header = word[0], word[1:]
        else:
            i, header = header[0], header[1:]
        nxt = hop(cur, i)
        if nxt is None:
            return dict(status="lost", hops=hops + 1, computations=computations,
                        header_max=header_max)
        cur = nxt
        hops += 1
        state = (cur, header, A)
        if state in history:
            return dict(status="loop", hops=hops, computations=computations,
                        header_max=header_max)
        history.add(state)
    return dict(status="loop", hops=hops, computations=computations,
                header_max=header_max)


def route_greedy(graph, oracle, src, dst, failures, max_hops=None):
    """Failure-oblivious greedy forwarding (the behaviour of RPS and GRWMS):
    at every node the message goes to the alive neighbour that is closest to
    the destination in the failure-free graph, ties broken by generator
    order.  The protocol is memoryless, so revisiting a node means an
    infinite loop."""
    max_hops = max_hops or 4 * graph.n
    down_nodes, down_links = split(failures)
    d = oracle.clean.dist_to(dst)
    cur, hops, visited = src, 0, {src}
    while cur != dst and hops < max_hops:
        best = None
        for y in graph.adj[cur]:
            if y in down_nodes or link(cur, y) in down_links:
                continue
            if best is None or d[y] < d[best]:
                best = y
        if best is None:
            return dict(status="lost", hops=hops)
        cur, hops = best, hops + 1
        if cur in visited:
            return dict(status="loop", hops=hops)
        visited.add(cur)
    return dict(status="ok" if cur == dst else "loop", hops=hops)


# ---------------------------------------------------------------------------
# Auditing a failure scenario
# ---------------------------------------------------------------------------

def connected_survivors(graph, oracle, failures):
    """Surviving nodes, and whether they are mutually connected in Gamma\\F."""
    down_nodes, _ = split(failures)
    survivors = [v for v in range(graph.n) if v not in down_nodes]
    if not survivors:
        return survivors, True
    d = oracle.sl(failures).dist_to(survivors[0])
    return survivors, all(d[v] != INF for v in survivors)


def audit(graph, oracle, failures, tables, pairs, rules=("original", "trace"),
          greedy=True):
    """Route every (s, t) in `pairs` under each rule and summarise.

    Returns {rule: stats} with stats = pairs, lost, loops, nonmin (delivered
    over a path longer than the distance in Gamma\\F), stretch_max,
    stretch_sum (extra hops summed over delivered messages), hops_sum,
    comp_sum (shortLex computations), header_max; and, if `greedy`, the same
    counters for the greedy baseline under key "greedy"."""
    truth = oracle.sl(failures)
    keys = list(rules) + (["greedy"] if greedy else [])
    stats = {k: dict(pairs=0, lost=0, loops=0, nonmin=0, stretch_max=0,
                     stretch_sum=0, hops_sum=0, comp_sum=0, header_max=0)
             for k in keys}
    for s, t in pairs:
        d = truth.dist_to(t)[s]
        for k in keys:
            if k == "greedy":
                r = route_greedy(graph, oracle, s, t, failures)
            else:
                r = route(graph, oracle, s, t, tables, failures, rule=k)
            st = stats[k]
            st["pairs"] += 1
            if r["status"] == "lost":
                st["lost"] += 1
            elif r["status"] == "loop":
                st["loops"] += 1
            else:
                st["hops_sum"] += r["hops"]
                if d != INF and r["hops"] > d:
                    st["nonmin"] += 1
                    st["stretch_sum"] += r["hops"] - d
                    st["stretch_max"] = max(st["stretch_max"], r["hops"] - d)
            if k != "greedy":
                st["comp_sum"] += r["computations"]
                st["header_max"] = max(st["header_max"], r["header_max"])
    return stats


def all_pairs(survivors):
    return ((s, t) for s in survivors for t in survivors if s != t)


def sample_pairs(survivors, count, rng, destinations=None):
    """`count` random ordered pairs of distinct survivors.  When `destinations`
    is given, targets are drawn from that many destinations only, which keeps
    the number of BFS computations (one per destination and failure set) low
    on large graphs."""
    if destinations:
        targets = rng.sample(survivors, min(destinations, len(survivors)))
    else:
        targets = survivors
    out = []
    while len(out) < count:
        s, t = rng.choice(survivors), rng.choice(targets)
        if s != t:
            out.append((s, t))
    return out


def merge(a, b):
    """Add the counters of stats b into a (same keys)."""
    for k, st in b.items():
        dst = a.setdefault(k, dict(pairs=0, lost=0, loops=0, nonmin=0,
                                   stretch_max=0, stretch_sum=0, hops_sum=0,
                                   comp_sum=0, header_max=0))
        for f, v in st.items():
            if f in ("stretch_max", "header_max"):
                dst[f] = max(dst[f], v)
            else:
                dst[f] += v
    return a
