# pokemon_app/utils/species_normalize.py
from __future__ import annotations

def normalize_species_name(name: str, ability: str | None = None, gender: str | None = None) -> str:
    """
    Normaliza cuando el set no trae la forma explícita.
    - Lycanroc: por habilidad (Tough Claws → Dusk, No Guard → Midnight, otro → Midday)
    - Basculegion: por género (♀ → Female, default → Male)
    """
    if not name:
        return name
    n = name.strip()
    if n.lower() == "lycanroc":
        a = (ability or "").lower()
        if "tough claws" in a:
            return "Lycanroc-Dusk"
        if "no guard" in a:
            return "Lycanroc-Midnight"
        return "Lycanroc-Midday"
    if n.lower() == "basculegion":
        g = (gender or "").strip().lower()
        if g in ("f", "female", "hembra", "♀"):
            return "Basculegion-Female"
        return "Basculegion-Male"
    return n
