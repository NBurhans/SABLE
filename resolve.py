#!/usr/bin/env python3
"""
HALYARD / target SABLE — form-aware species name resolution.

Phase 1 stores `species_name` as the BASE name for every form: both
SPECIES_NINETALES and SPECIES_NINETALES_ALOLA carry the name "Ninetales".
Boss rosters, which come from the hzla dataset, use Showdown-style names
("Ninetales-Alola", "Charizard-Mega-X", "Urshifu-Rapid-Strike").

Joining those two on `species_name` silently resolves every regional and mega
boss Pokemon to its BASE form — wrong typing, wrong stats, wrong matrix — and
drops the hyphenated ones entirely. This module joins on the constant instead.
"""
import csv, re, collections

def _k(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())

# Showdown suffix -> the token used inside SPECIES_* constants
SUFFIX = {
    "mega": "MEGA", "megax": "MEGA_X", "megay": "MEGA_Y",
    "alola": "ALOLA", "alolan": "ALOLA", "galar": "GALAR", "galarian": "GALAR",
    "hisui": "HISUI", "hisuian": "HISUI", "paldea": "PALDEA", "paldean": "PALDEA",
    "primal": "PRIMAL", "gmax": "GIGANTAMAX", "totem": "TOTEM",
    "rapidstrike": "RAPID_STRIKE", "singlestrike": "SINGLE_STRIKE",
    "zen": "ZEN_MODE", "school": "SCHOOL", "solo": "SOLO",
    "origin": "ORIGIN", "therian": "THERIAN", "incarnate": "INCARNATE",
    "crowned": "CROWNED", "shadow": "SHADOW", "ice": "ICE", "eternamax": "ETERNAMAX",
    "wellspring": "WELLSPRING", "hearthflame": "HEARTHFLAME", "cornerstone": "CORNERSTONE",
    "bloodmoon": "BLOODMOON", "f": "F", "m": "M", "female": "F", "male": "M",
}

def build_index(species_rows):
    """Return (resolve, report). resolve(name) -> species row or None."""
    by_const = {s["species_const"]: s for s in species_rows}
    # exact constant-key index
    idx = {}
    for s in species_rows:
        const = s["species_const"]
        idx.setdefault(_k(const.replace("SPECIES_", "")), s)
    # base-name index, preferring the base form
    base = {}
    for s in species_rows:
        if s["form_type"] == "base":
            base.setdefault(_k(s["species_name"]), s)
    for s in species_rows:
        base.setdefault(_k(s["species_name"]), s)

    unresolved = collections.Counter()

    def resolve(name):
        raw = name.strip()
        k = _k(raw)
        if k in idx:
            return idx[k]
        parts = raw.split("-")
        if len(parts) > 1:
            head, tail = parts[0], parts[1:]
            # try progressively: full suffix chain, then each suffix alone
            chains = ["".join(tail)] + tail
            for ch in chains:
                tok = SUFFIX.get(_k(ch))
                if tok:
                    cand = _k(head + tok)
                    if cand in idx:
                        return idx[cand]
            # hyphenated species whose real name contains a hyphen (Chi-Yu,
            # Ho-Oh, Porygon-Z, Jangmo-o): the whole string IS the name
            if k in base:
                return base[k]
            # last resort: base form of the head, but ONLY report it, never
            # silently substitute — a mega scored as its base form is a lie
            unresolved[raw] += 1
            return None
        if k in base:
            return base[k]
        unresolved[raw] += 1
        return None

    return resolve, unresolved


if __name__ == "__main__":
    sp = list(csv.DictReader(open("/home/claude/out/01_species.tsv"), delimiter="\t"))
    tr = list(csv.DictReader(open("/home/claude/out/03_trainers.tsv"), delimiter="\t"))
    resolve, unres = build_index(sp)
    total = ok = 0
    for t in tr:
        if t["role"] == "route":
            continue
        for slot in t["roster"].split("|"):
            nm = slot.split(":")[0]
            if not nm:
                continue
            total += 1
            if resolve(nm) is not None:
                ok += 1
    print(f"boss slots {total}, resolved {ok} ({ok/total:.1%})")
    print(f"unresolved distinct {len(unres)}:")
    for n, c in unres.most_common(40):
        print("   ", n, c)
