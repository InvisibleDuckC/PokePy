from typing import Iterable

ALL_TYPES = [
    "Normal","Fire","Water","Electric","Grass","Ice",
    "Fighting","Poison","Ground","Flying","Psychic","Bug",
    "Rock","Ghost","Dragon","Dark","Steel","Fairy",
    # Si usas Tera Stellar, podrías añadir "Stellar"
]

# Gen 9 type chart (multiplicadores: 2, 0.5, 0)
# Formato: TYPE_CHART[atk_type][def_type] = mult
TYPE_CHART = {
    "Normal":  {"Rock":0.5,"Ghost":0.0,"Steel":0.5},
    "Fire":    {"Fire":0.5,"Water":0.5,"Grass":2.0,"Ice":2.0,"Bug":2.0,"Rock":0.5,"Dragon":0.5,"Steel":2.0},
    "Water":   {"Fire":2.0,"Water":0.5,"Grass":0.5,"Ground":2.0,"Rock":2.0,"Dragon":0.5},
    "Electric":{"Water":2.0,"Electric":0.5,"Grass":0.5,"Ground":0.0,"Flying":2.0,"Dragon":0.5},
    "Grass":   {"Fire":0.5,"Water":2.0,"Grass":0.5,"Poison":0.5,"Ground":2.0,"Flying":0.5,"Bug":0.5,"Rock":2.0,"Dragon":0.5,"Steel":0.5},
    "Ice":     {"Fire":0.5,"Water":0.5,"Ice":0.5,"Ground":2.0,"Flying":2.0,"Dragon":2.0,"Steel":0.5},
    "Fighting":{"Normal":2.0,"Ice":2.0,"Rock":2.0,"Dark":2.0,"Steel":2.0,"Poison":0.5,"Flying":0.5,"Psychic":0.5,"Bug":0.5,"Ghost":0.0,"Fairy":0.5},
    "Poison":  {"Grass":2.0,"Poison":0.5,"Ground":0.5,"Rock":0.5,"Ghost":0.5,"Steel":0.0,"Fairy":2.0},
    "Ground":  {"Fire":2.0,"Electric":2.0,"Grass":0.5,"Poison":2.0,"Flying":0.0,"Bug":0.5,"Rock":2.0,"Steel":2.0},
    "Flying":  {"Electric":0.5,"Grass":2.0,"Fighting":2.0,"Bug":2.0,"Rock":0.5,"Steel":0.5},
    "Psychic": {"Fighting":2.0,"Poison":2.0,"Psychic":0.5,"Dark":0.0,"Steel":0.5},
    "Bug":     {"Fire":0.5,"Grass":2.0,"Fighting":0.5,"Poison":0.5,"Flying":0.5,"Psychic":2.0,"Ghost":0.5,"Dark":2.0,"Steel":0.5,"Fairy":0.5},
    "Rock":    {"Fire":2.0,"Ice":2.0,"Fighting":0.5,"Ground":0.5,"Flying":2.0,"Bug":2.0,"Steel":0.5},
    "Ghost":   {"Normal":0.0,"Psychic":2.0,"Ghost":2.0,"Dark":0.5},
    "Dragon":  {"Dragon":2.0,"Steel":0.5,"Fairy":0.0},
    "Dark":    {"Fighting":0.5,"Psychic":2.0,"Ghost":2.0,"Dark":0.5,"Fairy":0.5},
    "Steel":   {"Fire":0.5,"Water":0.5,"Electric":0.5,"Ice":2.0,"Rock":2.0,"Fairy":2.0,"Steel":0.5},
    "Fairy":   {"Fire":0.5,"Fighting":2.0,"Poison":0.5,"Dragon":2.0,"Dark":2.0,"Steel":0.5},
}

def type_effectiveness(move_type: str, defender_types: Iterable[str]) -> float:
    """Devuelve el multiplicador de efectividad combinando los tipos del defensor."""
    mt = (move_type or "").capitalize()
    chart = TYPE_CHART.get(mt, {})
    mult = 1.0
    for dt in defender_types or []:
        m = chart.get((dt or "").capitalize(), 1.0)
        mult *= m
    return mult
