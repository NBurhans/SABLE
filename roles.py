#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 5: roles, valuation, VORP.

Implements references/roles.md. The point of this phase, in one line from that
file: answer "what is this build FOR, in this fight" rather than "how good is
this Pokemon" — because conflating them re-derives the BST ranking with extra
steps, which is exactly what Phase 4 measured itself doing (r = 0.82).

Structure:
  1. move classification, scanned from the hack's own move table
  2. gates      — binary. Fail one and role_fit is 0 regardless of stats.
  3. S T Y F    — percentile-normalised WITHIN the obtainable pool at that
                  checkpoint, never min-maxed across the dex
  4. VORP       — vs the third-best obtainable at zero investment, per
                  (checkpoint, role)
  5. tiers, cant_miss
  6. invariants I1-I5, I7

The decorrelation from BST is expected to come from the gates and from T, which
are the only parts of this that are not monotone in stats.
"""
import csv, json, collections, statistics, math, sys

OUT = "/home/claude/out"
WORK = "/home/claude/work"
LOG = []
def log(c, d, s="INFO"): LOG.append({"check": c, "severity": s, "detail": d})
def tsv(p): return list(csv.DictReader(open(f"{OUT}/{p}", encoding="utf-8"), delimiter="\t"))

TYPES = json.load(open(f"{WORK}/typechart.json"))
norm = lambda n: __import__("re").sub(r"[^a-z0-9]", "", n.lower())

def eff(mt, d1, d2):
    e = TYPES.get(mt, {}).get("eff", {})
    m = e.get(d1, 1)
    if d2 and d2 not in ("NONE", d1): m *= e.get(d2, 1)
    return m

TY = lambda s: s.replace("TYPE_", "").capitalize() if s not in ("NONE", "UNK") else None

# ---------------------------------------------------------------- 1. moves
# roles.md s4: build these by scanning the hack's own move table, not by
# hardcoding names. Where the source exposes no machine-readable property
# (recovery fraction, self-stat-raise), a curated list is used and each entry is
# verified to exist in THIS hack's table before use — unverified names are
# reported, never silently assumed absent.
RECOVERY = ["Recover","Roost","Soft-Boiled","Synthesis","Moonlight","Morning Sun",
            "Slack Off","Milk Drink","Rest","Shore Up","Strength Sap","Jungle Healing",
            "Life Dew","Wish","Purify","Heal Order"]
SETUP_ATK = ["Swords Dance","Dragon Dance","Bulk Up","Curse","Howl","Hone Claws",
             "Coil","Work Up","Victory Dance","Shift Gear","Clangorous Soul"]
SETUP_SPA = ["Nasty Plot","Calm Mind","Quiver Dance","Tail Glow","Growth","Geomancy",
             "Torch Song","Take Heart"]
SETUP_SPE = ["Agility","Rock Polish","Autotomize","Shell Smash","Dragon Dance",
             "Quiver Dance","Shift Gear","Flame Charge"]
HAZARD = ["Stealth Rock","Spikes","Toxic Spikes","Sticky Web"]
REMOVAL = ["Rapid Spin","Defog","Mortal Spin","Tidy Up","Court Change"]
PIVOT = ["U-turn","Volt Switch","Flip Turn","Teleport","Parting Shot","Baton Pass",
         "Chilly Reception"]
SCREENS = ["Reflect","Light Screen","Aurora Veil"]
CLERIC = ["Heal Bell","Aromatherapy","Healing Wish","Lunar Dance","Wish"]
PHAZE = ["Whirlwind","Roar","Dragon Tail","Circle Throw","Haze","Clear Smog"]
STATUS = ["Will-O-Wisp","Thunder Wave","Toxic","Spore","Glare","Sleep Powder",
          "Hypnosis","Nuzzle","Yawn","Stun Spore","Poison Powder"]
SPEEDCTL = ["Tailwind","Trick Room","Sticky Web","Thunder Wave","Icy Wind","Electroweb"]
TRICKROOM = ["Trick Room"]
SACRIFICE = ["Memento","Healing Wish","Explosion","Self-Destruct","Final Gambit",
             "Lunar Dance","Misty Explosion"]
REDIRECT = ["Follow Me","Rage Powder"]
TRAP = ["Mean Look","Block","Spider Web","Fairy Lock","Jaw Lock","Thousand Waves"]
WEATHER = ["Rain Dance","Sunny Day","Sandstorm","Hail","Snowscape","Chilly Reception"]
TERRAIN = ["Electric Terrain","Grassy Terrain","Misty Terrain","Psychic Terrain"]


def build_move_index():
    moves = tsv("01b_moves.tsv")
    by_name = {m["move_name"]: m for m in moves}
    present, absent = {}, collections.defaultdict(list)
    for label, names in [("recovery",RECOVERY),("setup_atk",SETUP_ATK),
        ("setup_spa",SETUP_SPA),("setup_spe",SETUP_SPE),("hazard",HAZARD),
        ("removal",REMOVAL),("pivot",PIVOT),("screens",SCREENS),("cleric",CLERIC),
        ("phaze",PHAZE),("status",STATUS),("speedctl",SPEEDCTL),
        ("trickroom",TRICKROOM),("sacrifice",SACRIFICE),("redirect",REDIRECT),
        ("trap",TRAP),("weather",WEATHER),("terrain",TERRAIN)]:
        ok = set()
        for n in names:
            if n in by_name: ok.add(norm(n))
            else: absent[label].append(n)
        present[label] = ok
    # priority moves are machine-readable in this hack's table
    present["priority"] = {norm(m["move_name"]) for m in moves
                           if m["priority"].lstrip("-").isdigit()
                           and int(m["priority"]) > 0
                           and m["category"] in ("PHYSICAL","SPECIAL")}
    log("R0_move_index",
        "verified against this hack's move table: " +
        ", ".join(f"{k} {len(v)}" for k, v in sorted(present.items())))
    miss = {k: v for k, v in absent.items() if v}
    log("R1_moves_absent",
        f"curated names not present in this hack: "
        f"{sum(len(v) for v in miss.values())} across {len(miss)} categories; "
        f"{dict(list(miss.items())[:4])}", "INFO")
    return present, by_name


def pct(values):
    """percentile rank within the pool — roles.md s1 forbids min-max"""
    order = sorted(values)
    n = len(order)
    def f(v):
        lo, hi = 0, n
        while lo < hi:
            mid = (lo+hi)//2
            if order[mid] < v: lo = mid+1
            else: hi = mid
        return lo / max(1, n-1)
    return f


ROLES = ["wallbreaker_phys","wallbreaker_spec","setup_sweeper","revenge_killer",
         "trick_room_attacker","priority_abuser","mixed_attacker",
         "physical_wall","special_wall","mixed_wall","regen_pivot","tank",
         "hazard_setter","hazard_remover","cleric","status_spreader",
         "screens_setter","phazer","trapper","weather_terrain_setter","speed_control"]

# enabler roles score only at the team layer; roles.md is explicit that a
# standalone number for them is meaningless. Recorded as excluded, not omitted.
EXCLUDED_ROLES = ["sacrificial_pivot","redirection","baton_passer"]

WEIGHTS = {  # w_stat, w_tool, w_type, w_fight  — sum to 1
    "offense": (0.25, 0.20, 0.15, 0.40),
    "defense": (0.25, 0.25, 0.15, 0.35),
    "utility": (0.10, 0.35, 0.10, 0.45),
}
FAMILY = {r: ("offense" if r in ("wallbreaker_phys","wallbreaker_spec","setup_sweeper",
              "revenge_killer","trick_room_attacker","priority_abuser","mixed_attacker")
              else "defense" if r in ("physical_wall","special_wall","mixed_wall",
              "regen_pivot","tank") else "utility") for r in ROLES}


def main():
    MV, by_name = build_move_index()
    species = {s["species_const"]: s for s in tsv("01_species.tsv")}
    moves_by_name = by_name
    # norm(name) -> move, precomputed. The scoring loop previously did a linear
    # scan of 938 moves per roster move per build, which is why it ran long.
    MV_BY_NORM = {norm(m["move_name"]): m for m in moves_by_name.values()}
    avail = {a["species_const"]: a for a in tsv("01c_availability.tsv")}
    scores = tsv("04c_build_scores.tsv")
    trainers = tsv("03_trainers.tsv")
    resolved = json.load(open(f"{WORK}/boss_resolved.json"))
    names = json.load(open(f"{WORK}/species_names.json"))
    by_disp = {}
    for c, n in names.items():
        if c in species: by_disp[n] = species[c]

    # ---- roster facts per checkpoint, for the F term
    roster = collections.defaultdict(list)
    for t in trainers:
        if t["role"] == "route" or t["checkpoint"] == "DYNAMIC": continue
        cp = int(t["checkpoint"])
        for slot in t["roster"].split("|"):
            p = slot.split(":")
            if len(p) < 5: continue
            s = by_disp.get(resolved.get(p[0], ""), None)
            if not s: continue
            mvs = (p[5].split(",") if len(p) > 5 else [])
            roster[cp].append({"s": s, "moves": [norm(m) for m in mvs],
                               "trainer": t["trainer_label"], "role": t["role"]})
    # borrow the next roster ahead for checkpoints without one (VISION 8)
    caps = {int(r["order"]): int(r["level_cap"]) for r in tsv("03b_checkpoints.tsv")}
    for cp in sorted(caps):
        if not roster[cp]:
            nxt = next((o for o in sorted(caps) if o > cp and roster[o]), None)
            if nxt: roster[cp] = roster[nxt]

    rfacts = {}
    for cp, mem in roster.items():
        if not mem: continue
        phys = spec = 0
        srsum = 0.0
        for m in mem:
            s = m["s"]
            t1, t2 = TY(s["type_1"]), TY(s["type_2"])
            srsum += 0.125 * eff("Rock", t1, t2)
            for mn in m["moves"]:
                mo = MV_BY_NORM.get(mn)
                if not mo: continue
                if mo["category"] == "PHYSICAL": phys += 1
                elif mo["category"] == "SPECIAL": spec += 1
        allmv = {mn for m in mem for mn in m["moves"]}
        rfacts[cp] = {
            "n": len(mem),
            "phys_share": phys / max(1, phys+spec),
            "sr_chip": srsum / len(mem),
            "has_removal": bool(allmv & MV["removal"]),
            "has_setup": bool(allmv & (MV["setup_atk"]|MV["setup_spa"]|MV["setup_spe"])),
            "inflicts_status": bool(allmv & MV["status"]),
            "has_hazards": bool(allmv & MV["hazard"]),
            "speeds": sorted(int(m["s"]["base_spe"]) for m in mem),
        }
    log("R2_rosters", f"{len(rfacts)} checkpoints carry roster facts; "
                      f"mean roster size {statistics.mean(v['n'] for v in rfacts.values()):.1f}")

    # ---- score every candidate build
    out, gate_fail_all, role_counts = [], 0, collections.Counter()
    by_cp = collections.defaultdict(list)
    for b in scores:
        by_cp[int(b["checkpoint"])].append(b)

    for cp, builds in sorted(by_cp.items()):
        rf = rfacts.get(cp)
        if not rf: continue
        # roster defensive typings and first attacking type, computed once
        rost = [(TY(m["s"]["type_1"]), TY(m["s"]["type_2"]),
                 next((MV_BY_NORM[mn]["type"] for mn in m["moves"]
                       if mn in MV_BY_NORM and MV_BY_NORM[mn]["category"] != "STATUS"),
                      None))
                for m in roster[cp]]
        pool = [species[b["species_const"]] for b in builds]
        P = {k: pct([int(s[f"base_{k}"]) for s in pool])
             for k in ("hp","atk","def","spa","spd","spe")}
        Pbulk_p = pct([int(s["base_hp"])*int(s["base_def"]) for s in pool])
        Pbulk_s = pct([int(s["base_hp"])*int(s["base_spd"]) for s in pool])
        Pmargin = pct([float(b["mean_margin"]) for b in builds])
        Psurv   = pct([float(b["mean_turns_survived"]) for b in builds])
        med_spe = statistics.median(int(s["base_spe"]) for s in pool)

        for b in builds:
            s = species[b["species_const"]]
            t1, t2 = TY(s["type_1"]), TY(s["type_2"])
            mv = {norm(x) for x in b["moves"].split(",")}
            atk, spa, spe = int(s["base_atk"]), int(s["base_spa"]), int(s["base_spe"])
            has = lambda k: bool(mv & MV[k])
            dmg = [moves_by_name.get(x) for x in b["moves"].split(",")]
            dmg = [m for m in dmg if m and m["category"] in ("PHYSICAL","SPECIAL")]
            def bp(m):
                try: return int(m["power"])
                except (ValueError, TypeError): return 0
            hi_phys = sum(1 for m in dmg if m["category"]=="PHYSICAL" and bp(m)>=90)
            hi_spec = sum(1 for m in dmg if m["category"]=="SPECIAL" and bp(m)>=90)
            atk_types = {m["type"] for m in dmg}
            stab = any(TY(m["type"]) in (t1,t2) for m in dmg)
            F_off = Pmargin(float(b["mean_margin"]))
            F_def = Psurv(float(b["mean_turns_survived"]))
            outsp = float(b["outspeeds_rate"])

            fits = {}
            for role in ROLES:
                # ---------- gates: binary, evaluated on THIS checkpoint's pool
                g = True
                if role == "wallbreaker_phys":
                    g = hi_phys >= 2 and len(atk_types) >= 3
                elif role == "wallbreaker_spec":
                    g = hi_spec >= 2 and len(atk_types) >= 3
                elif role == "setup_sweeper":
                    g = bool(mv & (MV["setup_atk"]|MV["setup_spa"]|MV["setup_spe"])) \
                        and any(bp(m) >= 75 and TY(m["type"]) in (t1,t2) for m in dmg)
                elif role == "revenge_killer":
                    g = has("priority") or P["spe"](spe) >= 0.75
                elif role == "trick_room_attacker":
                    g = P["spe"](spe) <= 0.25 and max(atk,spa) > med_spe \
                        and bool(mv & MV["trickroom"])
                elif role == "priority_abuser":
                    g = has("priority") and stab
                elif role == "mixed_attacker":
                    g = P["atk"](atk) > 0.5 and P["spa"](spa) > 0.5 \
                        and hi_phys >= 1 and hi_spec >= 1
                elif role == "physical_wall":
                    g = has("recovery") and (has("status") or has("phaze"))
                elif role == "special_wall":
                    g = has("recovery") and (has("status") or len(dmg) >= 1)
                elif role == "mixed_wall":
                    g = has("recovery") and P["def"](int(s["base_def"])) > 0.5 \
                        and P["spd"](int(s["base_spd"])) > 0.5
                elif role == "regen_pivot":
                    g = has("pivot")
                elif role == "tank":
                    g = Pbulk_p(int(s["base_hp"])*int(s["base_def"])) > 0.5 \
                        and max(P["atk"](atk), P["spa"](spa)) > 0.5 \
                        and not bool(mv & (MV["setup_atk"]|MV["setup_spa"]))
                elif role == "hazard_setter":   g = has("hazard")
                elif role == "hazard_remover":  g = has("removal")
                elif role == "cleric":          g = has("cleric")
                elif role == "status_spreader": g = has("status")
                elif role == "screens_setter":  g = len(mv & MV["screens"]) >= 1
                elif role == "phazer":          g = has("phaze")
                elif role == "trapper":         g = has("trap")
                elif role == "weather_terrain_setter":
                    g = bool(mv & (MV["weather"]|MV["terrain"]))
                elif role == "speed_control":   g = has("speedctl")
                if not g:
                    continue

                # ---------- S, T, Y, F
                if role in ("wallbreaker_phys",):
                    S = P["atk"](atk); T = min(1.0, hi_phys/3 + 0.2*len(atk_types)/4)
                elif role in ("wallbreaker_spec",):
                    S = P["spa"](spa); T = min(1.0, hi_spec/3 + 0.2*len(atk_types)/4)
                elif role == "setup_sweeper":
                    S = (max(P["atk"](atk),P["spa"](spa)) + P["spe"](spe))/2
                    T = min(1.0, len(mv & (MV["setup_atk"]|MV["setup_spa"]|MV["setup_spe"]))/2
                            + (0.3 if not rf["has_setup"] else 0.0))
                elif role == "revenge_killer":
                    S = P["spe"](spe); T = min(1.0, (0.6 if has("priority") else 0)+0.4*outsp)
                elif role == "trick_room_attacker":
                    S = 1 - P["spe"](spe); T = min(1.0, max(P["atk"](atk),P["spa"](spa)))
                elif role == "priority_abuser":
                    S = max(P["atk"](atk),P["spa"](spa)); T = min(1.0, len(mv & MV["priority"])/2+0.5)
                elif role == "mixed_attacker":
                    S = (P["atk"](atk)+P["spa"](spa))/2; T = min(1.0,(hi_phys+hi_spec)/4)
                elif role == "physical_wall":
                    S = Pbulk_p(int(s["base_hp"])*int(s["base_def"]))
                    T = min(1.0, 0.5 + 0.25*has("status") + 0.25*has("phaze"))
                elif role == "special_wall":
                    S = Pbulk_s(int(s["base_hp"])*int(s["base_spd"]))
                    T = min(1.0, 0.5 + 0.25*has("status") + 0.25*has("cleric"))
                elif role == "mixed_wall":
                    S = min(Pbulk_p(int(s["base_hp"])*int(s["base_def"])),
                            Pbulk_s(int(s["base_hp"])*int(s["base_spd"])))
                    T = min(1.0, 0.5 + 0.5*has("status"))
                elif role == "regen_pivot":
                    S = (P["hp"](int(s["base_hp"]))+max(P["def"](int(s["base_def"])),
                         P["spd"](int(s["base_spd"]))))/2
                    T = min(1.0, 0.6 + 0.4*has("recovery"))
                elif role == "tank":
                    S = (Pbulk_p(int(s["base_hp"])*int(s["base_def"]))
                         + max(P["atk"](atk),P["spa"](spa)))/2
                    T = min(1.0, 0.4 + 0.2*len(dmg))
                else:
                    S = (P["hp"](int(s["base_hp"]))
                         + max(P["def"](int(s["base_def"])),P["spd"](int(s["base_spd"]))))/2
                    tools = len(mv & (MV["recovery"]|MV["pivot"]|MV["status"]|MV["screens"]))
                    T = min(1.0, 0.3 + 0.25*tools)

                # Y: offensive = STAB reach; defensive/utility = resistance profile
                if FAMILY[role] == "offense":
                    reach = sum(1 for d1, d2, _ in rost
                                if max((eff(TY(x["type"]), d1, d2) for x in dmg),
                                       default=0) >= 1)
                    Y = (0.5 if stab else 0.0) + 0.5*reach/max(1, len(rost))
                else:
                    res = sum(1 for _, _, at in rost
                              if at and eff(TY(at), t1, t2) < 1)
                    Y = res/max(1, len(rost))

                # F: the boss-relative term (roles.md s2)
                if FAMILY[role] == "offense":
                    F = F_off
                elif FAMILY[role] == "defense":
                    F = F_def
                elif role == "hazard_setter":
                    F = min(1.0, rf["sr_chip"]*4) * (0.5 if rf["has_removal"] else 1.0) \
                        * min(1.0, rf["n"]/6)
                elif role == "hazard_remover":
                    F = 1.0 if rf["has_hazards"] else 0.0
                elif role == "cleric":
                    F = 1.0 if rf["inflicts_status"] else 0.0
                elif role == "status_spreader":
                    F = 0.8 if not rf["inflicts_status"] else 0.6
                elif role == "phazer":
                    F = 1.0 if rf["has_setup"] else 0.15
                elif role == "screens_setter":
                    F = 0.6
                elif role == "trapper":
                    F = 0.5
                elif role == "speed_control":
                    F = min(1.0, sum(1 for x in rf["speeds"] if x > spe)/max(1,rf["n"]))
                else:
                    F = 0.5
                ws, wt, wy, wf = WEIGHTS[FAMILY[role]]
                fits[role] = (round(ws*S + wt*T + wy*Y + wf*F, 4),
                              round(S,3), round(T,3), round(Y,3), round(F,3))

            if not fits:
                gate_fail_all += 1
                out.append({"species_const": b["species_const"],
                    "species_name": b["species_name"], "checkpoint": cp,
                    "anchor": b["anchor"],
                    "track": b["track"], "ability": b["ability"],
                    "nature": b["nature"], "item": b["item"], "moves": b["moves"],
                    "item_reliable": b["item_reliable"],
                    "primary_role": "NONE", "primary_fit": 0.0,
                    "hybrid_role": "NA", "top3": "NONE",
                    "S":"NA","T":"NA","Y":"NA","F":"NA",
                    "matrix_score": b["weighted_score"], "confidence": "Derived"})
                continue
            ranked = sorted(fits.items(), key=lambda kv: -kv[1][0])
            top, (fit, S, T, Y, F) = ranked[0]
            hybrid = ranked[1][0] if len(ranked) > 1 and \
                     abs(ranked[1][1][0]-fit) <= 0.05 else "NA"
            role_counts[top] += 1
            out.append({"species_const": b["species_const"],
                "species_name": b["species_name"], "checkpoint": cp,
                "anchor": b["anchor"],
                "track": b["track"], "ability": b["ability"], "nature": b["nature"],
                "item": b["item"], "moves": b["moves"],
                "item_reliable": b["item_reliable"],
                "primary_role": top, "primary_fit": fit, "hybrid_role": hybrid,
                "top3": ";".join(f"{r}:{v[0]}" for r, v in ranked[:3]),
                "S": S, "T": T, "Y": Y, "F": F,
                "matrix_score": b["weighted_score"], "confidence": "Derived"})

    nfl = sum(1 for r in out if r["anchor"] == "floor")
    log("R3_scored", f"{len(out)} builds scored across {len(by_cp)} checkpoints "
                     f"({nfl} floor, {len(out)-nfl} ceiling candidates)")
    log("R4_gate_fail_all",
        f"{gate_fail_all} builds ({gate_fail_all/len(out):.1%}) fail every role gate — "
        f"a finding, not a bug; no generalist bucket invented", "INFO")
    log("R5_excluded_roles",
        f"enabler roles scored at the team layer only, excluded here: {EXCLUDED_ROLES}")
    log("R6_role_spread", str(dict(role_counts.most_common(10))))
    empty = [r for r in ROLES if role_counts[r] == 0]
    log("R7_empty_roles", f"{len(empty)} roles are never any build's primary: {empty}",
        "WARN" if empty else "INFO")

    cols = list(out[0].keys())
    with open(f"{OUT}/05_roles.tsv","w",encoding="utf-8") as f:
        f.write("\t".join(cols)+"\n")
        for r in out: f.write("\t".join(str(r[c]) for c in cols)+"\n")
    json.dump({"log": LOG}, open(f"{OUT}/INT_integrity_log_phase5a.json","w"), indent=2)
    for e in LOG: print(f"  [{e['severity']}] {e['check']}: {e['detail'][:220]}")

if __name__ == "__main__":
    main()
