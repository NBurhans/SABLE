#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 2: world, items, and interactions.

One row per acquirable thing or interaction, parsed from all placement sources:
  1. item balls   — object_events in data/maps/*/map.json, item in
                    trainer_sight_or_berry_tree_id (NOT in the script)
  2. hidden items — bg_events with type "hidden_item"
  3. mart stock   — `pokemart <Label>` in scripts.inc -> .2byte ITEM_ list
  4. script gifts — giveitem / giveitemfast in scripts.inc
  5. berry trees  — object_events using the berry tree script

Quantity is literal: a mart is unlimited supply, everything else is a finite
copy count. That distinction drives the Phase 5 scarcity gate.
"""
import json, glob, os, re, collections

SRC = "/home/claude/src_sable"
OUT = "/home/claude/out"
os.makedirs(OUT, exist_ok=True)
LOG = []
def log(check, detail, severity="INFO"):
    LOG.append({"check": check, "severity": severity, "detail": detail})

# ------------------------------------------------------------ item metadata
def parse_items():
    """name, price, pocket, hold effect per ITEM_ constant."""
    path = f"{SRC}/src/data/items.h"
    txt = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for m in re.finditer(r"^\s*\[(ITEM_[A-Z0-9_]+)\]\s*=\s*\n?\s*\{", txt, re.M):
        const = m.group(1)
        start = m.end(); depth = 1; i = start
        while i < len(txt) and depth:
            c = txt[i]
            if c == "{": depth += 1
            elif c == "}": depth -= 1
            i += 1
        body = txt[start:i-1]
        def f(n):
            mm = re.search(r"\.\s*" + n + r"\s*=\s*(.*?),?\s*\n", body)
            return mm.group(1).strip().rstrip(",") if mm else None
        nm = re.search(r'\.name\s*=\s*(?:COMPOUND_STRING|_)\("([^"]*)"\)', body)
        price = f("price")
        out[const] = {
            "item_name": nm.group(1) if nm else "UNK",
            "price": int(re.search(r"(\d+)", price).group(1)) if price and re.search(r"\d", price) else "UNK",
            "pocket": (f("pocket") or "UNK").replace("POCKET_", ""),
            "hold_effect": (f("holdEffect") or "NONE").replace("HOLD_EFFECT_", ""),
        }
    # alias defines: "#define ITEM_X_DEFEND ITEM_X_DEFENSE // Pre-Gen VI name"
    aliases = {}
    hdr = open(f"{SRC}/include/constants/items.h", encoding="utf-8", errors="replace").read()
    for a, b in re.findall(r"^\s*#define\s+(ITEM_[A-Z0-9_]+)\s+(ITEM_[A-Z0-9_]+)\s*(?://.*)?$",
                           hdr, re.M):
        aliases[a] = b
    for a, b in aliases.items():
        if a not in out and b in out:
            out[a] = out[b]
    log("W1_item_metadata", f"{len(out)} ITEM_ definitions parsed from items.h "
                            f"({len(aliases)} alias defines resolved)")
    return out

# ------------------------------------------------------------ placements
def parse_maps():
    rows = []
    ball = hidden = 0
    for f in sorted(glob.glob(f"{SRC}/data/maps/*/map.json")):
        mapname = f.split("/")[-2]
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            log("W2_map_parse_error", f"{mapname}: {e}", "ERROR"); continue
        region = d.get("region_map_section", "UNK").replace("MAPSEC_", "")
        for o in d.get("object_events", []):
            gfx = str(o.get("graphics_id", ""))
            tsid = str(o.get("trainer_sight_or_berry_tree_id", ""))
            # Key on the item field, NOT the sprite: TM/HM balls use different
            # graphics_id values, and filtering on OBJ_EVENT_GFX_ITEM_BALL silently
            # drops every TM and HM placement in the game.
            if tsid.startswith("ITEM_") and "FindItem" in str(o.get("script", "")):
                ball += 1
                rows.append(dict(entity_type="item", item_const=tsid, method="ground",
                                 map=mapname, region=region, x=o.get("x"), y=o.get("y"),
                                 flag=o.get("flag", "NONE"), quantity=1,
                                 source_file=f"data/maps/{mapname}/map.json"))
        for b in d.get("bg_events", []):
            if b.get("type") == "hidden_item" and str(b.get("item", "")).startswith("ITEM_"):
                hidden += 1
                rows.append(dict(entity_type="item", item_const=b["item"], method="hidden",
                                 map=mapname, region=region, x=b.get("x"), y=b.get("y"),
                                 flag=b.get("flag", "NONE"), quantity=1,
                                 source_file=f"data/maps/{mapname}/map.json"))
    log("W3_ground_items", f"{ball} item-ball placements across maps")
    log("W4_hidden_items", f"{hidden} hidden-item placements across maps")
    return rows

def parse_scripts():
    """Mart stock and script-granted items."""
    rows = []
    marts = gifts = 0
    files = sorted(glob.glob(f"{SRC}/data/maps/*/scripts.inc")) + \
            sorted(glob.glob(f"{SRC}/data/scripts/*.inc"))
    log("W5b_script_files", f"{len(files)} script files scanned "
                            f"(per-map plus shared data/scripts)")
    for f in files:
        mapname = f.split("/")[-2] if "/maps/" in f else "SHARED:" + os.path.basename(f)[:-4]
        txt = open(f, encoding="utf-8", errors="replace").read()

        # mart stock: pokemart <Label>  ->  Label: ... .2byte ITEM_X
        for lbl in re.findall(r"^\s*pokemart\s+(\w+)", txt, re.M):
            m = re.search(r"^" + re.escape(lbl) + r":\s*\n(.*?)(?:\n\s*\.align|\n\s*\w+:|\Z)",
                          txt, re.S | re.M)
            if not m:
                log("W5_mart_label_unresolved", f"{mapname}:{lbl}", "WARN"); continue
            items = re.findall(r"\.2byte\s+(ITEM_[A-Z0-9_]+)", m.group(1))
            if not items:
                log("W5_mart_label_unresolved", f"{mapname}:{lbl} (no .2byte entries)", "WARN")
            for it in items:
                marts += 1
                rows.append(dict(entity_type="mart_stock", item_const=it, method="purchase",
                                 map=mapname, region="UNK", x="NA", y="NA",
                                 flag="NONE", quantity="UNLIMITED",
                                 source_file=f.replace(SRC + "/", "")))

        # script-granted items
        for mm in re.finditer(r"^\s*(giveitem|giveitemfast)\s+(ITEM_[A-Z0-9_]+)(?:\s*,\s*(\w+))?",
                              txt, re.M):
            gifts += 1
            qty = mm.group(3) or 1
            try: qty = int(qty)
            except (TypeError, ValueError): qty = str(qty)
            rows.append(dict(entity_type="item", item_const=mm.group(2), method="script_gift",
                             map=mapname, region="UNK", x="NA", y="NA",
                             flag="NONE", quantity=qty,
                             source_file=f.replace(SRC + "/", "")))
    log("W6_mart_entries", f"{marts} mart stock entries")
    log("W7_script_gifts", f"{gifts} script-granted item events")
    return rows

def main():
    items = parse_items()
    rows = parse_maps() + parse_scripts()

    unknown = collections.Counter()
    for r in rows:
        meta = items.get(r["item_const"])
        if meta is None:
            unknown[r["item_const"]] += 1
            meta = {"item_name": "UNK", "price": "UNK", "pocket": "UNK", "hold_effect": "UNK"}
        r.update(meta)
        # earliest_gate needs the Phase 3 checkpoint graph; do not guess it here
        r["earliest_gate"] = "UNK"
        r["prerequisites"] = "UNK"
        r["missable"] = "UNK"
        r["confidence"] = "Measured"

    for k, v in unknown.most_common(10):
        log("W8_item_not_in_items_h", f"{k} referenced {v}x but absent from items.h", "ERROR")
    log("W8b_unknown_total", f"{len(unknown)} distinct unresolved ITEM_ constants")

    placed = {r["item_const"] for r in rows}
    log("W9_items_never_placed",
        f"{len(set(items) - placed)} of {len(items)} defined items have no placement "
        f"(expected: unobtainables, debug and event items)")

    by_type = collections.Counter(r["entity_type"] for r in rows)
    by_method = collections.Counter(r["method"] for r in rows)
    log("W10_rows_by_type", str(dict(by_type)))
    log("W10b_rows_by_method", str(dict(by_method)))
    log("W11_earliest_gate_unk",
        f"{len(rows)} rows have earliest_gate=UNK — blocked on the Phase 3 checkpoint graph")

    # TM placement is the one that gates build legality
    tms = [r for r in rows if r["item_const"].startswith(("ITEM_TM", "ITEM_HM"))]
    log("W12_tm_placements", f"{len(tms)} TM/HM placements covering "
                             f"{len({r['item_const'] for r in tms})} distinct TMs/HMs")

    cols = ["entity_type", "item_const", "item_name", "method", "map", "region", "x", "y",
            "flag", "quantity", "price", "pocket", "hold_effect", "earliest_gate",
            "prerequisites", "missable", "source_file", "confidence"]
    with open(f"{OUT}/02_world.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r.get(c, "UNK")).replace("\t", "\\t").replace("\n", "\\n")
                              for c in cols) + "\n")
    json.dump(LOG, open(f"{OUT}/INT_integrity_log_phase2.json", "w"), indent=2)

    print(f"rows: {len(rows)}  columns: {len(cols)}")
    for e in LOG:
        print(f"  [{e['severity']}] {e['check']}: {e['detail'][:150]}")

if __name__ == "__main__":
    main()
