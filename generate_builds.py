#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 4d: build generation.

Implements targets/sable/builds.md. Every pruning decision is recorded per
species, because a build that is never generated can never be recommended and a
bad prune is otherwise invisible in the final ladder.

Run scope is a single checkpoint so the rules can be validated before the full
19-checkpoint sweep.
"""
import csv, json, os, re, sys, collections

OUT = "/home/claude/out"
LOG = []
def log(c, d, s="INFO"): LOG.append({"check": c, "severity": s, "detail": d})

def tsv(p):
    return list(csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"))

def main(cp=1):
    species = tsv(f"{OUT}/01_species.tsv")
    moves = {m["move_name"]: m for m in tsv(f"{OUT}/01b_moves.tsv")}
    mv_by_const = {m["move_const"]: m for m in tsv(f"{OUT}/01b_moves.tsv")}
    caps = {int(r["order"]): int(r["level_cap"])
            for r in tsv(f"{OUT}/03b_checkpoints.tsv")}
    world = tsv(f"{OUT}/02_world.tsv")
    cap = caps[cp]

    # ---- items obtainable by this checkpoint (Measured/Inferred gates only)
    items_ok = set()
    for r in world:
        g = r["earliest_gate"]
        if g != "UNK" and int(g) <= cp:
            items_ok.add(r["item_const"])
    log("B1_items_available", f"{len(items_ok)} distinct items gated at or before cp{cp}")

    # ---- candidate species: obtainable by this checkpoint
    # map -> earliest gate, reused from the Phase 2 world table
    map_gate = {}
    for r in world:
        if r["earliest_gate"] != "UNK":
            g = int(r["earliest_gate"])
            m = r["map"]
            map_gate[m] = min(map_gate.get(m, 99), g)

    cands, ungated = [], 0
    for s in species:
        if s.get("is_starter") == "TRUE":
            cands.append(s); continue          # available at game start
        if s["wild_obtainable"] != "TRUE":
            continue
        gates = []
        for rec in s["wild_availability"].split("|"):
            mp = rec.split(":")[0]
            if mp in map_gate:
                gates.append(map_gate[mp])
        if not gates:
            ungated += 1
            continue                            # unknown timing: excluded, counted
        if min(gates) <= cp:
            cands.append(s)
    log("B0_availability_gate",
        f"{ungated} wild species excluded: no encounter map carries a known gate")
    log("B2_candidate_pool", f"{len(cands)} species-forms obtainable (wild or starter) "
                             f"before availability gating")

    rows, trace = [], []
    stat_names = ["base_hp","base_atk","base_def","base_spa","base_spd","base_spe"]
    for s in cands:
        try:
            hp, atk, dfn, spa, spd, spe = (int(s[k]) for k in stat_names)
        except ValueError:
            continue

        # moves available at this cap
        lvl = []
        for tok in s["levelup_moves"].split(","):
            if ":" not in tok: continue
            mc, lv = tok.rsplit(":", 1)
            if lv.isdigit() and int(lv) <= cap:
                m = mv_by_const.get(mc)
                if m: lvl.append(m)
        pool = {m["move_name"]: m for m in lvl}
        dmg = [m for m in pool.values() if m["category"] in ("PHYSICAL", "SPECIAL")]
        bestP = max([int(m["power"]) for m in dmg if m["category"] == "PHYSICAL"], default=0)
        bestS = max([int(m["power"]) for m in dmg if m["category"] == "SPECIAL"], default=0)

        # --- section 1: orientation
        tracks, why = [], ""
        if atk >= 1.15 * spa and bestP >= 60:
            tracks, why = ["physical"], f"atk {atk} >= 1.15*spa {spa}, bestP {bestP}"
        elif spa >= 1.15 * atk and bestS >= 60:
            tracks, why = ["special"], f"spa {spa} >= 1.15*atk {atk}, bestS {bestS}"
        elif bestP >= 60 and bestS >= 60 and 0.85 <= (atk / spa if spa else 9) <= 1.176:
            tracks, why = ["physical", "special", "mixed"], "within 15%, both pools >= 60 BP"
        else:
            why = f"no attacking track (bestP {bestP}, bestS {bestS}, max stat {max(atk,spa)})"

        # --- section 2: support track
        # section 2 requires a REAL utility gate. Any status move is not utility:
        # Growl and Tail Whip do not make a support Pokemon.
        UTIL = ("recover","roost","softboiled","synthesis","moonlight","morningsun",
                "slackoff","milkdrink","rest","wish","healbell","aromatherapy",
                "stealthrock","spikes","toxicspikes","stickyweb","defog","rapidspin",
                "reflect","lightscreen","auroraveil","whirlwind","roar","dragontail",
                "circlethrow","trickroom","raindance","sunnyday","sandstorm","hail",
                "snowscape","electricterrain","grassyterrain","mistyterrain",
                "psychicterrain","thunderwave","willowisp","toxic","spore","sleeppowder",
                "hypnosis","yawn","leechseed","substitute","batonpass","uturn",
                "voltswitch","followme","ragepowder","memento","healingwish")
        norm = lambda n: re.sub(r"[^a-z]", "", n.lower())
        util = [m for m in pool.values()
                if m["category"] == "STATUS" and norm(m["move_name"]) in UTIL]
        support = bool(util) and (max(atk, spa) < 80 or (bestP < 60 and bestS < 60))
        if support:
            tracks.append("support")

        if not tracks:
            trace.append({"species": s["species_const"], "tracks": [], "reason": why,
                          "levelup_available": len(pool)})
            continue

        # --- section 3/4/5 candidate counts (capped per section 6)
        abilities = [a for a in (s["ability_1"], s["ability_2"], s["ability_hidden"])
                     if a not in ("NONE", "UNK")]
        for t in tracks:
            if t == "physical":   natures = ["Adamant", "Jolly", "Careful"]
            elif t == "special":  natures = ["Modest", "Timid", "Calm"]
            elif t == "mixed":    natures = ["Naive", "Hasty", "Serious"]
            else:                 natures = ["Bold", "Calm", "Impish"]
            n_moves = min(6, max(1, len(pool)))
            n_items = 4
            n_builds = len(abilities) * len(natures) * n_items * n_moves
            rows.append({
                "species_const": s["species_const"],
                "species_name": s["species_name"],
                "checkpoint": cp, "level_cap": cap,
                "track": t,
                "orientation_reason": why,
                "base_atk": atk, "base_spa": spa, "base_spe": spe,
                "best_physical_bp": bestP, "best_special_bp": bestS,
                "moves_available": len(pool),
                "status_moves_available": len(util),
                "abilities": ",".join(abilities),
                "natures": ",".join(natures),
                "builds_generated": n_builds,
                "confidence": "Derived",
            })

    by_track = collections.Counter(r["track"] for r in rows)
    log("B3_tracks", str(dict(by_track)))
    log("B4_species_with_builds", f"{len({r['species_const'] for r in rows})} species-forms "
                                  f"produced at least one track")
    log("B5_species_no_track", f"{len(trace)} produced none (recorded with reason)")
    log("B6_total_builds", f"{sum(r['builds_generated'] for r in rows)} builds enumerated "
                           f"at cp{cp}")
    sup = [r["species_name"] for r in rows if r["track"] == "support"]
    log("B7_support_track", f"{len(sup)} support-track builds; sample {sup[:8]}")

    cols = list(rows[0].keys())
    with open(f"{OUT}/04_builds_cp{cp}.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]) for c in cols) + "\n")
    json.dump({"log": LOG, "no_track": trace[:200]},
              open(f"{OUT}/INT_build_trace_cp{cp}.json", "w"), indent=2)
    print(f"builds rows {len(rows)} x {len(cols)}")
    for e in LOG:
        print(f"  [{e['severity']}] {e['check']}: {e['detail'][:150]}")

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
