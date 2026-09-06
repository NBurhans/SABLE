#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 3 REBUILD from the version-matched trainer dataset.

Why this replaces the trainers.party parse:
  The cloned `release` branch (2576d0f, 2025-09-01) is a development line whose
  boss rosters have moved past the 1.3.x builds people play. Three independent
  sources — hzla's calculator dataset, the compiled locations workbook, and the
  seatgem guide — agree with each other and disagree with that clone.

Authority for trainers is now hzla/Dynamic-Calc-Decomps backups/imp_1-3.js.
Seatgem is dropped: it is the outlier of the three (its Brawly Hariyama holds a
Sitrus Berry with Thick Fat; hzla and the workbook both give Flame Orb / Guts).

Tier: the dataset is a secondary source, so trainer rows are Asserted, not
Measured. The checkpoint graph stays Measured — it comes from src/caps.c, which
is engine code and unaffected by roster drift.

Residual risk, recorded in the log rather than smoothed: the dataset is 1.3 and
the player is on 1.3.1. No source available here distinguishes those two for
trainers.
"""
import json, os, re, csv, collections

DCALC = "/home/claude/dcalc/backups/imp_1-3.js"
SRC = "/home/claude/src_sable"
OUT = "/home/claude/out"
LOG = []
def log(check, detail, severity="INFO"):
    LOG.append({"check": check, "severity": severity, "detail": detail})

ROLE_PREFIX = [
    ("Leader", "gym_leader"), ("Elite Four", "elite_four"), ("Champion", "champion"),
    ("Rival", "rival"), ("Aqua Leader", "team_boss"), ("Magma Leader", "team_boss"),
    ("Aqua Admin", "admin"), ("Magma Admin", "admin"),
]

def load_dataset():
    t = open(DCALC, encoding="utf-8", errors="replace").read()
    d = json.loads(t[t.index("backup_data = ") + 14:].strip().rstrip(";"))
    trainers = collections.defaultdict(dict)
    label_of = {}
    for species, sets in d.items():
        for label, s in sets.items():
            tid = s["tr_id"]
            trainers[tid][s.get("sub_index", 0)] = (species, s)
            label_of[tid] = re.sub(r"^Lvl \d+\s*", "", label).strip()
    log("R1_dataset", f"{len(d)} species, {sum(len(v) for v in trainers.values())} "
                      f"roster slots, {len(trainers)} distinct trainers")
    return trainers, label_of

def ev_str(e):
    parts = [f"{v} {k}" for k, v in e.items() if v]
    return ",".join(parts) if parts else "0"

def iv_str(i):
    return ",".join(f"{v} {k}" for k, v in i.items())

def parse_checkpoints():
    txt = open(f"{SRC}/src/caps.c", encoding="utf-8", errors="replace").read()
    m = re.search(r"sLevelCapFlagMap\s*\[\]\s*\[\s*2\s*\]\s*=\s*\{(.*?)\n\s*\};", txt, re.S)
    out = []
    if m:
        for i, (flag, cap) in enumerate(
                re.findall(r"\{\s*(FLAG_[A-Z0-9_]+)\s*,\s*(\d+)\s*\}", m.group(1))):
            out.append({"order": i + 1, "gate_flag": flag, "level_cap": int(cap)})
    log("R2_checkpoints", f"{len(out)} progression gates (Measured, from src/caps.c)")
    return out

def main():
    trainers, label_of = load_dataset()
    rows = []
    for tid, slots in sorted(trainers.items()):
        label = label_of[tid]
        m = re.match(r"^(.*?)(\d*)$", label)
        base, suffix = m.group(1).strip(), m.group(2)
        role = "route"
        for pre, r in ROLE_PREFIX:
            if base.startswith(pre):
                role = r; break

        mons = [slots[k] for k in sorted(slots)]
        levels = [s["level"] for _, s in mons]
        iv_sums = [sum(s["ivs"].values()) for _, s in mons]
        ev_any = any(any(s["evs"].values()) for _, s in mons)
        ai = mons[0][1].get("ai_tags", [])
        bt = mons[0][1].get("battle_type", "UNK")

        roster = "|".join(
            ":".join([
                sp, str(s["level"]), s.get("ability") or "UNK", s["item"] or "NONE",
                s["nature"], ",".join(s["moves"]) or "NONE",
            ]) for sp, s in mons)

        rows.append({
            "trainer_id": tid,
            "trainer_label": label,
            "trainer_base": base,
            "battle_index": int(suffix) if suffix else 1,
            "role": role,
            "battle_type": bt,
            "ai_flags": ",".join(ai) if ai else "NONE",
            "party_size": len(mons),
            "min_level": min(levels), "max_level": max(levels),
            "perfect_ivs": "TRUE" if all(x == 186 for x in iv_sums) else "FALSE",
            "has_ev_spread": "TRUE" if ev_any else "FALSE",
            "roster": roster,
            "ivs": "|".join(iv_str(s["ivs"]) for _, s in mons),
            "evs": "|".join(ev_str(s["evs"]) for _, s in mons),
            "source": "hzla_dynamic_calc_imp_1-3",
            "confidence": "Asserted",
        })

    by_role = collections.Counter(r["role"] for r in rows)
    log("R3_trainers", f"{len(rows)} trainers; roles {dict(by_role)}")
    log("R4_slots", f"{sum(r['party_size'] for r in rows)} roster slots")
    bosses = [r for r in rows if r["role"] != "route"]
    withev = [r for r in bosses if r["has_ev_spread"] == "TRUE"]
    log("R5_boss_ev_coverage",
        f"{len(withev)}/{len(bosses)} boss-tier trainers carry EV spreads")
    slot_ev = sum(1 for r in rows for e in r["evs"].split("|") if e != "0")
    log("R6_slots_with_evs", f"{slot_ev} roster slots have non-zero EVs")
    imperfect = [r["trainer_label"] for r in bosses if r["perfect_ivs"] == "FALSE"]
    log("R7_boss_imperfect_ivs",
        f"{len(imperfect)} boss-tier trainers have deliberately tuned (non-31) IVs; "
        f"sample {imperfect[:5]}")
    log("R8_seatgem_dropped",
        "seatgem guide excluded: outlier of three sources (its Brawly Hariyama is "
        "Sitrus Berry / Thick Fat; hzla and the workbook both give Flame Orb / Guts)",
        "FINDING")
    log("R9_version_risk",
        "Dataset is Emerald Imperium 1.3; player is on 1.3.1. No available source "
        "distinguishes those revisions for trainer rosters. Rows are Asserted.",
        "FINDING")
    log("R10_clone_trainers_rejected",
        "src/data/trainers.party from release@2576d0f was NOT used: only 8 of 115 "
        "boss rosters matched the 1.3 sources; Cynthia shared almost no species.",
        "FINDING")

    cols = list(rows[0].keys())
    with open(f"{OUT}/03_trainers.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]).replace("\t", " ").replace("\n", " ")
                              for c in cols) + "\n")

    cps = parse_checkpoints()
    with open(f"{OUT}/03b_checkpoints.tsv", "w", encoding="utf-8") as f:
        f.write("order\tgate_flag\tlevel_cap\tconfidence\n")
        for c in cps:
            f.write(f"{c['order']}\t{c['gate_flag']}\t{c['level_cap']}\tMeasured\n")

    json.dump(LOG, open(f"{OUT}/INT_integrity_log_phase3.json", "w"), indent=2)
    print(f"trainers: {len(rows)} x {len(cols)}   checkpoints: {len(cps)}")
    for e in LOG:
        print(f"  [{e['severity']}] {e['check']}: {e['detail'][:150]}")

if __name__ == "__main__":
    main()
