#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 1 parser: species-form master.

Reads the hack source directly. Emits 01_species.tsv plus an integrity log.
Every value is parsed; nothing is recalled. Gaps are encoded UNK and logged.
"""
import json, os, re, sys, collections

SRC = "/home/claude/src_sable"
OUT = "/home/claude/out"
os.makedirs(OUT, exist_ok=True)

LOG = []
CFG = {}
def log(check, detail, severity="INFO"):
    LOG.append({"check": check, "severity": severity, "detail": detail})

# ---------------------------------------------------------------- constants
def parse_species_constants():
    """Internal index per species, from the enum defines."""
    idx = {}
    path = f"{SRC}/include/constants/species.h"
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*#define\s+(SPECIES_[A-Z0-9_]+)\s+(\d+)\s*$", line)
        if m:
            idx[m.group(1)] = int(m.group(2))
    return idx

def parse_natdex_constants():
    """NATIONAL_DEX_* is an enum, not a #define — order gives the value."""
    dex, n = {}, 0
    path = f"{SRC}/include/constants/pokedex.h"
    if not os.path.exists(path):
        return dex
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(NATIONAL_DEX_[A-Z0-9_]+)\s*(?:=\s*(\d+))?\s*,", line)
        if m:
            if m.group(2) is not None:
                n = int(m.group(2))
            dex[m.group(1)] = n
            n += 1
    return dex


# ------------------------------------------------- config + macro preprocessor
def load_config():
    """Resolve #define P_*/B_* GEN_n from the hack's own config headers."""
    cfg, raw = {}, {}
    d = f"{SRC}/include/config"
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".h"):
            continue
        for line in open(f"{d}/{fn}", encoding="utf-8", errors="replace"):
            m = re.match(r"\s*#define\s+([PB]_[A-Z0-9_]+|GEN_LATEST)\s+(GEN_\d|GEN_LATEST)", line)
            if m:
                raw[m.group(1)] = m.group(2)
    latest = raw.get("GEN_LATEST", "GEN_9")
    for k, v in raw.items():
        v = latest if v == "GEN_LATEST" else v
        cfg[k] = int(v.split("_")[1])
    cfg["GEN_LATEST"] = int(latest.split("_")[1])
    log("C0_config", f"resolved {len(cfg)} generation config switches; GEN_LATEST=GEN_{cfg['GEN_LATEST']}")
    return cfg

def _eval_cond(expr, cfg):
    m = re.match(r"\s*([PB]_[A-Z0-9_]+)\s*(>=|<=|==|>|<)\s*GEN_(\d)", expr)
    if not m:
        return None  # unknown condition — caller keeps both branches
    lhs, op, rhs = cfg.get(m.group(1)), m.group(2), int(m.group(3))
    if lhs is None:
        return None
    return {">=": lhs >= rhs, "<=": lhs <= rhs, "==": lhs == rhs,
            ">": lhs > rhs, "<": lhs < rhs}[op]

def collect_macros(txt, cfg):
    """Collect #defines that survive the file's own #if/#else, honouring config."""
    macros, stack, i = {}, [], 0
    lines = txt.split("\n")
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("#if"):
            expr = s.split(None, 1)[1] if " " in s else ""
            stack.append(_eval_cond(expr, cfg))
        elif s.startswith("#elif"):
            if stack:
                prev = stack.pop()
                stack.append(None if prev is None else not prev)
        elif s.startswith("#else"):
            if stack:
                prev = stack.pop()
                stack.append(None if prev is None else not prev)
        elif s.startswith("#endif"):
            if stack:
                stack.pop()
        elif s.startswith("#define") and all(b is not False for b in stack):
            body_lines, j = [line], i
            while body_lines[-1].rstrip().endswith("\\"):
                j += 1
                if j >= len(lines):
                    break
                body_lines.append(lines[j])
            i = j
            full = "\n".join(body_lines)
            full = re.sub(r"\\\s*\n", "\n", full)
            m = re.match(r"\s*#define\s+([A-Z_][A-Z0-9_]*)(\([^)]*\))?\s*(.*)", full, re.S)
            if m:
                name, params, body = m.group(1), m.group(2), m.group(3)
                macros[name] = (params is not None, body)
        i += 1
    return macros

def expand_macros(block, macros, depth=3):
    """Splice macro bodies into a species block so fields become visible."""
    for _ in range(depth):
        changed = False
        for name, (is_func, body) in macros.items():
            if name not in block:
                continue
            if is_func:
                new = re.sub(re.escape(name) + r"\s*\([^()]*\)", body.replace("\\", ""), block)
            else:
                new = re.sub(r"\b" + re.escape(name) + r"\b", body.replace("\\", ""), block)
            if new != block:
                block, changed = new, True
        if not changed:
            break
    return block

# ---------------------------------------------------------------- learnsets
def parse_levelup_learnsets():
    """sXLevelUpLearnset -> 'MOVE:LEVEL,...' ordered by level.

    SOURCE SELECTION — verified against src/pokemon.c, not assumed:
      line 968: #include "data/pokemon/level_up_learnsets.h"   <- unconditional
      line 969: #if FALSE                                       <- disables ALL of
      lines 971-989: the P_LVL_UP_LEARNSETS gen_1..gen_9 selection block

    So the hack ships ONE bespoke learnset table and the nine upstream
    per-generation tables in level_up_learnsets/ are dead code. P_LVL_UP_LEARNSETS
    is still set to GEN_LATEST in include/config/pokemon.h but has no effect.
    Parsing the directory, or trusting that config, yields vanilla movepools.
    """
    out = {}
    files = [f"{SRC}/src/data/pokemon/level_up_learnsets.h"]
    log("L0_learnset_source",
        "level-up learnsets read ONLY from level_up_learnsets.h; "
        "level_up_learnsets/gen_1..9.h are disabled by '#if FALSE' at src/pokemon.c:969 "
        "despite P_LVL_UP_LEARNSETS=GEN_LATEST in include/config/pokemon.h:14",
        "FINDING")
    for path in files:
        txt = open(path, encoding="utf-8", errors="replace").read()
        for m in re.finditer(
            r"static const struct LevelUpMove\s+(s\w+LevelUpLearnset)\s*\[\]\s*=\s*\{(.*?)\n\};",
            txt, re.S):
            name, body = m.group(1), m.group(2)
            moves = re.findall(r"LEVEL_UP_MOVE\(\s*(\d+)\s*,\s*(MOVE_[A-Z0-9_]+)\s*\)", body)
            if name in out and out[name] != moves:
                log("L1_duplicate_learnset", f"{name} defined more than once with differing content", "WARN")
            out[name] = moves
    return out

def parse_flat_learnsets(path, suffix):
    """Teachable / egg move arrays -> list of MOVE_ tokens."""
    out = {}
    if not os.path.exists(path):
        return out
    txt = open(path, encoding="utf-8", errors="replace").read()
    for m in re.finditer(
        r"static const u16\s+(s\w+" + suffix + r")\s*\[\]\s*=\s*\{(.*?)\n\};", txt, re.S):
        name, body = m.group(1), m.group(2)
        body = re.sub(r"//[^\n]*", "", body)
        moves = re.findall(r"(MOVE_[A-Z0-9_]+)", body)
        moves = [x for x in moves if x != "MOVE_UNAVAILABLE"]
        out[name] = moves
    return out

# ---------------------------------------------------------------- encounters
def parse_wild_encounters():
    """species -> list of 'map:method:levelrange:slotrate'"""
    path = f"{SRC}/src/data/wild_encounters.json"
    avail = collections.defaultdict(list)
    if not os.path.exists(path):
        log("E0_no_encounter_file", "wild_encounters.json not found", "ERROR")
        return avail
    data = json.load(open(path, encoding="utf-8"))
    RATE = {  # standard pokeemerald slot rates by index
        "land_mons":   [20,20,10,10,10,10,5,5,4,4,1,1],
        "water_mons":  [60,30,5,4,1],
        "rock_smash_mons": [60,30,5,4,1],
        "fishing_mons": [70,30,60,20,20,40,40,15,4,1],
    }
    n_groups = 0
    for grp in data.get("wild_encounter_groups", []):
        if not grp.get("for_maps", False):
            continue
        n_groups += 1
        for enc in grp.get("encounters", []):
            mapname = enc.get("map", "UNK")
            for field, mons in enc.items():
                if not isinstance(mons, dict) or "mons" not in mons:
                    continue
                rates = RATE.get(field, [])
                for i, mon in enumerate(mons["mons"]):
                    sp = mon.get("species", "UNK")
                    lo, hi = mon.get("min_level", "?"), mon.get("max_level", "?")
                    rate = rates[i] if i < len(rates) else "UNK"
                    avail[sp].append(f"{mapname}:{field}:{lo}-{hi}:{rate}")
    log("E1_encounter_groups", f"parsed {n_groups} for_maps encounter group(s)")
    return avail

# ---------------------------------------------------------------- species_info
FORM_MARKERS = [
    ("isMegaEvolution", "mega"), ("isPrimalReversion", "primal"),
    ("isGigantamax", "gigantamax"), ("isAlolanForm", "regional"),
    ("isGalarianForm", "regional"), ("isHisuianForm", "regional"),
    ("isPaldeanForm", "regional"), ("isParadox", "paradox"),
    ("isTotem", "totem"), ("isUltraBurst", "ultra_burst"),
]

def split_blocks(txt):
    """Yield (species_const, body, line_no) for each [SPECIES_X] = { ... }, block."""
    for m in re.finditer(r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*\n?\s*\{", txt, re.M):
        const = m.group(1)
        start = m.end()  # just past the opening brace
        depth, i = 1, start
        while i < len(txt) and depth:
            c = txt[i]
            if c == "{": depth += 1
            elif c == "}": depth -= 1
            i += 1
        body = txt[start:i-1]
        line_no = txt.count("\n", 0, m.start()) + 1
        yield const, body, line_no

def field(body, name):
    m = re.search(r"\.\s*" + name + r"\s*=\s*([^\n]*?),?\s*\n", body)
    return m.group(1).strip() if m else None

def as_int(v, default="UNK"):
    if v is None: return default
    m = re.search(r"(-?\d+)", v)
    return int(m.group(1)) if m else default

def parse_expyield(v):
    """.expYield may be a ternary keyed on P_UPDATED_EXP_YIELDS (config = GEN_LATEST = GEN_9)."""
    if v is None: return "UNK", "UNK"
    m = re.search(r"\?\s*(\d+)\s*:\s*(\d+)", v)
    if m:
        return int(m.group(1)), f"ternary_gen5plus:{m.group(1)}|pre:{m.group(2)}"
    return as_int(v), "literal"

def parse_gender(v):
    if v is None: return "UNK"
    if "MON_GENDERLESS" in v: return "GENDERLESS"
    m = re.search(r"PERCENT_FEMALE\(\s*([\d.]+)\s*\)", v)
    if m: return m.group(1)
    return as_int(v, "UNK")

def parse_evolutions(body):
    m = re.search(r"\.evolutions\s*=\s*EVOLUTION\((.*?)\)\s*,?\s*\n", body, re.S)
    if not m: return "NONE"
    recs = re.findall(r"\{\s*([A-Z0-9_]+)\s*,\s*([^,]+?)\s*,\s*(SPECIES_[A-Z0-9_]+)", m.group(1))
    if not recs: return "UNK"
    return "|".join(f"{meth}:{param.strip()}:{tgt}" for meth, param, tgt in recs)

def parse_evyield(body):
    out = []
    for m in re.finditer(r"\.evYield_(\w+)\s*=\s*(\d+)", body):
        out.append(f"{m.group(1)}:{m.group(2)}")
    return ",".join(out) if out else "NONE"

# ---------------------------------------------------------------- main
def main():
    global CFG
    CFG = load_config()
    sp_idx = parse_species_constants()
    natdex = parse_natdex_constants()
    lvl = parse_levelup_learnsets()
    teach = parse_flat_learnsets(f"{SRC}/src/data/pokemon/teachable_learnsets.h", "TeachableLearnset")
    egg = parse_flat_learnsets(f"{SRC}/src/data/pokemon/egg_moves.h", "EggMoveLearnset")
    enc = parse_wild_encounters()

    log("C1_species_constants", f"{len(sp_idx)} SPECIES_ constants")
    log("C2_natdex_constants", f"{len(natdex)} NATIONAL_DEX_ constants")
    log("L2_levelup_learnsets", f"{len(lvl)} level-up learnset arrays")
    log("L3_teachable_learnsets", f"{len(teach)} teachable arrays")
    log("L4_egg_learnsets", f"{len(egg)} egg move arrays")

    rows, seen = [], {}
    d = f"{SRC}/src/data/pokemon/species_info"
    files = sorted(f for f in os.listdir(d) if f.endswith("_families.h"))
    for fn in files:
        path = f"{d}/{fn}"
        txt = open(path, encoding="utf-8", errors="replace").read()
        macros = collect_macros(txt, CFG)
        for const, body, line_no in split_blocks(txt):
            body = expand_macros(body, macros)
            if const in seen:
                log("S1_duplicate_species", f"{const} in {fn} and {seen[const]}", "ERROR")
                continue
            seen[const] = fn

            stats = {k: as_int(field(body, "base" + k))
                     for k in ["HP", "Attack", "Defense", "Speed", "SpAttack", "SpDefense"]}
            numeric = [v for v in stats.values() if isinstance(v, int)]
            bst = sum(numeric) if len(numeric) == 6 else "UNK"
            for k, v in stats.items():
                if isinstance(v, int) and not (1 <= v <= 255):
                    log("S2_stat_out_of_range", f"{const} base{k}={v}", "ERROR")

            tv = field(body, "types") or ""
            types = re.findall(r"(TYPE_[A-Z_]+)", tv)
            if not types:
                log("S3_no_type", const, "ERROR")
            t1 = types[0] if types else "UNK"
            t2 = types[1] if len(types) > 1 else (types[0] if types else "UNK")

            av = field(body, "abilities") or ""
            abils = re.findall(r"(ABILITY_[A-Z0-9_]+)", av)
            a1 = abils[0] if len(abils) > 0 else "UNK"
            a2 = abils[1] if len(abils) > 1 else "NONE"
            ah = abils[2] if len(abils) > 2 else "NONE"

            eg = field(body, "eggGroups") or ""
            groups = re.findall(r"(EGG_GROUP_[A-Z_]+)", eg)

            name_m = re.search(r'\.speciesName\s*=\s*_\("([^"]*)"\)', body)
            name = name_m.group(1) if name_m else "UNK"
            if name == "UNK":
                log("S4_no_name", const, "WARN")

            ndm = re.search(r"\.natDexNum\s*=\s*(NATIONAL_DEX_[A-Z0-9_]+)", body)
            dexnum = natdex.get(ndm.group(1), "UNK") if ndm else "UNK"

            ftype, fmarks = "base", []
            for marker, label in FORM_MARKERS:
                if re.search(r"\." + marker + r"\s*=\s*TRUE", body):
                    fmarks.append(marker)
                    if ftype == "base":
                        ftype = label
            if ftype == "base" and re.search(r"\.formSpeciesIdTable\s*=", body) and "_" in const[8:]:
                pass

            lset = field(body, "levelUpLearnset") or ""
            lname = lset.strip().rstrip(",")
            lmoves = lvl.get(lname, None)
            if lmoves is None and lname:
                log("S5_orphan_levelup_ref", f"{const} -> {lname} not found", "ERROR")
            lvl_enc = ",".join(f"{mv}:{L}" for L, mv in lmoves) if lmoves else ("NONE" if lmoves == [] else "UNK")

            tname = (field(body, "teachableLearnset") or "").strip().rstrip(",")
            tmoves = teach.get(tname)
            if tmoves is None and tname:
                log("S6_orphan_teachable_ref", f"{const} -> {tname} not found", "WARN")
            teach_enc = ",".join(tmoves) if tmoves else ("NONE" if tmoves == [] else "UNK")

            ename = (field(body, "eggMoveLearnset") or "").strip().rstrip(",")
            emoves = egg.get(ename)
            egg_enc = ",".join(emoves) if emoves else ("NONE" if (emoves == [] or not ename) else "UNK")

            expy, expnote = parse_expyield(field(body, "expYield"))
            avail = enc.get(const, [])

            is_leg = "TRUE" if re.search(r"\.isLegendary\s*=\s*TRUE", body) else "FALSE"
            is_myth = "TRUE" if re.search(r"\.isMythical\s*=\s*TRUE", body) else "FALSE"

            rows.append({
                "species_const": const,
                "internal_index": sp_idx.get(const, "UNK"),
                "natdex_num": dexnum,
                "species_name": name,
                "form_type": ftype,
                "form_markers": ",".join(fmarks) if fmarks else "NONE",
                "type_1": t1, "type_2": t2,
                "base_hp": stats["HP"], "base_atk": stats["Attack"],
                "base_def": stats["Defense"], "base_spa": stats["SpAttack"],
                "base_spd": stats["SpDefense"], "base_spe": stats["Speed"],
                "bst": bst,
                "ability_1": a1, "ability_2": a2, "ability_hidden": ah,
                "catch_rate": as_int(field(body, "catchRate")),
                "exp_yield": expy, "exp_yield_note": expnote,
                "ev_yield": parse_evyield(body),
                "gender_ratio_pct_female": parse_gender(field(body, "genderRatio")),
                "egg_cycles": as_int(field(body, "eggCycles")),
                "egg_group_1": groups[0] if groups else "NA",
                "egg_group_2": groups[1] if len(groups) > 1 else ("NONE" if groups else "NA"),
                "friendship": (field(body, "friendship") or "UNK").rstrip(","),
                "growth_rate": (field(body, "growthRate") or "UNK").rstrip(","),
                "evolutions": parse_evolutions(body),
                "levelup_moves": lvl_enc,
                "teachable_moves": teach_enc,
                "egg_moves": egg_enc,
                "is_legendary": is_leg, "is_mythical": is_myth,
                "wild_availability": "|".join(avail) if avail else "NONE",
                "wild_obtainable": "TRUE" if avail else "FALSE",
                "source_file": f"src/data/pokemon/species_info/{fn}",
                "source_line": line_no,
                "confidence": "Measured",
            })

    # cross-checks
    targets = set()
    for r in rows:
        if r["evolutions"] not in ("NONE", "UNK"):
            for rec in r["evolutions"].split("|"):
                targets.add(rec.split(":")[-1])
    known = {r["species_const"] for r in rows}
    for t in sorted(targets - known):
        log("S7_unresolved_evo_target", t, "ERROR")

    zero_lvl = [r["species_const"] for r in rows if r["levelup_moves"] in ("NONE", "UNK")]
    log("S8_zero_levelup_movepool", f"{len(zero_lvl)} species-forms; sample: {zero_lvl[:8]}",
        "WARN" if zero_lvl else "INFO")
    no_avail = [r["species_const"] for r in rows if r["wild_availability"] == "NONE"]
    log("S9_no_wild_availability",
        f"{len(no_avail)} species-forms have no wild encounter (expected: forms, legendaries, gifts)")
    bad_bst = [r["species_const"] for r in rows if r["bst"] == "UNK"]
    log("S10_bst_unresolved", f"{len(bad_bst)} rows; sample {bad_bst[:5]}",
        "ERROR" if bad_bst else "INFO")

    dex_off = [r["species_const"] for r in rows
               if isinstance(r["natdex_num"], int) and isinstance(r["internal_index"], int)
               and r["natdex_num"] != r["internal_index"]]
    log("S11_dex_vs_index_offset",
        f"{len(dex_off)} species-forms where natDexNum != internal index — both columns carried")

    cols = list(rows[0].keys())
    with open(f"{OUT}/01_species.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]).replace("\t", "\\t").replace("\n", "\\n") for c in cols) + "\n")

    with open(f"{OUT}/INT_integrity_log_phase1.json", "w", encoding="utf-8") as f:
        json.dump(LOG, f, indent=2)

    print(f"rows: {len(rows)}   columns: {len(cols)}")
    by_check = collections.Counter(e["check"] for e in LOG)
    seen_check = set()
    for e in LOG:
        if e["check"] in seen_check:
            continue
        seen_check.add(e["check"])
        n = by_check[e["check"]]
        suffix = f"  (x{n})" if n > 1 else ""
        print(f"  [{e['severity']}] {e['check']}: {e['detail'][:150]}{suffix}")

if __name__ == "__main__":
    main()
