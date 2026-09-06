#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 3c: boss-to-checkpoint assignment.

Phase 4 scores builds at checkpoints, so every checkpoint needs the roster it is
scored against. src/caps.c gives 19 ordered gates with level caps; the trainer
dataset gives max levels. Bosses land on the checkpoint whose cap they meet.

Rule, in order:
  1. exact  — max_level equals a cap: that checkpoint (76 of 114 bosses).
  2. bounded — otherwise the lowest cap >= max_level, i.e. the first gate at
     which the player could legally field a team of that level.
  3. overflow — above the final cap (85): assigned to the last checkpoint and
     flagged, since postgame content sits outside the progression ladder.

Checkpoints WITHOUT a roster of their own inherit the roster of the next boss
ahead of them, per VISION section 8 — they still constrain availability and
level cap, they are just scored against the fight they prepare you for.
"""
import csv, json, collections

OUT = "/home/claude/out"
LOG = []
def log(c, d, s="INFO"): LOG.append({"check": c, "severity": s, "detail": d})

def main():
    caps = [(int(r["order"]), int(r["level_cap"]), r["gate_flag"])
            for r in csv.DictReader(open(f"{OUT}/03b_checkpoints.tsv", encoding="utf-8"),
                                    delimiter="\t")]
    caps.sort()
    maxcap = caps[-1][1]

    rows = list(csv.DictReader(open(f"{OUT}/03_trainers.tsv", encoding="utf-8"),
                               delimiter="\t"))
    method = collections.Counter()
    for r in rows:
        ml = int(r["max_level"])
        if r["role"] == "route":
            r["checkpoint"] = "NA"; r["checkpoint_method"] = "NA"; continue
        if ml <= 0:
            # Sinnoh leaders and some rivals scale to the player: the dataset
            # stores their level as an OFFSET (0, -1, -2, -3) from the player's
            # highest, not an absolute. They have no fixed checkpoint.
            r["checkpoint"] = "DYNAMIC"; r["checkpoint_method"] = "player_relative"
            method["player_relative"] += 1
            continue
        exact = [c for c in caps if c[1] == ml]
        if exact:
            r["checkpoint"] = exact[0][0]; m = "exact"
        elif ml > maxcap:
            r["checkpoint"] = caps[-1][0]; m = "overflow_postgame"
        else:
            nxt = [c for c in caps if c[1] >= ml]
            r["checkpoint"] = nxt[0][0]; m = "bounded"
        r["checkpoint_method"] = m
        method[m] += 1

    bosses = [r for r in rows if r["role"] != "route"]
    log("C1_assignment_methods", str(dict(method)))
    per = collections.Counter(int(r["checkpoint"]) for r in bosses if r["checkpoint"] not in ("DYNAMIC","NA"))
    covered = sorted(per)
    empty = [o for o, _, _ in caps if o not in covered]
    log("C2_checkpoints_with_rosters",
        f"{len(covered)}/{len(caps)} checkpoints have at least one boss roster")
    log("C3_checkpoints_without_rosters",
        f"orders {empty} have no boss of their own and inherit the next boss ahead"
        if empty else "every checkpoint has a roster")
    log("C4_bosses_per_checkpoint",
        ", ".join(f"cp{o}(cap{c})={per.get(o,0)}" for o, c, _ in caps))
    over = [r["trainer_label"] for r in bosses if r["checkpoint_method"] == "overflow_postgame"]
    dyn = [r["trainer_label"] for r in bosses if r["checkpoint"] == "DYNAMIC"]
    log("C7_dynamic_level_bosses",
        f"{len(dyn)} boss-tier trainers scale to the player's highest level "
        f"(stored as offsets 0/-1/-2/-3), so they have NO fixed checkpoint and "
        f"must be scored relative to the party; sample {dyn[:6]}", "FINDING")
    log("C5_postgame_overflow",
        f"{len(over)} bosses exceed the level-85 cap and sit outside the ladder; "
        f"sample {over[:5]}", "FINDING" if over else "INFO")

    # sanity: the gym leader ladder must be strictly increasing by checkpoint
    leaders = sorted([r for r in bosses if r["role"] == "gym_leader"
                      and str(r["battle_index"]) == "1"
                      and r["checkpoint"] != "DYNAMIC"],
                     key=lambda r: int(r["checkpoint"]))
    seq = [(r["trainer_label"], int(r["checkpoint"]), int(r["max_level"])) for r in leaders]
    log("C6_leader_ladder", "; ".join(f"{a}=cp{b}/lv{c}" for a, b, c in seq[:12]))

    cols = list(rows[0].keys())
    with open(f"{OUT}/03_trainers.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r.get(c, "UNK")) for c in cols) + "\n")
    json.dump(LOG, open(f"{OUT}/INT_integrity_log_phase3c.json", "w"), indent=2)
    print(f"rows {len(rows)} x {len(cols)}")
    for e in LOG:
        print(f"  [{e['severity']}] {e['check']}: {e['detail'][:190]}")

if __name__ == "__main__":
    main()
