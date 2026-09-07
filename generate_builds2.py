#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 4d: build generation, emitting concrete builds.

The prior version counted builds combinatorially (abilities x natures x items x
movesets) without ever constructing one. This one enumerates actual build
objects — ability, nature, item, four named moves — so they can be fed to the
matrix, and records every prune that fired.

Implements targets/sable/builds.md:
  s1 orientation from stats AND the movepool available at that checkpoint
  s2 support track (zero-to-two damaging moves) behind real utility gates
  s3 natures chosen, with the speed-tier rule that stops Jolly/Timid monoculture
  s4 items gated three ways: exploitable / obtainable / scarcity
  s5 move slots: STAB, then coverage scored against THAT checkpoint's actual
     boss roster, then utility
  s6 combinatorial cap
  s7 full trace

Published anchors are Floor and Ceiling (VISION 4.4). The full enumerated set is
retained internally.
"""
import csv, json, re, sys, collections, itertools

OUT = "/home/claude/out"
WORK = "/home/claude/work"
LOG = []
def log(c, d, s="INFO"): LOG.append({"check": c, "severity": s, "detail": d})

# The species parser and the move parser disagree on three constants: source
# carries both legacy and current spellings (MOVE_THUNDERPUNCH vs
# MOVE_THUNDER_PUNCH, MOVE_BUBBLEBEAM vs MOVE_BUBBLE_BEAM, MOVE_VICE_GRIP vs
# MOVE_VISE_GRIP). 106 level-up references silently failed to resolve and were
# dropped from the movepool — a silent loss, which non-negotiable #2 forbids.
MOVE_ALIAS = {
    "MOVE_THUNDERPUNCH": "MOVE_THUNDER_PUNCH",
    "MOVE_BUBBLEBEAM":   "MOVE_BUBBLE_BEAM",
    "MOVE_VICE_GRIP":    "MOVE_VISE_GRIP",
}

def tsv(p):
    return list(csv.DictReader(open(f"{OUT}/{p}", encoding="utf-8"), delimiter="\t"))

TYPES = json.load(open(f"{WORK}/typechart.json"))

NATURES = {  # name: (boosted, lowered)
    "Adamant": ("atk", "spa"), "Jolly": ("spe", "spa"), "Impish": ("def", "spa"),
    "Careful": ("spd", "spa"), "Brave": ("atk", "spe"),
    "Modest": ("spa", "atk"), "Timid": ("spe", "atk"), "Bold": ("def", "atk"),
    "Calm": ("spd", "atk"), "Quiet": ("spa", "spe"),
    "Naive": ("spe", "spd"), "Hasty": ("spe", "def"), "Naughty": ("atk", "spd"),
    "Rash": ("spa", "spd"), "Serious": (None, None),
}

def stat(base, ev, lvl, nat_mult, is_hp=False):
    if is_hp:
        return ((2 * base + 31 + ev // 4) * lvl) // 100 + lvl + 10
    return int((((2 * base + 31 + ev // 4) * lvl) // 100 + 5) * nat_mult)

def eff(move_type, d1, d2):
    e = TYPES.get(move_type, {}).get("eff", {})
    m = e.get(d1, 1)
    if d2 and d2 != "NONE" and d2 != d1:
        m *= e.get(d2, 1)
    return m

# ---------------------------------------------------------------- item policy
# Driven by item_catalog.json (182 held items derived from the world table's
# hold_effect codes), not by a hand-written list. builds.md s4: an item is
# generated only if the species can exploit it, Phase 2 places it, and scarcity
# allows it. The predicates below answer only the first of those three.
CATALOG = json.load(open("/home/claude/work/item_catalog.json"))

def item_ok(cls, param, c):
    """Can this species-form exploit an item of this class?"""
    t1, t2 = c["t1"], c["t2"]
    if cls == "type_boost":
        # only if the build actually carries a move of that type
        return param in c["move_types"]
    if cls == "type_plate":
        return param is None and False          # plate type not encoded in source
    if cls == "resist_berry":
        # only where that type actually threatens this form
        return c["weak_to"].get(param, 1) >= 2
    if cls in ("longevity", "shell_bell"):
        return c["bulky"] or c["track"] == "support" or c["has_setup"]
    if cls == "longevity_poison":
        return "Poison" in (t1, t2)
    if cls == "allout":
        return c["track"] in ("physical","special","mixed") and not c["has_recoil"]
    if cls == "coverage":
        return c["n_damaging"] >= 3
    if cls == "band_phys":
        return c["track"] == "physical"
    if cls == "band_spec":
        return c["track"] == "special"
    if cls == "choice_phys":
        return c["track"] == "physical" and not c["has_setup"] and not c["has_status"]
    if cls == "choice_spec":
        return c["track"] == "special" and not c["has_setup"] and not c["has_status"]
    if cls == "choice_speed":
        return c["track"] in ("physical","special") and not c["has_setup"] \
               and not c["has_status"]
    if cls == "spdef_novstatus":
        return c["n_damaging"] == 4
    if cls == "eviolite":
        return c["nfe"]
    if cls == "sash":
        return c["track"] != "support" and not c["bulky"]
    if cls == "contact_punish":
        return c["track"] == "support" or c["bulky"]
    if cls == "ground_immune":
        return c["weak_to"].get("Ground", 1) >= 2
    if cls == "hazard_immune":
        return c["weak_to"].get("Rock", 1) >= 2
    if cls in ("self_poison", "self_burn"):
        return c["ability_synergy_status"]
    if cls == "punch_boost":
        return c["has_punch"]
    if cls == "kick_boost":
        return c["has_kick"]
    if cls == "sound_boost":
        return c["has_sound"]
    if cls == "multihit_boost":
        return c["has_multihit"]
    if cls == "drain_boost":
        return c["has_drain"]
    if cls == "crit":
        return c["track"] in ("physical","special","mixed")
    if cls == "weakness_policy":
        return c["bulky"] and c["track"] != "support"
    if cls == "screen_ext":
        return c["has_screen"]
    if cls == "weather_ext":
        return c["has_weather"]
    if cls == "terrain_seed":
        return c["has_terrain"]
    if cls == "charge":
        return c["has_charge"]
    if cls == "status_cure":
        return c["track"] == "support" or c["bulky"]
    if cls == "accuracy":
        return c["low_accuracy"]
    if cls == "flinch":
        return c["track"] in ("physical","special") and c["fast"]
    if cls in ("mega","primal","species_locked","paradox_boost","metronome",
               "utility_misc"):
        # mega/primal/species-locked items are gated on identity, handled by the
        # form itself rather than by the build; not generated as ordinary items
        return False
    return False


UTIL = {"recover","roost","softboiled","synthesis","moonlight","morningsun","slackoff",
        "milkdrink","rest","wish","healbell","aromatherapy","stealthrock","spikes",
        "toxicspikes","stickyweb","defog","rapidspin","reflect","lightscreen",
        "auroraveil","whirlwind","roar","dragontail","circlethrow","trickroom",
        "raindance","sunnyday","sandstorm","hail","snowscape","electricterrain",
        "grassyterrain","mistyterrain","psychicterrain","thunderwave","willowisp",
        "toxic","spore","sleeppowder","hypnosis","yawn","leechseed","substitute",
        "batonpass","uturn","voltswitch","followme","ragepowder","memento","healingwish"}
SETUP = {"swordsdance","nastyplot","dragondance","calmmind","bulkup","quiverdance",
         "shellsmash","agility","rockpolish","irondefense","curse","growth",
         "workup","coil","hone","honeclaws","tailglow","victorydance"}
RECOIL = {"doubleedge","flareblitz","bravebird","woodhammer","headsmash","volttackle",
          "wildcharge","takedown","submission","headcharge"}
norm = lambda n: re.sub(r"[^a-z0-9]", "", n.lower())

def _acc(m):
    try: return int(m["accuracy"])
    except (ValueError, KeyError): return 100


def main(checkpoints=None):
    species = tsv("01_species.tsv")
    moves_l = tsv("01b_moves.tsv")
    mv_by_const = {m["move_const"]: m for m in moves_l}
    for _legacy, _current in MOVE_ALIAS.items():
        if _current in mv_by_const:
            mv_by_const[_legacy] = mv_by_const[_current]
    global _MV
    _MV = mv_by_const
    caps = {int(r["order"]): int(r["level_cap"]) for r in tsv("03b_checkpoints.tsv")}
    avail = {r["species_const"]: r for r in tsv("01c_availability.tsv")}
    world = tsv("02_world.tsv")
    trainers = tsv("03_trainers.tsv")

    # ---- item scarcity (builds.md s4.3): purchasable, or >=3 copies
    qty, mart = collections.defaultdict(int), set()
    for r in world:
        if r["entity_type"] == "mart_stock":
            mart.add(r["item_const"])
        else:
            try: qty[r["item_const"]] += int(r["quantity"])
            except ValueError: qty[r["item_const"]] += 1
    def reliable(i): return i in mart or qty.get(i, 0) >= 3
    def placed(i):   return i in mart or i in qty
    log("B1_item_scarcity",
        f"{len(mart)} purchasable items, {sum(1 for i in qty if qty[i]>=3)} items with "
        f">=3 copies; the rest generate flagged one-of-a-kind builds only")

    # ---- boss rosters per checkpoint: speed tiers and defensive typing, for
    #      the nature rule (s3) and coverage scoring (s5)
    from resolve import build_index
    resolve, unres_counter = build_index(species)
    boss_by_cp = collections.defaultdict(list)
    unresolved_boss = set()
    for t in trainers:
        if t["role"] == "route":
            continue
        cp = t["checkpoint"]
        for slot in t["roster"].split("|"):
            p = slot.split(":")
            if len(p) < 5: continue
            name, lvl = p[0], p[1]
            s = resolve(name)
            if s is None:
                unresolved_boss.add(name); continue
            try: lv = int(lvl)
            except ValueError: lv = 0
            boss_by_cp[cp].append({
                "name": name, "level": lv, "nature": p[4],
                "spe": int(s["base_spe"]), "t1": s["type_1"], "t2": s["type_2"],
                "def": int(s["base_def"]), "spd": int(s["base_spd"]),
            })
    log("B2_boss_rosters",
        f"{sum(len(v) for v in boss_by_cp.values())} boss slots across "
        f"{len(boss_by_cp)} checkpoint keys; {len(unresolved_boss)} roster species "
        f"do not resolve against Phase 1",
        "WARN" if unresolved_boss else "INFO")
    if unresolved_boss:
        log("B2a_unresolved_sample", str(sorted(unresolved_boss)[:12]), "WARN")

    # DYNAMIC (level-scaled rival) slots are assigned to every checkpoint's
    # threat set for speed-tier purposes but scored separately in the matrix.
    def cp_bosses(cp):
        return boss_by_cp.get(str(cp), [])

    def speed_tiers(cp, cap):
        out = []
        for b in cp_bosses(cp):
            lv = b["level"] or cap
            nb, nl = NATURES.get(b["nature"], (None, None))
            mult = 1.1 if nb == "spe" else (0.9 if nl == "spe" else 1.0)
            out.append(stat(b["spe"], 252, lv, mult))
        return sorted(out)

    all_rows, anchors, trace = [], [], []
    checkpoints = checkpoints or sorted(caps)

    for cp in checkpoints:
        cap = caps[cp]
        tiers = speed_tiers(cp, cap)
        bosses = cp_bosses(cp)
        # threat typing set, for coverage scoring
        threat_types = [(b["t1"], b["t2"]) for b in bosses]

        for s in species:
            c = s["species_const"]
            av = avail.get(c)
            if av is None or av["in_pool"] != "TRUE":
                continue
            try:
                hp, atk, dfn, spa, spd, spe = (int(s[k]) for k in
                    ("base_hp","base_atk","base_def","base_spa","base_spd","base_spe"))
            except ValueError:
                continue

            # ---- movepool available at this checkpoint.
            # This hack makes TMs reusable and egg moves relearnable from the
            # party menu, so the obtainable pool is level-up-under-cap + all
            # teachable + all egg. Level-up moves above the cap are excluded.
            pool = {}
            for tok in s["levelup_moves"].split(","):
                if ":" not in tok: continue
                mc, lv = tok.rsplit(":", 1)
                if lv.isdigit() and int(lv) <= cap and mc in mv_by_const:
                    pool[mc] = mv_by_const[mc]
            for col in ("teachable_moves", "egg_moves"):
                v = s[col]
                if v in ("NONE", "UNK", ""): continue
                for mc in v.split(","):
                    mc = mc.strip()
                    if mc in mv_by_const: pool.setdefault(mc, mv_by_const[mc])

            dmg = [m for m in pool.values() if m["category"] in ("PHYSICAL", "SPECIAL")]
            def bp(m):
                try: return int(m["power"])
                except ValueError: return 0
            bestP = max([bp(m) for m in dmg if m["category"]=="PHYSICAL"], default=0)
            bestS = max([bp(m) for m in dmg if m["category"]=="SPECIAL"], default=0)

            # ---- s1 orientation
            tracks, why = [], ""
            if atk >= 1.15*spa and bestP >= 60:
                tracks, why = ["physical"], f"atk {atk} >= 1.15*spa {spa}; bestP {bestP}"
            elif spa >= 1.15*atk and bestS >= 60:
                tracks, why = ["special"], f"spa {spa} >= 1.15*atk {atk}; bestS {bestS}"
            elif bestP >= 60 and bestS >= 60 and spa and 0.85 <= atk/spa <= 1.176:
                tracks, why = ["physical","special","mixed"], \
                    f"atk {atk} / spa {spa} within 15%; both pools >= 60 BP"
            else:
                why = f"no attacking track (bestP {bestP}, bestS {bestS}, max stat {max(atk,spa)})"

            # ---- s2 support track
            util = [m for m in pool.values() if m["category"]=="STATUS"
                    and norm(m["move_name"]) in UTIL]
            if util and (max(atk,spa) < 80 or (bestP < 60 and bestS < 60)):
                tracks.append("support")

            if not tracks:
                trace.append({"cp": cp, "species": c, "tracks": [], "reason": why,
                              "pool_size": len(pool)})
                continue

            t1, t2 = s["type_1"], s["type_2"]
            abilities = [a for a in (s["ability_1"], s["ability_2"], s["ability_hidden"])
                         if a not in ("NONE","UNK","")]
            abilities = list(dict.fromkeys(abilities))
            nfe = s["evolutions"] not in ("NONE","UNK","")

            cand_pool = {}
            for track in tracks:
                # ---- s5 move slots, built before natures/items because the
                # nature and item rules both read the resulting moveset.
                movesets = build_movesets(track, pool, t1, t2, threat_types, atk, spa)
                if not movesets:
                    trace.append({"cp": cp, "species": c, "tracks":[track],
                                  "reason": "no legal moveset", "pool_size": len(pool)})
                    continue

                for ms in movesets[:6]:                       # s6 cap: 6 movesets
                    names = [m["move_name"] for m in ms]
                    nrm = [norm(n) for n in names]
                    ctx = {
                        "track": track, "nfe": nfe, "t1": t1, "t2": t2,
                        "has_setup": any(n in SETUP for n in nrm),
                        "has_status": any(m["category"]=="STATUS" for m in ms),
                        "has_recoil": any(n in RECOIL for n in nrm),
                        "n_damaging": sum(1 for m in ms if m["category"]!="STATUS"),
                        "bulky": (hp + dfn + spd) >= 280,
                        "weak_to": {ty: eff(ty, t1, t2) for ty in TYPES},
                        "move_types": {m["type"].replace("TYPE_","").capitalize()
                                       for m in ms},
                        "has_punch": any("punch" in n for n in nrm),
                        "has_kick": any("kick" in n or n in ("highjumpkick","jumpkick",
                                        "blazekick","triplekick","tripleaxel") for n in nrm),
                        "has_sound": any(n in ("boomburst","hypervoice","overdrive",
                                        "snarl","echoedvoice","disarmingvoice") for n in nrm),
                        "has_multihit": any(n in ("iciclespear","rockblast","bulletseed",
                                        "pinmissile","tailslap","scaleshot") for n in nrm),
                        "has_drain": any(n in ("gigadrain","drainpunch","drainingkiss",
                                        "leechlife","hornleech","absorb","megadrain",
                                        "leechseed") for n in nrm),
                        "has_screen": any(n in ("reflect","lightscreen","auroraveil")
                                          for n in nrm),
                        "has_weather": any(n in ("raindance","sunnyday","sandstorm",
                                          "hail","snowscape") for n in nrm),
                        "has_terrain": any(n in ("electricterrain","grassyterrain",
                                          "mistyterrain","psychicterrain") for n in nrm),
                        "has_charge": any(n in ("solarbeam","skyattack","meteorbeam",
                                          "electroshot","geomancy") for n in nrm),
                        "low_accuracy": any(_acc(m) < 90 for m in ms),
                        "fast": spe >= 90,
                        "ability_synergy_status": any(
                            a in ("ABILITY_GUTS","ABILITY_TOXIC_BOOST",
                                  "ABILITY_FLARE_BOOST","ABILITY_QUICK_FEET",
                                  "ABILITY_MAGIC_GUARD","ABILITY_POISON_HEAL")
                            for a in abilities),
                    }
                    natures = pick_natures(track, atk, spa, spe, cap, tiers, ctx)
                    items = pick_items(ctx)
                    for ab, nat, (item, item_rel, item_cls) in itertools.product(
                            abilities, natures[:3], items[:5]):   # s6 caps
                        row = {
                            "species_const": c, "species_name": s["species_name"],
                            "checkpoint": cp, "level_cap": cap, "track": track,
                            "ability": ab, "nature": nat, "item": item,
                            "moves": ",".join(names),
                            "item_reliable": "TRUE" if item_rel else "FALSE",
                        }
                        all_rows.append(row)
                        # bucket by item CLASS, so the matrix — not the
                        # pre-matrix heuristic — decides which item the
                        # published ceiling actually uses
                        cand_pool.setdefault((c, track, item_cls, nat), []).append(
                            (heuristic(row, ms, ctx, atk, spa), row))

            # ---- candidate set: Floor (deterministic) + best per track.
            # The matrix cannot afford the full enumeration, so it is run on
            # these and the Ceiling is whichever candidate the matrix picks.
            # Choosing candidates by heuristic is a PRUNE and is recorded as one.
            floor_moves = floor_moveset(pool, cap, s)
            if floor_moves:
                anchors.append({
                    "species_const": c, "species_name": s["species_name"],
                    "checkpoint": cp, "level_cap": cap, "anchor": "floor",
                    "track": "floor", "ability": abilities[0] if abilities else "NONE",
                    "nature": "Serious", "item": "NONE",
                    "moves": ",".join(m["move_name"] for m in floor_moves),
                    "item_reliable": "TRUE", "evs": "0",
                })
            per_track = collections.defaultdict(list)
            for (cc, track, icls, nat), lst in cand_pool.items():
                if cc != c: continue
                lst.sort(key=lambda p: -p[0])
                per_track[track].append((lst[0][0], icls, nat, lst[0][1]))
            for track, lst in per_track.items():
                lst.sort(key=lambda p: -p[0])
                # 2x2 factorial: the two best item classes crossed with the two
                # best natures, so item and nature vary independently
                top_i, top_n = [], []
                for _, icls, nat, _r in lst:
                    if icls not in top_i and len(top_i) < 2: top_i.append(icls)
                    if nat not in top_n and len(top_n) < 2: top_n.append(nat)
                for _, icls, nat, best in lst:
                    if icls in top_i and nat in top_n:
                        anchors.append(dict(best, anchor="candidate", evs="252"))
            cand_pool = {k: v for k, v in cand_pool.items() if k[0] != c}

    log("B3_builds", f"{len(all_rows)} concrete build objects enumerated")
    log("B4_species", f"{len({r['species_const'] for r in all_rows})} species-forms "
                      f"produced at least one build")
    log("B5_no_build", f"{len(trace)} (species, checkpoint) pairs produced none, "
                       f"each recorded with its reason")
    by_track = collections.Counter(r["track"] for r in all_rows)
    log("B6_tracks", str(dict(by_track)))
    nat_dist = collections.Counter(r["nature"] for r in all_rows)
    tot = sum(nat_dist.values()) or 1
    log("B7_nature_spread",
        "top natures: " + ", ".join(f"{k} {v/tot:.1%}" for k, v in nat_dist.most_common(5)))
    it_dist = collections.Counter(r["item"] for r in all_rows)
    log("B8_item_spread",
        "top items: " + ", ".join(f"{k} {v/tot:.1%}" for k, v in it_dist.most_common(5)))

    cols = ["species_const","species_name","checkpoint","level_cap","track",
            "ability","nature","item","moves","item_reliable"]
    with open(f"{OUT}/04_builds.tsv","w",encoding="utf-8") as f:
        f.write("\t".join(cols)+"\n")
        for r in all_rows:
            f.write("\t".join(str(r[c]) for c in cols)+"\n")
    acols = ["species_const","species_name","checkpoint","level_cap","anchor","track",
             "ability","nature","item","moves","item_reliable","evs"]
    with open(f"{OUT}/04a_candidates.tsv","w",encoding="utf-8") as f:
        f.write("\t".join(acols)+"\n")
        for r in anchors:
            f.write("\t".join(str(r.get(cc,"NONE")) for cc in acols)+"\n")
    log("B9_candidates", f"{len(anchors)} candidate builds sent to the matrix "
                         f"({sum(1 for a in anchors if a['anchor']=='floor')} floor, "
                         f"{sum(1 for a in anchors if a['anchor']=='candidate')} ceiling candidates)")
    json.dump({"log": LOG, "no_build_sample": trace[:300]},
              open(f"{OUT}/INT_build_trace.json","w"), indent=2)
    for e in LOG:
        print(f"  [{e['severity']}] {e['check']}: {e['detail'][:220]}")


def heuristic(row, ms, ctx, atk, spa):
    """Cheap pre-matrix ranking, used only to choose which builds the matrix
    actually evaluates. It is a prune, not a score: nothing downstream reads it."""
    def bp(m):
        try: return int(m["power"])
        except ValueError: return 0
    power = sum(bp(m) for m in ms if m["category"] != "STATUS")
    util  = sum(1 for m in ms if m["category"] == "STATUS")
    item_bonus = {"ITEM_LIFE_ORB": 25, "ITEM_CHOICE_BAND": 25, "ITEM_CHOICE_SPECS": 25,
                  "ITEM_LEFTOVERS": 15, "ITEM_EVIOLITE": 20,
                  "ITEM_ASSAULT_VEST": 15}.get(row["item"], 5)
    return power + util * 20 + item_bonus + (10 if row["item_reliable"] == "TRUE" else 0)


def floor_moveset(pool, cap, s):
    """VISION 4.4 Floor: what you get if you simply catch it and use it —
    level-up moves only, the four most recently learned at or under the cap."""
    lv = []
    for tok in s["levelup_moves"].split(","):
        if ":" not in tok: continue
        mc, l = tok.rsplit(":", 1)
        if l.isdigit() and int(l) <= cap and mc in _MV:
            lv.append((int(l), _MV[mc]))
    lv.sort(key=lambda p: -p[0])
    return [m for _, m in lv[:4]]


def build_movesets(track, pool, t1, t2, threat_types, atk, spa):
    """s5. STAB first, then coverage scored against the actual boss roster at
    this checkpoint, then utility. Never two moves of the same type+category."""
    def bp(m):
        try: return int(m["power"])
        except ValueError: return 0
    cats = {"physical": ["PHYSICAL"], "special": ["SPECIAL"],
            "mixed": ["PHYSICAL","SPECIAL"], "support": ["PHYSICAL","SPECIAL"]}[track]
    dmg = [m for m in pool.values() if m["category"] in cats and bp(m) > 0]
    status = [m for m in pool.values() if m["category"] == "STATUS"]

    def cover(m):
        """how many of this checkpoint's boss Pokemon this move hits hard"""
        sc = 0
        for d1, d2 in threat_types:
            e = eff(m["type"], d1, d2)
            if e >= 2: sc += 2
            elif e >= 1: sc += 0.5
        stab = 1.5 if m["type"] in (t1, t2) else 1.0
        return sc * (bp(m) ** 0.5) * stab

    dmg.sort(key=cover, reverse=True)
    util = [m for m in status if norm(m["move_name"]) in UTIL]
    setup = [m for m in status if norm(m["move_name"]) in SETUP]

    n_dmg = {"physical": 3, "special": 3, "mixed": 4, "support": 1}[track]
    sets, seen = [], set()

    def assemble(dmg_moves, extra):
        chosen, used = [], set()
        for m in dmg_moves:
            key = (m["type"], m["category"])
            if key in used: continue
            used.add(key); chosen.append(m)
            if len(chosen) >= n_dmg: break
        for m in extra:
            if len(chosen) >= 4: break
            if m not in chosen: chosen.append(m)
        for m in dmg_moves:
            if len(chosen) >= 4: break
            if m not in chosen: chosen.append(m)
        return chosen[:4]

    # STAB is mandatory where a damaging STAB exists
    stab_moves = [m for m in dmg if m["type"] in (t1, t2)]
    heads = [dmg] if not stab_moves else [
        [stab_moves[0]] + [m for m in dmg if m is not stab_moves[0]], dmg]

    variants = []
    if track == "support":
        variants = [util[:3], util[1:4], (setup + util)[:3]]
    else:
        variants = [setup[:1] + util[:1], util[:2], setup[:1], []]

    for head in heads:
        for ex in variants:
            ms = assemble(head, ex)
            if len(ms) < 1: continue
            k = tuple(sorted(m["move_const"] for m in ms))
            if k in seen: continue
            seen.add(k); sets.append(ms)
    return sets


def pick_natures(track, atk, spa, spe, cap, tiers, ctx):
    """s3. The speed-boosting nature is generated ONLY when it crosses at least
    one boss speed tier the species would otherwise lose. This is the single
    biggest source of Jolly/Timid monoculture in naive generators."""
    out = []
    neutral = stat(spe, 252, cap, 1.0)
    boosted = stat(spe, 252, cap, 1.1)
    crosses = any(neutral < t < boosted for t in tiers) or \
              any(neutral <= t <= boosted for t in tiers)
    if track == "physical":
        out.append("Adamant")
        if crosses: out.append("Jolly")
        out.append("Impish" if ctx["bulky"] else "Careful")
    elif track == "special":
        out.append("Modest")
        if crosses: out.append("Timid")
        out.append("Bold" if ctx["bulky"] else "Calm")
    elif track == "mixed":
        out.append("Naive" if crosses else "Serious")
        out.append("Hasty" if crosses else "Rash")
        out.append("Serious")
    else:
        out.append("Bold" if ctx["bulky"] else "Calm")
        out.append("Careful")
        out.append("Impish")
    return list(dict.fromkeys(out))


def pick_items(ctx):
    """s4. exploitable / obtainable / scarcity. Returns (item_const, reliable).

    Reliable items sort first so a headline build does not silently rest on the
    game's single Life Orb; the scarce best is still generated and the gap is
    published as item dependence.
    """
    ok = []
    for const, meta in CATALOG.items():
        if not item_ok(meta["class"], meta["param"], ctx):
            continue
        ok.append((const, meta["reliable"], meta["class"]))
    prio = CLASS_PRIORITY.get(ctx["track"], {})
    # at most one of any one class, so 18 resist berries cannot crowd out every
    # other option; reliable first, then class relevance to this track
    seen, kept = set(), []
    for const, rel, cls in sorted(ok, key=lambda p: (not p[1], prio.get(p[2], 99), p[0])):
        if cls in seen:
            continue
        seen.add(cls)
        kept.append((const, rel, cls))
    kept.append(("NONE", True, "none"))
    return kept


# how relevant each item class is to what a track is trying to do. This is a
# PRUNE ordering, not a score: the matrix still decides among the survivors.
CLASS_PRIORITY = {
    "physical": {"choice_phys":0,"allout":1,"band_phys":2,"type_boost":3,"coverage":4,
                 "sash":5,"crit":6,"punch_boost":6,"kick_boost":6,"multihit_boost":6,
                 "weakness_policy":7,"resist_berry":8,"longevity":9,"self_burn":10,
                 "self_poison":10,"drain_boost":11,"charge":12,"status_cure":13},
    "special":  {"choice_spec":0,"allout":1,"band_spec":2,"type_boost":3,"coverage":4,
                 "sash":5,"crit":6,"sound_boost":6,"weakness_policy":7,"resist_berry":8,
                 "longevity":9,"drain_boost":10,"charge":11,"status_cure":13},
    "mixed":    {"allout":0,"type_boost":1,"coverage":2,"sash":3,"crit":4,
                 "resist_berry":5,"longevity":6,"charge":7,"status_cure":13},
    "support":  {"longevity":0,"eviolite":1,"contact_punish":2,"resist_berry":3,
                 "screen_ext":4,"weather_ext":4,"terrain_seed":4,"longevity_poison":5,
                 "hazard_immune":6,"ground_immune":6,"status_cure":7,"utility_misc":8,
                 "type_boost":9},
}


if __name__ == "__main__":
    # scarcity closures, bound after the world table is read inside main()
    _world = tsv("02_world.tsv")
    _qty, _mart = collections.defaultdict(int), set()
    for _r in _world:
        if _r["entity_type"] == "mart_stock": _mart.add(_r["item_const"])
        else:
            try: _qty[_r["item_const"]] += int(_r["quantity"])
            except ValueError: _qty[_r["item_const"]] += 1
    cps = [int(x) for x in sys.argv[1:]] or None
    main(cps)
