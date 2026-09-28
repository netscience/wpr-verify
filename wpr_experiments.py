#!/usr/bin/env python3
"""wpr_experiments.py -- Experiments added in the revised version of

    D. Aguirre-Guerrero, L. Fabrega, P. Vila,
    "Word-Processing-based Routing: A Fault-tolerant Routing Scheme for
     Cayley Graphs".

Every experiment prints a text table and, with --csv DIR, also writes a CSV
file; --latex prints LaTeX tabular rows instead of the text table.

    two-failures   exhaustive sweep of every second failure (f1 = identity),
                   sequential and concurrent models, published vs. revised
                   forwarding rule, greedy baseline
    k-failures     random sets of k concurrent node (or link) failures
    mitigation     strengthened recording criterion (radius, courtesy hops):
                   criterion set vs. notified set, affected set, blind-spot
                   radius rho*, minimality
    large          single node failure on graphs of 10^4 - 4x10^5 nodes:
                   control-plane cost (exact), sampled routing, timings
    borel          Borel(47,23), 1081 nodes, 5-35 % random link failures
                   (the scenario of the RCRR evaluation), WPR vs. greedy
    greedy         greedy baseline under a single node failure, all families

Requirements: Python 3.6 or later, standard library only.
"""
import argparse
import csv
import os
import random
import sys
import time

import wpr_verify as W
import wpr_faults as F

INF = F.INF

FAMILIES = {
    "BS(4)": lambda: W.bubble_sort(4), "BS(5)": lambda: W.bubble_sort(5),
    "BS(6)": lambda: W.bubble_sort(6), "BS(7)": lambda: W.bubble_sort(7),
    "ST(4)": lambda: W.star(4), "ST(5)": lambda: W.star(5),
    "CT(4)": lambda: W.complete_transposition(4),
    "PC(4)": lambda: W.pancake(4), "PC(5)": lambda: W.pancake(5),
    "Q_4": lambda: W.hypercube(4), "Q_6": lambda: W.hypercube(6),
    "Q_8": lambda: W.hypercube(8), "Q_10": lambda: W.hypercube(10),
    "Torus 6x6": lambda: W.torus(6), "Torus 4x16": lambda: W.torus(4, 16),
    "Torus 8x8": lambda: W.torus(8), "Torus 14x14": lambda: W.torus(14),
    "Torus 10x10": lambda: W.torus(10), "Torus 12x12": lambda: W.torus(12),
    "Torus 16x16": lambda: W.torus(16), "Torus 20x20": lambda: W.torus(20),
    "C_20(1,2)": lambda: W.circulant(20, [1, 2]),
    "Borel(47,23)": lambda: W.borel(47, 23),
}
TABLE8 = ["BS(4)", "BS(5)", "ST(4)", "ST(5)", "CT(4)", "PC(4)", "PC(5)",
          "Q_4", "Torus 6x6", "Torus 4x16", "C_20(1,2)"]


def build(names):
    return [FAMILIES[n]() for n in names]


class Out(object):
    """Text / LaTeX / CSV reporting."""

    def __init__(self, args, name, columns):
        self.latex, self.columns = args.latex, columns
        self.rows = []
        self.csv = None
        if args.csv:
            os.makedirs(args.csv, exist_ok=True)
            self.csv = open(os.path.join(args.csv, name + ".csv"), "w",
                            newline="")
            self.writer = csv.writer(self.csv)
            self.writer.writerow(columns)
        if not self.latex:
            print("\n" + "  ".join("%-*s" % (w, c) for c, w in columns_widths(columns)))
            print("-" * (sum(w + 2 for _, w in columns_widths(columns))))

    def row(self, values):
        vals = [fmt(v) for v in values]
        if self.csv:
            self.writer.writerow(values)
        if self.latex:
            print(" & ".join(vals).replace("%", "\\%") + " \\\\")
        else:
            print("  ".join("%-*s" % (w, v) for v, (_, w) in
                            zip(vals, columns_widths(self.columns))))
        sys.stdout.flush()

    def close(self):
        if self.csv:
            self.csv.close()


def columns_widths(columns):
    return [(c, max(9, len(c))) for c in columns]


def fmt(v):
    if isinstance(v, float):
        return "%.2f" % v
    return str(v)


def pct(a, b):
    return 100.0 * a / b if b else 0.0


# ---------------------------------------------------------------------------
# two-failures: exhaustive over the second failure
# ---------------------------------------------------------------------------

def exp_two_failures(args):
    cols = ["graph", "n", "model", "rule", "f2 cases", "pairs", "lost",
            "loops", "loop %", "non-min", "non-min %", "stretch max",
            "comp/msg", "header max"]
    out = Out(args, "two_failures", cols)
    for g in build(args.families or TABLE8):
        oracle = F.Oracle(g)
        f1 = 0
        others = [v for v in range(g.n) if v != f1]
        rng = random.Random(args.seed)
        if args.f2_sample and args.f2_sample < len(others):
            f2s = rng.sample(others, args.f2_sample)
        else:
            f2s = others
        if args.links:
            # second failure = a link not incident to f1
            f2s = sorted({F.link(u, v) for u in others for v in g.adj[u]
                          if v != f1 and v != u})
            if args.f2_sample and args.f2_sample < len(f2s):
                f2s = rng.sample(f2s, args.f2_sample)
        totals = {}
        cases = 0
        t0 = time.time()
        for f2 in f2s:
            failures = frozenset((f1, f2))
            survivors, connected = F.connected_survivors(g, oracle, failures)
            if not connected:
                continue
            cases += 1
            for model in ("sequential", "concurrent"):
                tables = F.tables_after(g, oracle, [f1, f2], model)
                if args.pairs and args.pairs < len(survivors) ** 2:
                    pairs = F.sample_pairs(survivors, args.pairs, rng)
                else:
                    pairs = list(F.all_pairs(survivors))
                st = F.audit(g, oracle, failures, tables, pairs,
                             greedy=(model == "concurrent"))
                totals[model] = F.merge(totals.get(model, {}), st)
        for model in ("sequential", "concurrent"):
            for rule in ("original", "trace", "greedy"):
                if rule not in totals.get(model, {}):
                    continue
                s = totals[model][rule]
                delivered = s["pairs"] - s["lost"] - s["loops"]
                out.row([g.name, g.n, model, rule, cases, s["pairs"], s["lost"],
                         s["loops"], pct(s["loops"], s["pairs"]), s["nonmin"],
                         pct(s["nonmin"], s["pairs"]), s["stretch_max"],
                         (s["comp_sum"] / delivered) if (delivered and rule != "greedy") else 0.0,
                         s["header_max"]])
        if not args.latex:
            print("   [%s: %.1f s]" % (g.name, time.time() - t0))
    out.close()


# ---------------------------------------------------------------------------
# k-failures: random concurrent failure sets
# ---------------------------------------------------------------------------

def exp_k_failures(args):
    cols = ["graph", "n", "kind", "k", "sets", "connected sets", "pairs",
            "orig lost", "orig loops", "orig loop %", "trace lost",
            "trace loops", "trace non-min %", "trace stretch mean",
            "trace stretch max", "trace comp/msg", "header max",
            "greedy delivered %"]
    out = Out(args, "k_failures", cols)
    fractions = args.fractions or [0.01, 0.02, 0.05, 0.10]
    for g in build(args.families or TABLE8):
        oracle = F.Oracle(g)
        rng = random.Random(args.seed)
        if args.links:
            universe = sorted({F.link(u, v) for u in range(g.n) for v in g.adj[u]})
            kind = "links"
        else:
            universe = list(range(g.n))
            kind = "nodes"
        ks = sorted({max(2, int(round(fr * len(universe)))) for fr in fractions})
        for k in ks:
            totals, sets, connected_sets = {}, 0, 0
            t0 = time.time()
            for _ in range(args.sets):
                sets += 1
                failures = frozenset(rng.sample(universe, k))
                survivors, connected = F.connected_survivors(g, oracle, failures)
                if not connected or len(survivors) < 2:
                    continue
                connected_sets += 1
                tables = F.tables_after(g, oracle, sorted(failures, key=repr),
                                        "concurrent", rng=rng)
                if args.pairs and args.pairs < len(survivors) ** 2:
                    pairs = F.sample_pairs(survivors, args.pairs, rng,
                                           destinations=args.destinations)
                else:
                    pairs = list(F.all_pairs(survivors))
                st = F.audit(g, oracle, failures, tables, pairs)
                totals = F.merge(totals, st)
            if not totals:
                out.row([g.name, g.n, kind, k, sets, 0] + [0] * (len(cols) - 6))
                continue
            o, t, gr = totals["original"], totals["trace"], totals["greedy"]
            deliv_t = t["pairs"] - t["lost"] - t["loops"]
            out.row([g.name, g.n, kind, k, sets, connected_sets, t["pairs"],
                     o["lost"], o["loops"], pct(o["loops"], o["pairs"]),
                     t["lost"], t["loops"], pct(t["nonmin"], t["pairs"]),
                     (t["stretch_sum"] / deliv_t) if deliv_t else 0.0,
                     t["stretch_max"],
                     (t["comp_sum"] / deliv_t) if deliv_t else 0.0,
                     t["header_max"],
                     pct(gr["pairs"] - gr["lost"] - gr["loops"], gr["pairs"])])
            if not args.latex:
                print("   [%s k=%d: %.1f s]" % (g.name, k, time.time() - t0))
    out.close()


# ---------------------------------------------------------------------------
# mitigation: radius / courtesy hops, affected set, blind-spot radius
# ---------------------------------------------------------------------------

def affected_set(g, oracle, f):
    """Nodes u whose first hop towards some destination changes when f fails
    (or that lose the destination), and for each the smallest distance from f
    to a witnessing destination."""
    clean, faulty = oracle.clean, oracle.sl({f})
    df = clean.dist_to(f)
    rho = {}
    for u in range(g.n):
        if u == f:
            continue
        best = None
        for v in range(g.n):
            if v == f or v == u:
                continue
            w1 = faulty.first_letter(u, v)
            if w1 is None or w1 != clean.first_letter(u, v):
                if best is None or df[v] < best:
                    best = df[v]
                    if best == 1:
                        break
        if best is not None:
            rho[u] = best
    return rho


def exp_mitigation(args):
    cols = ["graph", "n", "affected", "rho*", "radius", "courtesy",
            "criterion set", "notified set", "notified >= affected", "msgs",
            "rounds", "pairs", "non-min", "stretch max"]
    out = Out(args, "mitigation", cols)
    for g in build(args.families or TABLE8):
        oracle = F.Oracle(g)
        f = 0
        rho = affected_set(g, oracle, f)
        affected = set(rho)
        rho_star = max(rho.values()) if rho else 0
        settings = [(1, 0), (2, 0), (2, 1), (1, 1)]
        if (rho_star, 1) not in settings:      # rho = rho*, c = 1
            settings.append((rho_star, 1))
        survivors = [v for v in range(g.n) if v != f]
        if args.pairs and args.pairs < len(survivors) ** 2:
            pairs = F.sample_pairs(survivors, args.pairs, random.Random(args.seed),
                                   destinations=args.destinations)
        else:
            pairs = list(F.all_pairs(survivors))
        for radius, courtesy in settings:
            crit = {u for u in survivors
                    if F.criterion(g, oracle, u, f, frozenset(), radius)}
            tables, info = F.notify(g, oracle, [f], [frozenset()] * g.n,
                                    radius=radius, courtesy=courtesy)
            notified = info[f]["recorded"]
            st = F.audit(g, oracle, frozenset([f]), tables, pairs,
                         rules=("trace",), greedy=False)["trace"]
            out.row([g.name, g.n, len(affected), rho_star, radius, courtesy,
                     len(crit), len(notified), "yes" if affected <= notified else "no",
                     info[f]["msgs"], info[f]["rounds"], st["pairs"],
                     st["nonmin"], st["stretch_max"]])
    out.close()


# ---------------------------------------------------------------------------
# large: control-plane cost and sampled routing on big graphs
# ---------------------------------------------------------------------------

LARGE = {
    "Torus 100x100": lambda: W.torus(100), "Torus 200x200": lambda: W.torus(200),
    "Q_14": lambda: W.hypercube(14), "Q_16": lambda: W.hypercube(16),
    "Q_18": lambda: W.hypercube(18),
    "BS(8)": lambda: W.bubble_sort(8), "ST(8)": lambda: W.star(8),
    "PC(8)": lambda: W.pancake(8), "BS(9)": lambda: W.bubble_sort(9),
    "Borel(47,23)": lambda: W.borel(47, 23),
}


def exp_large(args):
    cols = ["graph", "n", "deg", "build s", "notified", "msgs", "rounds",
            "flood", "share %", "notify s", "pairs", "lost", "loops",
            "non-min", "stretch max", "us/decision src", "us/decision int"]
    out = Out(args, "large", cols)
    rng = random.Random(args.seed)
    for name in (args.families or list(LARGE)):
        t0 = time.time()
        g = LARGE[name]() if name in LARGE else FAMILIES[name]()
        build_s = time.time() - t0
        oracle = F.Oracle(g)
        f = 0
        t0 = time.time()
        tables, info = F.notify(g, oracle, [f], [frozenset()] * g.n)
        notify_s = time.time() - t0
        flood = (g.n - 1) * (g.deg - 1)
        survivors = [v for v in range(g.n) if v != f]
        pairs = F.sample_pairs(survivors, args.pairs or 10000, rng,
                               destinations=args.destinations or 50)
        st = F.audit(g, oracle, frozenset([f]), tables, pairs,
                     rules=("trace",), greedy=False)["trace"]
        # timings: a source decision = one shortLex computation with a cold
        # distance cache (BFS from the destination); an intermediate node
        # with an empty table only pops a letter from the header.
        reps = 20
        t0 = time.time()
        for s, t in pairs[:reps]:
            F.ShortLexF(g).path(s, t)
        src_us = 1e6 * (time.time() - t0) / reps
        header = tuple(range(min(10, g.deg)))
        t0 = time.time()
        for _ in range(100000):
            i, header2 = header[0], header[1:]
            g.adj[0][i]
        int_us = 1e6 * (time.time() - t0) / 100000
        out.row([g.name, g.n, g.deg, build_s, len(info[f]["recorded"]),
                 info[f]["msgs"], info[f]["rounds"], flood,
                 pct(info[f]["msgs"], flood), notify_s, st["pairs"], st["lost"],
                 st["loops"], st["nonmin"], st["stretch_max"], src_us, int_us])
        del g, oracle, tables
    out.close()


# ---------------------------------------------------------------------------
# borel: the RCRR scenario
# ---------------------------------------------------------------------------

def exp_borel(args):
    cols = ["graph", "n", "links", "failed %", "reps", "pairs",
            "disconnected pairs %", "orig delivered %", "orig loops %",
            "trace delivered %", "trace non-min %", "trace stretch mean",
            "trace comp/msg", "header max", "greedy delivered %",
            "notified mean", "msgs mean", "rounds mean"]
    out = Out(args, "borel", cols)
    g = W.borel(47, 23)
    oracle = F.Oracle(g)
    links = sorted({F.link(u, v) for u in range(g.n) for v in g.adj[u]})
    rng = random.Random(args.seed)
    for pc in (args.percents or [5, 10, 15, 20, 25, 30, 35]):
        k = int(round(pc / 100.0 * len(links)))
        totals = {}
        disconnected_pairs = total_pairs = 0
        notified_sum = msgs_sum = rounds_sum = 0.0
        t0 = time.time()
        for _ in range(args.sets):
            failures = frozenset(rng.sample(links, k))
            truth = oracle.sl(failures)
            tables, info = F.notify(g, oracle, sorted(failures),
                                    [frozenset()] * g.n, rng=rng)
            notified_sum += len({u for u in range(g.n) if tables[u]})
            msgs_sum += sum(info[x]["msgs"] for x in failures)
            rounds_sum += info["rounds"]
            survivors = list(range(g.n))
            cand = F.sample_pairs(survivors, args.pairs or 5000, rng,
                                  destinations=args.destinations or 100)
            pairs = []
            for s, t in cand:
                total_pairs += 1
                if truth.dist_to(t)[s] == INF:
                    disconnected_pairs += 1
                else:
                    pairs.append((s, t))
            st = F.audit(g, oracle, failures, tables, pairs)
            totals = F.merge(totals, st)
        o, t, gr = totals["original"], totals["trace"], totals["greedy"]
        deliv_t = t["pairs"] - t["lost"] - t["loops"]
        out.row([g.name, g.n, len(links), pc, args.sets, t["pairs"],
                 pct(disconnected_pairs, total_pairs),
                 pct(o["pairs"] - o["lost"] - o["loops"], o["pairs"]),
                 pct(o["loops"], o["pairs"]),
                 pct(deliv_t, t["pairs"]), pct(t["nonmin"], t["pairs"]),
                 (t["stretch_sum"] / deliv_t) if deliv_t else 0.0,
                 (t["comp_sum"] / deliv_t) if deliv_t else 0.0, t["header_max"],
                 pct(gr["pairs"] - gr["lost"] - gr["loops"], gr["pairs"]),
                 notified_sum / args.sets, msgs_sum / args.sets,
                 rounds_sum / args.sets])
        if not args.latex:
            print("   [%d%%: %.1f s]" % (pc, time.time() - t0))
    out.close()


# ---------------------------------------------------------------------------
# greedy: single node failure, all families
# ---------------------------------------------------------------------------

def exp_greedy(args):
    cols = ["graph", "n", "pairs", "WPR delivered %", "WPR non-min",
            "greedy delivered %", "greedy loops", "greedy lost"]
    out = Out(args, "greedy", cols)
    for g in build(args.families or TABLE8):
        oracle = F.Oracle(g)
        f = 0
        tables, _ = F.notify(g, oracle, [f], [frozenset()] * g.n)
        survivors = [v for v in range(g.n) if v != f]
        st = F.audit(g, oracle, frozenset([f]), tables,
                     list(F.all_pairs(survivors)), rules=("trace",))
        w, gr = st["trace"], st["greedy"]
        out.row([g.name, g.n, w["pairs"],
                 pct(w["pairs"] - w["lost"] - w["loops"], w["pairs"]),
                 w["nonmin"],
                 pct(gr["pairs"] - gr["lost"] - gr["loops"], gr["pairs"]),
                 gr["loops"], gr["lost"]])
    out.close()


# ---------------------------------------------------------------------------
# self-test: recompute the quick tables and compare with the deposited CSVs
# ---------------------------------------------------------------------------

def self_test(args):
    """Recompute the deterministic tables that take seconds (greedy; mitigation
    and two-failures on the graphs of up to 64 nodes) and compare every value
    with the CSV files deposited with the paper (--reference DIR, default
    ../results)."""
    import io
    import contextlib
    here = os.path.dirname(os.path.abspath(__file__))
    ref = args.reference or (os.path.join(here, "results")
                             if os.path.isdir(os.path.join(here, "results"))
                             else os.path.join(here, "..", "results"))
    small = ["BS(4)", "ST(4)", "CT(4)", "PC(4)", "Q_4", "Torus 6x6",
             "Torus 4x16", "C_20(1,2)"]
    checks = [("greedy", exp_greedy, None), ("mitigation", exp_mitigation, small),
              ("two_failures", exp_two_failures, small)]
    ok = True
    for name, fn, fams in checks:
        path = os.path.join(ref, name + ".csv")
        if not os.path.exists(path):
            print("reference %s not found; skipped" % path)
            continue
        expected = {}
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                key = tuple(r.get(k, "") for k in ("graph", "model", "rule", "radius", "courtesy"))
                expected[key] = r
        tmp = os.path.join(ref, "_selftest")
        os.makedirs(tmp, exist_ok=True)
        sub = argparse.Namespace(**vars(args))
        sub.csv, sub.latex, sub.families = tmp, False, fams
        sub.f2_sample, sub.pairs, sub.destinations, sub.links = 0, 0, 0, False
        with contextlib.redirect_stdout(io.StringIO()):
            fn(sub)
        with open(os.path.join(tmp, name + ".csv"), newline="") as f:
            for r in csv.DictReader(f):
                key = tuple(r.get(k, "") for k in ("graph", "model", "rule", "radius", "courtesy"))
                e = expected.get(key)
                if e is None:
                    continue
                for col, v in r.items():
                    if col in e and e[col] != v:
                        try:
                            same = abs(float(e[col]) - float(v)) < 1e-6
                        except ValueError:
                            same = False
                        if not same:
                            ok = False
                            print("MISMATCH %s %s %s: got %s expected %s"
                                  % (name, key, col, v, e[col]))
        print("%s: checked" % name)
    print("self-test: %s" % ("all deposited figures reproduced" if ok
                             else "DISCREPANCIES FOUND"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("experiment", choices=["two-failures", "k-failures",
                                           "mitigation", "large", "borel",
                                           "greedy", "self-test"])
    ap.add_argument("--reference", help="self-test: directory with the deposited CSVs "
                                        "(default: results/ next to this script)")
    ap.add_argument("--families", nargs="+", help="graph names (see FAMILIES)")
    ap.add_argument("--links", action="store_true",
                    help="link failures instead of node failures")
    ap.add_argument("--f2-sample", type=int, default=0,
                    help="two-failures: number of second failures (0 = all)")
    ap.add_argument("--fractions", type=float, nargs="+",
                    help="k-failures: failed fractions of the element set")
    ap.add_argument("--percents", type=int, nargs="+",
                    help="borel: failed link percentages")
    ap.add_argument("--sets", type=int, default=20,
                    help="k-failures/borel: random failure sets per level")
    ap.add_argument("--pairs", type=int, default=0,
                    help="pairs routed per scenario (0 = exhaustive)")
    ap.add_argument("--destinations", type=int, default=0,
                    help="sampled pairs are drawn towards this many targets")
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--latex", action="store_true")
    ap.add_argument("--csv", help="directory for CSV output")
    args = ap.parse_args()
    if args.experiment == "self-test":
        return self_test(args)
    {"two-failures": exp_two_failures, "k-failures": exp_k_failures,
     "mitigation": exp_mitigation, "large": exp_large, "borel": exp_borel,
     "greedy": exp_greedy}[args.experiment](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
