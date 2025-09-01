import math
import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, Spinbox
from pathlib import Path
import json, re, unicodedata



from sqlalchemy.orm import Session

from pokemon_app.controllers.consulta_datos_controller import ConsultarDatosController
from pokemon_app.parsing.showdown_parser import parse_showdown_text
from pokemon_app.services.calculations import compute_stats, DEFAULT_IV
from pokemon_app.services.species_provider import ensure_species_in_json
from pokemon_app.services.types import type_effectiveness, ALL_TYPES
from pokemon_app.services import battle_calc as bc
from pokemon_app.db.base import engine
from pokemon_app.db.repository import init_db, save_pokemon_set, list_sets, count_sets, delete_sets, get_set, update_set
from pokemon_app.db.models import Species, PokemonSet
from pokemon_app.gui.ui.treeview_kit import apply_style
from pokemon_app.gui.tabs.speed_tab import SpeedTab
from pokemon_app.gui.tabs.saved_sets_tab import SavedSetsTab
from pokemon_app.gui.tabs.damage_tab import DamageTab
from pokemon_app.gui.tabs.input_tab import InputTab
from pokemon_app.gui.tabs.defense_tab import DefenseTab

from pokemon_app.utils.logging_setup import setup_logging

setup_logging()  # nivel INFO por defecto; usa log_to_file=True para archivo rotativo

# --- Loader de tipos desde JSON + fallback a DB ---
_types_cache = None

def _load_types_cache():
    """Carga y normaliza pokemon_app/data/types_cache.json. Devuelve dict[str, list[str]]."""
    import os, json
    global _types_cache
    if _types_cache is not None:
        return _types_cache

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    path = os.path.join(base_dir, "types_cache.json")
    data = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        _types_cache = {}
        return _types_cache

    # Normalización flexible:
    # A) {"Corviknight": ["Steel","Flying"], "Indeedee": ["Psychic","Normal"], ...}
    if isinstance(raw, dict) and all(
        isinstance(k, str) and isinstance(v, (list, tuple)) for k, v in raw.items()
    ):
        for name, tlist in raw.items():
            types = [str(t).strip().capitalize() for t in tlist if str(t).strip()]
            if types:
                data[name.strip()]= types

    # B) Estilo PokéAPI por especie: {"corviknight": {"types":[{"type":{"name":"steel"}},{"type":{"name":"flying"}}]}, ...}
    elif isinstance(raw, dict):
        for key, node in raw.items():
            try:
                # nombre podría estar en la clave o dentro
                name = (node.get("name") or node.get("species", {}).get("name") or key or "").strip()
                if not name:
                    continue
                # lista de tipos
                tnodes = node.get("types") or []
                types = []
                for tn in tnodes:
                    # soporta {"type":{"name":"steel"}} o {"name":"steel"} o "steel"
                    if isinstance(tn, dict):
                        if "type" in tn and isinstance(tn["type"], dict):
                            tname = tn["type"].get("name", "")
                        else:
                            tname = tn.get("name", "")
                    else:
                        tname = str(tn)
                    tname = str(tname).strip()
                    if tname:
                        types.append(tname.capitalize())
                if types:
                    data[name.capitalize()] = types
            except Exception:
                continue

    _types_cache = data
    return _types_cache


# --- Loader de tipos con BD + fallback JSON ---
def get_species_types(species_name: str, gender: str | None = None):
    """
    1) BD (type1/type2) si existen columnas.
    2) JSON cache pokemon_app/data/types_cache.json
    3) Si no está, lo TRAE de PokéAPI y lo cachea (ensure_types_in_json).
    """
    # 1) BD
    try:
        from sqlalchemy import select
        from ..db.base import engine as _eng
        from ..db.models import Species
        with Session(_eng) as s:
            sp = s.execute(select(Species).where(Species.name == species_name)).scalar_one_or_none()
            if sp:
                types = []
                t1 = getattr(sp, "type1", None)
                t2 = getattr(sp, "type2", None)
                if t1: types.append(str(t1).capitalize())
                if t2: types.append(str(t2).capitalize())
                if types:
                    return types
    except Exception:
        pass

    # 2) JSON cache (si ya existe)
    import os, json
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    cache_path = os.path.join(base_dir, "types_cache.json")
    try:
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            t = data.get(species_name) or data.get(species_name.capitalize())
            if t:
                return [str(x).capitalize() for x in t]
    except Exception:
        pass

    # 3) Ensure desde PokéAPI y guardar en cache
    try:
        from ..services.types_provider import ensure_types_in_json
        types = ensure_types_in_json(species_name, cache_path)
        if types:
            return types
    except Exception:
        # último recurso: sin tipos
        return []

    return []


services = {
    "Session": Session,
    "engine": engine,
    "list_sets": list_sets,
    "compute_stats": compute_stats,
    "type_effectiveness": type_effectiveness,
    "get_species_types": get_species_types,
    "parse_showdown_text": parse_showdown_text,
    "ensure_species_in_json": ensure_species_in_json,
    "save_pokemon_set": save_pokemon_set,
    "terrain_xmod": bc.terrain_xmod,
    "screen_multiplier": bc.screen_multiplier,
    "weather_move_multiplier": bc.weather_move_multiplier,
    "defender_stat_weather_boost": bc.defender_stat_weather_boost,
    "tera_stab_multiplier": bc.tera_stab_multiplier,
    "attacker_item_multiplier_auto": bc.attacker_item_multiplier_auto,
    "defender_item_effects_auto": bc.defender_item_effects_auto,
    "resolve_hits": bc.resolve_hits,
    "hits_weights_for_selector": bc.hits_weights_for_selector,
    "single_hit_roll_dist": bc.single_hit_roll_dist,
    "ohko_probability_from_dist": bc.ohko_probability_from_dist,
    "ko_hits_bounds": bc.ko_hits_bounds,
    "ALL_TYPES": ALL_TYPES,
}


# ruta al cache
_MOVES_PATH = Path(__file__).resolve().parents[1] / "data" / "moves_cache.json"

def _load_moves():
    try:
        with _MOVES_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

_MOVES_CACHE = _load_moves()

def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")

def _canon(s: str) -> str:
    s = _strip_accents((s or "").strip().lower())
    s = re.sub(r"[–—\-]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s

# alias ES → EN (extiéndelo según uses)
_MOVE_ALIASES = {
    _canon("A Bocajarro"): "Close Combat",
    _canon("Puño Férreo"): "Iron Fist",   # (ej. habilidad si la usaras)
    _canon("Tajo Umbrío"): "Throat Chop",
    _canon("Cascada"): "Waterfall",
    _canon("Demolición"): "Brick Break",
    _canon("Nudo Hierba"): "Grass Knot",
    # ...
}

# índice canónico del cache actual
def _build_index():
    idx = {}
    for name, meta in _MOVES_CACHE.items():
        c = _canon(name)
        idx[c] = (name, meta)
        idx[c.replace(" ", "")] = (name, meta)
    return idx

_MOVES_BY_CANON = _build_index()

def get_move_info(name: str):
    global _MOVES_CACHE, _MOVES_BY_CANON
    raw = (name or "").strip()
    if not raw:
        return None

    key = _canon(raw)
    key = _canon(_MOVE_ALIASES.get(key, raw))

    hit = _MOVES_BY_CANON.get(key) or _MOVES_BY_CANON.get(key.replace(" ", ""))
    meta = None
    if hit:
        name, meta = hit
    else:
        # fallback: intentar rellenar desde PokéAPI y recargar una vez
        try:
            from pokemon_app.services.move_provider import ensure_move_in_json
            ensure_move_in_json(raw, str(_MOVES_PATH))
            _MOVES_CACHE = _load_moves()
            _MOVES_BY_CANON = _build_index()
            hit = _MOVES_BY_CANON.get(key) or _MOVES_BY_CANON.get(key.replace(" ", ""))
            if hit:
                name, meta = hit
        except Exception:
            pass

    if not meta:
        # último intento exacto (por si el cache viene con capitalización distinta)
        meta = _MOVES_CACHE.get(raw) or _MOVES_CACHE.get(raw.title())
        if not meta:
            return None
        name = meta.get("name", raw)

    dmgc = (meta.get("damage_class") or "").lower()
    return {
        "name": name,
        "type": meta.get("type", "Normal"),
        "power": int(meta.get("power") or 0),  # ver nota de Low Kick abajo
        "category": "Physical" if dmgc.startswith("phys")
                    else ("Special" if dmgc.startswith("spec") else "Status"),
        "accuracy": meta.get("accuracy"),
    }

services["get_move_info"] = get_move_info

def load_base_stats(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def safe_int(v):
    try:
        return int(v)
    except Exception:
        return None

def parse_date(dstr):
    dstr = (dstr or '').strip()
    if not dstr:
        return None
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(dstr, fmt)
        except Exception:
            pass
    return None

class PokemonApp(ttk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master.title("Pokémon Calc - Desktop (ttk)")
        self.master.geometry("1500x850")
        self.pack(fill="both", expand=True)
        
        # Inicializa logging global
        try:
            setup_logging()
        except Exception:
            pass

        style = ttk.Style(self.master)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.base_stats_path = os.path.join(os.path.dirname(__file__), "..", "data", "base_stats.json")
        self.base_stats = load_base_stats(os.path.abspath(self.base_stats_path))
        self.controller = ConsultarDatosController(self.base_stats)

        # Exponer ruta de base_stats a servicios para uso en tabs
        try:
            services['base_stats_json_path'] = os.path.abspath(self.base_stats_path)
        except Exception:
            pass

        init_db()

        # Estado debe existir antes de construir UI
        self.page_size = 25
        self.page_index = 1
        self.total_rows = 0
        self.sort_by = "created"
        self.sort_dir = "desc"
        self.last_selected_id = None
        
        # Estado pestaña Velocidad
        self.speed_sort_by = "speed"   # 'species'|'nature'|'iv'|'ev'|'speed'
        self.speed_sort_dir = "desc"   # 'asc'|'desc'
        
        # ---- Estado pestaña Daños ----
        self.dmg_sort_by = "max_pct"   # ordenar por % máximo por defecto
        self.dmg_sort_dir = "desc"

        self.services = services

        self._build_ui()

        # estado de parseo
        self.current_parsed = None
        self.current_stats = None

    def _build_ui(self): 
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)


        # --- Tab 1: Ingresar Set ---

        def _on_new_set_saved(new_id: int | None):
            # refrescar la pestaña de Sets guardados si existe
            if hasattr(self, "saved_tab"):
                try:
                    self.saved_tab.refresh()
                    if new_id and hasattr(self.saved_tab, "select_row_by_id"):
                        self.saved_tab.select_row_by_id(new_id)
                except Exception:
                    pass

        self.input_tab = InputTab(nb, self.services, on_saved=_on_new_set_saved)
        nb.add(self.input_tab, text="Ingresar Set")

        # --- Fin Tab 1 ---
        
        # --- Tab 2: Sets Guardados ---
        
        page_saved = ttk.Frame(nb)
        nb.add(page_saved, text="Sets Guardados")
        self.saved_tab = SavedSetsTab(page_saved, self.services)
        
        # --- Fin Tab 2 ---
        
        # --- Tab 3: Velocidad ---
        
        page_speed = ttk.Frame(nb)
        nb.add(page_speed, text="Velocidad")
        self.speed_tab = SpeedTab(page_speed, self.services)
        
        # --- Fin Tab 3 ---
        
        # --- Tab 4: Daños ---
        
        page_damage = ttk.Frame(nb)
        nb.add(page_damage, text="Daños")
        self.damage_tab = DamageTab(page_damage, self.services)
        
        # Fin Tab 4: Daños ---
        
        # --- Tab 5: Defensas ---
        
        page_defense = ttk.Frame(nb)
        nb.add(page_defense, text="Defensas")
        self.defense_tab = DefenseTab(page_defense, self.services)
        
        # --- Fin Tab 5 ---

# Fin de clase PokemonApp

def run():
    root = tk.Tk()
    apply_style(root, variant="light")  # o "dark"
    app = PokemonApp(master=root)
    app.mainloop()
