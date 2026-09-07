#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 4f: matrix summary and Ceiling selection.

The full matrix is ~1.47M cells across 19 files and is INTERNAL working data.
This collapses it to the artifact Phase 5 reads: one row per
(species-form, checkpoint, anchor), plus the Ceiling selection.

VISION 4.4: Floor is the deterministic zero-investment build. Ceiling is the
best build the player can actually reach. The generator produced candidates;
the MATRIX decides which is the Ceiling, so the choice rests on measured
outcomes rather than on the pre-matrix heuristic that only chose what to test.

Nothing here scores roles, VORP or ROI — that is Phase 5. This is the bridge.
"""
import csv, json, collections, statistics, os

OUT = "/home/claude/out"
LOG = []
def log(c, d, s="INFO"): LOG.append({"check": c, "severity": s, "detail": d})

VERDICT_PTS = {"win": 1.0, "marginal": 0.5, "loss": 0.0}

# Scoring basis: the CONTINUOUS margin, not the discretized verdict.
#
# The verdict-based score correlated with BST at r = 0.85 and produced only 26
# distinct scores for 1035 species at checkpoint 1, because 26 boss slots x
# three verdict values cannot separate them. The same cells scored on the margin
# the matrix already computes correlate at r = 0.31 — inside the target band —
# and resolve continuously. The verdict is kept as a display field.
#
# margin is (their_turns - my_turns) adjusted for speed: positive means the
# player wins the race and by how much. It is squashed to 0..1 so a blowout
# against one Pokemon cannot dominate an average across a roster; a 3-turn
# margin is decisively winning and further margin is not more informative.
def squash(margin, k=3.0):
    return 0.5 * (1.0 + max(-1.0, min(1.0, margin / k)))
BOSS_WEIGHT = {"champion": 3.0, "elite_four": 2.5, "gym_leader": 2.0,
               "team_boss": 1.5, "admin": 1.5, "rival": 1.2}

def main():
    per = collections.defaultdict(lambda: {
        "cells": 0, "win": 0, "loss": 0, "marginal": 0,
        "wpts": 0.0, "vpts": 0.0, "wsum": 0.0, "chipped_win": 0,
        "margins": [], "beats": [], "loses_to": [], "faster": 0,
        "their_turns": [], "incoming": [], "walls": 0,
    })
    meta = {}
    cps = []
    for cp in range(1, 20):
        p = f"{OUT}/04_matchups_cp{cp}.tsv"
        if not os.path.exists(p):
            continue
        cps.append(cp)
        with open(p, encoding="utf-8") as f:
            rd = csv.DictReader(f, delimiter="\t")
            for r in rd:
                key = (r["species_const"], int(r["checkpoint"]), r["anchor"],
                       r["track"], r["ability"], r["nature"], r["item"], r["moves"])
                d = per[key]
                w = BOSS_WEIGHT.get(r["boss_role"], 1.0)
                v = r["verdict"]
                d["cells"] += 1
                d[v] += 1
                try: mg = float(r["margin"])
                except ValueError: mg = 0.0
                d["wpts"] += squash(mg) * w
                d["wsum"] += w
                d["vpts"] += VERDICT_PTS[v] * w
                if r["verdict_chipped"] == "win":
                    d["chipped_win"] += 1
                try: d["margins"].append(float(r["margin"]))
                except ValueError: pass
                if int(r["speed_order"]) > 0: d["faster"] += 1
                # defensive aggregates: Phase 5 scores walls on turns survived
                # against the roster's win conditions, not on raw bulk
                try:
                    d["their_turns"].append(min(float(r["their_turns_to_ko"]), 20.0))
                    inc = float(r["incoming_after_utility"])
                    d["incoming"].append(inc)
                    if inc < 0.25: d["walls"] += 1
                except (ValueError, KeyError): pass
                if v == "win" and r["boss_role"] in ("gym_leader","elite_four","champion"):
                    d["beats"].append(f"{r['boss_species']}@{r['boss_trainer']}")
                if v == "loss" and r["boss_role"] in ("gym_leader","elite_four","champion"):
                    d["loses_to"].append(f"{r['boss_species']}@{r['boss_trainer']}")
                meta[key] = {"species_name": r["species_name"],
                             "roster_cp": r["roster_cp"],
                             "roster_borrowed": r["roster_borrowed"],
                             "level_cap": r["player_level"],
                             "item_reliable": None}
    log("S0_checkpoints", f"{len(cps)} checkpoint matrices read: {cps}")
    log("S1_build_rows", f"{len(per)} (species, checkpoint, build) groups")

    # item reliability from the candidate table
    rel = {}
    for c in csv.DictReader(open(f"{OUT}/04a_candidates.tsv"), encoding="utf-8"
                            if False else None, delimiter="\t") \
            if False else csv.DictReader(open(f"{OUT}/04a_candidates.tsv"), delimiter="\t"):
        rel[(c["species_const"], int(c["checkpoint"]), c["anchor"], c["track"],
             c["ability"], c["nature"], c["item"], c["moves"])] = c["item_reliable"]

    rows = []
    for key, d in per.items():
        sc, cp, anchor, track, ab, nat, item, moves = key
        m = meta[key]
        score = d["wpts"] / d["wsum"] if d["wsum"] else 0.0
        vscore = d["vpts"] / d["wsum"] if d["wsum"] else 0.0
        rows.append({
            "species_const": sc, "species_name": m["species_name"],
            "checkpoint": cp, "roster_cp": m["roster_cp"],
            "roster_borrowed": m["roster_borrowed"], "level": m["level_cap"],
            "anchor": anchor, "track": track, "ability": ab, "nature": nat,
            "item": item, "item_reliable": rel.get(key, "UNK"), "moves": moves,
            "cells": d["cells"], "wins": d["win"], "marginal": d["marginal"],
            "losses": d["loss"],
            "weighted_score": round(score, 4),
            "verdict_score": round(vscore, 4),
            "raw_win_rate": round(d["win"] / d["cells"], 4) if d["cells"] else 0,
            "chipped_win_rate": round(d["chipped_win"] / d["cells"], 4) if d["cells"] else 0,
            "mean_margin": round(statistics.mean(d["margins"]), 3) if d["margins"] else 0,
            "outspeeds_rate": round(d["faster"] / d["cells"], 4) if d["cells"] else 0,
            "mean_turns_survived": round(statistics.mean(d["their_turns"]), 3)
                                   if d["their_turns"] else 0,
            "mean_incoming": round(statistics.mean(d["incoming"]), 4)
                             if d["incoming"] else 0,
            "walls_rate": round(d["walls"] / d["cells"], 4) if d["cells"] else 0,
            "beats_sample": ",".join(sorted(set(d["beats"]))[:5]) or "NONE",
            "loses_to_sample": ",".join(sorted(set(d["loses_to"]))[:5]) or "NONE",
            "confidence": "Derived",
        })

    # ---- Ceiling selection: the matrix picks, not the heuristic.
    # Reliable-item builds win ties, so a ceiling does not silently rest on the
    # game's single Life Orb; the gap to the best unreliable build is published
    # as item_dependence.
    by_sc = collections.defaultdict(list)
    for r in rows:
        by_sc[(r["species_const"], r["checkpoint"])].append(r)

    final, no_floor, no_ceiling = [], 0, 0
    for (sc, cp), lst in by_sc.items():
        floor = next((r for r in lst if r["anchor"] == "floor"), None)
        cands = [r for r in lst if r["anchor"] == "candidate"]
        if not floor: no_floor += 1
        if not cands:
            no_ceiling += 1
            continue
        reliable = [r for r in cands if r["item_reliable"] == "TRUE"]
        pick_pool = reliable or cands
        ceiling = max(pick_pool, key=lambda r: (r["weighted_score"], r["mean_margin"]))
        best_any = max(cands, key=lambda r: (r["weighted_score"], r["mean_margin"]))
        item_dep = round(best_any["weighted_score"] - ceiling["weighted_score"], 4)

        f_score = floor["weighted_score"] if floor else 0.0
        final.append({
            "species_const": sc, "species_name": ceiling["species_name"],
            "checkpoint": cp, "roster_cp": ceiling["roster_cp"],
            "roster_borrowed": ceiling["roster_borrowed"], "level": ceiling["level"],
            "floor_score": round(f_score, 4),
            "floor_moves": floor["moves"] if floor else "UNK",
            "ceiling_score": ceiling["weighted_score"],
            "ceiling_track": ceiling["track"], "ceiling_ability": ceiling["ability"],
            "ceiling_nature": ceiling["nature"], "ceiling_item": ceiling["item"],
            "ceiling_moves": ceiling["moves"],
            "ceiling_item_reliable": ceiling["item_reliable"],
            "investment_delta": round(ceiling["weighted_score"] - f_score, 4),
            "item_dependence": item_dep,
            "unreliable_best_item": best_any["item"] if item_dep > 0 else "NA",
            "ceiling_verdict_score": ceiling["verdict_score"],
            "ceiling_win_rate": ceiling["raw_win_rate"],
            "ceiling_chipped_win_rate": ceiling["chipped_win_rate"],
            "ceiling_outspeeds_rate": ceiling["outspeeds_rate"],
            "ceiling_mean_margin": ceiling["mean_margin"],
            "cells": ceiling["cells"],
            "candidates_tested": len(cands),
            "beats_sample": ceiling["beats_sample"],
            "loses_to_sample": ceiling["loses_to_sample"],
            "confidence": "Derived",
        })

    log("S2_anchor_pairs", f"{len(final)} (species, checkpoint) pairs with a Ceiling")
    log("S3_missing_floor", f"{no_floor} pairs had no Floor build (no level-up moves "
                            f"under the cap); floor_score recorded as 0 and flagged",
        "WARN" if no_floor else "INFO")
    log("S4_missing_ceiling", f"{no_ceiling} pairs had no candidate build")

    dep = [r["item_dependence"] for r in final if r["item_dependence"] > 0]
    log("S5_item_dependence",
        f"{len(dep)} ceilings would score higher on a scarce item; "
        f"mean gap {statistics.mean(dep):.4f}, max {max(dep):.4f}" if dep
        else "no ceiling improved by a scarce item")

    # sanity: does investment actually buy anything?
    delta = [r["investment_delta"] for r in final]
    neg = sum(1 for d in delta if d < 0)
    log("S6_investment",
        f"mean ceiling-minus-floor {statistics.mean(delta):.4f}; "
        f"{neg} pairs where the Floor outscored every Ceiling candidate "
        f"({neg/len(delta):.1%}) — each is either a real finding or a generator bug",
        "WARN" if neg / len(delta) > 0.10 else "INFO")

    cols = list(final[0].keys())
    with open(f"{OUT}/04b_matchup_summary.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in sorted(final, key=lambda r: (r["checkpoint"], -r["ceiling_score"])):
            f.write("\t".join(str(r[c]) for c in cols) + "\n")

    bcols = list(rows[0].keys())
    with open(f"{OUT}/04c_build_scores.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(bcols) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]) for c in bcols) + "\n")

    json.dump({"log": LOG}, open(f"{OUT}/INT_integrity_log_phase4f.json", "w"), indent=2)
    for e in LOG:
        print(f"  [{e['severity']}] {e['check']}: {e['detail'][:200]}")

if __name__ == "__main__":
    main()
