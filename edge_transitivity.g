###########################################################################
##  edge_transitivity.g
##
##  Rigorous check of the edge-transitivity claims reported in the
##  verification table of the WPR paper.
##
##  The Python verification script (wpr_verify.py) does not decide
##  edge-transitivity: it only routes messages. Edge-transitivity is settled
##  here, by computing the full automorphism group of each Cayley graph with
##  GRAPE (which calls nauty) and testing whether it acts transitively on
##  the edge set.
##
##  Requirements: GAP 4.11 or later with the GRAPE package.
##      gap -q edge_transitivity.g
##
##  Note on scope: Aut(Gamma) is the automorphism group of the GRAPH, which
##  may be strictly larger than the group of automorphisms of G preserving
##  S. Deciding edge-transitivity therefore genuinely needs a graph-theoretic
##  computation, which is why this is not folded into the Python script.
###########################################################################

LoadPackage("grape");;

###########################################################################
##  Cayley graph constructors
###########################################################################

CayleyGraphOfGroup := function(G, S)
    # Undirected Cayley graph of G with connection set S (assumed inverse
    # closed and identity free).
    local elts;
    elts := Elements(G);
    return Graph(Group(()), [1 .. Length(elts)], OnPoints,
                 function(i, j)
                     return elts[i] <> elts[j] and
                            elts[i]^-1 * elts[j] in S;
                 end, true);
end;;

BubbleSortGraph := function(p)
    local S;
    S := List([1 .. p - 1], i -> (i, i + 1));
    return CayleyGraphOfGroup(SymmetricGroup(p), S);
end;;

StarGraph := function(p)
    local S;
    S := List([2 .. p], i -> (1, i));
    return CayleyGraphOfGroup(SymmetricGroup(p), S);
end;;

CompleteTranspositionGraph := function(p)
    local S;
    S := Filtered(Elements(SymmetricGroup(p)),
                  g -> CycleStructurePerm(g) = [1]);
    return CayleyGraphOfGroup(SymmetricGroup(p), S);
end;;

PancakeGraph := function(p)
    local S, k, l;
    S := [];
    for k in [2 .. p] do
        l := PermList(Concatenation(Reversed([1 .. k]), [k + 1 .. p]));
        Add(S, l);
    od;
    return CayleyGraphOfGroup(SymmetricGroup(p), S);
end;;

HypercubeGraph := function(k)
    local G, S, gens;
    G := AbelianGroup(IsPermGroup, List([1 .. k], i -> 2));
    gens := GeneratorsOfGroup(G);
    S := ShallowCopy(gens);
    return CayleyGraphOfGroup(G, S);
end;;

TorusGraph := function(m, k)
    local G, gens, S;
    G := AbelianGroup(IsPermGroup, [m, k]);
    gens := GeneratorsOfGroup(G);
    S := [gens[1], gens[1]^-1, gens[2], gens[2]^-1];
    return CayleyGraphOfGroup(G, S);
end;;

CirculantGraph := function(n, conns)
    local G, g, S, c;
    G := CyclicGroup(IsPermGroup, n);
    g := GeneratorsOfGroup(G)[1];
    S := [];
    for c in conns do
        Add(S, g^c);
        Add(S, g^(-c));
    od;
    return CayleyGraphOfGroup(G, S);
end;;

###########################################################################
##  Edge-transitivity test
###########################################################################

IsEdgeTransitiveGraph := function(gamma)
    local A, edges, orbits;
    A := AutomorphismGroup(gamma);
    edges := Set(UndirectedEdges(gamma));
    orbits := Orbits(A, edges, OnSets);
    return [Length(orbits) = 1, Length(orbits), Size(A)];
end;;

###########################################################################
##  Report
###########################################################################

cases := [
    ["BS(4)      bubble-sort",        BubbleSortGraph(4)],
    ["BS(5)      bubble-sort",        BubbleSortGraph(5)],
    ["ST(4)      star",               StarGraph(4)],
    ["ST(5)      star",               StarGraph(5)],
    ["CT(4)      compl. transp.",     CompleteTranspositionGraph(4)],
    ["PC(4)      pancake",            PancakeGraph(4)],
    ["PC(5)      pancake",            PancakeGraph(5)],
    ["Q_4        hypercube",          HypercubeGraph(4)],
    ["Torus 6x6",                     TorusGraph(6, 6)],
    ["Torus 4x16",                    TorusGraph(4, 16)],
    ["C_20(1,2)  circulant",          CirculantGraph(20, [1, 2])]
];;

ReportGraph := function(label, gamma)
    local res;
    res := IsEdgeTransitiveGraph(gamma);
    Print(String(label, -24), " ",
          String(gamma.order, 6), " ",
          String(Length(Adjacency(gamma, 1)), 5), "   ",
          String(String(res[1]), 15), "   ",
          String(res[2], 11), "   ",
          String(res[3], 12), "\n");
end;;

Print("\n");
Print("graph                         n   deg   edge-transitive   edge-orbits         |Aut|\n");
Print("-----------------------------------------------------------------------------------\n");
for c in cases do
    ReportGraph(c[1], c[2]);
od;
Print("\n");
QUIT;
