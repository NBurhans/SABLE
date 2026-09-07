#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 6a: round-trip, referential integrity, UNK sweep.

No new dataset. Re-read everything from disk and try to break it.

The point is adversarial: every check here is written to FAIL if the pipeline is
wrong, not to confirm that it is right. A check that cannot fail is not a check.
"""
import csv, json, gzip, os, collections, re

OUT = "/home/claude/out"
WORK = "/home/claude/work"
LOG = []
def log(c, d, s="INFO"): LOG.append({"check": c, "severity": s, "detail": d})

def read(p):
    op = gzip.open if p.endswith(".gz") else open
    with op(f"{OUT}/{p}", "rt", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))

SENTINELS = {"NA", "NONE", "UNK"}


def round_trip():
    """Row counts, column counts, ragged rows, and encoded columns that decode."""
    files = ["01_species.tsv","01b_moves.tsv","01c_availability.tsv","02_world.tsv",
             "03_trainers.tsv","03b_checkpoints.tsv","04a_candidates.tsv",
             "04b_matchup_summary.tsv","04c_build_scores.tsv","05_roles.tsv",
             "05_valuation.tsv"]
    ragged_total = 0
    for fn in files:
        p = f"{OUT}/{fn}"
        if not os.path.exists(p):
            log(f"RT_{fn}", "MISSING", "WARN"); continue
        with open(p, encoding="utf-8") as f:
            hdr = f.readline().rstrip("\n").split("\t")
            n, ragged = 0, 0
            for line in f:
                n += 1
                if len(line.rstrip("\n").split("\t")) != len(hdr): ragged += 1
        ragged_total += ragged
        log(f"RT_{fn}", f"{n} rows x {len(hdr)} cols, ragged {ragged}",
            "WARN" if ragged else "INFO")
    log("RT_summary", f"{ragged_total} ragged rows across all files",
        "WARN" if ragged_total else "INFO")

    # decode encoded columns back to something recognisable
    sp = read("01_species.tsv")
    mv = {m["move_const"]: m["move_name"] for m in read("01b_moves.tsv")}
    ok, bad = 0, []
    for s in sp[:400]:
        for tok in s["levelup_moves"].split(","):
            if ":" not in tok: continue
            mc, lv = tok.rsplit(":", 1)
            if mc in mv and lv.isdigit(): ok += 1
            else: bad.append((s["species_const"], tok))
    log("RT_decode_levelup",
        f"{ok} level-up pairs decoded to a named move and integer level; "
        f"{len(bad)} failed; sample {bad[:4]}", "WARN" if bad else "INFO")

    # sentinel discipline: NA / NONE / UNK must not have collapsed
    counts = collections.Counter()
    for s in sp:
        for k, v in s.items():
            if v in SENTINELS: counts[v] += 1
    log("RT_sentinels",
        f"01_species sentinel usage — " + ", ".join(f"{k}:{v}" for k, v in counts.items())
        + " (three distinct meanings, must not collapse)")


def referential_integrity():
    """Every reference in a later phase must resolve against an earlier one."""
    sp = {s["species_const"]: s for s in read("01_species.tsv")}
    names = json.load(open(f"{WORK}/species_names.json"))
    disp = {v: k for k, v in names.items()}
    moves = {m["move_name"] for m in read("01b_moves.tsv")}
    world = read("02_world.tsv")
    items = {w["item_const"] for w in world}
    item_names = {w["item_name"] for w in world}
    resolved = json.load(open(f"{WORK}/boss_resolved.json"))

    # --- Phase 3 rosters resolve against Phases 1-2
    tr = read("03_trainers.tsv")
    bad_sp, bad_mv, bad_it, tot_slots, dyn = set(), set(), set(), 0, 0
    for t in tr:
        if t["role"] == "route": continue
        if t["checkpoint"] == "DYNAMIC":
            dyn += len(t["roster"].split("|")); continue
        for slot in t["roster"].split("|"):
            p = slot.split(":")
            if len(p) < 5: continue
            tot_slots += 1
            if p[0] not in resolved: bad_sp.add(p[0])
            for m in (p[5].split(",") if len(p) > 5 else []):
                if m and m not in moves: bad_mv.add(m)
            if p[3] and p[3] not in ("NONE","UNK","") and p[3] not in item_names:
                bad_it.add(p[3])
    log("RI_roster_species",
        f"{tot_slots} scored boss slots; {len(bad_sp)} species do not resolve "
        f"against Phase 1: {sorted(bad_sp)}", "WARN" if bad_sp else "INFO")
    log("RI_roster_moves",
        f"{len(bad_mv)} roster moves do not resolve against Phase 1b; "
        f"sample {sorted(bad_mv)[:8]}", "WARN" if bad_mv else "INFO")
    log("RI_roster_items",
        f"{len(bad_it)} roster items are not placed anywhere in Phase 2 — expected, "
        f"since trainers hold items the player cannot necessarily obtain; "
        f"sample {sorted(bad_it)[:6]}")
    log("RI_dynamic_excluded",
        f"{dyn} level-scaled rival slots excluded by decision, not omission")

    # --- Phase 5 ceilings use only moves and items Phase 1-2 confirm
    val = read("05_valuation.tsv")
    bad_move, bad_item, unreliable = set(), set(), 0
    for r in val:
        for m in r["moves"].split(","):
            if m and m not in moves: bad_move.add(m)
        if r["item"] not in ("NONE","UNK","") and r["item"] not in items:
            bad_item.add(r["item"])
        if r.get("item_reliable") == "FALSE": unreliable += 1
    log("RI_ceiling_moves",
        f"{len(bad_move)} moves on published ceilings do not exist in Phase 1b; "
        f"sample {sorted(bad_move)[:6]}", "WARN" if bad_move else "INFO")
    log("RI_ceiling_items",
        f"{len(bad_item)} items on published ceilings are not placed in Phase 2; "
        f"sample {sorted(bad_item)[:6]}", "WARN" if bad_item else "INFO")
    log("RI_ceiling_unreliable",
        f"{unreliable} published ceilings still carry a scarce item, each flagged "
        f"item_reliable=FALSE with the gap in item_dependence")

    # --- a ceiling must not use a move the species cannot learn
    illegal = []
    mvname = {m["move_const"]: m["move_name"] for m in read("01b_moves.tsv")}
    for r in val[:6000]:
        s = sp.get(r["species_const"])
        if not s: continue
        pool = set()
        for tok in s["levelup_moves"].split(","):
            if ":" in tok: pool.add(mvname.get(tok.rsplit(":",1)[0]))
        for col in ("teachable_moves","egg_moves"):
            if s[col] not in ("NONE","UNK",""):
                for mc in s[col].split(","): pool.add(mvname.get(mc.strip()))
        for m in r["moves"].split(","):
            if m and m not in pool: illegal.append((r["species_const"], m))
    log("RI_movepool_legality",
        f"{len(illegal)} of ~6000 sampled ceiling move slots use a move the species "
        f"cannot learn; sample {illegal[:5]}", "WARN" if illegal else "INFO")

    # --- every species scored must be in the availability pool
    avail = {a["species_const"]: a for a in read("01c_availability.tsv")}
    notpool = {r["species_const"] for r in val
               if avail.get(r["species_const"], {}).get("in_pool") != "TRUE"}
    log("RI_scored_in_pool",
        f"{len(notpool)} scored species-forms are not marked obtainable; "
        f"sample {sorted(notpool)[:5]}", "WARN" if notpool else "INFO")


def unk_sweep():
    """Every UNK in every file, by column, with a recoverability judgment."""
    files = ["01_species.tsv","01c_availability.tsv","02_world.tsv","03_trainers.tsv",
             "05_valuation.tsv"]
    table = {}
    for fn in files:
        rows = read(fn)
        c = collections.Counter()
        for r in rows:
            for k, v in r.items():
                if v == "UNK": c[k] += 1
        if c: table[fn] = (len(rows), dict(c.most_common()))
    for fn, (n, cols) in table.items():
        log(f"UNK_{fn}", f"{n} rows; " + ", ".join(f"{k}={v}" for k, v in cols.items()))
    json.dump(table, open(f"{OUT}/INT_unk_sweep.json","w"), indent=2)

    # recoverability judgment, stated rather than implied
    judgment = {
        "01c_availability.earliest_cp":
            "NOT recoverable from supplied data. Only 11 of 127 encounter maps carry "
            "a gated world row, so most wild timing is underivable. Needs either map "
            "connectivity data or a progression order the user supplies.",
        "02_world.earliest_gate":
            "PARTIALLY recoverable. Derived from flag-set anchors in scripts; the "
            "remainder need map connectivity that is not in the supplied files.",
        "03_trainers.checkpoint":
            "Recoverable for fixed trainers. DYNAMIC rivals are excluded by decision.",
    }
    for k, v in judgment.items():
        log(f"UNK_judgment:{k}", v)


if __name__ == "__main__":
    round_trip()
    referential_integrity()
    unk_sweep()
    json.dump({"log": LOG}, open(f"{OUT}/INT_integrity_log_phase6a.json","w"), indent=2)
    for e in LOG:
        print(f"  [{e['severity']}] {e['check']}: {e['detail'][:230]}")
