#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 1b: move properties master.

Every damage number in Phase 4 rests on this table. Parsed from source only;
the EI dex JSON and the Vicfis change sheet are cross-checks, never inputs.
"""
import json, os, re, collections

SRC = "/home/claude/src_sable"
OUT = "/home/claude/out"
os.makedirs(OUT, exist_ok=True)
LOG = []
def log(check, detail, severity="INFO"):
    LOG.append({"check": check, "severity": severity, "detail": detail})

# reuse the config resolver from the species adapter
import importlib.util
spec = importlib.util.spec_from_file_location("psp", "/home/claude/parse_species.py")
psp = importlib.util.module_from_spec(spec)
spec.loader.exec_module.__self__ if False else None
try:
    spec.loader.exec_module(psp)
except SystemExit:
    pass

CFG = psp.load_config() if hasattr(psp, "load_config") else {}

# boolean flag fields worth keeping — these change damage or matchup outcomes
FLAGS = ["makesContact", "ignoresProtect", "soundMove", "ballisticMove", "punchingMove",
         "bitingMove", "slicingMove", "windMove", "powderMove", "danceMove",
         "kickingMove", "pulseMove", "healingMove", "gravityBanned", "thawsUser",
         "ignoresSubstitute", "cantUseTwice", "strikeCount", "criticalHitStage",
         "alwaysCriticalHit", "recoil", "makesContact"]

def split_blocks(txt):
    for m in re.finditer(r"^\s*\[(MOVE_[A-Z0-9_]+)\]\s*=\s*\n?\s*\{", txt, re.M):
        const = m.group(1)
        start = m.end(); depth = 1; i = start
        while i < len(txt) and depth:
            c = txt[i]
            if c == "{": depth += 1
            elif c == "}": depth -= 1
            i += 1
        yield const, txt[start:i-1], txt.count("\n", 0, m.start()) + 1

def field(body, name):
    m = re.search(r"\.\s*" + name + r"\s*=\s*(.*?),?\s*\n", body)
    return m.group(1).strip().rstrip(",") if m else None

BARE_TERNARY = re.compile(
    r"([PB]_[A-Z0-9_]+)\s*(>=|<=|==|>|<)\s*GEN_(\d)\s*\?\s*([^:?]+?)\s*:\s*([^,\n]+)")

def resolve_bare_ternary(v):
    """moves_info.h writes ternaries without parentheses:
         .pp = B_UPDATED_MOVE_DATA >= GEN_6 ? 25 : 40,
    The parenthesised resolver misses these, and a naive int-grab then returns
    the 6 from GEN_6. Resolve against the hack's own config instead."""
    def sub(m):
        lhs, op, rhs = CFG.get(m.group(1)), m.group(2), int(m.group(3))
        if lhs is None:
            log("V0_unresolved_ternary", m.group(0)[:70], "WARN")
            return m.group(4)
        keep = {">=": lhs >= rhs, "<=": lhs <= rhs, "==": lhs == rhs,
                ">": lhs > rhs, "<": lhs < rhs}[op]
        return m.group(4) if keep else m.group(5)
    return BARE_TERNARY.sub(sub, v)

def as_int(v, default="UNK"):
    if v is None: return default
    if hasattr(psp, "resolve_ternaries"):
        v = psp.resolve_ternaries(v, CFG)
    v = resolve_bare_ternary(v)
    if "GEN_" in v or "?" in v:
        log("V0b_unresolved_value", v[:70], "ERROR")
        return "UNK"
    m = re.search(r"(-?\d+)", v)
    return int(m.group(1)) if m else default

def main():
    path = f"{SRC}/src/data/moves_info.h"
    txt = open(path, encoding="utf-8", errors="replace").read()
    if hasattr(psp, "resolve_ternaries"):
        txt = psp.resolve_ternaries(txt, CFG)

    rows, seen = [], set()
    for const, body, line_no in split_blocks(txt):
        if const in seen:
            log("V1_duplicate_move", const, "ERROR"); continue
        seen.add(const)

        nm = re.search(r'\.name\s*=\s*COMPOUND_STRING\("([^"]*)"\)', body) or \
             re.search(r'\.name\s*=\s*_\("([^"]*)"\)', body)
        name = nm.group(1) if nm else "UNK"

        desc = "NONE"
        dm = re.search(r"\.description\s*=\s*COMPOUND_STRING\((.*?)\),\s*\n", body, re.S)
        if dm:
            desc = " ".join(re.findall(r'"([^"]*)"', dm.group(1))).replace("\\n", " ").strip()

        cat = (field(body, "category") or "UNK").replace("DAMAGE_CATEGORY_", "")
        typ = (field(body, "type") or "UNK")
        eff = (field(body, "effect") or "UNK")

        flags = []
        for f in dict.fromkeys(FLAGS):
            v = field(body, f)
            if v is None: continue
            if v == "TRUE": flags.append(f)
            elif re.match(r"^\d+$", v) and int(v) != 0: flags.append(f"{f}:{v}")

        rows.append({
            "move_const": const,
            "move_name": name,
            "type": typ,
            "category": cat,
            "power": as_int(field(body, "power"), 0),
            "accuracy": as_int(field(body, "accuracy"), 0),
            "pp": as_int(field(body, "pp")),
            "priority": as_int(field(body, "priority"), 0),
            "effect": eff,
            "target": (field(body, "target") or "UNK").replace("MOVE_TARGET_", ""),
            "flags": ",".join(flags) if flags else "NONE",
            "description": desc if desc else "NONE",
            "source_file": "src/data/moves_info.h",
            "source_line": line_no,
            "confidence": "Measured",
        })

    log("V2_move_count", f"{len(rows)} move entries parsed")
    dmg = [r for r in rows if r["category"] in ("PHYSICAL", "SPECIAL")]
    status = [r for r in rows if r["category"] == "STATUS"]
    log("V3_category_split", f"{len(dmg)} damaging, {len(status)} status, "
                             f"{len(rows)-len(dmg)-len(status)} other/unresolved")
    bad = [r["move_const"] for r in dmg if r["power"] in (0, "UNK")]
    log("V4_damaging_zero_power", f"{len(bad)} damaging moves with 0/UNK power "
                                  f"(expected: fixed-damage and variable-power moves); sample {bad[:6]}")
    noname = [r["move_const"] for r in rows if r["move_name"] == "UNK"]
    log("V5_unnamed", f"{len(noname)}", "WARN" if noname else "INFO")
    untyped = [r["move_const"] for r in rows if r["type"] == "UNK"]
    log("V6_untyped", f"{len(untyped)}; sample {untyped[:5]}", "ERROR" if untyped else "INFO")

    cols = list(rows[0].keys())
    with open(f"{OUT}/01b_moves.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]).replace("\t", "\\t").replace("\n", "\\n") for c in cols) + "\n")
    json.dump(LOG, open(f"{OUT}/INT_integrity_log_phase1b.json", "w"), indent=2)

    print(f"rows: {len(rows)}  columns: {len(cols)}")
    for e in LOG:
        print(f"  [{e['severity']}] {e['check']}: {e['detail'][:140]}")

if __name__ == "__main__":
    main()
