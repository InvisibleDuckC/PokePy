import math
from datetime import datetime
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, Spinbox

from sqlalchemy.orm import Session

from ..controllers.consulta_datos_controller import ConsultarDatosController
from ..parsing.showdown_parser import parse_showdown_text
from ..services.calculations import compute_stats, DEFAULT_IV
from ..services.species_provider import ensure_species_in_json
from ..db.base import engine
from ..db.repository import init_db, save_pokemon_set, list_sets, count_sets, delete_sets, get_set, update_set
from ..db.models import Species, PokemonSet

import os

# --- Type chart (Gen9) multiplicadores ---
TYPE_CHART = {
    "Normal":    {"Rock":0.5, "Ghost":0.0, "Steel":0.5},
    "Fire":      {"Fire":0.5, "Water":0.5, "Grass":2, "Ice":2, "Bug":2, "Rock":0.5, "Dragon":0.5, "Steel":2},
    "Water":     {"Fire":2, "Water":0.5, "Grass":0.5, "Ground":2, "Rock":2, "Dragon":0.5},
    "Electric":  {"Water":2, "Electric":0.5, "Grass":0.5, "Ground":0.0, "Flying":2, "Dragon":0.5},
    "Grass":     {"Fire":0.5, "Water":2, "Grass":0.5, "Poison":0.5, "Ground":2, "Flying":0.5, "Bug":0.5, "Rock":2, "Dragon":0.5, "Steel":0.5},
    "Ice":       {"Fire":0.5, "Water":0.5, "Grass":2, "Ice":0.5, "Ground":2, "Flying":2, "Dragon":2, "Steel":0.5},
    "Fighting":  {"Normal":2, "Ice":2, "Poison":0.5, "Flying":0.5, "Psychic":0.5, "Bug":0.5, "Rock":2, "Ghost":0.0, "Dark":2, "Steel":2, "Fairy":0.5},
    "Poison":    {"Grass":2, "Poison":0.5, "Ground":0.5, "Rock":0.5, "Ghost":0.5, "Steel":0.0, "Fairy":2},
    "Ground":    {"Fire":2, "Electric":2, "Grass":0.5, "Poison":2, "Flying":0.0, "Bug":0.5, "Rock":2, "Steel":2},
    "Flying":    {"Electric":0.5, "Grass":2, "Fighting":2, "Bug":2, "Rock":0.5, "Steel":0.5},
    "Psychic":   {"Fighting":2, "Poison":2, "Psychic":0.5, "Dark":0.0, "Steel":0.5},
    "Bug":       {"Fire":0.5, "Grass":2, "Fighting":0.5, "Poison":0.5, "Flying":0.5, "Psychic":2, "Ghost":0.5, "Dark":2, "Steel":0.5, "Fairy":0.5},
    "Rock":      {"Fire":2, "Ice":2, "Fighting":0.5, "Ground":0.5, "Flying":2, "Bug":2, "Steel":0.5},
    "Ghost":     {"Normal":0.0, "Psychic":2, "Ghost":2, "Dark":0.5},
    "Dragon":    {"Dragon":2, "Steel":0.5, "Fairy":0.0},
    "Dark":      {"Fighting":0.5, "Psychic":2, "Ghost":2, "Dark":0.5, "Fairy":0.5},
    "Steel":     {"Fire":0.5, "Water":0.5, "Electric":0.5, "Ice":2, "Rock":2, "Fairy":2, "Steel":0.5},
    "Fairy":     {"Fire":0.5, "Fighting":2, "Poison":0.5, "Dragon":2, "Dark":2, "Steel":0.5},
}

ALL_TYPES = sorted(TYPE_CHART.keys())

def type_effectiveness(move_type: str, defender_types: list[str]) -> float:
    move_type = (move_type or "").capitalize()
    mult = 1.0
    for t in defender_types or []:
        t = t.capitalize()
        mult *= TYPE_CHART.get(move_type, {}).get(t, 1.0)
    return mult

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
        self.master.geometry("1200x760")
        self.pack(fill="both", expand=True)

        style = ttk.Style(self.master)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.base_stats_path = os.path.join(os.path.dirname(__file__), "..", "data", "base_stats.json")
        self.base_stats = load_base_stats(os.path.abspath(self.base_stats_path))
        self.controller = ConsultarDatosController(self.base_stats)

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


        self._build_ui()

        # estado de parseo
        self.current_parsed = None
        self.current_stats = None

    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # Tab 1: Ingresar Set
        tab_input = ttk.Frame(nb)
        nb.add(tab_input, text="Ingresar Set")

        left = ttk.Frame(tab_input)
        left.pack(side="left", fill="both", expand=True, padx=(8,4), pady=8)

        right = ttk.Frame(tab_input)
        right.pack(side="left", fill="both", expand=True, padx=(4,8), pady=8)

        ttk.Label(left, text="Pega aquí el set estilo Showdown").pack(anchor="w")
        self.txt_input = tk.Text(left, height=20, wrap="word")
        self.txt_input.pack(fill="both", expand=True)

        btns = ttk.Frame(left); btns.pack(fill="x", pady=6)
        ttk.Button(btns, text="Parsear", command=self.on_parse).pack(side="left", padx=2)
        ttk.Button(btns, text="Calcular Stats", command=self.on_calc).pack(side="left", padx=2)
        ttk.Button(btns, text="Guardar en DB", command=self.on_save).pack(side="left", padx=2)
        ttk.Button(btns, text="Limpiar", command=self.on_clear).pack(side="left", padx=2)

        grp_parsed = ttk.LabelFrame(right, text="Datos Parseados")
        grp_parsed.pack(fill="x", padx=2, pady=2)

        grid = ttk.Frame(grp_parsed); grid.pack(fill="x", padx=6, pady=6)

        # --- vars del panel "Datos Parseados" ---
        self.p_name = tk.StringVar()
        self.p_gender = tk.StringVar()
        self.p_item = tk.StringVar()
        self.p_ability = tk.StringVar()
        self.p_level = tk.StringVar(value="50")
        self.p_tera = tk.StringVar()
        self.p_nature = tk.StringVar()
        self.p_evs = tk.StringVar()
        self.p_moves = tk.StringVar()
        self.p_ivs = tk.StringVar()
        
        rows = [
            ("Name", self.p_name), ("Gender", self.p_gender), ("Item", self.p_item),
            ("Ability", self.p_ability), ("Level", self.p_level), ("Tera", self.p_tera),
            ("Nature", self.p_nature), ("EVs", self.p_evs), ("IVs", self.p_ivs),  # <- NUEVO
            ("Moves", self.p_moves),
        ]


        for i,(label, var) in enumerate(rows):
            ttk.Label(grid, text=label, width=10).grid(row=i, column=0, sticky="w", padx=2, pady=2)
            ttk.Entry(grid, textvariable=var).grid(row=i, column=1, sticky="ew", padx=2, pady=2)
        grid.columnconfigure(1, weight=1)

        grp_stats = ttk.LabelFrame(right, text="Stats Calculadas")
        grp_stats.pack(fill="both", expand=True, padx=2, pady=4)
        stats_grid = ttk.Frame(grp_stats); stats_grid.pack(fill="x", padx=6, pady=6)
        self.stat_vars = {k: tk.StringVar(value="-") for k in ["HP","Atk","Def","SpA","SpD","Spe"]}
        for i,k in enumerate(["HP","Atk","Def","SpA","SpD","Spe"]):
            ttk.Label(stats_grid, text=k, width=5).grid(row=i, column=0, sticky="w", padx=2, pady=2)
            ttk.Label(stats_grid, textvariable=self.stat_vars[k]).grid(row=i, column=1, sticky="w", padx=2, pady=2)

        # Tab 2: Sets Guardados
        tab_db = ttk.Frame(nb); nb.add(tab_db, text="Sets Guardados")

        top = ttk.Frame(tab_db); top.pack(fill="x", padx=8, pady=6)
        # Row 1
        ttk.Label(top, text="Especie:").grid(row=0, column=0, sticky='w')
        self.var_filter = tk.StringVar()
        ttk.Entry(top, textvariable=self.var_filter, width=20).grid(row=0, column=1, padx=4)
        ttk.Label(top, text="Naturaleza:").grid(row=0, column=2, sticky='w')
        self.var_nat = tk.StringVar()
        self.cmb_nat = ttk.Combobox(top, textvariable=self.var_nat, width=14, values=sorted(list({
            'Adamant','Lonely','Brave','Naughty','Impish','Bold','Relaxed','Lax','Modest','Mild','Quiet','Rash','Calm','Gentle','Sassy','Careful','Jolly','Hasty','Naive','Timid','Serious','Bashful','Docile','Hardy','Quirky'})))
        self.cmb_nat.grid(row=0, column=3, padx=4)
        ttk.Label(top, text="Tera:").grid(row=0, column=4, sticky='w')
        self.var_tera = tk.StringVar(); ttk.Entry(top, textvariable=self.var_tera, width=10).grid(row=0, column=5, padx=4)
        ttk.Label(top, text="Item:").grid(row=0, column=6, sticky='w')
        self.var_item = tk.StringVar(); ttk.Entry(top, textvariable=self.var_item, width=16).grid(row=0, column=7, padx=4)
        ttk.Button(top, text="Actualizar", command=self.refresh_sets).grid(row=0, column=8, padx=6)
        ttk.Button(top, text="Limpiar", command=self.clear_filters).grid(row=0, column=9, padx=2)
        ttk.Button(top, text="Exportar HTML", command=self.export_html).grid(row=0, column=10, padx=6)
        ttk.Button(top, text="Eliminar seleccionados", command=self.delete_selected).grid(row=0, column=11, padx=6)
        ttk.Button(top, text="Editar seleccionado", command=self.edit_selected).grid(row=0, column=12, padx=6)

        # Row 2
        ttk.Label(top, text="Ability:").grid(row=1, column=0, sticky='w', pady=(6,0))
        self.var_ability = tk.StringVar(); ttk.Entry(top, textvariable=self.var_ability, width=20).grid(row=1, column=1, padx=4, pady=(6,0))
        ttk.Label(top, text="Nivel min/max:").grid(row=1, column=2, sticky='w', pady=(6,0))
        self.var_lvl_min = tk.StringVar(); self.var_lvl_max = tk.StringVar()
        ttk.Entry(top, textvariable=self.var_lvl_min, width=6).grid(row=1, column=3, sticky='w', padx=(0,2), pady=(6,0))
        ttk.Entry(top, textvariable=self.var_lvl_max, width=6).grid(row=1, column=3, sticky='e', padx=(2,0), pady=(6,0))
        ttk.Label(top, text="Fecha desde/hasta (YYYY-MM-DD):").grid(row=1, column=4, sticky='w', pady=(6,0))
        self.var_date_from = tk.StringVar(); self.var_date_to = tk.StringVar()
        ttk.Entry(top, textvariable=self.var_date_from, width=12).grid(row=1, column=5, padx=2, pady=(6,0))
        ttk.Entry(top, textvariable=self.var_date_to, width=12).grid(row=1, column=6, padx=2, pady=(6,0))
        ttk.Label(top, text="Movimientos (coma):").grid(row=1, column=7, sticky='w', pady=(6,0))
        self.var_moves = tk.StringVar(); ttk.Entry(top, textvariable=self.var_moves, width=24).grid(row=1, column=8, padx=4, pady=(6,0))

        # Tree
        self.tree = ttk.Treeview(tab_db, columns=("id","species","level","nature","tera","item","ability","evs","moves","created"), show="headings", selectmode="extended")
        for col, w in [("id",60),("species",120),("level",60),("nature",80),("tera",80),("item",140),("ability",140),("evs",140),("moves",260),("created",140)]:
            self.tree.column(col, width=w, anchor="w")
        self.tree.heading("id", text="Id", command=lambda c="id": self.on_sort(c))
        self.tree.heading("species", text="Species", command=lambda c="species": self.on_sort(c))
        self.tree.heading("level", text="Level", command=lambda c="level": self.on_sort(c))
        self.tree.heading("nature", text="Nature", command=lambda c="nature": self.on_sort(c))
        self.tree.heading("tera", text="Tera", command=lambda c="tera": self.on_sort(c))
        self.tree.heading("item", text="Item", command=lambda c="item": self.on_sort(c))
        self.tree.heading("ability", text="Ability", command=lambda c="ability": self.on_sort(c))
        self.tree.heading("evs", text="EVs")
        self.tree.heading("moves", text="Moves")
        self.tree.heading("created", text="Created", command=lambda c="created": self.on_sort(c))
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0,0))
        self.tree.bind("<<TreeviewSelect>>", self.on_select_row)

        # Pager
        self.pager = ttk.Frame(tab_db); self.pager.pack(fill='x', padx=8, pady=6)
        ttk.Label(self.pager, text='Tamaño página:').pack(side='left')
        self.var_page_size = tk.StringVar(value=str(self.page_size))
        cmb_size = ttk.Combobox(self.pager, textvariable=self.var_page_size, width=5, values=['10','25','50','100'])
        cmb_size.pack(side='left', padx=4); cmb_size.bind('<<ComboboxSelected>>', lambda e: self.on_change_page_size())
        ttk.Button(self.pager, text='⟨ Anterior', command=self.on_prev_page).pack(side='left', padx=6)
        ttk.Button(self.pager, text='Siguiente ⟩', command=self.on_next_page).pack(side='left', padx=6)
        self.lbl_page = ttk.Label(self.pager, text='Página 1/1 (0 filas)'); self.lbl_page.pack(side='left', padx=10)

        self.detail = ttk.LabelFrame(tab_db, text="Detalle del Set Seleccionado (stats en tiempo real)")
        self.detail.pack(fill="x", padx=8, pady=6)
        self.detail_stats = {k: tk.StringVar(value="-") for k in ["HP","Atk","Def","SpA","SpD","Spe"]}
        row = ttk.Frame(self.detail); row.pack(fill="x", padx=6, pady=6)
        for k in ["HP","Atk","Def","SpA","SpD","Spe"]:
            frame = ttk.Frame(row); frame.pack(side="left", padx=6)
            ttk.Label(frame, text=k).pack(); ttk.Label(frame, textvariable=self.detail_stats[k]).pack()

        self.refresh_sets()
        
        # --- Tab 3: Velocidad ---
        tab_speed = ttk.Frame(nb)
        nb.add(tab_speed, text="Velocidad")

        # Filtros arriba
        frm_sf = ttk.Frame(tab_speed); frm_sf.pack(fill="x", padx=8, pady=6)

        ttk.Label(frm_sf, text="Especie:").grid(row=0, column=0, sticky="w")
        self.s_filter = tk.StringVar()
        ttk.Entry(frm_sf, textvariable=self.s_filter, width=20).grid(row=0, column=1, padx=4)

        ttk.Label(frm_sf, text="Naturaleza:").grid(row=0, column=2, sticky="w")
        self.s_nat = tk.StringVar()
        ttk.Combobox(
            frm_sf, textvariable=self.s_nat, width=14,
            values=sorted(list({
                'Adamant','Lonely','Brave','Naughty','Impish','Bold','Relaxed','Lax','Modest','Mild',
                'Quiet','Rash','Calm','Gentle','Sassy','Careful','Jolly','Hasty','Naive','Timid',
                'Serious','Bashful','Docile','Hardy','Quirky'
            }))
        ).grid(row=0, column=3, padx=4)

        ttk.Label(frm_sf, text="Velocidad min/max:").grid(row=0, column=4, sticky="w")
        self.s_speed_min = tk.StringVar(); self.s_speed_max = tk.StringVar()
        ttk.Entry(frm_sf, textvariable=self.s_speed_min, width=7).grid(row=0, column=5, padx=(0,2))
        ttk.Entry(frm_sf, textvariable=self.s_speed_max, width=7).grid(row=0, column=6, padx=(2,4))

        ttk.Button(frm_sf, text="Actualizar", command=self.refresh_speed_list).grid(row=0, column=7, padx=6)
        ttk.Button(frm_sf, text="Limpiar", command=self.clear_speed_filters).grid(row=0, column=8)

        # Tabla
        cols = ("species","nature","base_stat","iv","ev","calc","speed")
        self.speed_tree = ttk.Treeview(
            tab_speed, columns=cols, show="headings", selectmode="browse", height=16
        )
        self.speed_tree.pack(fill="both", expand=True, padx=8, pady=(0,8))

        # Anchos
        self.speed_tree.column("species", width=160, anchor="w")
        self.speed_tree.column("nature",  width=90,  anchor="w")
        self.speed_tree.column("base_stat", width=90, anchor="e")
        self.speed_tree.column("iv",      width=70,  anchor="center")
        self.speed_tree.column("ev",      width=70,  anchor="center")
        self.speed_tree.column("calc",      width=100, anchor="e")
        self.speed_tree.column("speed",   width=90,  anchor="e")

        # Encabezados con sort
        self.speed_tree.heading("species", text="Species", command=lambda c="species": self.on_sort_speed(c))
        self.speed_tree.heading("nature",  text="Nature",  command=lambda c="nature":  self.on_sort_speed(c))
        self.speed_tree.heading("base_stat", text="Base Stat",  command=lambda c="base_stat": self.on_sort_speed(c))
        self.speed_tree.heading("iv",      text="IV Spe",  command=lambda c="iv":      self.on_sort_speed(c))
        self.speed_tree.heading("ev",      text="EV Spe",  command=lambda c="ev":      self.on_sort_speed(c))
        self.speed_tree.heading("calc",      text="Vel (Base)", command=lambda c="calc":      self.on_sort_speed(c))
        self.speed_tree.heading("speed",     text="Vel (Final)",command=lambda c="speed":     self.on_sort_speed(c))
        
        # --- Modificadores ---
        frm_mod = ttk.LabelFrame(tab_speed, text="Modificadores")
        frm_mod.pack(fill="x", padx=8, pady=(0,8))

        ttk.Label(frm_mod, text="Etapas (+/-6):").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.s_stage = tk.StringVar(value="0")
        ttk.Combobox(frm_mod, textvariable=self.s_stage, width=5, values=[str(i) for i in range(-6, 7)]).grid(row=0, column=1, padx=4, pady=4)

        self.s_tailwind = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm_mod, text="Tailwind (x2)", variable=self.s_tailwind).grid(row=0, column=2, padx=8, pady=4)

        self.s_para = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm_mod, text="Parálisis (x0.5)", variable=self.s_para).grid(row=0, column=3, padx=8, pady=4)

        self.s_scarf = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm_mod, text="Choice Scarf (x1.5)", variable=self.s_scarf).grid(row=0, column=4, padx=8, pady=4)

        ttk.Label(frm_mod, text="Habilidad/efecto:").grid(row=0, column=5, sticky="w", padx=8, pady=4)
        self.s_ability = tk.StringVar(value="—")
        ttk.Combobox(
            frm_mod, textvariable=self.s_ability, width=16,
            values=["—","Swift Swim (Lluvia)","Chlorophyll (Sol)","Sand Rush (Tormenta Arena)","Slush Rush (Nieve)","Unburden (Objeto consumido)"]
        ).grid(row=0, column=6, padx=4, pady=4)

        ttk.Button(frm_mod, text="Recalcular", command=self.refresh_speed_list).grid(row=0, column=7, padx=8)
        
        ttk.Label(frm_mod, text="Preset:").grid(row=1, column=0, sticky="w", padx=4, pady=(0,6))
        self.s_preset = tk.StringVar(value="")
        self.cmb_preset = ttk.Combobox(frm_mod, textvariable=self.s_preset, width=24, values=[])
        self.cmb_preset.grid(row=1, column=1, columnspan=2, sticky="w", padx=4, pady=(0,6))

        ttk.Button(frm_mod, text="Guardar como…", command=self.on_save_preset).grid(row=1, column=3, padx=6, pady=(0,6))
        ttk.Button(frm_mod, text="Cargar", command=self.on_load_preset).grid(row=1, column=4, padx=6, pady=(0,6))
        ttk.Button(frm_mod, text="Eliminar", command=self.on_delete_preset).grid(row=1, column=5, padx=6, pady=(0,6))

        # Llenar lista al inicio
        self._reload_presets_into_combo()

        # Primer llenado
        self.refresh_speed_list()
        
        # --- Tab 4: Daños ---
        tab_damage = ttk.Frame(nb)
        nb.add(tab_damage, text="Daños")

        # Controles superiores
        top = ttk.LabelFrame(tab_damage, text="Atacante y Parámetros")
        top.pack(fill="x", padx=8, pady=8)

        # Atacante
        ttk.Label(top, text="Atacante:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.d_attacker = tk.StringVar()
        self.d_attacker_map = {}  # label -> set_id
        self.d_attacker_combo = ttk.Combobox(top, textvariable=self.d_attacker, width=40, values=[])
        self.d_attacker_combo.grid(row=0, column=1, columnspan=3, sticky="w", padx=4, pady=4)
        ttk.Button(top, text="Cargar atacantes", command=self._reload_attackers).grid(row=0, column=4, padx=6)

        # Parámetros de movimiento
        ttk.Label(top, text="Categoría:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.d_category = tk.StringVar(value="Physical")
        ttk.Combobox(top, textvariable=self.d_category, width=12, values=["Physical","Special"]).grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(top, text="Poder:").grid(row=1, column=2, sticky="w", padx=4, pady=4)
        self.d_power = tk.StringVar(value="80")
        ttk.Entry(top, textvariable=self.d_power, width=8).grid(row=1, column=3, sticky="w", padx=4, pady=4)

        # Modificadores
        self.d_stab = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="STAB (x1.5)", variable=self.d_stab).grid(row=2, column=0, padx=4, pady=4, sticky="w")

        self.d_crit = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Crítico (x1.5)", variable=self.d_crit).grid(row=2, column=1, padx=4, pady=4, sticky="w")

        # Tipo del movimiento
        ttk.Label(top, text="Tipo mov.:").grid(row=1, column=4, sticky="w", padx=4, pady=4)
        self.d_move_type = tk.StringVar(value="Normal")
        ttk.Combobox(top, textvariable=self.d_move_type, width=14, values=ALL_TYPES).grid(row=1, column=5, sticky="w", padx=4, pady=4)

        # STAB: automático o manual
        self.d_auto_stab = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="STAB automático", variable=self.d_auto_stab).grid(row=2, column=0, padx=4, pady=4, sticky="w")

        self.d_stab = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="STAB forzar", variable=self.d_stab).grid(row=2, column=1, padx=4, pady=4, sticky="w")  # se usa si auto_stab=False

        ttk.Label(top, text="Objeto:").grid(row=2, column=4, sticky="w", padx=4, pady=4)
        self.d_item = tk.StringVar(value="None")
        ttk.Combobox(top, textvariable=self.d_item, width=22, values=["None","Choice Band/Specs (x1.5)","Life Orb (x1.3)"]).grid(row=2, column=5, sticky="w", padx=4, pady=4)

        ttk.Button(top, text="Calcular", command=self.refresh_damage_list).grid(row=2, column=6, padx=8, pady=4)

        # Tabla de resultados
        cols = ("target","hp","def_used","xef","min","max","min_pct","max_pct","ohko")
        self.dmg_tree = ttk.Treeview(tab_damage, columns=cols, show="headings", height=18)
        self.dmg_tree.pack(fill="both", expand=True, padx=8, pady=(0,8))

        # Anchos + encabezados con sort
        cfg = [
            ("target", 200, "Target"),
            ("hp",     80,  "HP"),
            ("def_used",100,"Def usada"),
            ("xef",    70,  "xEF"),      
            ("min",    90,  "Daño min"),
            ("max",    90,  "Daño max"),
            ("min_pct",90,  "% min"),
            ("max_pct",90,  "% max"),
            ("ohko",   80,  "OHKO?")
        ]
        for key,w,txt in cfg:
            self.dmg_tree.column(key, width=w, anchor="e" if key not in ("target","def_used","ohko") else "w")
            self.dmg_tree.heading(key, text=txt, command=lambda c=key: self.on_sort_damage(c))

        # llenar atacantes de entrada
        self._reload_attackers()



    # helpers
    def _update_parsed_view(self, p):
        # Campos básicos
        self.p_name.set(p.name or "")
        self.p_gender.set(p.gender or "")
        self.p_item.set(p.item or "")
        self.p_ability.set(p.ability or "")
        self.p_level.set(str(p.level or 50))
        self.p_tera.set(p.tera_type or "")
        self.p_nature.set(p.nature or "")
        self.p_evs.set(" / ".join(f"{k}{v}" for k, v in p.evs.items() if v) or "—")
        # si quieres mostrar IVs:
        self.p_ivs.set(" / ".join(f"{k}{v}" for k, v in p.ivs.items()))
        self.p_moves.set(", ".join(p.moves) if p.moves else "—")


    def _update_stats_view(self, stats):
        for k,v in stats.items(): self.stat_vars[k].set(str(v))

    def _ensure_base_stats(self, species_name: str, gender: str | None):
        path = os.path.abspath(self.base_stats_path)
        stats = ensure_species_in_json(species_name, gender, path)
        self.base_stats = load_base_stats(path)
        return stats

    # tab 1 handlers
    def on_parse(self):
        text = self.txt_input.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Info", "Pega un set en el cuadro de texto."); return
        try:
            p = parse_showdown_text(text)
        except Exception as e:
            messagebox.showerror("Error al parsear", str(e)); return
        self.current_parsed = p; self._update_parsed_view(p); self._update_stats_view({k:"-" for k in ["HP","Atk","Def","SpA","SpD","Spe"]})

    def on_calc(self):
        if not self.current_parsed:
            self.on_parse()
            if not self.current_parsed:
                return
        p = self.current_parsed

        # Asegurar base stats (autofetch + caché)
        try:
            if p.name not in self.base_stats:
                # descarga y cachea en data/base_stats.json
                self._ensure_base_stats(p.name, p.gender)
            base = self.base_stats[p.name]
        except Exception as e:
            messagebox.showwarning(
                "Base stats faltantes",
                f"No pude obtener base stats para '{p.name}'.\n\nDetalle: {e}\n\n"
                "Si no tienes internet ahora mismo, agrega manualmente la especie a data/base_stats.json y vuelve a intentar."
            )
            return

        # Usa IVs parseados si existen; si no, 31
        ivs = getattr(p, "ivs", None)
        if not ivs:
            from ..services.calculations import DEFAULT_IV
            ivs = {k: DEFAULT_IV for k in ["HP","Atk","Def","SpA","SpD","Spe"]}

        try:
            stats = compute_stats(pokemon=p, base_stats=base, ivs=ivs)
        except Exception as e:
            # debug para saber qué pasó realmente
            import traceback
            tb = traceback.format_exc()
            messagebox.showerror("Error al calcular", f"{e}\n\n{tb}")
            return

        self.current_stats = stats
        self._update_stats_view(stats)


    def on_save(self):
        # Asegurarse de que se haya parseado un set
        if not self.current_parsed:
            messagebox.showinfo("Info", "Primero parsea un set."); return
        p = self.current_parsed
        # Asegurarse de que la especie tenga stats base
        if p.name not in self.base_stats:
            try: self._ensure_base_stats(p.name, p.gender)
            except Exception as e: messagebox.showwarning("Base stats faltantes", str(e)); return
            
        # Asegurarse de que se hayan calculado los stats    
        ivs = getattr(self.current_parsed, "ivs", None)
        if not ivs:
            from ..services.calculations import DEFAULT_IV
            ivs = {k: DEFAULT_IV for k in ["HP","Atk","Def","SpA","SpD","Spe"]}
        try:
            save_pokemon_set(name=p.name, gender=p.gender, item=p.item, ability=p.ability, level=p.level,
                             tera_type=p.tera_type, nature=p.nature, evs=p.evs, ivs=ivs, moves=p.moves,
                             base_stats_registry=self.base_stats, raw_text=self.txt_input.get("1.0","end").strip())
            messagebox.showinfo("Guardado", "Set guardado en la base de datos."); self.refresh_sets()
        except Exception as e:
            messagebox.showerror("Error al guardar", str(e))

    def on_clear(self):
        self.txt_input.delete("1.0", "end")
        self.current_parsed = None; self.current_stats = None
        for var in (self.p_name, self.p_gender, self.p_item, self.p_ability,
                self.p_level, self.p_tera, self.p_nature, self.p_evs, self.p_moves):
            var.set("")
        self._update_stats_view({k:"-" for k in ["HP","Atk","Def","SpA","SpD","Spe"]})

    # tab 2 handlers
    def clear_filters(self):
        for name in ("var_filter","var_nat","var_tera","var_item","var_ability","var_lvl_min","var_lvl_max","var_date_from","var_date_to","var_moves"):
            if hasattr(self, name):
                try: getattr(self, name).set("")
                except Exception: pass
        self.page_index = 1; self.refresh_sets()

    def on_sort(self, col: str):
        if self.sort_by == col:
            self.sort_dir = "asc" if self.sort_dir == "desc" else "desc"
        else:
            self.sort_by = col; self.sort_dir = "asc" if col in ("species","item","ability","nature","tera") else "desc"
        self.refresh_sets()

    def on_change_page_size(self):
        try: self.page_size = max(1, int(self.var_page_size.get()))
        except Exception: self.page_size = 25; self.var_page_size.set("25")
        self.page_index = 1; self.refresh_sets()

    def on_prev_page(self):
        if self.page_index > 1:
            self.page_index -= 1; self.refresh_sets()

    def on_next_page(self):
        total_pages = max(1, math.ceil(self.total_rows / self.page_size)) if self.page_size else 1
        if self.page_index < total_pages:
            self.page_index += 1; self.refresh_sets()

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Eliminar", "Selecciona una o más filas primero."); return
        ids = [int(iid) for iid in sel]
        if not messagebox.askyesno("Confirmar", f"¿Eliminar {len(ids)} set(s) seleccionados? Esta acción no se puede deshacer."):
            return
        try:
            with Session(engine) as s:
                deleted = delete_sets(s, ids)
            self.last_selected_id = None
            self.refresh_sets()
            messagebox.showinfo("Eliminar", f"Eliminados: {deleted}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def edit_selected(self):
        sel = self.tree.selection()
        if not sel or len(sel) != 1:
            messagebox.showinfo("Editar", "Selecciona exactamente un set para editar."); return
        set_id = int(sel[0]); self.open_editor(set_id)

    def open_editor(self, set_id: int):
        editor = tk.Toplevel(self.master)
        editor.title(f"Editar Set #{set_id}"); editor.transient(self.master); editor.grab_set(); editor.geometry("600x520")
        with Session(engine) as s:
            row = get_set(s, set_id)
            if not row: messagebox.showerror("Error", "No se encontró el set."); editor.destroy(); return
            pset, sp = row; evs = json.loads(pset.evs_json); moves = json.loads(pset.moves_json)
        frm = ttk.Frame(editor); frm.pack(fill="both", expand=True, padx=10, pady=10)
        ttk.Label(frm, text="Species:").grid(row=0, column=0, sticky="e", padx=4, pady=4); ttk.Label(frm, text=sp.name).grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(frm, text="Level:").grid(row=1, column=0, sticky="e", padx=4, pady=4); var_level = tk.StringVar(value=str(pset.level)); ttk.Entry(frm, textvariable=var_level, width=8).grid(row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(frm, text="Nature:").grid(row=1, column=2, sticky="e", padx=4, pady=4); var_nat = tk.StringVar(value=pset.nature or ""); 
        cmb_nat = ttk.Combobox(frm, textvariable=var_nat, width=16, values=sorted(list({'Adamant','Lonely','Brave','Naughty','Impish','Bold','Relaxed','Lax','Modest','Mild','Quiet','Rash','Calm','Gentle','Sassy','Careful','Jolly','Hasty','Naive','Timid','Serious','Bashful','Docile','Hardy','Quirky'})))
        cmb_nat.grid(row=1, column=3, sticky="w", padx=4, pady=4)
        ttk.Label(frm, text="Tera:").grid(row=2, column=0, sticky="e", padx=4, pady=4); var_tera = tk.StringVar(value=pset.tera_type or ""); ttk.Entry(frm, textvariable=var_tera, width=16).grid(row=2, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(frm, text="Item:").grid(row=2, column=2, sticky="e", padx=4, pady=4); var_item = tk.StringVar(value=pset.item or ""); ttk.Entry(frm, textvariable=var_item, width=20).grid(row=2, column=3, sticky="w", padx=4, pady=4)
        ttk.Label(frm, text="Ability:").grid(row=3, column=0, sticky="e", padx=4, pady=4); var_ability = tk.StringVar(value=pset.ability or ""); ttk.Entry(frm, textvariable=var_ability, width=20).grid(row=3, column=1, sticky="w", padx=4, pady=4)
        ev_frame = ttk.LabelFrame(frm, text="EVs"); ev_frame.grid(row=4, column=0, columnspan=4, sticky="ew", padx=4, pady=8)
        ev_vars = {k: tk.StringVar(value=str(evs.get(k,0))) for k in ["HP","Atk","Def","SpA","SpD","Spe"]}
        r=0
        for k in ["HP","Atk","Def","SpA","SpD","Spe"]:
            ttk.Label(ev_frame, text=k+":").grid(row=r//3*2, column=(r%3)*2, sticky="e", padx=4, pady=2)
            ttk.Entry(ev_frame, textvariable=ev_vars[k], width=6).grid(row=r//3*2, column=(r%3)*2+1, sticky="w", padx=4, pady=2)
            r+=1
        ivs = json.loads(pset.ivs_json)

        iv_frame = ttk.LabelFrame(frm, text="IVs")
        iv_frame.grid(row=5, column=0, columnspan=4, sticky="ew", padx=4, pady=8)
        iv_vars = {k: tk.StringVar(value=str(ivs.get(k,31))) for k in ["HP","Atk","Def","SpA","SpD","Spe"]}
        r = 0
        for k in ["HP","Atk","Def","SpA","SpD","Spe"]:
            ttk.Label(iv_frame, text=k+":").grid(row=r//3*2, column=(r%3)*2, sticky="e", padx=4, pady=2)
            ttk.Entry(iv_frame, textvariable=iv_vars[k], width=6).grid(row=r//3*2, column=(r%3)*2+1, sticky="w", padx=4, pady=2)
            r += 1

        ttk.Label(frm, text="Moves (uno por línea):").grid(row=6, column=0, sticky="ne", padx=4, pady=4)
        txt_moves = tk.Text(frm, height=6, width=40); txt_moves.grid(row=6, column=1, columnspan=3, sticky="ew", padx=4, pady=4)
        txt_moves.insert("1.0", "\n".join(moves))
        btns = ttk.Frame(frm); btns.grid(row=7, column=0, columnspan=4, sticky="e", pady=12)
        def on_save():
            # Level
            try:
                lvl = int(var_level.get().strip()); 
                if not (1 <= lvl <= 100):
                    raise ValueError("El nivel debe estar entre 1 y 100.")
            except Exception as e:
                messagebox.showerror("Validación", f"Nivel inválido: {e}")
                return
            
            # EVs
            new_evs = {}
            total = 0
            for k in ["HP","Atk","Def","SpA","SpD","Spe"]:
                try: 
                    v = int(ev_vars[k].get().strip() or "0")
                except Exception: 
                    messagebox.showerror("Validación", f"EV inválido en {k}.") 
                    return
                if v < 0 or v > 252: 
                    messagebox.showerror("Validación", f"EV de {k} debe estar entre 0 y 252.")
                    return
                new_evs[k] = v
                total += v
            if total > 508:
                messagebox.showerror("Validación", f"La suma de EVs ({total}) excede 508.")
                return
            # IVs
            new_ivs = {}
            for k in ["HP","Atk","Def","SpA","SpD","Spe"]:
                try:
                    v = int(iv_vars[k].get().strip() or "31")
                except Exception:
                    messagebox.showerror("Validación", f"IV inválido en {k}.")
                    return
                if v < 0 or v > 31:
                    messagebox.showerror("Validación", f"IV de {k} debe estar entre 0 y 31.")
                    return
                new_ivs[k] = v
                
            # Moves
            raw_moves = txt_moves.get("1.0","end").strip()
            mv = [m.strip() for m in raw_moves.replace(",", "\n").splitlines() if m.strip()]         
            
            try:
                with Session(engine) as s:
                    update_set(s, set_id, level=lvl, nature=(var_nat.get().strip() or None), tera_type=(var_tera.get().strip() or None),
                               item=(var_item.get().strip() or None), ability=(var_ability.get().strip() or None), evs=new_evs, ivs=new_ivs, moves=mv)
                editor.destroy(); self.refresh_sets()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(btns, text="Guardar cambios", command=on_save).pack(side="right", padx=6)
        ttk.Button(btns, text="Cancelar", command=editor.destroy).pack(side="right", padx=6)

    def on_select_row(self, event=None):
        sel = self.tree.selection()
        if not sel: return
        row_id = int(sel[0]); self.last_selected_id = row_id
        with Session(engine) as s:
            pset = s.get(PokemonSet, row_id); sp = s.get(Species, pset.species_id)
            evs = json.loads(pset.evs_json); ivs = json.loads(pset.ivs_json)
            base_stats = {"HP": sp.base_hp, "Atk": sp.base_atk, "Def": sp.base_def, "SpA": sp.base_spa, "SpD": sp.base_spd, "Spe": sp.base_spe}
            tmp = type("Tmp", (), {"evs": evs, "level": pset.level, "nature": pset.nature})
            stats = compute_stats(pokemon=tmp, base_stats=base_stats, ivs=ivs)
            for k,v in stats.items(): self.detail_stats[k].set(str(v))

    def export_html(self):
        path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML","*.html")], title="Guardar como")
        if not path: return
        rows = []
        with Session(engine) as s:
            for pset, sp in list_sets(s):
                evs = json.loads(pset.evs_json); ivs = json.loads(pset.ivs_json); moves = json.loads(pset.moves_json)
                base_stats = {"HP": sp.base_hp, "Atk": sp.base_atk, "Def": sp.base_def, "SpA": sp.base_spa, "SpD": sp.base_spd, "Spe": sp.base_spe}
                tmp = type("Tmp", (), {"evs": evs, "level": pset.level, "nature": pset.nature})
                stats = compute_stats(pokemon=tmp, base_stats=base_stats, ivs=ivs)
                rows.append({
                    "id": pset.id, "species": sp.name, "level": pset.level, "nature": pset.nature or "—",
                    "tera": pset.tera_type or "—", "item": pset.item or "—", "ability": pset.ability or "—",
                    "evs": " / ".join(f"{k}{v}" for k,v in evs.items() if v) or "—",
                    "moves": ", ".join(moves) if moves else "—",
                    "stats": stats, "created_at": pset.created_at.strftime("%Y-%m-%d %H:%M:%S")
                })
        html = ["<!doctype html><html><head><meta charset='utf-8'><title>Pokémon Sets</title>",
                "<style>body{font-family:Segoe UI,Roboto,Arial,sans-serif;margin:24px} table{border-collapse:collapse;width:100%} th,td{border:1px solid #ccc;padding:8px;text-align:left}</style>",
                "</head><body><h1>Pokémon Sets</h1><table><thead><tr>",
                "<th>ID</th><th>Species</th><th>Lvl</th><th>Nature</th><th>Tera</th><th>Item</th><th>Ability</th><th>EVs</th><th>Moves</th><th>Stats</th><th>Created</th>",
                "</tr></thead><tbody>"]
        for r in rows:
            stats_str = " / ".join(f"{k}:{v}" for k,v in r["stats"].items())
            html.append(f"<tr><td>{r['id']}</td><td>{r['species']}</td><td>{r['level']}</td><td>{r['nature']}</td><td>{r['tera']}</td><td>{r['item']}</td><td>{r['ability']}</td><td>{r['evs']}</td><td>{r['moves']}</td><td>{stats_str}</td><td>{r['created_at']}</td></tr>")
        html.append("</tbody></table></body></html>")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("".join(html))
            messagebox.showinfo("Exportado", f"Archivo HTML generado en:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh_sets(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        flt = self.var_filter.get().strip()
        if flt and "%" not in flt: flt = f"%{flt}%"
        nat = self.var_nat.get().strip() or None
        tera = self.var_tera.get().strip(); tera = f"%{tera}%" if tera and "%" not in tera else (tera or None)
        item = self.var_item.get().strip(); item = f"%{item}%" if item and "%" not in item else (item or None)
        ability = self.var_ability.get().strip(); ability = f"%{ability}%" if ability and "%" not in ability else (ability or None)
        lvl_min = safe_int(self.var_lvl_min.get()); lvl_max = safe_int(self.var_lvl_max.get())
        date_from = parse_date(self.var_date_from.get()); date_to = parse_date(self.var_date_to.get())
        tokens = [t.strip() for t in (self.var_moves.get().split(",") if self.var_moves.get() else []) if t.strip()]
        like_tokens = [t if "%" in t else f"%{t}%" for t in tokens]
        offset = (self.page_index - 1) * self.page_size if self.page_size else None
        with Session(engine) as s:
            self.total_rows = count_sets(s, only_species=flt or None, nature=nat, item=item, ability=ability, tera=tera,
                                         level_min=lvl_min, level_max=lvl_max, date_from=date_from, date_to=date_to,
                                         move_contains=like_tokens)
            rows = list_sets(s, only_species=flt or None, limit=self.page_size, nature=nat, item=item, ability=ability, tera=tera,
                             level_min=lvl_min, level_max=lvl_max, date_from=date_from, date_to=date_to,
                             move_contains=like_tokens, order_by=self.sort_by, order_dir=self.sort_dir, offset=offset)
            for pset, sp in rows:
                evs = json.loads(pset.evs_json); evs_str = " / ".join(f"{k}{v}" for k,v in evs.items() if v) or "—"
                moves = ", ".join(json.loads(pset.moves_json)) or "—"
                self.tree.insert("", "end", iid=str(pset.id), values=(
                    pset.id, sp.name, pset.level, pset.nature or "—", pset.tera_type or "—",
                    pset.item or "—", pset.ability or "—", evs_str, moves, pset.created_at.strftime("%Y-%m-%d %H:%M:%S")
                ))
        total_pages = max(1, math.ceil(self.total_rows / self.page_size)) if self.page_size else 1
        self.lbl_page.config(text=f"Página {self.page_index}/{total_pages} ({self.total_rows} filas)")
        last = getattr(self, "last_selected_id", None)
        if last and str(last) in self.tree.get_children():
            try: self.tree.selection_set(str(last))
            except Exception: pass
            
    def _safe_int(self, v):
        try: return int(str(v).strip())
        except Exception: return None

    def clear_speed_filters(self):
        for var in (self.s_filter, self.s_nat, self.s_speed_min, self.s_speed_max):
            var.set("")
        self.refresh_speed_list()

    def on_sort_speed(self, col: str):
        if self.speed_sort_by == col:
            self.speed_sort_dir = "asc" if self.speed_sort_dir == "desc" else "desc"
        else:
            self.speed_sort_by = col
            # por defecto velocidad desc, resto asc
            self.speed_sort_dir = "desc" if col == "speed" else "asc"
        self.refresh_speed_list()

    def refresh_speed_list(self):
        # Limpiar
        for iid in self.speed_tree.get_children():
            self.speed_tree.delete(iid)

        # Filtros básicos que sí podemos pasar a SQL
        species_like = (self.s_filter.get().strip() or "")
        if species_like and "%" not in species_like:
            species_like = f"%{species_like}%"
        nature = self.s_nat.get().strip() or None

        # Trae sets ya filtrados por especie/naturaleza (SQL), resto se filtra en Python
        from sqlalchemy.orm import Session
        from ..db.base import engine
        from ..db.repository import list_sets
        with Session(engine) as s:
            rows = list_sets(
                s,
                only_species=species_like or None,
                nature=nature,
                # no limit: esta lista suele ser pequeña; si crece, añadimos paginación aquí
            )

        # Construye filas con cálculo de Speed
        items = []
        for pset, sp in rows:
            import json
            evs = json.loads(pset.evs_json) or {}
            ivs = json.loads(pset.ivs_json) or {}
            base_stats = {
                "HP": sp.base_hp, "Atk": sp.base_atk, "Def": sp.base_def,
                "SpA": sp.base_spa, "SpD": sp.base_spd, "Spe": sp.base_spe
            }
            tmp = type("Tmp", (), {"evs": evs, "level": pset.level, "nature": pset.nature})
            try:
                from ..services.calculations import compute_stats
                base_stat_spe = int(sp.base_spe)
                stats = compute_stats(tmp, base_stats=base_stats, ivs=ivs)
                calc_spe = int(stats["Spe"])
                
                # Modificadores manuales
                stage_mult = self._stage_multiplier(self.s_stage.get())
                tailwind_mult = 2.0 if self.s_tailwind.get() else 1.0
                para_mult = 0.5 if self.s_para.get() else 1.0   # (Gen 7+)
                scarf_mult = 1.5 if self.s_scarf.get() else 1.0
                ability_mult = self._ability_speed_mult(self.s_ability.get())

                eff_speed = calc_spe * stage_mult
                eff_speed *= tailwind_mult
                eff_speed *= scarf_mult
                eff_speed *= ability_mult
                eff_speed *= para_mult

                # Truncamos al entero (como hace el juego en la mayoría de efectos)
                eff_speed = int(eff_speed)

            except Exception:
                # si algo falla, seguimos pero sin velocidad calculada
                spe = -1

            items.append({
                "species": sp.name,
                "nature": pset.nature or "—",
                "base_stat": base_stat_spe,
                "iv": int(ivs.get("Spe", 31)),
                "ev": int(evs.get("Spe", 0)),
                "calc": calc_spe,
                "speed": eff_speed, 
            })

        # Filtro por velocidad min/max (en Python)
        vmin = self._safe_int(self.s_speed_min.get())
        vmax = self._safe_int(self.s_speed_max.get())
        if vmin is not None:
            items = [r for r in items if r["speed"] >= vmin]
        if vmax is not None:
            items = [r for r in items if r["speed"] <= vmax]

        # Orden
        key = self.speed_sort_by
        reverse = (self.speed_sort_dir == "desc")
        items.sort(key=lambda r: (r[key] if r[key] is not None else -999999), reverse=reverse)

        # Insertar en la tabla
        for r in items:
            self.speed_tree.insert("", "end", values=(r["species"], r["nature"],r["base_stat"], r["iv"], r["ev"],r["calc"], r["speed"]))
            
    def _stage_multiplier(self, stage: int) -> float:
        """Multiplicador de etapas de Velocidad. -6..+6"""
        try:
            s = int(stage)
        except Exception:
            s = 0
        s = max(-6, min(6, s))
        if s >= 0:
            return (2 + s) / 2.0
        # negativo: 2 / (2 - s)  (ej: -1 -> 2/3 ≈ 0.6667)
        return 2.0 / (2 - s)

    def _ability_speed_mult(self, label: str) -> float:
        m = {
            "Swift Swim (Lluvia)": 2.0,
            "Chlorophyll (Sol)": 2.0,
            "Sand Rush (Tormenta Arena)": 2.0,
            "Slush Rush (Nieve)": 2.0,
            "Unburden (Objeto consumido)": 2.0,
        }
        return m.get(label or "—", 1.0)

    def _reload_presets_into_combo(self):
        from sqlalchemy.orm import Session
        from ..db.base import engine
        from ..db.repository import list_speed_presets
        with Session(engine) as s:
            presets = list_speed_presets(s)
        names = [p.name for p in presets]
        self.cmb_preset["values"] = names

    def on_save_preset(self):
        # pedir nombre
        import tkinter.simpledialog as sd
        name = sd.askstring("Guardar preset", "Nombre del preset:")
        if not name:
            return
        try:
            stage = int(self.s_stage.get() or "0")
        except Exception:
            stage = 0
        tailwind = bool(self.s_tailwind.get())
        para = bool(self.s_para.get())
        scarf = bool(self.s_scarf.get())
        ability_label = self.s_ability.get() or "—"

        from sqlalchemy.orm import Session
        from ..db.base import engine
        from ..db.repository import save_speed_preset
        try:
            with Session(engine) as sess:
                save_speed_preset(sess, name, stage=stage, tailwind=tailwind, para=para, scarf=scarf, ability_label=ability_label)
            self._reload_presets_into_combo()
            self.s_preset.set(name)
            messagebox.showinfo("Preset", f"Preset '{name}' guardado.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_load_preset(self):
        name = (self.s_preset.get() or "").strip()
        if not name:
            messagebox.showinfo("Preset", "Selecciona un preset de la lista.")
            return
        from sqlalchemy.orm import Session
        from ..db.base import engine
        from ..db.repository import get_speed_preset
        with Session(engine) as s:
            sp = get_speed_preset(s, name)
            if not sp:
                messagebox.showwarning("Preset", f"No existe el preset '{name}'.")
                return
            # aplicar a los controles
            self.s_stage.set(str(sp.stage))
            self.s_tailwind.set(bool(sp.tailwind))
            self.s_para.set(bool(sp.para))
            self.s_scarf.set(bool(sp.scarf))
            self.s_ability.set(sp.ability_label or "—")
        # recalcular
        self.refresh_speed_list()

    def on_delete_preset(self):
        name = (self.s_preset.get() or "").strip()
        if not name:
            messagebox.showinfo("Preset", "Selecciona un preset para eliminar.")
            return
        if not messagebox.askyesno("Eliminar preset", f"¿Eliminar '{name}'?"):
            return
        from sqlalchemy.orm import Session
        from ..db.base import engine
        from ..db.repository import delete_speed_preset
        with Session(engine) as s:
            deleted = delete_speed_preset(s, name)
        if deleted:
            messagebox.showinfo("Preset", f"Preset '{name}' eliminado.")
            self.s_preset.set("")
            self._reload_presets_into_combo()
        else:
            messagebox.showwarning("Preset", f"Preset '{name}' no encontrado.")
            
    def _safe_int(self, v):
        try: return int(str(v).strip())
        except Exception: return None

    def _dmg_modifier(self, *, stab: bool, crit: bool, eff_mult: float, item_mult: float):
        mod = 1.0
        if stab: mod *= 1.5
        if crit: mod *= 1.5
        mod *= eff_mult
        mod *= item_mult
        return mod

    def _choice_item_mult(self, item_label: str) -> float:
        if item_label == "Choice Band/Specs (x1.5)":
            return 1.5
        if item_label == "Life Orb (x1.3)":
            return 1.3
        return 1.0

    def _eff_from_label(self, lbl: str) -> float:
        mapping = {"×0": 0.0, "×0.25": 0.25, "×0.5": 0.5, "×1": 1.0, "×2": 2.0, "×4": 4.0}
        return mapping.get(lbl, 1.0)
    
    def _reload_attackers(self):
        # Rellena el combo con "id - Species (Lvl/Nature)" -> id
        from sqlalchemy.orm import Session
        from ..db.base import engine
        from ..db.repository import list_sets
        lbls = []
        self.d_attacker_map.clear()
        with Session(engine) as s:
            rows = list_sets(s, limit=None)
            for pset, sp in rows:
                label = f"{pset.id} - {sp.name} (Lv{pset.level}/{pset.nature or '—'})"
                lbls.append(label)
                self.d_attacker_map[label] = pset.id
        self.d_attacker_combo["values"] = lbls
        if lbls and not self.d_attacker.get():
            self.d_attacker.set(lbls[0])

    def on_sort_damage(self, col: str):
        if self.dmg_sort_by == col:
            self.dmg_sort_dir = "asc" if self.dmg_sort_dir == "desc" else "desc"
        else:
            self.dmg_sort_by = col
            self.dmg_sort_dir = "desc" if col in ("max","max_pct","xef") else "asc"
        self.refresh_damage_list()

    def refresh_damage_list(self):
        # limpiar tabla
        for iid in self.dmg_tree.get_children():
            self.dmg_tree.delete(iid)

        # validar atacante
        label = (self.d_attacker.get() or "").strip()
        if not label or label not in self.d_attacker_map:
            messagebox.showinfo("Daños", "Elige un atacante.")
            return
        set_id = self.d_attacker_map[label]

        # leer parámetros
        cat = (self.d_category.get() or "Physical").lower()
        power = self._safe_int(self.d_power.get()) or 0
        if power <= 0:
            messagebox.showwarning("Daños", "Poder debe ser un número mayor a 0.")
            return

        item_mult = self._choice_item_mult(self.d_item.get())
        move_type = self.d_move_type.get()

        # traer atacante y defensores
        from sqlalchemy.orm import Session
        from ..db.base import engine
        from ..db.models import PokemonSet, Species
        from ..services.calculations import compute_stats
        import json as _json
        from ..db.repository import list_sets as _list_sets

        with Session(engine) as s:
            # 1) Atacante
            attacker = s.get(PokemonSet, set_id)
            if not attacker:
                messagebox.showerror("Daños", "No se encontró el set atacante.")
                return

            att_sp = s.get(Species, attacker.species_id)  # <-- definir ANTES de usarlo

            att_evs = _json.loads(attacker.evs_json)
            att_ivs = _json.loads(attacker.ivs_json)
            att_base = {
                "HP": att_sp.base_hp, "Atk": att_sp.base_atk, "Def": att_sp.base_def,
                "SpA": att_sp.base_spa, "SpD": att_sp.base_spd, "Spe": att_sp.base_spe
            }
            A_tmp = type("Tmp", (), {"evs": att_evs, "level": attacker.level, "nature": attacker.nature})
            att_stats = compute_stats(A_tmp, base_stats=att_base, ivs=att_ivs)
            atk_stat = att_stats["Atk"] if cat == "physical" else att_stats["SpA"]

            # 2) Tipo de movimiento + STAB
            move_type = self.d_move_type.get()
            try:
                att_types = self.get_species_types(att_sp.name, attacker.gender)  # usa att_sp YA definido
            except Exception:
                att_types = []
            if bool(self.d_auto_stab.get()):
                stab = (move_type in att_types)
            else:
                stab = bool(self.d_stab.get())

            # 3) Defensores
            rows = _list_sets(s, limit=None)


            items = []
            
            # Bucle sobre defensores
            for pset, sp in rows:
                # Tipos del defensor y efectividad por type chart
                try:
                    def_types = self.get_species_types(sp.name, pset.gender)  # ej ['Steel','Flying']
                except Exception:
                    def_types = []
                eff_mult = type_effectiveness(move_type, def_types)
                xef_txt = f"×{eff_mult:g}"  # muestra “×2”, “×0.5”, etc.

                D_evs = _json.loads(pset.evs_json)
                D_ivs = _json.loads(pset.ivs_json)
                D_base = {
                    "HP": sp.base_hp, "Atk": sp.base_atk, "Def": sp.base_def,
                    "SpA": sp.base_spa, "SpD": sp.base_spd, "Spe": sp.base_spe
                }
                D_tmp = type("Tmp", (), {"evs": D_evs, "level": pset.level, "nature": pset.nature})
                d_stats = compute_stats(D_tmp, base_stats=D_base, ivs=D_ivs)
                def_stat = d_stats["Def"] if cat == "physical" else d_stats["SpD"]
                hp_stat = d_stats["HP"]

                L = attacker.level
                base_damage = (((2 * L / 5) + 2) * power * atk_stat / max(1, def_stat)) / 50 + 2

                # Objeto ya lo tienes como item_mult; crítico viene de self.d_crit
                mod = self._dmg_modifier(
                    stab=stab,
                    crit=bool(self.d_crit.get()),
                    eff_mult=eff_mult,
                    item_mult=item_mult
                )
                

                dmin = int(base_damage * 0.85 * mod)
                dmax = int(base_damage * 1.00 * mod)

                min_pct = round(dmin * 100.0 / hp_stat, 1)
                max_pct = round(dmax * 100.0 / hp_stat, 1)
                ohko = "Sí" if dmin >= hp_stat else ("Posible" if dmax >= hp_stat else "No")

                items.append({
                    "target": f"{sp.name} (Lv{pset.level}/{pset.nature or '—'})",
                    "hp": hp_stat,
                    "def_used": f"{'Def' if cat=='physical' else 'SpD'} {def_stat}",
                    "xef": xef_txt,
                    "xef_val": eff_mult,
                    "min": dmin,
                    "max": dmax,
                    "min_pct": min_pct,
                    "max_pct": max_pct,
                    "ohko": ohko,
                })
            # Fin bucle defensores


        # ordenar
        key = self.dmg_sort_by
        reverse = (self.dmg_sort_dir == "desc")
        sort_key = (lambda r: r["xef_val"]) if key == "xef" else (lambda r: (r[key] if r.get(key) is not None else -999999))
        items.sort(key=sort_key, reverse=reverse)


        # pintar
        for r in items:
            self.dmg_tree.insert("", "end", values=(r["target"], r["hp"], r["def_used"],r["xef"], r["min"], r["max"], r["min_pct"], r["max_pct"], r["ohko"]))


    # Fin refresh_damage_list


    def get_species_types(self, species_name: str, gender: str | None):
        from ..services.species_provider import ensure_types_in_json
        types_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "types_cache.json"))
        try:
            return ensure_types_in_json(species_name, gender, types_path)
        except Exception:
            # fallback: sin tipos
            return []
        
    # Fin get_species_types

    
    
# Fin de clase PokemonApp

def run():
    root = tk.Tk()
    app = PokemonApp(master=root)
    app.mainloop()
