#############################################################################
##
##  wda_cost.g
##
##  Size and wall-clock cost of the shortlex automatic structure (word
##  acceptor + word-difference automata, computed by KBMAG) of the groups
##  behind the Cayley graphs used in the paper.
##
##  Requirements: GAP >= 4.12 with the kbmag package (tested: GAP 4.15.1,
##  kbmag 1.5.11, macOS/arm64).
##
##  Files in this directory:
##    wda_cost.g      this script (measurement + report)
##    run_wda.py      driver: one GAP process per case under a wall-clock cap
##    build_patch.sh  builds kbmag_patch/bin (patched gpaxioms/autgroup)
##    wda_verify.g    independent check of the word acceptors (BFS normal forms)
##    wda_wacheck.g   same check for acceptor files in kbmag_out/ (ST8, PC8)
##    wda_brute.g     WA / diff1c / diff2c sizes computed without kbmag
##    wda_cost.csv    raw results (one row per attempt), wda_cost.txt: report
##    wda_verify.txt, wda_brute.txt: outputs of the checks; logs/: per-case logs
##
##  Usage (run from this directory, stdin from /dev/null):
##
##    WDA_CASE=list   gap -q -b wda_cost.g < /dev/null   # list case ids
##    WDA_CASE=BS6    gap -q -b wda_cost.g < /dev/null   # run one case, append a
##                                                       # row to wda_cost.csv
##    WDA_LARGE=1 WDA_CASE=BS6 gap ...                   # same, with the "large"
##                                                       # option of AutomaticStructure
##    WDA_MAXWDIFFS=200000 WDA_LARGE=1 WDA_CASE=ST8 gap ... # same, and raise kbmag's
##                                                       # word-difference limit (see below)
##    WDA_CASE=report gap -q -b wda_cost.g < /dev/null   # rebuild wda_cost.txt from
##                                                       # wda_cost.csv
##    gap -q -b wda_cost.g < /dev/null                   # run every case in one
##                                                       # process (no time cap!)
##
##  The companion driver run_wda.py runs each case in a fresh GAP process under
##  a wall-clock cap (default 600 s), retries with the large option and then
##  with large + WDA_MAXWDIFFS=200000 when AutomaticStructure returns false,
##  and records "timeout" rows.  build_patch.sh prepares kbmag_patch/bin (see
##  below); wda_verify.g checks the word acceptors independently.
##
##  WDA_MAXWDIFFS=N sets OptionsRecordOfKBMAGRewritingSystem(R).maxwdiffs := N
##  (honoured by kbprog through the rws file) and, through the patched autgroup
##  script in kbmag_patch/bin, passes "-mwd N" to gpmakefsa.  kbmag's defaults
##  (512 for kbprog, grown at tidying time; a fixed limit in gpmakefsa) are too
##  small for Sym_8 on star or pancake generators.
##
##  What is measured for each group G = <S | R>:
##    * R := KBMAGRewritingSystem(G) with the default shortlex ordering.  The
##      alphabet is S in the listed order; kbmag adds an inverse letter right
##      after each generator that is not declared involutory by a literal g^2
##      relator (so involutory generating sets keep |alphabet| = |S|).
##    * ok := AutomaticStructure(R) [or AutomaticStructure(R, true)], timed
##      with NanosecondsSinceEpoch (wall clock).  Internally this runs the
##      standalone programs  autgroup  (kbprog -wd, gpmakefsa, gpaxioms) and
##      then  gpminkb, and reads the resulting automata into GAP.
##    * wa_states     = states of WordAcceptor(R)                   (file .wa)
##    * diff1_states  = states of FirstWordDifferenceAutomaton(R)   (file .diff1c:
##                      the *correct minimal* first word-difference machine
##                      produced by gpminkb from the minimal confluent
##                      rewriting system)
##    * diff2_states  = states of SecondWordDifferenceAutomaton(R)  (file .diff2:
##                      the second word-difference machine as produced by
##                      kbprog -wd and corrected by gpmakefsa; it is closed
##                      under inversion and may contain word differences that
##                      are not needed by the final multiplier)
##    * diff2c_states = states of the corrected minimal second word-difference
##                      machine written by gpminkb (file .diff2c; kbmag's GAP
##                      interface does not expose it, so it is read from the
##                      file before the temporary files are deleted)
##    * gm_states     = states of the general multiplier (file .gm)
##    * diff1kb_states= states of the first word-difference machine as output
##                      by kbprog -wd (file .diff1), before correction
##    * seconds_total = wall clock of the AutomaticStructure(...) call
##    * seconds_autgroup / seconds_gpminkb = wall clock of the two external
##                      programs (the remainder of seconds_total is GAP parsing
##                      the automata files)
##    * size_check    = Size(R) (number of words accepted by the word acceptor)
##                      equals the expected group order
##
#############################################################################

LoadPackage("kbmag");
SetInfoLevel(InfoRWS, 1);   # the external programs report their progress
                            # (and state counts) on stdout -> case logs
SetPrintFormattingStatus("*stdout*", false);   # no 80-column line wrapping

WDA_DIR := DirectoryCurrent();
WDA_CSV := Filename(WDA_DIR, "wda_cost.csv");
WDA_TXT := Filename(WDA_DIR, "wda_cost.txt");

WDA_Env := function(name, default)
  if IsBound(GAPInfo.SystemEnvironment.(name)) then
    return GAPInfo.SystemEnvironment.(name);
  fi;
  return default;
end;

WDA_MAXWDIFFS := WDA_Env("WDA_MAXWDIFFS", "");   # "" = kbmag defaults

WDA_HEADER := [ "case", "family", "param", "order", "nS", "alphabet", "large", "maxwdiffs",
  "success", "wa_states", "diff1_states", "diff2_states", "diff2c_states",
  "gm_states", "diff1kb_states", "seconds_total", "seconds_autgroup",
  "seconds_gpminkb", "seconds_build", "size_check", "notes" ];

#############################################################################
##  Wrap Exec so that (a) each external program call is timed and (b) kbmag's
##  final "/bin/rm -f <tmp>*" is skipped, so the .diff2c/.gm/.diff1 files can
##  be inspected.  The temporary files live in a DirectoryTemporary(), which
##  GAP removes on exit; WDA_RunCase also removes them explicitly.
#############################################################################
WDA_OrigExec := Exec;
WDA_ExecLog := [];
MakeReadWriteGlobal("Exec");
Exec := function(arg)
  local cmd, t0;
  cmd := JoinStringsWithSeparator(List(arg, String), " ");
  if Length(cmd) >= 7 and cmd{[1..7]} = "/bin/rm" then
    return;
  fi;
  t0 := NanosecondsSinceEpoch();
  WDA_OrigExec(cmd);
  Add(WDA_ExecLog, rec(cmd := cmd, seconds := (NanosecondsSinceEpoch() - t0) / 10^9));
end;
MakeReadOnlyGlobal("Exec");

## kbmag's gpaxioms builds the names of its temporary multiplier files in
## 100-byte buffers (gpaxioms.c: static char inf[100], outf[100]; names are
## "<file>.m<word suffix>").  With GAP's default temporary path
## (/var/folders/.../gaptempdirXXXXXX/..., ~70 characters) the buffer
## overflows for relators of length >~ 25 and gpaxioms dies with SIGTRAP, so
## AutomaticStructure returns false for e.g. <a,b | a^50, b^50, [a,b]>.
## Work-around: a short *relative* path inside this directory (Exec runs in
## the current directory), set per case in WDA_RunCase.
WDA_TMPREL := "wdatmp";
if not IsDirectoryPath(WDA_TMPREL) then CreateDir(WDA_TMPREL); fi;

## Even with a short path, relator sides of >= ~45 letters (a^100 in
## Z_100 x Z_100) overflow those buffers.  build_patch.sh rebuilds gpaxioms
## with 4096-byte buffers into kbmag_patch/bin (plus symlinks to the other
## package binaries); when that directory exists it is used instead of the
## package binaries.  Rows computed with it carry "[patched gpaxioms]" in
## their notes.
WDA_PATCHBIN := "kbmag_patch/bin";
WDA_USES_PATCH := IsExistingFile(Concatenation(WDA_PATCHBIN, "/gpaxioms")) and
                  IsExistingFile(Concatenation(WDA_PATCHBIN, "/autgroup"));
if WDA_USES_PATCH then
  _KBExtDir := [Directory(WDA_PATCHBIN)];
  Print("#WDA using kbmag binaries in ", WDA_PATCHBIN, " (gpaxioms with enlarged buffers)\n");
fi;

#############################################################################
##  Helpers
#############################################################################

# seconds (rational or float) -> string with 2 decimals
WDA_Fmt2 := function(x)
  local n, q, r, s;
  if IsString(x) then return x; fi;
  n := Int(Round(Float(x) * 100));
  q := QuoInt(n, 100); r := RemInt(n, 100);
  s := String(r); if Length(s) < 2 then s := Concatenation("0", s); fi;
  return Concatenation(String(q), ".", s);
end;

# number of states recorded in the "states := rec( ... size := N ..." block
# of a kbmag FSA file, read line by line (the files can be large)
WDA_StatesInFSAFile := function(fname)
  local s, line, instates, pos, rest, i;
  if not IsExistingFile(fname) then return ""; fi;
  s := InputTextFile(fname);
  instates := false;
  line := ReadLine(s);
  while line <> fail do
    if PositionSublist(line, "states := rec(") <> fail then
      instates := true;
    elif instates and PositionSublist(line, "size :=") <> fail then
      pos := PositionSublist(line, "size :=");
      rest := line{[pos + 7 .. Length(line)]};
      i := PositionProperty(rest, IsDigitChar);
      if i = fail then break; fi;
      rest := rest{[i .. Length(rest)]};
      i := PositionProperty(rest, c -> not IsDigitChar(c));
      if i = fail then i := Length(rest) + 1; fi;
      CloseStream(s);
      return Int(rest{[1 .. i - 1]});
    fi;
    line := ReadLine(s);
  od;
  CloseStream(s);
  return "";
end;

WDA_CSVField := function(x)
  local s;
  if IsString(x) then s := ShallowCopy(x);
  elif IsInt(x) then s := String(x);
  elif IsFloat(x) or IsRat(x) then s := WDA_Fmt2(x);
  else s := String(x); fi;
  s := ReplacedString(s, ",", ";");
  s := ReplacedString(s, "\n", " ");
  return s;
end;

# write lines verbatim (AppendTo/PrintTo would wrap long lines at 80 columns)
WDA_WriteLines := function(fname, append, lines)
  local s, l;
  s := OutputTextFile(fname, append);
  SetPrintFormattingStatus(s, false);
  for l in lines do WriteLine(s, l); od;
  CloseStream(s);
end;

WDA_AppendRow := function(row)
  local line;
  if not IsExistingFile(WDA_CSV) then
    WDA_WriteLines(WDA_CSV, false, [JoinStringsWithSeparator(WDA_HEADER, ",")]);
  fi;
  line := JoinStringsWithSeparator(List(WDA_HEADER, h -> WDA_CSVField(row.(h))), ",");
  WDA_WriteLines(WDA_CSV, true, [line]);
  Print("#WDA ROW ", line, "\n");
end;

WDA_SecondsOf := function(progname)
  local e;
  for e in WDA_ExecLog do
    if PositionSublist(e.cmd, Concatenation("/", progname, " ")) <> fail then
      return e.seconds;
    fi;
  od;
  return "";
end;

#############################################################################
##  Group constructions.  Each returns rec(G, order, nS, desc) where G is an
##  fp group on a free group with named generators (in the order of S).
#############################################################################

# 1. Bubble-sort graph BS(p): Sym_p on the adjacent transpositions s_i=(i,i+1),
#    Coxeter presentation of type A_{p-1}.
WDA_BubbleSort := function(p)
  local F, s, rels, i, j;
  F := FreeGroup(List([1 .. p - 1], i -> Concatenation("s", String(i))));
  s := GeneratorsOfGroup(F);
  rels := List(s, x -> x^2);
  for i in [1 .. p - 2] do Add(rels, (s[i] * s[i + 1])^3); od;
  for i in [1 .. p - 1] do
    for j in [i + 2 .. p - 1] do Add(rels, (s[i] * s[j])^2); od;
  od;
  return rec(G := F / rels, order := Factorial(p), nS := p - 1,
             desc := Concatenation("Sym_", String(p), ", adjacent transpositions, Coxeter presentation A_",
                                   String(p - 1)));
end;

# Sym_p on exactly the listed permutations, presentation obtained with
# IsomorphismFpGroupByGenerators, transported to a free group with the given
# generator names.  Involutory generators get an explicit g^2 relator (kbmag
# only recognises involutions from a literal g^2), the relators are checked
# to hold in Sym_p, and the fp group order is verified by coset enumeration
# in WDA_RunCase.
WDA_SymOnPerms := function(p, perms, names, desc)
  local S, iso, Fp, F, fgens, rels, i, r;
  S := SymmetricGroup(p);
  if Group(perms) <> S then Error("perms do not generate Sym_", p); fi;
  iso := IsomorphismFpGroupByGenerators(S, perms);
  Fp := Range(iso);
  if List(GeneratorsOfGroup(Fp), f -> PreImagesRepresentative(iso, f)) <> perms then
    Error("generators of the fp group do not correspond to the listed permutations");
  fi;
  F := FreeGroup(names);
  fgens := GeneratorsOfGroup(F);
  rels := List(RelatorsOfFpGroup(Fp),
               r -> MappedWord(r, FreeGeneratorsOfFpGroup(Fp), fgens));
  for i in [1 .. Length(perms)] do
    if Order(perms[i]) = 2 and not fgens[i]^2 in rels then
      Add(rels, fgens[i]^2, 1);
    fi;
  od;
  rels := DuplicateFreeList(Filtered(rels, r -> not IsOne(r)));
  for r in rels do
    if not IsOne(MappedWord(r, fgens, perms)) then
      Error("relator ", r, " does not hold in Sym_", p);
    fi;
  od;
  return rec(G := F / rels, order := Factorial(p), nS := Length(perms), desc := desc);
end;

# 2. Star graph ST(p): star transpositions t_i = (1,i), i = 2..p.
WDA_Star := function(p)
  return WDA_SymOnPerms(p, List([2 .. p], i -> (1, i)),
    List([2 .. p], i -> Concatenation("t", String(i))),
    Concatenation("Sym_", String(p), ", star transpositions (1 i), presentation via IsomorphismFpGroupByGenerators"));
end;

# 3. Complete-transposition graph CT(p): all transpositions, lexicographic order.
WDA_CompleteTransposition := function(p)
  local pairs;
  pairs := Filtered(Tuples([1 .. p], 2), t -> t[1] < t[2]);
  return WDA_SymOnPerms(p, List(pairs, t -> (t[1], t[2])),
    List(pairs, t -> Concatenation("t", String(t[1]), String(t[2]))),
    Concatenation("Sym_", String(p), ", all transpositions, presentation via IsomorphismFpGroupByGenerators"));
end;

# 4. Pancake graph PC(p): prefix reversals r_k, k = 2..p.
WDA_Pancake := function(p)
  return WDA_SymOnPerms(p,
    List([2 .. p], k -> Product([1 .. Int(k / 2)], i -> (i, k + 1 - i))),
    List([2 .. p], k -> Concatenation("r", String(k))),
    Concatenation("Sym_", String(p), ", prefix reversals r_2..r_", String(p), ", presentation via IsomorphismFpGroupByGenerators"));
end;

# 5. Hypercube Q_k: (Z_2)^k on the standard basis.
WDA_Hypercube := function(k)
  local F, a, rels, i, j;
  F := FreeGroup(List([1 .. k], i -> Concatenation("a", String(i))));
  a := GeneratorsOfGroup(F);
  rels := List(a, x -> x^2);
  for i in [1 .. k] do
    for j in [i + 1 .. k] do Add(rels, Comm(a[i], a[j])); od;
  od;
  return rec(G := F / rels, order := 2^k, nS := k,
             desc := Concatenation("(Z_2)^", String(k), ", standard basis"));
end;

# 6. 2D torus Z_m x Z_m.
WDA_Torus := function(m)
  local F, a, b;
  F := FreeGroup("a", "b");
  a := F.1; b := F.2;
  return rec(G := F / [a^m, b^m, Comm(a, b)], order := m^2, nS := 2,
             desc := Concatenation("Z_", String(m), " x Z_", String(m), " = <a,b | a^m, b^m, [a,b]>"));
end;

# 7. Circulant C_20(1,2): Z_20 with a = 1, b = 2.
WDA_Circulant20 := function(dummy)
  local F, a, b;
  F := FreeGroup("a", "b");
  a := F.1; b := F.2;
  return rec(G := F / [a^20, a^2 * b^-1], order := 20, nS := 2,
             desc := "Z_20 = <a,b | a^20, a^2 = b>  (C_20(1,2))");
end;

# 8. Borel Cayley graph Borel(47,23): {[[a,b],[0,1]] : a in <g> <= Z_47^*, |<g>| = 23}
#    x = diag(g,1), y = [[1,1],[0,1]];  x y x^-1 = y^g.
WDA_Borel := function(dummy)
  local q, k, g, F, x, y;
  q := 47; k := 23;
  g := First([2 .. q - 1], t -> OrderMod(t, q) = k);
  if g <> 2 then Print("#WDA note: smallest element of order 23 mod 47 is ", g, "\n"); fi;
  F := FreeGroup("x", "y");
  x := F.1; y := F.2;
  return rec(G := F / [x^k, y^q, x * y * x^-1 * y^-g], order := q * k, nS := 2,
             desc := Concatenation("Z_47 x| Z_23 = <x,y | x^23, y^47, x y x^-1 = y^", String(g), ">"));
end;

#############################################################################
##  Case list (cheap families first).
#############################################################################
WDA_CASES := [];
WDA_Thunk := function(f, x) return function() return f(x); end; end;
# order and nS are the expected group order and number of generators (used
# by the driver to fill in rows for cases that timed out); both are verified
# against the constructed group in WDA_RunCase.
WDA_AddCase := function(id, family, param, order, nS, f)
  Add(WDA_CASES, rec(id := id, family := family, param := param, order := order,
                     nS := nS, build := WDA_Thunk(f, param)));
end;

for k in [4, 6, 8, 10, 12, 14, 16] do
  WDA_AddCase(Concatenation("Q", String(k)), "hypercube Q_k", k, 2^k, k, WDA_Hypercube);
od;
for m in [4, 6, 8, 14, 20, 50, 100] do
  WDA_AddCase(Concatenation("T", String(m)), "torus Z_m x Z_m", m, m^2, 2, WDA_Torus);
od;
WDA_AddCase("C20", "circulant C_20(1;2)", 20, 20, 2, WDA_Circulant20);
WDA_AddCase("Borel47", "Borel(47;23)", 47, 1081, 2, WDA_Borel);
for p in [4, 5, 6] do
  WDA_AddCase(Concatenation("BS", String(p)), "bubble-sort BS(p)", p, Factorial(p), p - 1, WDA_BubbleSort);
od;
for p in [4, 5, 6] do
  WDA_AddCase(Concatenation("ST", String(p)), "star ST(p)", p, Factorial(p), p - 1, WDA_Star);
od;
WDA_AddCase("CT4", "complete-transposition CT(p)", 4, 24, 6, WDA_CompleteTransposition);
for p in [4, 5, 6] do
  WDA_AddCase(Concatenation("PC", String(p)), "pancake PC(p)", p, Factorial(p), p - 1, WDA_Pancake);
od;
WDA_AddCase("BS7", "bubble-sort BS(p)", 7, Factorial(7), 6, WDA_BubbleSort);
WDA_AddCase("ST7", "star ST(p)", 7, Factorial(7), 6, WDA_Star);
WDA_AddCase("PC7", "pancake PC(p)", 7, Factorial(7), 6, WDA_Pancake);
WDA_AddCase("BS8", "bubble-sort BS(p)", 8, Factorial(8), 7, WDA_BubbleSort);
WDA_AddCase("ST8", "star ST(p)", 8, Factorial(8), 7, WDA_Star);
WDA_AddCase("PC8", "pancake PC(p)", 8, Factorial(8), 7, WDA_Pancake);

WDA_CaseById := function(id)
  local c;
  for c in WDA_CASES do if c.id = id then return c; fi; od;
  return fail;
end;

#############################################################################
##  Running one case
#############################################################################
WDA_RunCase := function(c, large)
  local row, h, tb0, bld, G, sz, R, t0, ok, wa, d1, d2, base;
  row := rec();
  for h in WDA_HEADER do row.(h) := ""; od;
  row.case := c.id; row.family := c.family; row.param := c.param;
  row.large := large;
  Print("#WDA case ", c.id, " (", c.family, ", param ", c.param, "), large = ", large, "\n");

  # --- build the fp group and verify its order by coset enumeration
  tb0 := NanosecondsSinceEpoch();
  bld := c.build();
  G := bld.G;
  sz := Size(G);
  row.seconds_build := (NanosecondsSinceEpoch() - tb0) / 10^9;
  row.order := sz; row.nS := bld.nS;
  row.notes := bld.desc;
  if WDA_USES_PATCH then row.notes := Concatenation("[patched gpaxioms] ", row.notes); fi;
  Print("#WDA presentation: ", Length(GeneratorsOfGroup(G)), " generators, ",
        Length(RelatorsOfFpGroup(G)), " relators, total relator length ",
        Sum(List(RelatorsOfFpGroup(G), Length)), "; Size(G) = ", sz, "\n");
  if sz <> bld.order or bld.order <> c.order or bld.nS <> c.nS then
    row.success := "build-error";
    row.notes := Concatenation("fp group has order ", String(sz), " but expected ",
                               String(bld.order), " (case record: ", String(c.order), ")");
    WDA_AppendRow(row);
    return row;
  fi;

  # --- rewriting system, shortlex (default), alphabet = generators (+ inverses)
  R := KBMAGRewritingSystem(G);
  row.alphabet := Length(Alphabet(R));
  Print("#WDA alphabet (", row.alphabet, " letters): ", Alphabet(R), "  ordering: ", R!.ordering, "\n");

  if WDA_MAXWDIFFS <> "" then
    OptionsRecordOfKBMAGRewritingSystem(R).maxwdiffs := Int(WDA_MAXWDIFFS);
    row.maxwdiffs := Int(WDA_MAXWDIFFS);
    row.notes := Concatenation("[maxwdiffs=", WDA_MAXWDIFFS, "] ", row.notes);
    Print("#WDA maxwdiffs = ", WDA_MAXWDIFFS, " (options record -> kbprog; WDA_MAXWDIFFS -> gpmakefsa -mwd via kbmag_patch/bin/autgroup: ",
          WDA_USES_PATCH, ")\n");
  fi;

  # --- the measurement (short relative temp path, see WDA_TMPREL above)
  _KBTmpFileName := Concatenation(WDA_TMPREL, "/", c.id);
  WDA_OrigExec(Concatenation("/bin/rm -f ", _KBTmpFileName, " ", _KBTmpFileName, ".*"));
  WDA_ExecLog := [];
  t0 := NanosecondsSinceEpoch();
  if large then
    ok := AutomaticStructure(R, true);
  else
    ok := AutomaticStructure(R);
  fi;
  row.seconds_total := (NanosecondsSinceEpoch() - t0) / 10^9;
  row.seconds_autgroup := WDA_SecondsOf("autgroup");
  row.seconds_gpminkb := WDA_SecondsOf("gpminkb");
  row.success := ok;
  base := _KBTmpFileName;
  if ok = true then
    wa := WordAcceptor(R);
    d1 := FirstWordDifferenceAutomaton(R);
    d2 := SecondWordDifferenceAutomaton(R);
    row.wa_states := NumberOfStatesFSA(wa);
    row.diff1_states := NumberOfStatesFSA(d1);
    row.diff2_states := NumberOfStatesFSA(d2);
    row.diff2c_states := WDA_StatesInFSAFile(Concatenation(base, ".diff2c"));
    row.gm_states := WDA_StatesInFSAFile(Concatenation(base, ".gm"));
    row.diff1kb_states := WDA_StatesInFSAFile(Concatenation(base, ".diff1"));
    # cross-checks against the files GAP read
    if WDA_StatesInFSAFile(Concatenation(base, ".wa")) <> row.wa_states or
       WDA_StatesInFSAFile(Concatenation(base, ".diff1c")) <> row.diff1_states or
       WDA_StatesInFSAFile(Concatenation(base, ".diff2")) <> row.diff2_states then
      row.notes := Concatenation(row.notes, "; WARNING: file/GAP state count mismatch");
    fi;
    row.size_check := (Size(R) = bld.order);
    if row.size_check <> true then
      row.notes := Concatenation(row.notes, "; WARNING: Size(R) = ", String(Size(R)));
    fi;
  fi;
  WDA_OrigExec(Concatenation("/bin/rm -f ", base, " ", base, ".*"));
  WDA_AppendRow(row);
  return row;
end;

#############################################################################
##  Report: wda_cost.txt from wda_cost.csv (last row per case, case order)
#############################################################################
WDA_Report := function()
  local rows, last, r, c, out, cols, widths, line, i, v, s, cap, sel;
  if not IsExistingFile(WDA_CSV) then Print("no ", WDA_CSV, "\n"); return; fi;
  rows := ReadCSV(WDA_CSV);
  last := rec();
  for r in rows do last.(r.case) := r; od;
  cap := WDA_Env("WDA_CAP", "600");
  out := "";
  Append(out, "Shortlex automatic structures of the Cayley-graph groups (GAP ");
  Append(out, GAPInfo.Version); Append(out, " + kbmag ");
  Append(out, InstalledPackageVersion("kbmag")); Append(out, ")\n");
  Append(out, Concatenation("Architecture: ", GAPInfo.Architecture, "\n"));
  if IsExistingFile(Filename(WDA_DIR, "machine.txt")) then
    Append(out, StringFile(Filename(WDA_DIR, "machine.txt")));
  fi;
  Append(out, Concatenation("Wall-clock cap per computation: ", cap, " s.  ",
    "Script: wda_cost.g (driver run_wda.py); raw data: wda_cost.csv; logs: logs/\n"));
  Append(out, "kbmag temporary files are written to the short relative path wdatmp/<case>: with GAP's default\n");
  Append(out, "temporary path (~70 characters) the gpaxioms program overflows its 100-byte file-name buffers on\n");
  Append(out, "relators of length >~ 25 and AutomaticStructure returns false (observed for Borel(47,23), T50, T100).\n");
  Append(out, "Rows marked [patched gpaxioms] were computed with kbmag_patch/bin (gpaxioms rebuilt from the package\n");
  Append(out, "sources with 4096-byte buffers by build_patch.sh; needed for relator sides of >= ~45 letters, i.e. T100).\n\n");

  cols := [ ["case", "case"], ["family", "family"], ["order", "n=|G|"], ["nS", "|S|"],
            ["alphabet", "alph"], ["success", "success"], ["wa_states", "WA"],
            ["diff1_states", "diff1"], ["diff2_states", "diff2"], ["diff2c_states", "diff2c"],
            ["gm_states", "GM"], ["seconds_total", "seconds"], ["seconds_autgroup", "t_autgroup"],
            ["large", "large"], ["maxwdiffs", "mwd"], ["size_check", "sizeOK"] ];
  sel := function(r, f)
    if IsBound(r.(f)) then return String(r.(f)); fi; return "";
  end;
  widths := List(cols, c -> Length(c[2]));
  for c in WDA_CASES do
    widths[1] := Maximum(widths[1], Length(c.id));
    widths[2] := Maximum(widths[2], Length(c.family));
    if IsBound(last.(c.id)) then
      for i in [1 .. Length(cols)] do
        widths[i] := Maximum(widths[i], Length(sel(last.(c.id), cols[i][1])));
      od;
    fi;
  od;
  line := "";
  for i in [1 .. Length(cols)] do
    Append(line, String(cols[i][2], -(widths[i] + 2)));
  od;
  Append(out, line); Append(out, "\n");
  Append(out, RepeatedString("-", Length(line))); Append(out, "\n");
  for c in WDA_CASES do
    line := "";
    if IsBound(last.(c.id)) then
      r := last.(c.id);
      for i in [1 .. Length(cols)] do
        v := sel(r, cols[i][1]);
        if i <= 2 or cols[i][1] in ["success", "large", "size_check"] then
          Append(line, String(v, -(widths[i] + 2)));
        else
          Append(line, String(v, widths[i])); Append(line, "  ");
        fi;
      od;
    else
      line := Concatenation(String(c.id, -(widths[1] + 2)), String(c.family, -(widths[2] + 2)), "(not run)");
    fi;
    Append(out, line); Append(out, "\n");
  od;
  Append(out, "\nColumns\n");
  Append(out, "  n=|G|      group order (verified by coset enumeration of the fp group, and by Size(R) = number of words accepted by the word acceptor -> sizeOK)\n");
  Append(out, "  |S|        number of generators as listed in the paper; alph = size of kbmag's alphabet (S plus an inverse letter for each non-involutory generator)\n");
  Append(out, "  success    true/false = return value of AutomaticStructure; timeout = killed at the cap; build-error = fp group of unexpected order\n");
  Append(out, "  WA         states of WordAcceptor(R) (minimized DFA accepting the shortlex normal forms)\n");
  Append(out, "  diff1      states of FirstWordDifferenceAutomaton(R) = kbmag file .diff1c, the correct minimal first word-difference machine (word differences of the minimal confluent rewriting system), output of gpminkb\n");
  Append(out, "  diff2      states of SecondWordDifferenceAutomaton(R) = kbmag file .diff2, the second word-difference machine of kbprog -wd (closed under inversion, all transitions) as corrected by gpmakefsa; may contain unneeded differences\n");
  Append(out, "  diff2c     states of the correct minimal second word-difference machine (file .diff2c written by gpminkb; not exposed by the GAP interface, read from the temporary file)\n");
  Append(out, "  GM         states of the general multiplier automaton (file .gm)\n");
  Append(out, "  seconds    wall-clock time of the AutomaticStructure(R[, large]) call (autgroup + gpminkb + GAP reading the automata files); t_autgroup = wall clock of the autgroup program alone (kbprog -wd, gpmakefsa, gpaxioms), i.e. the automatic structure computation proper\n");
  Append(out, "  large      true if the row comes from AutomaticStructure(R, true)\n");
  Append(out, "  mwd        word-difference limit passed to kbprog (options record) and gpmakefsa (-mwd, via the patched autgroup script) when kbmag's defaults were exceeded; empty = defaults\n");
  Append(out, "\nNotes per case\n");
  for c in WDA_CASES do
    if IsBound(last.(c.id)) and IsBound(last.(c.id).notes) then
      Append(out, Concatenation("  ", c.id, ": ", String(last.(c.id).notes), "\n"));
    fi;
  od;
  Append(out, "\nCases kbmag did not complete (ST8, PC8; see kbmag_out/*.pipeline.log)\n");
  Append(out, "  ST8: AutomaticStructure returns false (default and large): Knuth-Bendix completes with a confluent system of\n");
  Append(out, "       16799 rules (60 s), kbprog's diff1/diff2 have 2855/4278 states and gpmakefsa builds the 545-state word\n");
  Append(out, "       acceptor, but the general multiplier keeps being found incorrect (word differences missing from diff2) and\n");
  Append(out, "       gpmakefsa stops at kbmag's word-difference limit; with the limit raised to 200000 (kbmag_patch/bin) it was\n");
  Append(out, "       still adding word differences after 25 min (multiplier > 47000 states) and was stopped.\n");
  Append(out, "  PC8: Knuth-Bendix exceeds maxeqns (32767) with the defaults; with large + maxwdiffs 200000 it completes with a\n");
  Append(out, "       confluent system of 37964 rules (375 s), diff1/diff2 with 15515/19089 states, and gpmakefsa then crashes\n");
  Append(out, "       (SIGBUS) building the word acceptor from diff2; with -diff1 it builds the 5671-state word acceptor but\n");
  Append(out, "       did not finish the multiplier within the time budget.\n");
  Append(out, "  The word acceptors kbmag wrote for both cases (kbmag_out/ST8.wa, PC8.wa) accept exactly the 40320 shortlex\n");
  Append(out, "  normal forms (wda_wacheck.g), and wda_brute.g computes WA / diff1c / diff2c for them without kbmag:\n");
  Append(out, "       ST8: WA = 545, diff1c = 2855, diff2c = 13359;   PC8: WA = 5671, diff1c = 15515, diff2c = 24460.\n");
  Append(out, "  (wda_brute.g reproduces kbmag's WA, diff1 and diff2c exactly on all 30 completed cases, see below.)\n");
  for s in [ ["wda_verify.txt", "Independent verification of the word acceptors (wda_verify.g, wda_wacheck.g)"],
             ["wda_brute.txt", "Brute-force WA / diff1c / diff2c without kbmag (wda_brute.g)"] ] do
    if IsExistingFile(Filename(WDA_DIR, s[1])) then
      Append(out, Concatenation("\n", s[2], "\n"));
      for line in SplitString(StringFile(Filename(WDA_DIR, s[1])), "\n") do
        if line <> "" then Append(out, Concatenation("  ", line, "\n")); fi;
      od;
    fi;
  od;
  FileString(WDA_TXT, out);
  Print("#WDA report written to ", WDA_TXT, " (", Length(rows), " csv rows)\n");
end;

#############################################################################
##  Main
#############################################################################
WDA_MODE := WDA_Env("WDA_CASE", "all");
if IsBoundGlobal("WDA_DEFINE_ONLY") and ValueGlobal("WDA_DEFINE_ONLY") = true then
  WDA_MODE := "define";   # set by wda_verify.g before Read("wda_cost.g")
fi;
WDA_LARGE := WDA_Env("WDA_LARGE", "0") = "1";
if WDA_MAXWDIFFS <> "" and Int(WDA_MAXWDIFFS) = fail then
  Error("WDA_MAXWDIFFS must be an integer");
fi;

if WDA_MODE = "define" then
  ;   # only define the functions and the case list (used by wda_verify.g)
elif WDA_MODE = "list" then
  Print("HEADER ", JoinStringsWithSeparator(WDA_HEADER, ","), "\n");
  for c in WDA_CASES do
    Print("CASE ", c.id, " ", ReplacedString(c.family, " ", "_"), " ", c.param, " ",
          c.order, " ", c.nS, "\n");
  od;
elif WDA_MODE = "report" then
  WDA_Report();
elif WDA_MODE = "all" then
  for c in WDA_CASES do
    WDA_RunCase(c, WDA_LARGE);
  od;
  WDA_Report();
else
  c := WDA_CaseById(WDA_MODE);
  if c = fail then
    Print("#WDA unknown case ", WDA_MODE, "\n");
  else
    WDA_RunCase(c, WDA_LARGE);
  fi;
fi;
if WDA_MODE <> "define" then QUIT_GAP(0); fi;
