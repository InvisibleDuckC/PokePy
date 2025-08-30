import os
import json as _json
import tkinter as tk
from tkinter import ttk, messagebox
from pokemon_app.utils.species_normalize import normalize_species_name
from pokemon_app.gui.ui.treeview_kit import apply_damage_tags, insert_with_zebra, set_style, apply_zebra


# Berries de resistencia por tipo
_RESIST_BERRY_BY_TYPE = {
        "Fire": "Occa Berry",
        "Water": "Passho Berry",
        "Electric": "Wacan Berry",
        "Grass": "Rindo Berry",
        "Ice": "Yache Berry",
        "Fighting": "Chople Berry",
        "Poison": "Kebia Berry",
        "Ground": "Shuca Berry",
        "Flying": "Coba Berry",
        "Psychic": "Payapa Berry",
        "Bug": "Tanga Berry",
        "Rock": "Charti Berry",
        "Ghost": "Kasib Berry",
        "Dragon": "Haban Berry",
        "Dark": "Colbur Berry",
        "Steel": "Babiri Berry",
        "Fairy": "Roseli Berry",
        "Normal": "Chilan Berry",
    }

class DamageTab:
    """
    Pestaña 'Daños' migrada a módulo propio.
    services esperados:
      - Session, engine
      - list_sets(session, ...)
      - compute_stats
      - type_effectiveness (opcional; si no, usa fallback interno simple)
      - get_species_types (opcional; si no, devuelve [])
    """
    def __init__(self, master, services: dict):
        self.master = master
        self.services = services

        # estado de orden
        self.dmg_sort_by = "max_pct"
        self.dmg_sort_dir = "desc"

        # estado de combos
        self.d_attacker = tk.StringVar()
        self.d_attacker_map = {}   # label -> set_id
        self.d_move_pick = tk.StringVar()
        self.d_move_type = tk.StringVar(value="Normal")
        self.d_category = tk.StringVar(value="Physical")
        self.d_power = tk.StringVar(value="80")
        self.d_item = tk.StringVar(value="None")
        self.d_auto_stab = tk.BooleanVar(value=True)
        self.d_stab_force = tk.BooleanVar(value=True)
        self.d_crit = tk.BooleanVar(value=False)
        self.d_burn = tk.BooleanVar(value=False)
        self.d_spread = tk.BooleanVar(value=False)
        self.d_hits = tk.StringVar(value="Auto")  # nº de golpes (Auto por defecto)

        # Tera / clima / pantallas
        self.d_tera_off_on = tk.BooleanVar(value=False)
        self.d_tera_off_type = tk.StringVar(value="Normal")
        self.d_tera_def_on = tk.BooleanVar(value=False)
        self.d_tera_def_type = tk.StringVar(value="Normal")
        self.d_weather = tk.StringVar(value="Ninguno")
        self.d_reflect = tk.BooleanVar(value=False)
        self.d_lightscreen = tk.BooleanVar(value=False)
        self.d_veil = tk.BooleanVar(value=False)
        self.d_format = tk.StringVar(value="Singles")
        
        # Terreno
        self.d_terrain = tk.StringVar(value="Ninguno")
        self.d_terrain.trace_add("write", lambda *_: self.refresh_damage_list())

        # Ítems extra
        self.d_item_extra = tk.StringVar(value="Ninguno")
        self.d_assault_vest = tk.BooleanVar(value=False)
        
        # al lado de tus otros StringVar ya existentes:
        self._last_attacker_label = None

        # cuando cambia el atacante, recuerda el último label
        self.d_attacker.trace_add("write", lambda *args: setattr(self, "_last_attacker_label", self.d_attacker.get()))

        # cuando cambia el movimiento seleccionado, actualiza sus datos (si hay algo seleccionado)
        self.d_move_pick.trace_add("write", lambda *args: (self.on_pick_move() if (self.d_move_pick.get() or "").strip() else None))

        # contadores ohko / pos / no / total
        self.d_cnt_ohko  = tk.StringVar(value="0")
        self.d_cnt_pos   = tk.StringVar(value="0")
        self.d_cnt_no    = tk.StringVar(value="0")
        self.d_cnt_total = tk.StringVar(value="0")


        # UI
        self._build_ui()

        # primera carga
        self._reload_attackers()

    # ---------- UI ----------
    def _build_ui(self):
        nb_container = self.master  # el Frame que te pasó app.py para esta página

        # === Fila superior: TOP + TERA en la misma línea ===
        top_row = ttk.Frame(nb_container)
        top_row.pack(fill="x", padx=8, pady=8)

        # LabelFrame izquierdo
        top = ttk.LabelFrame(top_row, text="Atacante y Parámetros")
        top.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # Atacante
        ttk.Label(top, text="Atacante:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.attacker_combo = ttk.Combobox(top, textvariable=self.d_attacker, width=40, state="readonly", values=[])
        self.attacker_combo.grid(row=0, column=1, columnspan=3, sticky="w", padx=4, pady=4)
        self.attacker_combo.bind("<<ComboboxSelected>>", self._on_attacker_selected)

        # Movimiento
        ttk.Label(top, text="Movimiento:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.cmb_move_pick = ttk.Combobox(top, textvariable=self.d_move_pick, width=28, values=[], state="readonly")
        self.cmb_move_pick.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        self.cmb_move_pick.bind("<<ComboboxSelected>>", lambda e: self.on_pick_move())

        # Ítem
        self.att_item_var = tk.StringVar(value="—")
        ttk.Label(top, text="Ítem (att):").grid(row=0, column=3, sticky="e", padx=4, pady=4)
        ttk.Label(top, textvariable=self.att_item_var, width=22, relief="sunken", anchor="w")\
        .grid(row=0, column=4, sticky="w", padx=4, pady=4)

        self.att_stat_var = tk.StringVar(value="—")
        ttk.Label(top, text="Stat (att):").grid(row=1, column=3, sticky="e", padx=4, pady=(0,4))
        ttk.Label(top, textvariable=self.att_stat_var, width=22, relief="sunken", anchor="w")\
        .grid(row=1, column=4, sticky="w", padx=4, pady=(0,4))

        # Parámetros
        ttk.Label(top, text="Categoría:").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Combobox(top, textvariable=self.d_category, width=12, state="readonly",
                     values=["Physical","Special"]).grid(row=2, column=1, sticky="w", padx=4, pady=4)
        self.d_category.trace_add("write", lambda *args: self._update_attacker_item_and_stat())

        ttk.Label(top, text="Poder:").grid(row=3, column=2, sticky="e", padx=4, pady=4)
        ttk.Entry(top, textvariable=self.d_power, width=8).grid(row=3, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(top, text="Tipo mov.:").grid(row=2, column=2, sticky="w", padx=4, pady=4)
        ALL_TYPES = self._all_types()
        ttk.Combobox(top, textvariable=self.d_move_type, width=14, values=ALL_TYPES, state="readonly")\
            .grid(row=2, column=3, sticky="w", padx=4, pady=4)
            
        # Precisión display
        self.lbl_accuracy_var = tk.StringVar(value="—")
        ttk.Label(top, text="Acc:").grid(row=4, column=2, sticky="e", padx=4, pady=4)
        ttk.Label(top, textvariable=self.lbl_accuracy_var, width=6).grid(row=4, column=3, sticky="w", padx=4, pady=4)

        # Golpes multiples
        ttk.Label(top, text="Golpes:").grid(row=3, column=4, sticky="sw", padx=4, pady=4)
        ttk.Combobox(
            top, textvariable=self.d_hits, width=16, state="readonly",
            values=["Auto","1","2","3","4","5","10","2-5 (prob.)","4-5 (Loaded Dice)"]
        ).grid(row=4, column=4, sticky="nw", padx=4, pady=4)

        # STAB
        ttk.Checkbutton(top, text="STAB automático", variable=self.d_auto_stab).grid(row=3, column=0, padx=4, pady=4, sticky="w")
        ttk.Checkbutton(top, text="STAB forzar", variable=self.d_stab_force).grid(row=4, column=0, padx=4, pady=4, sticky="w")

        # Crit / Burn / Spread
        ttk.Checkbutton(top, text="Crítico (x1.5)", variable=self.d_crit).grid(row=3, column=1, padx=4, pady=4, sticky="w")
        ttk.Checkbutton(top, text="Quemado (Atk x0.5)", variable=self.d_burn).grid(row=4, column=1, padx=4, pady=4, sticky="w")
        ttk.Checkbutton(top, text="Movimiento de área (Dobles x0.75)", variable=self.d_spread).grid(row=2, column=4, padx=4, pady=4, sticky="w")
        
        # Calcular daño
        ttk.Button(top, text="Calcular", command=self.refresh_damage_list).grid(row=4, column=6, padx=8, pady=4)

        # LabelFrame derecho
        tera_frame = ttk.LabelFrame(top_row, text="Tera / Campo")
        tera_frame.pack(side="left", fill="both", expand=True)
        
        # Tera
        ttk.Checkbutton(tera_frame, text="Atacante Tera ON", variable=self.d_tera_off_on).grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ttk.Label(tera_frame, text="Tera tipo (Atacante):").grid(row=0, column=1, sticky="w")
        ttk.Combobox(tera_frame, textvariable=self.d_tera_off_type, width=14,
                     values=ALL_TYPES, state="readonly").grid(row=0, column=2, padx=4)
        
        ttk.Checkbutton(tera_frame, text="Defensor Tera ON", variable=self.d_tera_def_on).grid(row=1, column=0, padx=6, pady=6, sticky="w")
        ttk.Label(tera_frame, text="Tera tipo (Defensor):").grid(row=1, column=1, sticky="w")
        ttk.Combobox(tera_frame, textvariable=self.d_tera_def_type, width=14,
                     values=ALL_TYPES, state="readonly").grid(row=1, column=2, padx=4)
        
        # Clima
        ttk.Label(tera_frame, text="Clima:").grid(row=2, column=1, sticky="w", padx=6)
        ttk.Combobox(tera_frame, textvariable=self.d_weather, width=14, state="readonly",
                     values=["Ninguno","Lluvia","Sol","Tormenta Arena","Nieve"]).grid(row=3, column=1, padx=4)
        
        # Terreno
        ttk.Label(tera_frame, text="Campo:").grid(row=2, column=2, sticky="w", padx=6)
        ttk.Combobox(
            tera_frame, textvariable=self.d_terrain, width=14, state="readonly",
            values=["Ninguno", "Eléctrico", "Hierba", "Niebla", "Psíquico"]
        ).grid(row=3, column=2, padx=4)
        
        # Pantallas
        ttk.Label(tera_frame, text="Walls:").grid(row=2, column=0, sticky="w", padx=6)
        ttk.Checkbutton(tera_frame, text="Reflect", variable=self.d_reflect).grid(row=3, column=0, padx=6, sticky="w")
        ttk.Checkbutton(tera_frame, text="Light Screen", variable=self.d_lightscreen).grid(row=4, column=0, padx=6, sticky="w")
        ttk.Checkbutton(tera_frame, text="Aurora Veil", variable=self.d_veil).grid(row=5, column=0, padx=6, sticky="w")

        ttk.Label(tera_frame, text="Formato:").grid(row=5, column=1, sticky="e")
        ttk.Combobox(tera_frame, textvariable=self.d_format, width=14, state="readonly",
                     values=["Singles","Dobles"]).grid(row=5, column=2, padx=4)


        # Tabla
        cols = ("target","hp","def_base","def_ev","def_used","def_item","xef","xmod","min","max","min_pct","max_pct","ohko")
        self.dmg_tree = ttk.Treeview(nb_container, columns=cols, show="headings", height=18)
        self.dmg_tree.pack(fill="both", expand=True, padx=8, pady=(0,8))
        apply_damage_tags(self.dmg_tree)
        set_style(self.dmg_tree)
        apply_zebra(self.dmg_tree)
        
        # Resumen de KOs
        sum_bar = ttk.LabelFrame(nb_container, text="Resumen KO")
        sum_bar.pack(fill="x", padx=8, pady=(0,8))

        def _mk(label_txt, var):
            frm = ttk.Frame(sum_bar); frm.pack(side="left", padx=10)
            ttk.Label(frm, text=label_txt).pack(side="left")
            ttk.Label(frm, textvariable=var, width=4, relief="sunken", anchor="e").pack(side="left")

        _mk("OHKO:",  self.d_cnt_ohko)
        _mk("Posible:", self.d_cnt_pos)
        _mk("No:",    self.d_cnt_no)
        _mk("Total:", self.d_cnt_total)

        cfg = [
            ("target", 200, "Target"),
            ("hp",     70,  "HP"),
            ("def_base", 80, "Def Base"),
            ("def_ev",   70, "EV Def"),
            ("def_used",90, "Def usada"),
            ("def_item", 130, "Item (Def)"),
            ("xef",    60,  "xEF"),
            ("xmod",   70,  "xMOD"),     # NUEVA
            ("min",    90,  "Daño min"),
            ("max",    90,  "Daño max"),
            ("min_pct",90,  "% min"),
            ("max_pct",90,  "% max"),
            ("ohko",   80,  "OHKO?"),
        ]
        for key,w,txt in cfg:
            self.dmg_tree.column(key, width=w, anchor="e" if key not in ("target","def_used","ohko") else "w")
            self.dmg_tree.heading(key, text=txt, command=lambda c=key: self.on_sort_damage(c))

        # --- Loader (oculto por defecto) ---
        self.loader_frame = ttk.Frame(nb_container)
        self.loader_bar = ttk.Progressbar(self.loader_frame, mode="indeterminate", length=220)
        self.loader_bar.pack(side="left", padx=(0,8))
        self.loader_label = ttk.Label(self.loader_frame, text="Calculando...")
        self.loader_label.pack(side="left")
        # No lo mostramos aún: queda oculto con pack_forget()
        self.loader_frame.pack_forget()

        # cargar automáticamente al mostrar/focalizar la pestaña
        try:
            self.master.bind("<FocusIn>", lambda e: self._ensure_default_loaded())
        except Exception:
            pass

        # disparo inicial tras construir la UI
        self.master.after(0, self._ensure_default_loaded)
        
        # --- recargar atacantes cuando se muestre esta pestaña ---
        try:
            nb = self.master.nametowidget(self.master.winfo_parent())  # Notebook contenedor
            nb.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed, add="+")
        except Exception:
            pass




    # ---------- datos auxiliares ----------
    def _all_types(self):
        # intenta cargar desde services.types
        try:
            from ...services.types import ALL_TYPES
            return list(ALL_TYPES)
        except Exception:
            return ["Normal","Fire","Water","Electric","Grass","Ice","Fighting","Poison","Ground","Flying",
                    "Psychic","Bug","Rock","Ghost","Dragon","Dark","Steel","Fairy"]

    def _type_eff(self, move_type: str, def_types: list[str]) -> float:
        # Usa servicio si está disponible
        fn = self.services.get("type_effectiveness")
        if callable(fn):
            return fn(move_type, def_types)
        # Fallback trivial (todo neutro)
        return 1.0

    def _get_species_types(self, species_name: str, gender: str | None) -> list[str]:
        fn = self.services.get("get_species_types")
        if callable(fn):
            try:
                return fn(species_name, gender)
            except Exception:
                return []
        return []

    # ---------- cargar atacantes / movimientos ----------
    def _reload_attackers(self):
        self.d_attacker_map.clear()
        labels = []
        Session = self.services["Session"]; engine = self.services["engine"]; list_sets = self.services["list_sets"]
        with Session(engine) as s:
            rows = list_sets(s, limit=None)
        for pset, sp in rows:
            label = f"{sp.name} (Lv{pset.level}/{pset.nature or '—'}) #{pset.id}"
            self.d_attacker_map[label] = pset.id
            labels.append(label)
        self.attacker_combo["values"] = labels
        if labels:
            self.d_attacker.set(labels[0])
            self._reload_moves_for_selected_attacker()
        else:
            self.d_attacker.set("")
            self.cmb_move_pick["values"] = []
            self.d_move_pick.set("")

    def _reload_moves_for_selected_attacker(self):
        label = (self.d_attacker.get() or "").strip()
        if not label or label not in self.d_attacker_map:
            self.cmb_move_pick["values"] = []
            self.d_move_pick.set("")
            return
        set_id = self.d_attacker_map[label]
        Session = self.services["Session"]; engine = self.services["engine"]
        with Session(engine) as s:
            from ...db.models import PokemonSet
            pset = s.get(PokemonSet, set_id)
        try:
            mv = _json.loads(pset.moves_json) or []
        except Exception:
            mv = []
        self.cmb_move_pick["values"] = mv
        self.d_move_pick.set(mv[0] if mv else "")
        
        if (self.d_move_pick.get() or "").strip():
            self.on_pick_move()

    # ---------- PokéAPI (caché local) ----------
    def on_pick_move(self):
        move = (self.d_move_pick.get() or "").strip()
        if not move:
            if hasattr(self, "lbl_accuracy_var"):
                self.lbl_accuracy_var.set("—")
            messagebox.showinfo("Movimientos", "Selecciona un movimiento del listado.")
            return

        cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__),"..", "..", "data"))
        os.makedirs(cache_dir, exist_ok=True)
        move_cache = os.path.join(cache_dir, "moves_cache.json")

        try:
            from ...services.move_provider import ensure_move_in_json
            info = ensure_move_in_json(move, move_cache)
        except Exception as e:
            messagebox.showerror("PokéAPI", f"No pude obtener datos del movimiento.\n{e}")
            if hasattr(self, "lbl_accuracy_var"):
                self.lbl_accuracy_var.set("—")
            return

        # Autocompletar
        if info.get("type"):
            self.d_move_type.set(info["type"].capitalize())
        if info.get("power") is not None:
            self.d_power.set(str(info["power"]))
        dmgc = (info.get("damage_class") or "").lower()
        if dmgc in ("physical","special"):
            self.d_category.set("Physical" if dmgc == "physical" else "Special")

        # Precisión
        acc = info.get("accuracy")
        if hasattr(self, "lbl_accuracy_var"):
            self.lbl_accuracy_var.set(f"{acc}%" if acc is not None else "—")

        # Lógica especial Tera Blast (ajuste runtime se hace también en refresh)
        name_norm = move.strip().lower()
        if name_norm in ("tera blast","tera-blast"):
            # categoría por stat mayor del atacante
            set_id = self.d_attacker_map.get((self.d_attacker.get() or "").strip())
            if set_id:
                from sqlalchemy.orm import Session as _S
                from ...db.models import PokemonSet, Species
                from ...services.calculations import compute_stats as _compute
                with _S(self.services["engine"]) as s:
                    att = s.get(PokemonSet, set_id); sp = s.get(Species, att.species_id)
                    evs = _json.loads(att.evs_json) or {}; ivs = _json.loads(att.ivs_json) or {}
                    base = {"HP": sp.base_hp,"Atk": sp.base_atk,"Def": sp.base_def,"SpA": sp.base_spa,"SpD": sp.base_spd,"Spe": sp.base_spe}
                    tmp = type("Tmp", (), {"evs": evs, "level": att.level, "nature": att.nature})
                    stats = _compute(tmp, base_stats=base, ivs=ivs)
                self.d_category.set("Physical" if stats["Atk"] >= stats["SpA"] else "Special")
                # tipo final según Tera ON/OFF
                mt = self.d_tera_off_type.get() if self.d_tera_off_on.get() else (info["type"].capitalize() if info.get("type") else "Normal")
                self.d_move_type.set(mt)

    # ---------- Orden ----------
    def on_sort_damage(self, col: str):
        if self.dmg_sort_by == col:
            self.dmg_sort_dir = "asc" if self.dmg_sort_dir == "desc" else "desc"
        else:
            self.dmg_sort_by = col
            self.dmg_sort_dir = "desc" if col in ("max_pct","max","xef") else "asc"
        self.refresh_damage_list()

    # ---------- Cálculo principal ----------
    def refresh_damage_list(self):
        """Coordinador: valida, muestra loader y agenda el cálculo pesado."""
        # limpiar tabla
        for iid in self.dmg_tree.get_children():
            self.dmg_tree.delete(iid)
            
        # reset de contadores (por si salimos por validación)
        self.d_cnt_ohko.set("0")
        self.d_cnt_pos.set("0")
        self.d_cnt_no.set("0")
        self.d_cnt_total.set("0")

        # validar atacante
        label = (self.d_attacker.get() or "").strip()
        if not label or label not in self.d_attacker_map:
            messagebox.showinfo("Daños", "Elige un atacante.")
            return

        # leer parámetros rápidos (cualquier parsing/validación simple aquí)
        cat = (self.d_category.get() or "Physical").lower()
        try:
            power = int(self.d_power.get())
        except Exception:
            power = 0
        if power <= 0:
            messagebox.showwarning("Daños", "Poder debe ser un número mayor a 0.")
            return
        move_type = (self.d_move_type.get() or "Normal").capitalize()
        item_label = self.d_item.get()

        # empaquetar todo lo que necesitará el cálculo pesado (evita leer del UI en _compute_damage)
        params = {
            "attacker_label": label,
            "category": cat,
            "power": power,
            "item_label": item_label,
            "auto_stab": bool(self.d_auto_stab.get()),
            "stab_force": bool(self.d_stab_force.get()),
            "crit": bool(self.d_crit.get()),
            "burn": bool(self.d_burn.get()),
            "spread": bool(self.d_spread.get()),
            "tera_off_on": bool(self.d_tera_off_on.get()),
            "tera_off_type": self.d_tera_off_type.get(),
            "tera_def_on": bool(self.d_tera_def_on.get()),
            "tera_def_type": self.d_tera_def_type.get(),
            "weather": self.d_weather.get(),
            "reflect": bool(self.d_reflect.get()),
            "lightscreen": bool(self.d_lightscreen.get()),
            "veil": bool(self.d_veil.get()),
            "fmt_doubles": (self.d_format.get() == "Dobles"),
            "item_extra": self.d_item_extra.get(),
            "assault_vest": bool(self.d_assault_vest.get()),
            "picked_move": (self.d_move_pick.get() or "").strip().lower(),
            "hits": (self.d_hits.get() or "Auto"),
            "terrain": self.d_terrain.get(),
            "move_type": self.d_move_type.get(),
        }

        # mostrar loader y agendar el cálculo pesado para el próximo ciclo del loop
        self._show_loader("Calculando daños...")
        self.master.after(20, lambda: self._compute_damage(params))

    def _compute_damage(self, params: dict):
        try:
            # Desempaquetar
            label        = params["attacker_label"]
            cat          = params["category"]
            power        = params["power"]
            move_type    = params["move_type"]
            #item_mult    = self._choice_item_mult(params["item_label"])
            auto_stab    = params["auto_stab"]
            stab_force   = params["stab_force"]
            crit         = params["crit"]
            burn         = params["burn"]
            spread       = params["spread"]
            tera_off_on  = params["tera_off_on"]
            tera_off_type= params["tera_off_type"]
            tera_def_on  = params["tera_def_on"]
            tera_def_type= params["tera_def_type"]
            weather      = params["weather"]
            reflect      = params["reflect"]
            lightscreen  = params["lightscreen"]
            veil         = params["veil"]
            fmt_doubles  = params["fmt_doubles"]
            item_extra   = params["item_extra"]
            assault_vest = params["assault_vest"]
            picked_move  = params["picked_move"]
            

            # servicios
            Session = self.services["Session"]; engine = self.services["engine"]
            list_sets = self.services["list_sets"]; compute_stats = self.services["compute_stats"]

            # 1) Atacante
            from ...db.models import PokemonSet, Species
            set_id = self.d_attacker_map[label]
            with Session(engine) as s:
                attacker = s.get(PokemonSet, set_id)
                att_item = (attacker.item or "").strip()
                try:
                    self.att_item_var.set(att_item if att_item else "—")
                except Exception:
                    pass
                att_sp = s.get(Species, attacker.species_id)
                att_evs = _json.loads(attacker.evs_json); att_ivs = _json.loads(attacker.ivs_json)
                att_base = {"HP": att_sp.base_hp,"Atk": att_sp.base_atk,"Def": att_sp.base_def,"SpA": att_sp.base_spa,"SpD": att_sp.base_spd,"Spe": att_sp.base_spe}
                A_tmp = type("Tmp", (), {"evs": att_evs, "level": attacker.level, "nature": attacker.nature})
                att_stats = compute_stats(A_tmp, base_stats=att_base, ivs=att_ivs)

                # categoría puede cambiar por Tera Blast
                if picked_move in ("tera blast","tera-blast"):
                    move_type = (tera_off_type if tera_off_on else move_type).capitalize()
                    cat = "physical" if att_stats["Atk"] >= att_stats["SpA"] else "special"

                atk_stat = att_stats["Atk"] if cat == "physical" else att_stats["SpA"]

                # Refresca el label con el valor real usado en este cálculo
                try:
                    self.att_stat_var.set(f"{'Atk' if cat=='physical' else 'SpA'} {atk_stat}")
                except Exception:
                    pass

                if burn and cat == "physical":
                    atk_stat = int(atk_stat * 0.5)

                # tipos
                try:
                    att_types = self._get_species_types(
                        normalize_species_name(att_sp.name, getattr(attacker, "ability", None), getattr(attacker, "gender", None)),
                        attacker.gender,
                    )
                except Exception:
                    att_types = []

                # STAB manual si auto OFF
                stab_override = None if auto_stab else bool(stab_force)

                # 2) Defensores (trae todos)
                rows = list_sets(s, limit=None)

            items = []
            
            cnt_ohko = cnt_pos = cnt_no = 0
            
            for pset, sp in rows:
                # Item del defensor
                def_item = (pset.item or "").strip()

                # tipos del defensor + Tera defensivo
                try:
                    def_types = self._get_species_types(
                        normalize_species_name(sp.name, getattr(pset, "ability", None), getattr(pset, "gender", None)),
                        pset.gender,
                    )
                except Exception:
                    def_types = []
                if tera_def_on:
                    def_types = [tera_def_type]

                # 1) Efectividad base (por tipos)
                eff_mult = self._type_eff(move_type, def_types)
                
                # 2) Ajuste por baya del defensor (si corresponde)
                def_stat_mult, eff_adj = self._defender_item_effects_auto(def_item, cat, move_type, eff_mult)
                eff_mult *= eff_adj
                xef_txt = f"×{eff_mult:g}"

                # stats defensor
                D_evs = _json.loads(pset.evs_json) or {}
                D_ivs = _json.loads(pset.ivs_json) or {}
                D_base = {"HP": sp.base_hp,"Atk": sp.base_atk,"Def": sp.base_def,"SpA": sp.base_spa,"SpD": sp.base_spd,"Spe": sp.base_spe}
                D_tmp = type("Tmp", (), {"evs": D_evs, "level": pset.level, "nature": pset.nature})
                d_stats = compute_stats(D_tmp, base_stats=D_base, ivs=D_ivs)
                is_phys = (cat == "physical")
                def_stat = d_stats["Def"] if is_phys else d_stats["SpD"]
                hp_stat = d_stats["HP"]

                # boosts defensivos
                def_types_uc = [t.capitalize() for t in def_types]
                def_boost = self._defender_stat_weather_boost(def_types_uc, cat)
                def_stat_eff = int(def_stat * def_boost * def_stat_mult)
                if (cat == "special") and assault_vest:
                    def_stat_eff = int(def_stat_eff * 1.5)

                # daño base
                L = attacker.level
                base_damage = (((2 * L / 5) + 2) * power * atk_stat / max(1, def_stat_eff)) / 50 + 2

                # multiplicadores
                # sobrescribe pantalla/formato para usar los params locales
                old_weather = self.d_weather.get()
                old_reflect = self.d_reflect.get()
                old_ls      = self.d_lightscreen.get()
                old_veil    = self.d_veil.get()
                old_format  = self.d_format.get()
                try:
                    self.d_weather.set(weather)
                    self.d_reflect.set(reflect)
                    self.d_lightscreen.set(lightscreen)
                    self.d_veil.set(veil)
                    self.d_format.set("Dobles" if fmt_doubles else "Singles")

                    mod = self._dmg_modifier(
                        move_type=move_type,
                        attacker_types=att_types,
                        tera_off_on=tera_off_on,
                        tera_off_type=tera_off_type,
                        eff_mult=eff_mult,
                        item_mult_choice=1.0,
                        category=cat,
                        crit=bool(crit),
                        stab_override=stab_override,
                    )
                    # Añade el multiplicador por item del atacante (Choice/Life Orb/Expert Belt/Muscle/Wise)
                    mod *= self._attacker_item_multiplier_auto(att_item, cat, eff_mult, move_type)
                    if fmt_doubles and spread:
                        mod *= 0.75
                    xmod_val = float(mod)
                    terrain_mod = self._terrain_xmod(params.get("terrain"), params.get("move_type"), params.get("picked_move"))
                    xmod_val *= terrain_mod

                finally:
                    # restaurar UI vars
                    self.d_weather.set(old_weather)
                    self.d_reflect.set(old_reflect)
                    self.d_lightscreen.set(old_ls)
                    self.d_veil.set(old_veil)
                    self.d_format.set(old_format)

                # Daño por HITO único (single hit)
                dmin = int(base_damage * 0.85 * xmod_val)
                dmax = int(base_damage * 1.00 * xmod_val)

                # Nº de golpes (Auto usa nombre del movimiento + Loaded Dice)
                min_hits, max_hits, exp_hits, _mode = self._resolve_hits(
                    params.get("picked_move"), params.get("hits"), att_item
                )

                # Total por turno (rango)
                tdmin = int(dmin * min_hits)
                tdmax = int(dmax * max_hits)

                min_pct = round(tdmin * 100.0 / hp_stat, 1)
                max_pct = round(tdmax * 100.0 / hp_stat, 1)

                ohko = "Sí" if tdmin >= hp_stat else ("Posible" if tdmax >= hp_stat else "No")

                # contadores KO
                if ohko == "Sí":
                    cnt_ohko += 1
                elif str(ohko).lower().startswith("pos"):
                    cnt_pos += 1
                else:
                    cnt_no += 1
                    
                import math
                n_best = 999 if tdmax <= 0 else math.ceil(hp_stat / tdmax)         # mejor caso
                n_worst = 999 if tdmin <= 0 else math.ceil(hp_stat / max(1, tdmin)) # peor caso

                if n_best <= 1:
                    ko_label = "OHKO"
                elif n_best == n_worst:
                    ko_label = f"{n_best}HKO"
                else:
                    ko_label = f"{n_best}–{n_worst}HKO"

                def_base_stat = int(sp.base_def if is_phys else sp.base_spd)
                def_ev_val = int(D_evs.get("Def" if is_phys else "SpD", 0))

                items.append({
                    "target": f"{sp.name} (Lv{pset.level}/{pset.nature or '—'})",
                    "hp": hp_stat,
                    "def_base": def_base_stat,
                    "def_ev": def_ev_val,
                    "def_used": f"{'Def' if is_phys else 'SpD'} {def_stat}",
                    "def_item": def_item, 
                    "xef": xef_txt,
                    "xmod": f"×{xmod_val:.2f}",
                    "xmod_val": xmod_val,
                    "min": dmin,
                    "max": dmax,
                    "min_pct": min_pct,
                    "max_pct": max_pct,
                    "ko": ko_label,     # <— etiqueta visible
                    "ko_best": n_best,  # <— para ordenar / tags
                })

            # ordenar
            key = self.dmg_sort_by
            reverse = (self.dmg_sort_dir == "desc")

            def sort_key(r):
                if key == "xef":
                    try: return float(r.get("xef", "×1").replace("×",""))
                    except Exception: return 1.0
                if key == "xmod":
                    return r.get("xmod_val", 1.0)
                if key == "ko":
                    return r.get("ko_best", 99)

                return r.get(key, -999999) if r.get(key) is not None else -999999

            items.sort(key=sort_key, reverse=reverse)

            total = cnt_ohko + cnt_pos + cnt_no
            self.d_cnt_ohko.set(str(cnt_ohko))
            self.d_cnt_pos.set(str(cnt_pos))
            self.d_cnt_no.set(str(cnt_no))
            self.d_cnt_total.set(str(total))
            
            

            # pintar
            for r in items:
                tags = []
                kb = r.get("ko_best", 99)
                if kb <= 1:
                    tags.append("ko_ohko")
                elif kb == 2:
                    tags.append("ko_2hko")
                elif kb >= 4:
                    tags.append("ko_4hko")

                insert_with_zebra(self.dmg_tree, values=(r["target"], r["hp"], r["def_base"], r["def_ev"], r["def_used"], r["def_item"],
                            r["xef"], r["xmod"], r["min"], r["max"], r["min_pct"], r["max_pct"], r["ko"], r["ko_best"]), tags=tuple(tags))

        finally:
            # ocultar loader siempre, incluso si hay excepción
            self._hide_loader()
    
    # Fin _compute_damage

    # ---------- multiplicadores (versión básica; en Paso 2 pegamos la avanzada) ----------
    def _choice_item_mult(self, label: str) -> float:
        s = (label or "").lower()
        if "choice" in s: return 1.5
        if "life orb" in s: return 1.3
        return 1.0

    def _attacker_extra_item_mult(self, category: str, eff_mult: float) -> float:
        # Expert Belt, Muscle Band, Wise Glasses (simplificado)
        s = (self.d_item_extra.get() or "")
        if "Expert Belt" in s and eff_mult > 1.0:
            return 1.2
        if "Muscle Band" in s and category == "physical":
            return 1.1
        if "Wise Glasses" in s and category == "special":
            return 1.1
        return 1.0
    
    def _attacker_item_multiplier_auto(self, item_label: str, category: str, eff_mult: float, move_type: str) -> float:
        """
        Multiplicador por item del atacante, según el nombre del ítem del set.
        category: 'physical' | 'special'
        """
        s = (item_label or "").strip().lower()
        if not s:
            return 1.0

        # Choice
        if "choice band" in s and category == "physical":
            return 1.5
        if "choice specs" in s and category == "special":
            return 1.5
        # Life Orb
        if "life orb" in s:
            return 1.3
        # Expert Belt (si es superefectivo)
        if "expert belt" in s and eff_mult > 1.0:
            return 1.2
        # Muscle Band (físico)
        if "muscle band" in s and category == "physical":
            return 1.1
        # Wise Glasses (especial)
        if "wise glasses" in s and category == "special":
            return 1.1

        type_item_map = {
            "charcoal": "Fire",
            "mystic water": "Water",
            "magnet": "Electric",
            "miracle seed": "Grass",
            "never-melt ice": "Ice",
            "black belt": "Fighting",
            "poison barb": "Poison",
            "soft sand": "Ground",
            "sharp beak": "Flying",
            "twisted spoon": "Psychic",
            "silver powder": "Bug",
            "hard stone": "Rock",
            "spell tag": "Ghost",
            "dragon fang": "Dragon",
            "black glasses": "Dark",
            "metal coat": "Steel",
            "pixie plate": "Fairy",  # (u objetos equivalentes)
        }
        for key, t in type_item_map.items():
            if key in s and (move_type or "").capitalize() == t:
                return 1.2

        return 1.0

    def _defender_item_effects_auto(self, item_label: str, category: str, move_type: str, eff_mult: float) -> tuple[float, float]:
        """
        Efectos defensivos por item del set.
        Devuelve (def_stat_mult, eff_mult_adjust)
        - def_stat_mult: multiplicador sobre la defensa efectiva (ej. Assault Vest)
        - eff_mult_adjust: factor para el multiplicador de efectividad (ej. bayas 0.5)
        """
        s = (item_label or "").strip().lower()
        def_mult = 1.0
        eff_adj = 1.0

        if not s:
            return def_mult, eff_adj

        # Assault Vest: SpD x1.5 cuando el ataque es especial
        if "assault vest" in s and category == "special":
            def_mult *= 1.5

        # Resist berries: si es superefectivo y tipo coincide, x0.5
        wanted = _RESIST_BERRY_BY_TYPE.get((move_type or "").capitalize())
        if wanted and wanted.lower() in s and eff_mult > 1.0:
            eff_adj *= 0.5

        # (Opcional: Eviolite, Multiscale, etc.)
        return def_mult, eff_adj

    def _weather_move_multiplier(self, move_type: str) -> float:
        w = self.d_weather.get()
        mt = (move_type or "").capitalize()
        if w == "Lluvia" and mt in ("Water","Fire"):
            return 1.5 if mt == "Water" else 0.5
        if w == "Sol" and mt in ("Water","Fire"):
            return 0.5 if mt == "Water" else 1.5
        return 1.0

    def _screen_multiplier(self, category: str) -> float:
        # Singles: 0.5; Dobles: ~0.67
        singles = (self.d_format.get() == "Singles")
        base = 0.5 if singles else (2/3)
        if category == "physical" and self.d_reflect.get():
            return base
        if category == "special" and self.d_lightscreen.get():
            return base
        if self.d_veil.get():
            return base
        return 1.0

    def _defender_stat_weather_boost(self, def_types_uc: list[str], category: str) -> float:
        # Sand: Rock SpD x1.5 ; Snow: Ice Def x1.5 (gen9)
        w = self.d_weather.get()
        if category == "special" and w == "Tormenta Arena" and "Rock" in def_types_uc:
            return 1.5
        if category == "physical" and w == "Nieve" and "Ice" in def_types_uc:
            return 1.5
        return 1.0

    def _tera_stab_multiplier(self, *, move_type: str, attacker_types: list[str], tera_on: bool, tera_type: str) -> float:
        mt = (move_type or "").capitalize()
        atts = [t.capitalize() for t in (attacker_types or [])]
        tt = (tera_type or "").capitalize()
        if not tera_on:
            return 1.5 if mt in atts else 1.0
        if mt == tt and mt in atts:  # doble STAB
            return 2.0
        if mt == tt and mt not in atts:
            return 1.5
        if mt != tt and mt in atts:
            return 1.5
        return 1.0

    def _dmg_modifier(self, *, move_type: str, attacker_types: list[str], tera_off_on: bool, tera_off_type: str,
                      eff_mult: float, item_mult_choice: float, category: str, crit: bool, stab_override: bool|None=None) -> float:
        if stab_override is not None:
            stab = 1.5 if stab_override else 1.0
        else:
            stab = self._tera_stab_multiplier(move_type=move_type, attacker_types=attacker_types,
                                              tera_on=tera_off_on, tera_type=tera_off_type)
        extra_item = self._attacker_extra_item_mult(category, eff_mult)
        weather_mv = self._weather_move_multiplier(move_type)
        screens = self._screen_multiplier(category)
        crit_mult = 1.5 if crit else 1.0
        spread_mult = 0.75 if (self.d_format.get()=="Dobles" and self.d_spread.get()) else 1.0

        return stab * eff_mult * item_mult_choice * extra_item * weather_mv * screens * crit_mult * spread_mult

    def _show_loader(self, msg: str = "Calculando..."):
        try:
            self.loader_label.config(text=msg)
            # Mostrar el frame del loader
            self.loader_frame.pack(fill="x", padx=8, pady=(0,8))
            # Arrancar la animación
            self.loader_bar.start(12)  # ms entre pasos (ajusta si quieres más rápido/lento)
            # Forzar refresco visual antes del cálculo
            self.master.update_idletasks()
        except Exception:
            pass

    def _hide_loader(self):
        try:
            self.loader_bar.stop()
            self.loader_frame.pack_forget()
            self.master.update_idletasks()
        except Exception:
            pass

    def _update_attacker_item_and_stat(self):
        """Lee el set atacante desde la BD y actualiza el Ítem y el Stat (Atk/SpA) según la categoría actual."""
        label = (self.d_attacker.get() or "").strip()
        set_id = self.d_attacker_map.get(label)
        if not set_id:
            self.att_item_var.set("—")
            self.att_stat_var.set("—")
            return

        from ...db.models import PokemonSet, Species
        Session = self.services["Session"]; engine = self.services["engine"]
        compute_stats = self.services["compute_stats"]

        import json as _json
        with Session(engine) as s:
            p = s.get(PokemonSet, set_id)
            sp = s.get(Species, p.species_id)

            # Ítem atacante
            self.att_item_var.set((p.item or "—").strip())

            # Stat del atacante (según categoría UI actual)
            cat = (self.d_category.get() or "Physical").lower()
            evs = _json.loads(p.evs_json) or {}
            ivs = _json.loads(p.ivs_json) or {}
            base = {"HP": sp.base_hp, "Atk": sp.base_atk, "Def": sp.base_def,
                    "SpA": sp.base_spa, "SpD": sp.base_spd, "Spe": sp.base_spe}
            tmp = type("Tmp", (), {"evs": evs, "level": p.level, "nature": p.nature})
            stats = compute_stats(tmp, base_stats=base, ivs=ivs)
            if cat == "physical":
                self.att_stat_var.set(f"Atk {stats['Atk']}")
            else:
                self.att_stat_var.set(f"SpA {stats['SpA']}")
                

    def _resolve_hits(self, picked_move: str, hits_sel: str, att_item: str):
        """
        Devuelve (min_hits, max_hits, expected_hits, mode)
        - mode: "fixed" (N fijo), "range" (min..max), "auto" (detectado)
        """
        mv = (picked_move or "").strip().lower()
        item = (att_item or "").strip().lower()
        sel = (hits_sel or "Auto").strip().lower()

        PRESETS = {
            # fijos 2
            "double hit": (2, 2), "double kick": (2, 2), "dual chop": (2, 2),
            "bonemerang": (2, 2), "twinneedle": (2, 2), "dragon darts": (2, 2),
            # fijos 3
            "surging strikes": (3, 3), "triple kick": (3, 3), "triple axel": (3, 3),
            # 2–5
            "bullet seed": (2, 5), "icicle spear": (2, 5), "rock blast": (2, 5),
            "arm thrust": (2, 5), "fury swipes": (2, 5), "pin missile": (2, 5),
            "scale shot": (2, 5), "water shuriken": (2, 5),
            # 2–10 aprox
            "population bomb": (2, 10),
        }

        def dist_2_5_expected():
            # 37.5%:2, 37.5%:3, 12.5%:4, 12.5%:5 → 3.0 esperado
            return 3.0

        # Selección manual
        if sel in {"1","2","3","4","5","10"}:
            n = int(sel); return (n, n, float(n), "fixed")
        if sel.startswith("2-5"):
            if "loaded dice" in item:
                return (4, 5, 4.5, "range")
            return (2, 5, dist_2_5_expected(), "range")
        if sel.startswith("4-5"):
            return (4, 5, 4.5, "range")

        # Auto por movimiento
        if mv in PRESETS:
            lo, hi = PRESETS[mv]
            if (lo, hi) == (2, 5) and "loaded dice" in item:
                return (4, 5, 4.5, "auto")
            if (lo, hi) == (2, 5):
                esp = 3.0
            elif (lo, hi) == (2, 10):
                esp = 6.0
            else:
                esp = (lo + hi) / 2.0
            return (lo, hi, esp, "auto")

        # fallback: 1 golpe
        return (1, 1, 1.0, "fixed")


    def _reload_attackers(self):
        """Reconstruye la lista desde DB y preserva selección/último visto."""
        self.d_attacker_map.clear()
        labels = []
        Session = self.services["Session"]; engine = self.services["engine"]; list_sets = self.services["list_sets"]
        with Session(engine) as s:
            rows = list_sets(s, limit=None)

        for pset, sp in rows:
            label = f"{sp.name} (Lv{pset.level}/{pset.nature or '—'}) #{pset.id}"
            self.d_attacker_map[label] = pset.id
            labels.append(label)

        self.attacker_combo["values"] = labels

        if labels:
            # 1) Preferir selección actual si sigue válida; si no, último visto; si no, el primero
            current = (self.d_attacker.get() or "").strip()
            prefer  = current or (self._last_attacker_label or "")
            target  = prefer if prefer in labels else labels[0]
            if target != current:
                self.d_attacker.set(target)

            # 2) Sincronizar movimientos y stats del atacante
            self._reload_moves_for_selected_attacker()
            self._update_attacker_item_and_stat()

            # 3) Actualizar datos del movimiento seleccionado (power/tipo/categoría/acc, etc.)
            if (self.d_move_pick.get() or "").strip():
                self.on_pick_move()
        else:
            # No hay registros: limpiar UI relacionada
            self.d_attacker.set("")
            self.cmb_move_pick["values"] = []
            self.d_move_pick.set("")
            try:
                self.att_item_var.set("—")
                self.att_stat_var.set("—")
            except Exception:
                pass


    def _ensure_default_loaded(self):
        """Garantiza que al entrar a la pestaña haya un atacante y un movimiento con datos actualizados."""
        # si aún no hay lista de atacantes cargada, cárgala
        if not self.attacker_combo["values"]:
            self._reload_attackers()
            return  # _reload_attackers ya setea atacante+movimiento y actualiza

        # si no hay atacante seleccionado, selecciona uno
        if not (self.d_attacker.get() or "").strip():
            labels = list(self.attacker_combo["values"])
            if labels:
                target = self._last_attacker_label if (self._last_attacker_label in labels) else labels[0]
                self.d_attacker.set(target)
                self._reload_moves_for_selected_attacker()
                self._update_attacker_item_and_stat()
                return

        # si no hay movimiento, recargar de ese atacante
        if not (self.d_move_pick.get() or "").strip():
            self._reload_moves_for_selected_attacker()
            self._update_attacker_item_and_stat()
            return

        # sincroniza campos del movimiento por si se quedó viejo
        self.on_pick_move()

    def _on_attacker_selected(self, event=None):
        self._reload_moves_for_selected_attacker()
        self._update_attacker_item_and_stat()
        self.on_pick_move()  # actualiza datos del movimiento
        
    def _terrain_xmod(self, terrain: str | None, move_type: str | None, picked_move: str | None) -> float:
        """
        Devuelve el multiplicador por 'Campo':
        - Eléctrico: +30% a movimientos Eléctricos del atacante (1.3)
        - Psíquico:  +30% a movimientos Psíquicos del atacante (1.3)
        - Hierba:    +30% a movimientos de tipo Planta (1.3)
                    y -50% a Earthquake/Bulldoze/Magnitude (0.5)
        - Niebla:    -50% a movimientos Dragón (0.5)
        Nota: En juegos aplica a 'grounded'. Aquí asumimos grounded (simple).
        """
        t = (terrain or "").strip().lower()
        mt = (move_type or "").strip().lower()
        mv = (picked_move or "").strip().lower()

        # normaliza acentos
        def norm(s: str) -> str:
            return (s.replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u"))
        t, mt = norm(t), norm(mt)

        mod = 1.0
        if t in {"electrico", "electrico/campo", "campo electrico", "electrico campo", "electrico terrain", "electric", "electric terrain"}:
            if mt in {"electrico", "electric"}:
                mod *= 1.3
        elif t in {"psiquico", "campo psiquico", "psiquico terrain", "psiquico/campo", "psychic", "psychic terrain"}:
            if mt in {"psiquico", "psychic"}:
                mod *= 1.3
        elif t in {"hierba", "campo hierba", "hierba terrain", "grassy", "grassy terrain", "planta"}:
            if mt in {"hierba", "grassy", "planta", "grass"}:
                mod *= 1.3
            # Reducción de movimientos sísmicos
            if mv in {"earthquake", "bulldoze", "magnitude"}:
                mod *= 0.5
        elif t in {"niebla", "campo niebla", "misty", "misty terrain"}:
            if mt in {"dragon", "dragon/dragón", "dragon/dragon", "dragon type"} or mt.startswith("dragon"):
                mod *= 0.5

        return mod

    def _on_notebook_tab_changed(self, event=None):
        """Si la pestaña visible es ésta, recarga atacantes desde DB y sincroniza UI."""
        nb = event.widget
        try:
            current = nb.nametowidget(nb.select())
        except Exception:
            return
        if current is self.master:
            # recuerda el seleccionado actual si hay
            if (self.d_attacker.get() or "").strip():
                self._last_attacker_label = self.d_attacker.get()
            # recarga atacantes desde la base y sincroniza movimientos/valores
            self._reload_attackers()
