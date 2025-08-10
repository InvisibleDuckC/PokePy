from math import floor
from typing import Dict, Optional
from ..models.pokemon import PokemonData
from ..utils.nature import nature_multipliers

DEFAULT_IV = 31

def _calc_hp(base: int, iv: int, ev: int, level: int) -> int:
    return floor(((2 * base + iv + floor(ev / 4)) * level) / 100) + level + 10

def _calc_other(base: int, iv: int, ev: int, level: int, nature_mult: float) -> int:
    return floor((floor(((2 * base + iv + floor(ev / 4)) * level) / 100) + 5) * nature_mult)

def compute_stats(
    pokemon: PokemonData,
    base_stats: Dict[str, int],
    ivs: Optional[Dict[str, int]] = None,
) -> Dict[str, int]:
    ivs = ivs or {k: DEFAULT_IV for k in ["HP","Atk","Def","SpA","SpD","Spe"]}
    mults = nature_multipliers(pokemon.nature)
    stats: Dict[str, int] = {}
    stats["HP"] = _calc_hp(base_stats["HP"], ivs["HP"], pokemon.evs.get("HP", 0), pokemon.level)
    stats["Atk"] = _calc_other(base_stats["Atk"], ivs["Atk"], pokemon.evs.get("Atk", 0), pokemon.level, mults["Atk"])
    stats["Def"] = _calc_other(base_stats["Def"], ivs["Def"], pokemon.evs.get("Def", 0), pokemon.level, mults["Def"])
    stats["SpA"] = _calc_other(base_stats["SpA"], ivs["SpA"], pokemon.evs.get("SpA", 0), pokemon.level, mults["SpA"])
    stats["SpD"] = _calc_other(base_stats["SpD"], ivs["SpD"], pokemon.evs.get("SpD", 0), pokemon.level, mults["SpD"])
    stats["Spe"] = _calc_other(base_stats["Spe"], ivs["Spe"], pokemon.evs.get("Spe", 0), pokemon.level, mults["Spe"])
    return stats
