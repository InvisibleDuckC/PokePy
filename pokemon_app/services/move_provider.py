import json, os, re
import requests
from typing import Optional, Dict

POKEAPI_ROOT_MOVE = "https://pokeapi.co/api/v2/move/"

# Mapeos de nombres “Showdown” → slug de PokéAPI (excepciones comunes)
MOVE_SPECIAL_CASES = {
    "high jump kick": "high-jump-kick",
    "solar beam": "solar-beam",
    "thunder punch": "thunder-punch",
    "ice punch": "ice-punch",
    "fire punch": "fire-punch",
    "volt switch": "volt-switch",
    "u-turn": "u-turn",
    "double-edge": "double-edge",
    "tera blast": "tera-blast",
    "draco meteor": "draco-meteor",
    "leaf storm": "leaf-storm",
    "ancient power": "ancient-power",
    "power-up punch": "power-up-punch",
    "x-scissor": "x-scissor",
}

def showdown_move_to_slug(name: str) -> str:
    s = (name or "").strip().lower()
    s = s.replace("’", "'")
    if s in MOVE_SPECIAL_CASES:
        return MOVE_SPECIAL_CASES[s]
    # “Hidden Power [Type]” (por ahora tratamos como hidden-power)
    if s.startswith("hidden power"):
        return "hidden-power"
    # genérico: quitar apóstrofes y puntos, espacios→guiones
    s = re.sub(r"[\'\.]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s

def ensure_move_in_json(move_name: str, cache_path: str) -> Dict:
    """
    Devuelve dict con:
      { "name": str, "type": "Fire", "power": int|None, "damage_class": "physical|special|status",
        "accuracy": int|None }
    Cachea en JSON local para no golpear PokéAPI siempre.
    """
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
    else:
        cache = {}

    key = move_name
    if key in cache and isinstance(cache[key], dict):
        return cache[key]

    slug = showdown_move_to_slug(move_name)
    url = POKEAPI_ROOT_MOVE + slug
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()

    mtype = (data["type"]["name"] or "normal").capitalize()
    dmg_class = (data["damage_class"]["name"] or "status").lower()  # "physical"/"special"/"status"
    power = data.get("power", None)  # puede ser null
    acc = data.get("accuracy", None)  # puede ser null

    info = {
        "name": move_name,
        "type": mtype,
        "power": power,
        "damage_class": dmg_class,
        "accuracy": acc,
    }
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    cache[key] = info
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    return info
