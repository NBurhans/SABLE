"""Unique, form-aware display key for every species row.

The prior key appended a form suffix only when form_type != 'base', but this
hack marks Deoxys-Attack, Wormadam-Sandy, Ursaluna-Bloodmoon and ~78 others as
form_type='base'. They collided onto the base name, so the data layer kept only
one of each and the matrix scored the survivors' stats under every colliding
name. Deriving the suffix from the constant instead of from form_type fixes
that, and also fixes multi-word names (SPECIES_WALKING_WAKE was becoming
'Walking Wake-Wake').
"""
import re

SPECIAL = {"SPECIES_NIDORAN_F": "Nidoran-F", "SPECIES_NIDORAN_M": "Nidoran-M"}

def species_key(r):
    const = r["species_const"]
    if const in SPECIAL:
        return SPECIAL[const]
    name = r["species_name"]
    toks = const.replace("SPECIES_", "").split("_")
    # consume however many constant tokens the display name accounts for
    base = re.sub(r"[^A-Z0-9]", "", name.upper())
    i, acc = 0, ""
    while i < len(toks) and len(acc) < len(base):
        acc += toks[i]; i += 1
    rest = toks[i:]
    if not rest:
        return name
    return name + "-" + "-".join(t[0] + t[1:].lower() for t in rest)
