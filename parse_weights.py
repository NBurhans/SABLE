#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 4c-i: species weights.

Feeds weightkg into the calc data layer. Without it every species defaults to
10 kg and weight-based moves (Low Kick, Grass Knot, Heat Crash, Heavy Slam)
return the same number for Gligar and Groudon.

Source stores .weight in HECTOGRAMS, so the value is divided by 10.
Verified against known values: Treecko 5.0 kg, Gligar 64.8 kg, Groudon 950.0 kg.
"""
import glob, json, os, re

SRC = "/home/claude/src_sable"
OUT = "/home/claude/out"
os.makedirs(OUT, exist_ok=True)

def main():
    weights, skipped = {}, []
    for path in sorted(glob.glob(f"{SRC}/src/data/pokemon/species_info/*_families.h")):
        txt = open(path, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*\n?\s*\{", txt, re.M):
            const = m.group(1)
            start, depth, i = m.end(), 1, m.end()
            while i < len(txt) and depth:
                if txt[i] == "{": depth += 1
                elif txt[i] == "}": depth -= 1
                i += 1
            body = txt[start:i - 1]
            wm = re.search(r"\.weight\s*=\s*(\d+)", body)
            if wm:
                weights[const] = int(wm.group(1)) / 10.0
            else:
                skipped.append(const)

    json.dump(weights, open(f"{OUT}/weights.json", "w"))
    checks = {"SPECIES_TREECKO": 5.0, "SPECIES_GLIGAR": 64.8, "SPECIES_GROUDON": 950.0}
    bad = {k: (weights.get(k), v) for k, v in checks.items() if weights.get(k) != v}
    print(f"weights parsed: {len(weights)}   no .weight field: {len(skipped)}")
    print(f"range: {min(weights.values())} - {max(weights.values())} kg")
    print("spot checks:", "PASS" if not bad else f"FAIL {bad}")
    if skipped:
        print(f"  sample without weight: {skipped[:5]}")

if __name__ == "__main__":
    main()
