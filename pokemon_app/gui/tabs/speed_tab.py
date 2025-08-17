import tkinter as tk
from tkinter import ttk, messagebox
from pokemon_app.utils.species_normalize import normalize_species_name

NATURES = sorted(list({
    'Adamant','Lonely','Brave','Naughty',
    'Impish','Bold','Relaxed','Lax',
    'Modest','Mild','Quiet','Rash',
    'Calm','Gentle','Sassy','Careful',
    'Jolly','Hasty','Naive','Timid',
    'Serious','Bashful','Docile','Hardy','Quirky'
}))

class SpeedTab:
    """
    Pestaña de Velocidad: lista sets guardados y calcula Velocidad efectiva
    con modificadores (etapas, tailwind, parálisis, scarf, habilidades).
    Usa services = {"Session","engine","list_sets","compute_stats"}.
    """
    def __init__(self, master, services: dict):
        self.master = master
        self.services = services

        # estado de ordenamiento
        self.speed_sort_by = "speed"
        self.speed_sort_dir = "desc"

        self._build_ui()

    def get_frame(self):
        return self.master

    # ---------- UI ----------
    def _build_ui(self):
        # Filtros arriba
        frm_sf = ttk.Frame(self.master); frm_sf.pack(fill="x", padx=8, pady=6)

        ttk.Label(frm_sf, text="Especie:").grid(row=0, column=0, sticky="w")
        self.s_filter = tk.StringVar()
        ttk.Entry(frm_sf, textvariable=self.s_filter, width=20)\
            .grid(row=0, column=1, padx=4)

        ttk.Label(frm_sf, text="Naturaleza:").grid(row=0, column=2, sticky="w")
        self.s_nat = tk.StringVar()
        ttk.Combobox(frm_sf, textvariable=self.s_nat, width=14, values=NATURES, state="readonly")\
            .grid(row=0, column=3, padx=4)

        ttk.Label(frm_sf, text="Vel. min/max:").grid(row=0, column=4, sticky="w")
        self.s_speed_min = tk.StringVar(); self.s_speed_max = tk.StringVar()
        ttk.Entry(frm_sf, textvariable=self.s_speed_min, width=7)\
            .grid(row=0, column=5, padx=(0,2))
        ttk.Entry(frm_sf, textvariable=self.s_speed_max, width=7)\
            .grid(row=0, column=6, padx=(2,4))

        ttk.Button(frm_sf, text="Actualizar", command=self.refresh)\
            .grid(row=0, column=7, padx=6)
        ttk.Button(frm_sf, text="Limpiar", command=self.clear_speed_filters)\
            .grid(row=0, column=8)

        # Tabla
        cols = ("pin","species","item","nature","base_stat","iv","ev","calc","speed_item","speed")
        self.speed_tree = ttk.Treeview(self.master, columns=cols, show="headings", selectmode="browse", height=16)
        self.speed_tree.pack(fill="both", expand=True, padx=8, pady=(0,8))

        self.speed_tree.column("pin",       width=36,  anchor="center") 
        self.speed_tree.column("species",  width=150, anchor="w")
        self.speed_tree.column("item",      width=130, anchor="w") 
        self.speed_tree.column("nature",   width=80,  anchor="w")
        self.speed_tree.column("base_stat",width=70,  anchor="e")
        self.speed_tree.column("iv",       width=50,  anchor="center")
        self.speed_tree.column("ev",       width=50,  anchor="center")
        self.speed_tree.column("calc",     width=80, anchor="e")
        self.speed_tree.column("speed_item", width=80, anchor="e")
        self.speed_tree.column("speed",    width=80,  anchor="e")
        
        self.speed_tree.heading("pin",        text="Fijar")
        self.speed_tree.heading("species",   text="Especie",       command=lambda c="species": self.on_sort_speed(c))
        self.speed_tree.heading("item",      text="Ítem",         command=lambda c="item":      self.on_sort_speed(c))
        self.speed_tree.heading("nature",    text="Naturaleza",    command=lambda c="nature":  self.on_sort_speed(c))
        self.speed_tree.heading("base_stat", text="Base Spe",      command=lambda c="base_stat": self.on_sort_speed(c))
        self.speed_tree.heading("iv",        text="IV Spe",        command=lambda c="iv":      self.on_sort_speed(c))
        self.speed_tree.heading("ev",        text="EV Spe",        command=lambda c="ev":      self.on_sort_speed(c))
        self.speed_tree.heading("calc",      text="Vel (Base)",    command=lambda c="calc":    self.on_sort_speed(c))
        self.speed_tree.heading("speed_item", text="Vel (Item)",  command=lambda c="speed_item": self.on_sort_speed(c))
        self.speed_tree.heading("speed",     text="Vel (Final)",   command=lambda c="speed":   self.on_sort_speed(c))

        # Estado para pines + cache de filas fijadas
        self.pinned_ids   = getattr(self, "pinned_ids", set())
        self.pinned_cache = getattr(self, "pinned_cache", {})

        # Click en la celda: alterna pin si hacen click en la primera columna
        self.speed_tree.bind("<Button-1>", self.on_speed_click)

        # Modificadores
        frm_mod = ttk.LabelFrame(self.master, text="Modificadores")
        frm_mod.pack(fill="x", padx=8, pady=(0,8))

        ttk.Label(frm_mod, text="Etapas (+/-6):").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.s_stage = tk.StringVar(value="0")
        ttk.Combobox(frm_mod, textvariable=self.s_stage, width=5,
                     values=[str(i) for i in range(-6, 7)], state="readonly")\
            .grid(row=0, column=1, padx=4, pady=4)

        self.s_tailwind = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm_mod, text="Tailwind (x2)", variable=self.s_tailwind)\
            .grid(row=0, column=2, padx=8, pady=4)

        self.s_para = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm_mod, text="Parálisis (x0.5)", variable=self.s_para)\
            .grid(row=0, column=3, padx=8, pady=4)

        ttk.Label(frm_mod, text="Habilidad/efecto:").grid(row=0, column=5, sticky="w", padx=8, pady=4)
        self.s_ability = tk.StringVar(value="—")
        ttk.Combobox(frm_mod, textvariable=self.s_ability, width=22, state="readonly",
                     values=["—","Swift Swim (Lluvia)","Chlorophyll (Sol)",
                             "Sand Rush (Tormenta Arena)","Slush Rush (Nieve)",
                             "Unburden (Objeto consumido)"])\
            .grid(row=0, column=6, padx=4, pady=4)

        ttk.Button(frm_mod, text="Recalcular", command=self.refresh)\
            .grid(row=0, column=7, padx=8)

        # binds útiles
        self.speed_tree.bind("<Double-1>", lambda e: self.refresh())  # opcional
        for w in frm_sf.winfo_children():
            if isinstance(w, (ttk.Entry, ttk.Combobox)):
                w.bind("<Return>", lambda e: self.refresh())

    # ---------- lógica ----------
    def clear_speed_filters(self):
        for var in (self.s_filter, self.s_nat, self.s_speed_min, self.s_speed_max):
            var.set("")
        self.refresh()

    def on_sort_speed(self, col: str):
        if self.speed_sort_by == col:
            self.speed_sort_dir = "asc" if self.speed_sort_dir == "desc" else "desc"
        else:
            self.speed_sort_by = col
            self.speed_sort_dir = "desc" if col == "speed" else "asc"
        self.refresh()

    def _stage_multiplier(self, stage: int | str) -> float:
        try:
            s = int(stage)
        except Exception:
            s = 0
        s = max(-6, min(6, s))
        if s >= 0:
            return (2 + s) / 2.0
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

    def _safe_int(self, v):
        try: return int(str(v).strip())
        except Exception: return None

    def refresh(self):
        # Limpiar tabla
        for iid in self.speed_tree.get_children():
            self.speed_tree.delete(iid)

        # Servicios inyectados
        Session = self.services["Session"]
        engine  = self.services["engine"]
        list_sets = self.services["list_sets"]
        compute_stats = self.services["compute_stats"]

        # Filtros
        species_like = (self.s_filter.get().strip() or "")
        if species_like and "%" not in species_like:
            species_like = f"%{species_like}%"
        nature = self.s_nat.get().strip() or None

        with Session(engine) as s:
            rows = list_sets(s, only_species=species_like or None, nature=nature)

        items = []
        for pset, sp in rows:
            import json as _json

            # Carga segura EVs/IVs
            def _load_json(s):
                try:
                    return _json.loads(s) if s else {}
                except Exception:
                    return {}
            evs = _load_json(getattr(pset, "evs_json", None))
            ivs = _load_json(getattr(pset, "ivs_json", None))

            base_stats = {
                "HP": sp.base_hp, "Atk": sp.base_atk, "Def": sp.base_def,
                "SpA": sp.base_spa, "SpD": sp.base_spd, "Spe": sp.base_spe
            }

            # Nivel seguro (fallback 50)
            try:
                level = int(pset.level) if pset.level is not None else 50
            except Exception:
                level = 50

            # Cálculo de stats protegido
            try:
                tmp = type("Tmp", (), {"evs": evs, "level": level, "nature": pset.nature})
                stats = compute_stats(tmp, base_stats=base_stats, ivs=ivs)
            except Exception as e:
                messagebox.showerror("Cálculo de velocidad", str(e))
                continue

            # Identificador estable de la fila
            rec_id = str(getattr(pset, "id", f"{sp.name}-{pset.level}-{pset.nature}-{pset.item}"))

            # Icono del pin por fila
            pin_icon = "📌" if rec_id in self.pinned_ids else "○"

            base_stat_spe = int(sp.base_spe)
            calc_spe = int(stats["Spe"])

            # Modificadores
            stage_mult    = self._stage_multiplier(self.s_stage.get())
            tailwind_mult = 2.0 if self.s_tailwind.get() else 1.0
            para_mult     = 0.5 if self.s_para.get() else 1.0
            ability_mult  = self._ability_speed_mult(self.s_ability.get())
            item_mult     = self._item_speed_mult(pset.item, sp.name)
            climate_mult  = self._climate_ability_mult(self.s_ability.get(), getattr(pset, "ability", None))

            # Habilidad climática: condicional por Pokémon
            climate_labels = {'Swift Swim (Lluvia)', 'Chlorophyll (Sol)', 'Sand Rush (Tormenta Arena)', 'Slush Rush (Nieve)'}
            ability_effective = 1.0 if (self.s_ability.get() in climate_labels) else ability_mult

            # Vel (Item): ítem + clima por fila  ← (ajuste #2)
            speed_item = int(calc_spe * item_mult * climate_mult)

            # Vel (Final): incluye ítem (no hay scarf_mult)
            eff_speed = int(
                calc_spe * stage_mult * tailwind_mult * para_mult
                * ability_effective * climate_mult * item_mult
            )

            items.append({
                "id": rec_id,
                "pin": pin_icon,
                "species": normalize_species_name(sp.name, getattr(pset, "ability", None), getattr(pset, "gender", None)),
                "item": (pset.item or "—"),
                "nature": pset.nature or "—",
                "base_stat": base_stat_spe,
                "iv": int(ivs.get("Spe", 31)),
                "ev": int(evs.get("Spe", 0)),
                "calc": calc_spe,
                "speed_item": speed_item,
                "speed": eff_speed,
            })

            # Actualiza cache si está fijado (para sobrevivir a filtros SQL)
            if rec_id in self.pinned_ids:
                self.pinned_cache[rec_id] = items[-1]

        # Filtro min/max (Python)
        vmin = self._safe_int(self.s_speed_min.get())
        vmax = self._safe_int(self.s_speed_max.get())
        if vmin is not None:
            items = [r for r in items if r["speed"] >= vmin]
        if vmax is not None:
            items = [r for r in items if r["speed"] <= vmax]

        # Unir fijados que fueron filtrados por SQL
        present = {r["id"] for r in items}
        for pid in list(self.pinned_ids):
            if pid not in present and pid in self.pinned_cache:
                items.append(self.pinned_cache[pid])

        # Orden
        key = self.speed_sort_by
        reverse = (self.speed_sort_dir == "desc")
        items.sort(key=lambda r: (r[key] if r[key] is not None else -999999), reverse=reverse)

        # Pintar  ← (ajuste #1: usar iid estable)
        for r in items:
            self.speed_tree.insert(
                "", "end",
                iid=r["id"],
                values=(r["pin"], r["species"], r["item"], r["nature"], r["base_stat"], r["iv"], r["ev"], r["calc"], r.get("speed_item"), r["speed"])
            )


    def _item_speed_mult(self, item_name: str, species_name: str) -> float:
        name = (item_name or "").strip().lower()
        if not name:
            return 1.0
        if name in {"choice scarf", "choicescarf"}:
            return 1.5
        half_items = {
            "iron ball","ironball","macho brace","machobrace",
            "power anklet","poweranklet","power band","powerband",
            "power belt","powerbelt","power bracer","powerbracer",
            "power lens","powerlens","power weight","powerweight"
        }
        if name in half_items:
            return 0.5
        if name in {"quick powder","quickpowder"} and (species_name or "").strip().lower() == "ditto":
            return 2.0
        return 1.0

    def _climate_ability_mult(self, selected_label: str, ability_name: str | None) -> float:
        """
        Aplica 2.0x SOLO si:
        - El selector de habilidad climática está activo (ej. "Swift Swim (Lluvia)"), y
        - La habilidad del Pokémon de la fila coincide (ej. "Swift Swim").
        """
        sel = (selected_label or "").strip()
        ab  = (ability_name or "").strip().lower()
        mapping = {
            "Swift Swim (Lluvia)": "swift swim",
            "Chlorophyll (Sol)": "chlorophyll",
            "Sand Rush (Tormenta Arena)": "sand rush",
            "Slush Rush (Nieve)": "slush rush",
        }
        target = mapping.get(sel)
        if target and ab == target:
            return 2.0
        return 1.0
    
    def on_speed_click(self, event):
        tree = self.speed_tree
        region = tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = tree.identify_column(event.x)  # "#1" = primera columna
        if col != "#1":
            return
        row = tree.identify_row(event.y)
        if not row:
            return

        rec_id = row  # usamos iid = id del set
        if rec_id in self.pinned_ids:
            self.pinned_ids.remove(rec_id)
        else:
            self.pinned_ids.add(rec_id)

        # refresca para redibujar icono y reinsertar fijados aunque el filtro los excluya
        self.refresh()

