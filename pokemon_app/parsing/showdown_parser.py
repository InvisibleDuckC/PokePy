import re
from typing import Dict, List, Optional
from ..models.pokemon import PokemonData, STAT_KEYS

# Mapas de etiquetas
_LAB = {"hp":"HP","atk":"Atk","def":"Def","spa":"SpA","spd":"SpD","spe":"Spe"}

# Regex tolerantes (ignoran espacios extra antes/después de ':')
RE_KV = {
    "ability": re.compile(r"^\s*ability\s*\:\s*(.+)\s*$", re.I),
    "item":    re.compile(r"^\s*item\s*\:\s*(.+)\s*$", re.I),
    "level":   re.compile(r"^\s*level\s*\:\s*(\d+)\s*$", re.I),
    "tera":    re.compile(r"^\s*tera[\s\-]*type\s*\:\s*(.+)\s*$", re.I),
    "evs":     re.compile(r"^\s*evs\s*\:\s*(.+)\s*$", re.I),
    "ivs":     re.compile(r"^\s*ivs\s*\:\s*(.+)\s*$", re.I),
}
RE_NATURE = re.compile(r"^\s*([A-Za-z]+)\s+Nature\s*$", re.I)

# Acepta guiones ascii y bullets comunes como inicio de movimiento
RE_MOVE = re.compile(r"^\s*[\-\–\—\•\·]\s*(.+?)\s*$")

def _parse_spread(spread_line: str, default_each: int, clamp_min: int, clamp_max: int) -> Dict[str, int]:
    """
    Soporta: '252 HP / 4 Def / 252 Spe' (espacios y mayúsculas flexibles).
    """
    out = {k: default_each for k in STAT_KEYS}
    if not spread_line:
        return out
    parts = [p.strip() for p in spread_line.split("/") if p.strip()]
    for part in parts:
        m = re.match(r"(?P<value>\d+)\s+(?P<label>HP|Atk|Def|SpA|SpD|Spe)", part, flags=re.I)
        if not m:
            continue
        val = int(m.group("value"))
        val = max(clamp_min, min(clamp_max, val))
        lab = _LAB.get(m.group("label").lower(), m.group("label"))
        out[lab] = val
    return out

def _parse_evs(line: str) -> Dict[str, int]:
    return _parse_spread(line, default_each=0, clamp_min=0, clamp_max=252)

def _parse_ivs(line: str) -> Dict[str, int]:
    return _parse_spread(line, default_each=31, clamp_min=0, clamp_max=31)

def parse_showdown_text(data_str: str) -> PokemonData:
    lines = [l.rstrip() for l in data_str.splitlines() if l.strip()]
    if not lines:
        raise ValueError("Entrada vacía.")

    # Primera línea: 'Nombre (M/F) @ Item' | 'Nombre @ Item' | 'Nombre'
    # - Soporta nombres con espacios/apóstrofes/guiones
    m1 = re.match(
        r"^(?P<name>[^@\(]+?)(?:\s*\((?P<gender>[MF])\))?(?:\s*@\s*(?P<item>.+))?$",
        lines[0]
    )
    if not m1:
        raise ValueError(f"No se pudo interpretar la primera línea: '{lines[0]}'")

    name   = m1.group("name").strip()
    gender = m1.group("gender")
    item   = (m1.group("item") or "").strip() or None

    ability: Optional[str] = None
    level: int = 50
    tera_type: Optional[str] = None
    evs = {k: 0 for k in STAT_KEYS}
    ivs = {k: 31 for k in STAT_KEYS}
    nature: Optional[str] = None
    moves: List[str] = []

    for raw in lines[1:]:
        # Campos clave:valor
        for key, rx in RE_KV.items():
            m = rx.match(raw)
            if m:
                val = m.group(1).strip()
                if key == "ability":
                    ability = val or ability
                elif key == "item":
                    item = val or item
                elif key == "level":
                    try:
                        level = int(val)
                    except ValueError:
                        pass
                elif key == "tera":
                    tera_type = val or tera_type
                elif key == "evs":
                    evs = _parse_evs(val)
                elif key == "ivs":
                    ivs = _parse_ivs(val)
                break
        else:
            # Nature
            mnat = RE_NATURE.match(raw)
            if mnat:
                nature = mnat.group(1).capitalize()
                continue

            # Movimiento
            mm = RE_MOVE.match(raw)
            if mm:
                move = mm.group(1).strip()
                if move:
                    moves.append(move)
                continue
            # otras líneas (Shiny, Happiness, etc.) se ignoran

    return PokemonData(
        name=name, gender=gender, item=item, ability=ability, level=level,
        tera_type=tera_type, evs=evs, ivs=ivs, nature=nature, moves=moves
    )
