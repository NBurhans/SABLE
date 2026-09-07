#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 4d.0: availability closure.

The prior pass excluded 647 wild species because no encounter map of theirs
carried a known gate, and excluded every evolved form outright because
`wild_availability` is empty for anything you only obtain by evolving into it.
Both are data gaps being treated as absences, which non-negotiable #2 forbids.

This computes, per species-form:

  earliest_cp        first checkpoint the form can be in the player's hands
  availability_conf  Measured / Derived / UNK
  entry_reason       how it is reached

Rules:
  - starter                 -> cp 1
  - wild, map gate known    -> that gate
  - wild, map gate UNK      -> UNK (counted, NOT dropped)
  - evolution of an entry   -> parent's cp, pushed forward by the first
                               checkpoint whose level cap reaches the evolution
                               level; item/friendship/trade methods inherit the
                               parent cp and are flagged for review
  - mega / primal           -> base form's cp, gated on the stone if Phase 2
                               places it, else flagged
  - no path found           -> UNK, reason recorded

A form with earliest_cp UNK is NOT removed from the ladder. It is scored and
carries the gap on its face, because "we don't know when you get it" and
"you never get it" are different claims and collapsing them loses information.
"""
import csv, json, collections, re

def mapkey(s):
    """Species tables use MAP_ROUTE101; world tables use Route101. The two were
    never joining — 0 of 127 encounter maps matched — so every wild species was
    falling through to the ungated branch. Normalise both sides."""
    s = s.strip()
    if s.startswith("MAP_"):
        s = s[4:]
    return re.sub(r"[^a-z0-9]", "", s.lower())

OUT = "/home/claude/out"
LOG = []
def log(c, d, s="INFO"): LOG.append({"check": c, "severity": s, "detail": d})

def tsv(p):
    return list(csv.DictReader(open(f"{OUT}/{p}", encoding="utf-8"), delimiter="\t"))

def main():
    species = tsv("01_species.tsv")
    world   = tsv("02_world.tsv")
    caps    = {int(r["order"]): int(r["level_cap"]) for r in tsv("03b_checkpoints.tsv")}
    byc     = {s["species_const"]: s for s in species}

    # ---- map -> earliest reachable checkpoint.
    # Item placements alone dated only 11 of 127 encounter maps. 01d_map_gates
    # adds the rest from the creator's published walkthrough ordering, tagged
    # Asserted rather than Derived because it is a secondary source.
    map_gate, gate_conf = {}, {}
    for r in tsv("01d_map_gates.tsv"):
        if r["earliest_cp"] == "UNK":
            continue
        k = mapkey(r["map"])
        map_gate[k] = int(r["earliest_cp"])
        gate_conf[k] = r["confidence"]
    log("A0_map_gates",
        f"{len(map_gate)} encounter maps carry a gate ("
        + ", ".join(f"{c} {sum(1 for v in gate_conf.values() if v == c)}"
                    for c in sorted(set(gate_conf.values()))) + ")")

    # ---- item -> earliest gate (for evolution stones and mega stones)
    item_gate = {}
    for r in world:
        if r["earliest_gate"] != "UNK":
            g = int(r["earliest_gate"])
            item_gate[r["item_const"]] = min(item_gate.get(r["item_const"], 99), g)

    entry = {}          # const -> (cp or None, reason, confidence)
    ungated_wild = []

    # ---- seeds: starters and wild encounters
    for s in species:
        c = s["species_const"]
        if s.get("is_starter") == "TRUE":
            entry[c] = (1, "starter:game_start", "Measured")
            continue
        if s["wild_obtainable"] != "TRUE":
            continue
        gates = []
        for rec in s["wild_availability"].split("|"):
            mp = mapkey(rec.split(":")[0])
            if mp in map_gate:
                gates.append(map_gate[mp])
        if gates:
            best = min(gates)
            # a wild entry is only as trustworthy as the map gate behind it
            confs = {gate_conf.get(mapkey(rec.split(":")[0]))
                     for rec in s["wild_availability"].split("|")
                     if mapkey(rec.split(":")[0]) in map_gate}
            entry[c] = (best, "wild", "Derived" if confs == {"Derived"} else "Asserted")
        else:
            entry[c] = (None, "wild:map_gate_UNK", "UNK")
            ungated_wild.append(c)

    log("A1_seed_wild_gated", f"{sum(1 for v in entry.values() if v[0] is not None and v[1]=='wild')} "
                              f"wild forms with a derived gate")
    log("A2_seed_wild_ungated", f"{len(ungated_wild)} wild forms whose maps carry no gate — "
                                f"carried as UNK, not dropped", "WARN")

    # ---- evolution closure
    # evolutions column: METHOD:PARAM:TARGET, pipe-separated for branches
    def first_cp_at_level(lv):
        for o in sorted(caps):
            if caps[o] >= lv:
                return o
        return max(caps)

    parents = collections.defaultdict(list)
    for s in species:
        if s["evolutions"] in ("NONE", "UNK", ""):
            continue
        for br in s["evolutions"].split("|"):
            p = br.split(":")
            if len(p) < 3:
                continue
            method, param, target = p[0], p[1], p[2]
            parents[target].append((s["species_const"], method, param))

    LEVEL_METHODS = {"EVO_LEVEL", "EVO_LEVEL_ATK_GT_DEF", "EVO_LEVEL_ATK_LT_DEF",
                     "EVO_LEVEL_ATK_EQ_DEF", "EVO_LEVEL_SILCOON", "EVO_LEVEL_CASCOON",
                     "EVO_LEVEL_NINJASK", "EVO_LEVEL_DAY", "EVO_LEVEL_NIGHT",
                     "EVO_LEVEL_DUSK", "EVO_LEVEL_FEMALE", "EVO_LEVEL_MALE",
                     "EVO_LEVEL_RAIN", "EVO_LEVEL_MOVE_TWENTY_TIMES",
                     "EVO_LEVEL_DARK_TYPE_MON_IN_PARTY", "EVO_LEVEL_NATURE_AMPED",
                     "EVO_LEVEL_NATURE_LOW_KEY", "EVO_LEVEL_FAMILY_OF_THREE",
                     "EVO_LEVEL_FAMILY_OF_FOUR"}
    ITEM_METHODS = {"EVO_ITEM", "EVO_ITEM_HOLD", "EVO_ITEM_HOLD_DAY", "EVO_ITEM_HOLD_NIGHT",
                    "EVO_TRADE_ITEM", "EVO_ITEM_MALE", "EVO_ITEM_FEMALE",
                    "EVO_ITEM_NIGHT", "EVO_ITEM_DAY"}

    unresolved_evo_item = []
    changed, rounds = True, 0
    while changed and rounds < 25:
        changed, rounds = False, rounds + 1
        for target, plist in parents.items():
            if target not in byc:
                continue
            best = entry.get(target)
            for pc, method, param in plist:
                pe = entry.get(pc)
                if pe is None:
                    continue
                pcp, _, pconf = pe
                if pcp is None:
                    # parent timing unknown -> child timing unknown, but reachable
                    cand = (None, f"evolution:{method}:from {pc} (parent gate UNK)", "UNK")
                elif method in LEVEL_METHODS and param.isdigit():
                    cand = (max(pcp, first_cp_at_level(int(param))),
                            f"evolution:{method}@{param}:from {pc}", "Derived")
                elif method in ITEM_METHODS:
                    ig = item_gate.get(param)
                    if ig is None:
                        unresolved_evo_item.append((target, param))
                        cand = (None, f"evolution:{method}:{param} not placed in Phase 2",
                                "UNK")
                    else:
                        cand = (max(pcp, ig), f"evolution:{method}:{param}", "Derived")
                else:
                    # friendship, move, location, trade-without-item, etc.
                    cand = (pcp, f"evolution:{method}:{param}:from {pc}", "Inferred")
                # prefer a known cp over UNK, then the earliest
                if best is None:
                    best = cand; changed = True
                elif best[0] is None and cand[0] is not None:
                    best = cand; changed = True
                elif best[0] is not None and cand[0] is not None and cand[0] < best[0]:
                    best = cand; changed = True
            if best is not None and entry.get(target) != best:
                entry[target] = best
                changed = True

    log("A3_evo_rounds", f"closure converged in {rounds} rounds")
    log("A4_evo_item_unresolved",
        f"{len(set(unresolved_evo_item))} evolution items referenced by an evolution but "
        f"absent from Phase 2 — each is a data gap OR an unobtainable evolution; "
        f"sample {sorted(set(unresolved_evo_item))[:6]}", "WARN")

    # ---- megas / primals: base form's timing, gated on the stone
    mega_no_stone = []
    for s in species:
        c = s["species_const"]
        if s["form_type"] not in ("mega", "primal", "ultra_burst"):
            continue
        base = c.rsplit("_MEGA", 1)[0].rsplit("_PRIMAL", 1)[0]
        base = base.replace("_X", "").replace("_Y", "")
        be = entry.get(base)
        if be is None:
            continue
        mega_no_stone.append(c)
        entry.setdefault(c, (be[0], f"mega/primal form of {base} (stone not resolved)",
                             "Inferred"))
    log("A5_mega_forms",
        f"{len(mega_no_stone)} mega/primal/ultra forms inherit their base form's timing; "
        f"stone placement not resolved in Phase 2 — flagged Inferred", "WARN")

    # ---- write
    rows = []
    for s in species:
        c = s["species_const"]
        e = entry.get(c)
        if e is None:
            rows.append({"species_const": c, "species_name": s["species_name"],
                         "earliest_cp": "UNK", "entry_reason": "no path found",
                         "availability_confidence": "UNK", "in_pool": "FALSE"})
        else:
            cp, reason, conf = e
            rows.append({"species_const": c, "species_name": s["species_name"],
                         "earliest_cp": cp if cp is not None else "UNK",
                         "entry_reason": reason,
                         "availability_confidence": conf, "in_pool": "TRUE"})

    inpool = [r for r in rows if r["in_pool"] == "TRUE"]
    known  = [r for r in inpool if r["earliest_cp"] != "UNK"]
    log("A6_pool", f"{len(inpool)} of {len(rows)} species-forms have some obtainment path")
    log("A7_timed", f"{len(known)} of those have a derived checkpoint; "
                    f"{len(inpool)-len(known)} carry earliest_cp=UNK")
    dist = collections.Counter(r["earliest_cp"] for r in known)
    log("A8_cp_dist", str(dict(sorted(dist.items(), key=lambda k: int(k[0])))))
    log("A9_no_path", f"{len(rows)-len(inpool)} forms have no obtainment path at all "
                      f"(gigantamax/totem/paradox and unplaced evolutions)")

    cols = list(rows[0].keys())
    with open(f"{OUT}/01c_availability.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]) for c in cols) + "\n")
    json.dump({"log": LOG}, open(f"{OUT}/INT_integrity_log_phase4d0.json", "w"), indent=2)
    for e in LOG:
        print(f"  [{e['severity']}] {e['check']}: {e['detail'][:200]}")

if __name__ == "__main__":
    main()
