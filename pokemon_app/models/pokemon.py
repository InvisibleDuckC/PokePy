from dataclasses import dataclass, field
from typing import Dict, List, Optional

STAT_KEYS = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]

@dataclass
class PokemonData:
    name: str
    gender: Optional[str] = None
    item: Optional[str] = None
    ability: Optional[str] = None
    level: int = 50
    tera_type: Optional[str] = None
    evs: Dict[str, int] = field(default_factory=lambda: {k: 0 for k in STAT_KEYS})
    ivs: Dict[str, int] = field(default_factory=lambda: {k: 31 for k in STAT_KEYS})  # <- NUEVO
    nature: Optional[str] = None
    moves: List[str] = field(default_factory=list)
