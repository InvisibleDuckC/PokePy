from typing import Dict, Optional
from ..parsing.showdown_parser import parse_showdown_text
from ..models.pokemon import PokemonData
from ..services.calculations import compute_stats

class ConsultarDatosController:
    def __init__(self, base_stats_registry: Dict[str, Dict[str, int]] | None = None):
        self.base_stats_registry = base_stats_registry or {}

    def parse(self, data_str: str) -> PokemonData:
        return parse_showdown_text(data_str)

    def stats(self, pokemon: PokemonData, ivs: Optional[Dict[str, int]] = None) -> Dict[str, int]:
        base = self.base_stats_registry.get(pokemon.name)
        if not base:
            disponibles = sorted(self.base_stats_registry.keys())[:15]
            sugerencia = f"Disponibles: {', '.join(disponibles)}..." if disponibles else "(registry vacío)"
            raise KeyError(f"No hay base stats para '{pokemon.name}'. Agrega datos al registry. {sugerencia}")
        return compute_stats(pokemon, base_stats=base, ivs=ivs)

