#!/usr/bin/env python3
"""Driver for wda_cost.g.

Runs every case defined in wda_cost.g in a fresh GAP process (own process
group) under a wall-clock cap.  When AutomaticStructure returns false the
case is retried with AutomaticStructure(R, true) ("large"), and then once
more with large + a raised word-difference limit (WDA_MAXWDIFFS, see
wda_cost.g).  "timeout"/"error" rows are recorded in wda_cost.csv, no new
attempt is started once the total budget is exhausted, and wda_cost.txt is
regenerated after every case.

    python3 run_wda.py [case_id ...]

Environment: WDA_CAP (seconds per computation, default 600),
             WDA_BUDGET (total seconds, default 5400),
             WDA_MAXWDIFFS (limit used by the third attempt, default 200000),
             GAP (path to gap).
"""
import os
import signal
import subprocess
import sys
import time

GAP = os.environ.get("GAP", "/opt/homebrew/bin/gap")
HERE = os.path.dirname(os.path.abspath(__file__))
CAP = int(os.environ.get("WDA_CAP", "600"))
BUDGET = int(os.environ.get("WDA_BUDGET", "5400"))
MAXWDIFFS = int(os.environ.get("WDA_MAXWDIFFS", "200000"))
CSV = os.path.join(HERE, "wda_cost.csv")
LOGDIR = os.path.join(HERE, "logs")


def gap(env_extra, log_path=None, timeout=None):
    """Run wda_cost.g; return (returncode or None on timeout, stdout text)."""
    env = dict(os.environ)
    env.update(env_extra)
    env["WDA_CAP"] = str(CAP)
    log = open(log_path, "ab") if log_path else None
    p = subprocess.Popen(
        [GAP, "-q", "-b", "wda_cost.g"],
        cwd=HERE, env=env, stdin=subprocess.DEVNULL,
        stdout=log if log else subprocess.PIPE,
        stderr=subprocess.STDOUT, start_new_session=True,
    )
    try:
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, (out.decode(errors="replace") if out else "")
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)  # gap and its autgroup children
        except ProcessLookupError:
            pass
        p.wait()
        return None, ""
    finally:
        if log:
            log.close()


def read_rows():
    if not os.path.exists(CSV):
        return None, []
    with open(CSV) as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]
    header = lines[0].split(",")
    return header, [dict(zip(header, l.split(","))) for l in lines[1:]]


def append_row(header, values):
    new = not os.path.exists(CSV)
    with open(CSV, "a") as f:
        if new:
            f.write(",".join(header) + "\n")
        f.write(",".join(str(values.get(h, "")) for h in header) + "\n")


def last_row_for(cid, large):
    _, rows = read_rows()
    rows = [r for r in rows if r["case"] == cid and r["large"] == ("true" if large else "false")]
    return rows[-1] if rows else None


def main():
    os.makedirs(LOGDIR, exist_ok=True)
    rc, out = gap({"WDA_CASE": "list"})
    header, cases = None, []
    for line in out.splitlines():
        if line.startswith("HEADER "):
            header = line.split(" ", 1)[1].split(",")
        elif line.startswith("CASE "):
            _, cid, family, param, order, ns = line.split()
            cases.append((cid, family.replace("_", " "), param, order, ns))
    if not header or not cases:
        sys.exit("could not list cases:\n" + out)
    wanted = sys.argv[1:]
    if wanted:
        cases = [c for c in cases if c[0] in wanted]

    # machine description for the report header
    try:
        cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                             capture_output=True, text=True).stdout.strip()
        uname = subprocess.run(["uname", "-srm"], capture_output=True, text=True).stdout.strip()
        with open(os.path.join(HERE, "machine.txt"), "w") as f:
            f.write(f"Machine: {cpu}; {uname}; run started {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception:
        pass

    start = time.time()
    for cid, family, param, order, ns in cases:
        base = {"case": cid, "family": family, "param": param, "order": order, "nS": ns}
        elapsed = time.time() - start
        if elapsed > BUDGET:
            print(f"[{cid}] skipped: total budget {BUDGET}s exhausted ({elapsed:.0f}s used)", flush=True)
            append_row(header, dict(base, large="false", success="skipped-budget",
                                    notes="not run: total time budget exhausted"))
            continue
        # attempt ladder: default -> large -> large + raised word-difference limit
        for large, mwd in ((False, None), (True, None), (True, MAXWDIFFS)):
            tag = cid + ("_large" if large else "") + (f"_mwd{mwd}" if mwd else "")
            log_path = os.path.join(LOGDIR, tag + ".log")
            if os.path.exists(log_path):
                os.remove(log_path)
            if time.time() - start > BUDGET:
                print(f"[{tag}] skipped: total budget exhausted", flush=True)
                break
            print(f"[{tag}] running (cap {CAP}s) ...", end=" ", flush=True)
            t0 = time.time()
            env = {"WDA_CASE": cid, "WDA_LARGE": "1" if large else "0"}
            if mwd:
                env["WDA_MAXWDIFFS"] = str(mwd)
            rc, _ = gap(env, log_path=log_path, timeout=CAP)
            dt = time.time() - t0
            attempt = dict(base, large="true" if large else "false", maxwdiffs=str(mwd) if mwd else "")
            if rc is None:
                print(f"TIMEOUT after {dt:.0f}s", flush=True)
                append_row(header, dict(attempt, success="timeout",
                                        seconds_total=f">{CAP}", seconds_autgroup=f">{CAP}",
                                        notes=f"killed after {CAP} s wall clock; see logs/{tag}.log"))
                break  # no further retry after a timeout
            row = last_row_for(cid, large)
            if row is None:
                print(f"ERROR (no CSV row, rc={rc}) after {dt:.0f}s", flush=True)
                append_row(header, dict(attempt, success="error", seconds_total=f"{dt:.2f}",
                                        notes=f"GAP exited with code {rc} without a result; see logs/{tag}.log"))
                break
            print(f"success={row['success']} WA={row['wa_states']} diff1={row['diff1_states']} "
                  f"diff2={row['diff2_states']} diff2c={row['diff2c_states']} "
                  f"t={row['seconds_total']}s (process {dt:.0f}s)", flush=True)
            if row["success"] != "false":
                break  # true, build-error, ... -> done; only a plain false triggers the large retry
        gap({"WDA_CASE": "report"})
    gap({"WDA_CASE": "report"})
    print(f"done in {time.time() - start:.0f}s; see wda_cost.txt / wda_cost.csv", flush=True)


if __name__ == "__main__":
    main()
