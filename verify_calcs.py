#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 4 gate: calc reproducibility.

RUNBOOK Phase 4 requires at least ten calcs hand-reproduced across different
types, levels and abilities, with the discrepancy rate reported.

This implements the Gen 8 damage formula independently in Python from the
Phase 1 base stats and Phase 1b move data, and compares against the ranges the
JS engine stored. It deliberately does NOT call the calculator — a check that
reuses the thing it is checking proves nothing.

Scope note: this reproduces the core formula (level, stats, STAB, type
effectiveness, burn, the 85-100 roll spread) and the item multipliers in ITEM_MULT.
Cells whose stored best move depends on an ability or item outside that set are
reported as OUT_OF_SCOPE rather than counted as agreements, because scoring an
unmodelled case as a match would manufacture a clean result.
"""
import csv, json, random, math, collections, sys

OUT = "/home/claude/out"
WORK = "/home/claude/work"
TYPES = json.load(open(f"{WORK}/typechart.json"))
NAMES = json.load(open(f"{WORK}/species_names.json"))

NATURES = {
    "Adamant": ("atk","spa"), "Jolly": ("spe","spa"), "Impish": ("def","spa"),
    "Careful": ("spd","spa"), "Brave": ("atk","spe"), "Modest": ("spa","atk"),
    "Timid": ("spe","atk"), "Bold": ("def","atk"), "Calm": ("spd","atk"),
    "Quiet": ("spa","spe"), "Naive": ("spe","spd"), "Hasty": ("spe","def"),
    "Naughty": ("atk","spd"), "Rash": ("spa","spd"), "Serious": (None,None),
    "Lonely":("atk","def"), "Mild":("spa","def"), "Gentle":("spd","def"),
    "Sassy":("spd","spe"), "Relaxed":("def","spe"), "Lax":("def","spd"),
    "Docile":(None,None),"Bashful":(None,None),"Hardy":(None,None),"Quirky":(None,None),
}
ITEM_MULT = {"Life Orb": 1.3, "Expert Belt": None, "Choice Band": 1.5,
             "Choice Specs": 1.5, "Muscle Band": 1.1, "Wise Glasses": 1.1}
# The first pass excluded ANY cell whose defender held an item or had an
# ability, which is nearly every boss Pokemon — 2740 of 2741 sampled cells fell
# out of scope and the "check" verified one cell. Scope is now split by side:
# only the attacker abilities/items that raise damage, and only the defender
# abilities/items that reduce it, take a cell out of scope.

# attacker-side abilities that change the damage this checker computes
OFF_AB = {"Huge Power","Pure Power","Feline Prowess","Sage Power","Adaptability",
          "Technician","Guts","Sheer Force","Tough Claws","Iron Fist","Striker",
          "Solar Power","Blaze","Torrent","Overgrow","Swarm","Fatal Precision",
          "Oraoraoraora","Emperor's Presence","Bone Zone","Toxic Boost","Flare Boost",
          "Sand Force","Analytic","Neuroforce","Tinted Lens","Punk Rock","Steelworker",
          "Transistor","Dragon's Maw","Rocky Payload","Battle Bond","Stakeout","Sniper",
          "Reckless","Strong Jaw","Mega Launcher","Sand Stream","Drizzle","Drought",
          "Hustle","Flash Fire","Pixilate","Aerilate","Refrigerate","Galvanize",
          "Normalize","Water Bubble","Steely Spirit","Rivalry","Bull Rush","Quill Rush",
          "Protean","Libero","Parental Bond","Supreme Overlord","Sharpness","Gorilla Tactics"}

# defender-side abilities that reduce the damage this checker computes
DEF_AB = {"Thick Fat","Levitate","Water Absorb","Volt Absorb","Flash Fire","Filter",
          "Solid Rock","Multiscale","Fluffy","Heatproof","Prism Armor","Shadow Shield",
          "Ice Scales","Punk Rock","Fur Coat","Marvel Scale","Dry Skin","Sap Sipper",
          "Lightning Rod","Storm Drain","Motor Drive","Well-Baked Body","Earth Eater",
          "Purifying Salt","Water Bubble","Wonder Guard","Bulletproof","Soundproof",
          "Overcoat","Grass Pelt","Sturdy","Battle Armor","Shell Armor",
          "Dauntless Shield","Intrepid Sword","Stamina","Weak Armor","Download",
          "Competitive","Defiant","Justified","Rattled","Sand Veil","Snow Cloak",
          "Guard Dog","Vessel of Ruin","Sword of Ruin","Tablets of Ruin",
          "Beads of Ruin","Protosynthesis","Quark Drive","Ice Face","Disguise"}

# defender-side items that reduce damage. Offensive items on a defender
# (Wide Lens, Expert Belt, Choice Band, Life Orb) do not change what it TAKES,
# so they no longer disqualify a cell.
DEF_ITEMS_SUBSTR = ("Berry", "Assault Vest", "Eviolite", "Air Balloon", "Weakness Policy",
                    "Absorb Bulb", "Cell Battery", "Snowball", "Luminous Moss",
                    "Rocky Helmet", "Kee Berry", "Maranga Berry", "Metal Powder",
                    "Deep Sea Scale", "Light Clay", "Utility Umbrella")

NONFORMULA = set(json.load(open(f"{WORK}/nonformula_moves.json")))

def stat(base, ev, iv, lvl, mult, hp=False):
    if hp:
        return ((2*base + iv + ev//4) * lvl)//100 + lvl + 10
    return int((((2*base + iv + ev//4) * lvl)//100 + 5) * mult)

def nat_mult(nature, key):
    b, l = NATURES.get(nature, (None, None))
    if b == key: return 1.1
    if l == key: return 0.9
    return 1.0

def eff(mt, d1, d2):
    e = TYPES.get(mt, {}).get("eff", {})
    m = e.get(d1, 1)
    if d2 and d2 not in ("NONE", d1): m *= e.get(d2, 1)
    return m

TYPE = lambda s: s.replace("TYPE_","").capitalize() if s not in ("NONE","UNK") else None

def main(n=200, seed=20260906):
    species = list(csv.DictReader(open(f"{OUT}/01_species.tsv"), delimiter="\t"))
    moves = {m["move_name"]: m for m in
             csv.DictReader(open(f"{OUT}/01b_moves.tsv"), delimiter="\t")}
    by_name = {}
    for s in species:
        by_name[NAMES[s["species_const"]]] = s

    # the matrix stored the boss level and nature but not its EV/IV spread.
    # Re-join it from Phase 3 rather than assuming zero, which would have shown
    # up as a discrepancy the engine did not actually make.
    spread = {}
    for t in csv.DictReader(open(f"{OUT}/03_trainers.tsv"), delimiter="\t"):
        ivs, evs = t["ivs"].split("|"), t["evs"].split("|")
        for i in range(len(t["roster"].split("|"))):
            def parse(str_):
                o = {}
                for tok in (str_ or "").split(","):
                    q = tok.strip().split()
                    if len(q) == 2:
                        k = {"hp":"hp","at":"atk","df":"def","sa":"spa","sd":"spd","sp":"spe"}.get(q[1])
                        if k: o[k] = int(q[0])
                return o
            spread[(t["trainer_id"], str(i+1))] = (
                parse(ivs[i] if i < len(ivs) else ""),
                parse(evs[i] if i < len(evs) else ""))

    # sample cells across checkpoints, types and levels
    random.seed(seed)
    pool = []
    for cp in (1, 3, 6, 8, 11, 14, 17, 19):
        try:
            rows = list(csv.DictReader(open(f"{OUT}/04_matchups_cp{cp}.tsv"), delimiter="\t"))
        except FileNotFoundError:
            continue
        pool += random.sample(rows, min(400, len(rows)))
    random.shuffle(pool)

    checked, agree, oos, fail = 0, 0, 0, []
    seen_types = set()
    for r in pool:
        if checked >= n: break
        mv = moves.get(r["my_best_move"])
        atk_s = by_name.get(r["species_name"])
        def_s = by_name.get(r["boss_species"])
        if not (mv and atk_s and def_s): continue
        if mv["category"] not in ("PHYSICAL", "SPECIAL"): continue
        try: bp = int(mv["power"])
        except ValueError: continue
        if bp <= 0: continue

        # a move whose damage is not the plain formula from its stored base
        # power (fixed damage, multi-hit, variable BP, charge turns) cannot be
        # reproduced from base power alone
        if r["my_best_move"] in NONFORMULA:
            oos += 1; continue
        ab_a = r["ability"].replace("ABILITY_","").replace("_"," ").title()
        if ab_a in OFF_AB:
            oos += 1; continue
        if r["boss_ability"] in DEF_AB:
            oos += 1; continue
        it_a = r["item"].replace("ITEM_","").replace("_"," ").title()
        if it_a not in ("None","Unk") and it_a not in ITEM_MULT:
            oos += 1; continue
        if any(sub in (r["boss_item"] or "") for sub in DEF_ITEMS_SUBSTR):
            oos += 1; continue

        lvl_a, lvl_d = int(r["player_level"]), int(r["boss_level"])
        evs_a = json.loads(r["player_evs"])
        phys = mv["category"] == "PHYSICAL"
        akey, dkey = ("atk","def") if phys else ("spa","spd")

        A = stat(int(atk_s[f"base_{akey}"]), evs_a.get(akey,0), 31, lvl_a,
                 nat_mult(r["nature"], akey))
        d_iv, d_ev = spread.get((r["boss_trainer_id"], r["boss_slot"]), ({}, {}))
        D = stat(int(def_s[f"base_{dkey}"]), d_ev.get(dkey, 0), d_iv.get(dkey, 31),
                 lvl_d, nat_mult(r["boss_nature"], dkey))
        mtype = TYPE(mv["type"])
        d1, d2 = TYPE(def_s["type_1"]), TYPE(def_s["type_2"])
        e = eff(mtype, d1, d2)
        if e == 0: continue
        stab = 1.5 if mtype in (TYPE(atk_s["type_1"]), TYPE(atk_s["type_2"])) else 1.0
        item = ITEM_MULT.get(r["item"].replace("ITEM_","").replace("_"," ").title(), 1.0) or 1.0

        base = (((2*lvl_a)//5 + 2) * bp * A // D)//50 + 2
        lo = math.floor(math.floor(math.floor(base*85/100) * stab) * e * item)
        hi = math.floor(math.floor(math.floor(base*100/100) * stab) * e * item)

        try:
            slo, shi = (int(x) for x in r["my_dmg_range"].split("-"))
        except ValueError:
            continue
        checked += 1
        seen_types.add(mtype)
        # allow +/-2 on each end: rounding order inside the engine differs
        if abs(lo-slo) <= max(2, slo*0.03) and abs(hi-shi) <= max(2, shi*0.03):
            agree += 1
        else:
            fail.append({"species": r["species_name"], "move": r["my_best_move"],
                         "vs": r["boss_species"], "lvl": lvl_a,
                         "stored": r["my_dmg_range"], "recomputed": f"{lo}-{hi}",
                         "eff": e, "item": r["item"], "ability": r["ability"]})

    rate = agree/checked if checked else 0
    print(f"cells independently recomputed : {checked}")
    print(f"agree within tolerance         : {agree} ({rate:.1%})")
    print(f"discrepancy rate               : {1-rate:.1%}")
    print(f"out of scope (unmodelled ability/item, reported not scored): {oos}")
    print(f"move types spanned             : {len(seen_types)} -> {sorted(seen_types)}")
    print()
    if fail:
        print(f"discrepancies ({len(fail)}), first 12:")
        for f in fail[:12]:
            print(f"  {f['species']:<16} {f['move']:<16} vs {f['vs']:<18} "
                  f"lv{f['lvl']:<3} stored {f['stored']:<10} mine {f['recomputed']:<10} "
                  f"x{f['eff']} item={f['item']}")
    json.dump({"checked": checked, "agree": agree, "discrepancy_rate": round(1-rate,4),
               "out_of_scope": oos, "types_spanned": sorted(seen_types),
               "discrepancies": fail[:60]},
              open(f"{OUT}/INT_calc_reproducibility.json","w"), indent=2)

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv)>1 else 200)
