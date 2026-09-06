/*
 * HALYARD / target SABLE — Phase 4b: Generation adapter.
 *
 * @smogon/calc resolves species and moves through internal id-keyed maps
 * (SPECIES_BY_ID / MOVES_BY_ID) that are built at module load and never
 * re-read, so mutating the exported SPECIES table has no effect. The adaptable
 * entry point exists precisely for this: supply your own Generation.
 *
 * This wraps the stock gen-8 Generation and overrides species and moves from
 * data_layer.json, constructing entries from scratch for the 191 species and
 * 103 moves that do not exist in the calculator at all. Abilities, items,
 * types and natures still come from the stock tables — those are mechanics,
 * which is the only thing we take from the fork.
 */
const CALC = '/home/claude/rrcalc/calc/dist';
const {Generations} = require(`${CALC}/data/index.js`);

const toID = s => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '');

function makeGeneration(num, layer) {
  const stock = Generations.get(num);

  const spByID = {};
  for (const [name, d] of Object.entries(layer.species)) {
    const base = stock.species.get(toID(name));
    spByID[toID(name)] = {
      kind: 'Species',
      id: toID(name),
      name,
      baseStats: {
        hp: d.bs.hp, atk: d.bs.at, def: d.bs.df,
        spa: d.bs.sa, spd: d.bs.sd, spe: d.bs.sp,
      },
      types: d.types,
      weightkg: (base && base.weightkg) || d.weightkg || 10,
      abilities: d.abilities,
      nfe: d.nfe,
      // carry through anything mechanics rely on that source does not encode
      ...(base && base.otherFormes ? {otherFormes: base.otherFormes} : {}),
      ...(base && base.baseSpecies ? {baseSpecies: base.baseSpecies} : {}),
      ...(base && base.gender ? {gender: base.gender} : {}),
    };
  }

  const mvByID = {};
  for (const [name, d] of Object.entries(layer.moves)) {
    const base = stock.moves.get(toID(name));
    mvByID[toID(name)] = Object.assign({}, base || {}, {
      kind: 'Move',
      id: toID(name),
      name,
      basePower: d.bp,
      type: d.type,
      category: d.category,
      flags: Object.assign({}, (base && base.flags) || {},
        d.makesContact ? {contact: 1} : {},
        d.isPunch ? {punch: 1} : {},
        d.isBite ? {bite: 1} : {},
        d.isSlicing ? {slicing: 1} : {},
        d.isSound ? {sound: 1} : {},
        d.isBullet ? {bullet: 1} : {},
        d.isWind ? {wind: 1} : {},
        d.isKick ? {kick: 1} : {},
        d.isPowder ? {powder: 1} : {}),
      priority: d.priority || 0,
      ...(d.critRatio ? {critRatio: d.critRatio} : {}),
      ...(d.multihit ? {multihit: d.multihit} : {}),
    });
  }

  const wrap = (byID, stockCollection) => ({
    get: id => byID[id] !== undefined ? byID[id] : stockCollection.get(id),
    *[Symbol.iterator]() { for (const k in byID) yield byID[k]; },
  });

  return {
    num,
    abilities: stock.abilities,
    items: stock.items,
    types: stock.types,
    natures: stock.natures,
    species: wrap(spByID, stock.species),
    moves: wrap(mvByID, stock.moves),
    _counts: {species: Object.keys(spByID).length, moves: Object.keys(mvByID).length},
  };
}

module.exports = {makeGeneration, toID};
