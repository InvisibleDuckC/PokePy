import json, os, re
from typing import Dict, Optional
import requests

POKEAPI_ROOT = "https://pokeapi.co/api/v2/pokemon/"

SPECIAL_CASES = {
    ("indeedee", "F"): "indeedee-female",
    ("indeedee", "M"): "indeedee-male",
}

NAME_ONLY_CASES = {
    # Tauros Paldea (Showdown usa Tauros-Paldea-*)
    "tauros-paldea-aqua": "tauros-paldea-aqua-breed",
    "tauros-paldea-blaze": "tauros-paldea-blaze-breed",
    "tauros-paldea-combat": "tauros-paldea-combat-breed",

    # Oinkologne por género
    "oinkologne-f": "oinkologne-female",
    "oinkologne-m": "oinkologne-male",

    # Maushold familias
    "maushold-four": "maushold-family-of-four",
    "maushold-three": "maushold-family-of-three",

    # Basculin / Basculegion variantes
    "basculin-white-striped": "basculin-white-striped",
    "basculegion-f": "basculegion-female",
    "basculegion-m": "basculegion-male",

    # Otros frecuentes
    "mimikyu-busted": "mimikyu-busted",
    
    # Lycanroc sin forma explícita → usar Midday por defecto
    "lycanroc": "lycanroc-midday",
}

NAME_GENDER_CASES = {
    "basculegion": {"male": "basculegion-male", "female": "basculegion-female"},
}

def _ascii_slug(s: str) -> str:
    s = s.strip().lower()
    s = s.replace("♀", "-f").replace("♂", "-m")
    s = s.replace(".", "").replace("'", "").replace(":", "").replace(" ", "-")
    s = (s.replace("é", "e").replace("É", "e")
           .replace("á","a").replace("í","i").replace("ó","o").replace("ú","u"))
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-+", "-", s)
    return s

def showdown_to_pokeapi_slug(name: str, gender: Optional[str]) -> str:
    slug = _ascii_slug(name)
    # casos que dependen de género
    key = (slug, gender if gender in ("M", "F") else None)
    if key in SPECIAL_CASES:
        return SPECIAL_CASES[key]
    # casos solo por nombre
    if slug in NAME_ONLY_CASES:
        return NAME_ONLY_CASES[slug]
    return slug
    # NUEVO: casos por género
    if slug in NAME_GENDER_CASES:
        g = (gender or "").strip().lower()
        if g in ("f", "female", "hembra", "♀"):
            return NAME_GENDER_CASES[slug].get("female", slug)
        # por defecto, male
        return NAME_GENDER_CASES[slug].get("male", slug)

    # Casos por nombre solamente
    slug = NAME_ONLY_CASES.get(slug, slug)
    return slug

def fetch_base_stats_from_api(slug: str) -> Dict[str, int]:
    url = POKEAPI_ROOT + slug
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    stats_map = {"hp":"HP","attack":"Atk","defense":"Def","special-attack":"SpA","special-defense":"SpD","speed":"Spe"}
    out = {}
    for stat_obj in data["stats"]:
        k = stats_map[stat_obj["stat"]["name"]]
        out[k] = int(stat_obj["base_stat"])
    return out

def ensure_species_in_json(name: str, gender: Optional[str], base_stats_json_path: str) -> Dict[str, int]:
    if os.path.exists(base_stats_json_path):
        with open(base_stats_json_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
    else:
        registry = {}
    if name in registry and all(k in registry[name] for k in ("HP","Atk","Def","SpA","SpD","Spe")):
        return registry[name]
    slug = showdown_to_pokeapi_slug(name, gender)
    stats = fetch_base_stats_from_api(slug)
    registry[name] = stats
    os.makedirs(os.path.dirname(base_stats_json_path), exist_ok=True)
    with open(base_stats_json_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
    return stats

# --- NUEVO: cache de tipos ---
def ensure_types_in_json(name: str, gender: Optional[str], types_json_path: str) -> list[str]:
    """
    Devuelve ['Steel','Flying'] por ejemplo. Cachea en JSON para no golpear PokéAPI cada vez.
    """
    if os.path.exists(types_json_path):
        with open(types_json_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
    else:
        cache = {}

    if name in cache and isinstance(cache[name], list) and cache[name]:
        return cache[name]

    slug = showdown_to_pokeapi_slug(name, gender)
    url = POKEAPI_ROOT + slug
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    types = [t["type"]["name"].capitalize() for t in data.get("types", [])]  # ej ['Steel','Flying']
    cache[name] = types

    os.makedirs(os.path.dirname(types_json_path), exist_ok=True)
    with open(types_json_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    return types
