# pokemon_app/services/types_provider.py
import json
import os
import re

import requests


def _normalize_slug(name: str) -> str:
    """
    Convierte nombres de especie al slug que usa PokéAPI:
    - minúsculas
    - espacios -> guiones
    - elimina acentos, apóstrofes y puntos
    - símbolos de género -> -m / -f
    - corrige algunas variantes comunes
    """
    s = name.strip()

    # género
    s = s.replace("♀", "-f").replace("♂", "-m")

    # acentos / caracteres especiales básicos
    s = (
        s.replace("é", "e")
         .replace("É", "E")
         .replace("’", "")
         .replace("'", "")
         .replace(".", "")
         .replace(":", "")
    )

    # espacios -> guiones
    s = re.sub(r"\s+", "-", s)

    # minúsculas
    s = s.lower()

    # casos comunes (añade más si lo necesitas)
    fixes = {
        "mr-mime": "mr-mime",
        "mime-jr": "mime-jr",
        "farfetchd": "farfetchd",
        "nidoran-f": "nidoran-f",
        "nidoran-m": "nidoran-m",
        "lycanroc": "lycanroc-midday",
        "basculegion": "basculegion-male",
        # ejemplos de formas regionales o especiales ya suelen ir con guiones:
        # "tauros-paldea-aqua": "tauros-paldea-aqua",
    }
    return fixes.get(s, s)


def fetch_types_from_pokeapi(species_name: str) -> list[str]:
    """
    Descarga los tipos desde PokéAPI para la forma exacta (endpoint /pokemon/<slug>).
    Devuelve p.ej. ["Steel", "Flying"].
    Lanza Exception si no se pudo obtener.
    """
    slug = _normalize_slug(species_name)
    url = f"https://pokeapi.co/api/v2/pokemon/{slug}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    types = []
    for t in data.get("types", []):
        # soporta {"type":{"name":"steel"}}
        node = t.get("type", {})
        tname = (node.get("name") or "").strip()
        if tname:
            types.append(tname.capitalize())
    if not types:
        raise RuntimeError(f"No hay 'types' en respuesta para {species_name} ({slug}).")
    return types


def ensure_types_in_json(species_name: str, json_path: str) -> list[str]:
    """
    Asegura que species_name exista en json_path con su lista de tipos.
    Si no existe, intenta descargar de PokéAPI, almacena en el JSON y devuelve los tipos.
    """
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    data = {}
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        except Exception:
            data = {}

    # ya está cacheado
    if species_name in data and isinstance(data[species_name], list) and data[species_name]:
        return [str(x).capitalize() for x in data[species_name]]

    # intenta obtener de PokéAPI
    types = fetch_types_from_pokeapi(species_name)

    # guarda
    data[species_name] = types
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return types
