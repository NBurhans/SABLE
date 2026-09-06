/*
 * HALYARD / target SABLE — Phase 4c: custom ability handling.
 *
 * The fork implements Radical Red's abilities, not this hack's. Its 16 custom
 * abilities exist as names in source but have no mechanical effect in the
 * calculator, so a build relying on one would silently calc as if the ability
 * did nothing. That is a wrong number wearing a Measured tag, which is worse
 * than a missing one.
 *
 * Effects are applied in two places, because they are two different kinds of
 * thing:
 *   PRE  — stat transforms, applied when the Pokemon is built (Feline Prowess
 *          doubles Sp. Atk, so it must exist before the damage formula runs).
 *   POST — damage multipliers and immunities, applied to the result.
 *
 * Abilities with no damage-formula effect are listed explicitly as NO_CALC_EFFECT
 * rather than omitted, so the coverage report can distinguish "handled" from
 * "not yet handled". Silence there would be indistinguishable from a gap.
 *
 * Effect text is transcribed from the 1.3.1 change sheet; these are Asserted,
 * not Measured, because the mechanics are not parsed from source.
 */

// stat multipliers applied at Pokemon construction
const PRE = {
  'feline prowess': {stat: 'spa', mult: 2},      // Sp. Atk Huge Power
  'sage power':     {stat: 'spa', mult: 1.5},    // Sp. Atk Gorilla Tactics (locks move)
  'bull rush':      {stat: 'atk', mult: 1.2},    // first turn only
  'quill rush':     {stat: 'atk', mult: 1.2},    // first turn only
};

// damage multipliers, evaluated against the move and the matchup
const POST = [
  {ability: 'striker', mult: 1.3,
   when: m => m.flags && m.flags.kick,
   note: 'boosts kicking moves 30%'},
  {ability: 'iron fist', mult: 1.3,
   when: m => m.flags && m.flags.punch,
   note: 'punching moves 30% (buffed from 20% in this hack)'},
  {ability: 'oraoraoraora', mult: 1.5,
   when: m => m.flags && m.flags.punch,
   note: 'punching moves hit a second time for 50%'},
  {ability: 'fatal precision', mult: 1.2,
   when: (m, eff) => eff > 1,
   note: 'super effective moves +20% and never miss'},
  {ability: "emperor's presence", mult: 1.3,
   when: m => m.type === 'Water' || m.type === 'Steel',
   note: "user's and allies' Water/Steel moves +30%"},
  {ability: 'bone zone', mult: 1.0, ignoreImmunity: true,
   when: m => /bone/i.test(m.name || ''),
   note: 'bone moves ignore resistances and immunities'},
  {ability: 'toxic boost', mult: 1.5,
   when: (m, e, atk) => m.category === 'Physical' && atk.status === 'psn',
   note: 'attack +50% while poisoned'},
  {ability: 'flare boost', mult: 1.5,
   when: (m, e, atk) => m.category === 'Special' && atk.status === 'brn',
   note: 'attack +50% while burned'},
];

// absorb-style immunities: defender takes zero from this type
const ABSORB = {
  'ice eater':   'Ice',      // Water Absorb for Ice
  'mountaineer': 'Rock',     // also blocks Stealth Rock
};

// present in the hack, no effect on a damage roll — listed so the coverage
// report separates "handled" from "unhandled"
const NO_CALC_EFFECT = {
  'parasitic waste': 'poison-inflicting moves also heal; no damage change',
  'bad company': 'prevents self stat drops and recoil; no damage change',
  'self sufficient': 'heals 1/16 per turn; no damage change',
  'blazing soul': 'priority for Fire moves at full HP; changes order, not damage',
  'the gripper': 'contact moves trap; no damage change',
};

function applyPre(spec, abilityName) {
  const a = PRE[String(abilityName || '').toLowerCase()];
  if (!a) return spec;
  const out = Object.assign({}, spec);
  out.__preNote = `${abilityName}: ${a.stat} x${a.mult}`;
  out.__statMult = {stat: a.stat, mult: a.mult};
  return out;
}

function damageMultiplier(abilityName, move, effectiveness, attacker) {
  const id = String(abilityName || '').toLowerCase();
  let mult = 1, notes = [];
  for (const rule of POST) {
    if (rule.ability !== id) continue;
    let hit = false;
    try { hit = rule.when(move, effectiveness, attacker || {}); }
    catch (e) { hit = false; }
    if (hit) { mult *= rule.mult; notes.push(rule.note); }
  }
  return {mult, notes};
}

function absorbs(abilityName, moveType) {
  return ABSORB[String(abilityName || '').toLowerCase()] === moveType;
}

const CUSTOM = new Set([
  'parasitic waste','striker','bad company','ice eater','mountaineer',
  'self sufficient',"emperor's presence",'bone zone','bull rush','quill rush',
  'blazing soul','the gripper','fatal precision','feline prowess','sage power',
  'oraoraoraora',
]);

function coverage() {
  const handled = new Set([...Object.keys(PRE), ...POST.map(r => r.ability),
                           ...Object.keys(ABSORB)]);
  const noEffect = new Set(Object.keys(NO_CALC_EFFECT));
  const out = {handled: [], no_calc_effect: [], unhandled: []};
  for (const a of CUSTOM) {
    if (handled.has(a)) out.handled.push(a);
    else if (noEffect.has(a)) out.no_calc_effect.push(a);
    else out.unhandled.push(a);
  }
  return out;
}

module.exports = {applyPre, damageMultiplier, absorbs, coverage,
                  CUSTOM, NO_CALC_EFFECT};
