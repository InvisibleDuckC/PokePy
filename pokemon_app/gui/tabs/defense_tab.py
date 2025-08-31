# pokemon_app/gui/tabs/defense_tab.py
import json as _json
import tkinter as tk
from tkinter import ttk, messagebox

from pokemon_app.gui.ui.treeview_kit import set_style, apply_zebra, insert_with_zebra, autosize_columns, update_sort_arrows


class DefenseTab(ttk.Frame):
    def __init__(self, master, services: dict):
        super().__init__(master)
        self.services = services

        # estado
        self.d_defender = tk.StringVar()
        self._defender_map = {}      # label -> set_id
        self._last_def_label = None
        self.d_format = tk.StringVar(value="Singles")
        self.d_weather = tk.StringVar(value="Ninguno")
        self.d_terrain = tk.StringVar(value="Ninguno")
        self.d_reflect     = tk.BooleanVar(value=False)
        self.d_lightscreen = tk.BooleanVar(value=False)
        self.d_veil        = tk.BooleanVar(value=False)

        # orden tabla
        self.sort_by = "max_pct"
        self.sort_dir = "desc"

        self._build_ui()
        self.after(0, self._reload_defenders)

    # ---------------- UI ----------------
    def _build_ui(self):
        nb_container = self.master

        top = ttk.LabelFrame(nb_container, text="Defensor y Parámetros")
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="Defensor:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.cmb_defender = ttk.Combobox(top, textvariable=self.d_defender, width=42, state="readonly", values=[])
        self.cmb_defender.grid(row=0, column=1, columnspan=3, sticky="w", padx=4, pady=4)
        self.cmb_defender.bind("<<ComboboxSelected>>", self._on_defender_selected)

        # Stats visibles del defensor
        self.def_item_var = tk.StringVar(value="—")
        self.def_stat_var = tk.StringVar(value="HP/Def/SpD —")
        ttk.Label(top, text="Ítem (def):").grid(row=0, column=4, sticky="e", padx=4)
        ttk.Label(top, textvariable=self.def_item_var, width=18, relief="sunken", anchor="w").grid(row=0, column=5, sticky="w", padx=4)
        ttk.Label(top, text="Stats:").grid(row=1, column=4, sticky="e", padx=4)
        ttk.Label(top, textvariable=self.def_stat_var, width=18, relief="sunken", anchor="w").grid(row=1, column=5, sticky="w", padx=4)

        # Parámetros de campo
        ttk.Label(top, text="Clima:").grid(row=1, column=0, sticky="w", padx=4)
        ttk.Combobox(top, textvariable=self.d_weather, width=14, state="readonly",
                     values=["Ninguno","Lluvia","Sol","Tormenta Arena","Nieve"]).grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(top, text="Terreno:").grid(row=1, column=2, sticky="e", padx=4)
        ttk.Combobox(top, textvariable=self.d_terrain, width=14, state="readonly",
                     values=["Ninguno","Grassy","Electric","Psychic","Misty"]).grid(row=1, column=3, sticky="w", padx=4)

        ttk.Checkbutton(top, text="Reflect", variable=self.d_reflect).grid(row=2, column=0, padx=4, sticky="w")
        ttk.Checkbutton(top, text="Light Screen", variable=self.d_lightscreen).grid(row=2, column=1, padx=4, sticky="w")
        ttk.Checkbutton(top, text="Aurora Veil", variable=self.d_veil).grid(row=2, column=2, padx=4, sticky="w")

        ttk.Label(top, text="Formato:").grid(row=2, column=4, sticky="e")
        ttk.Combobox(top, textvariable=self.d_format, width=12, state="readonly",
                     values=["Singles","Dobles"]).grid(row=2, column=5, padx=4, sticky="w")

        self.btn_recalc = ttk.Button(top, text="Recalcular", command=self.refresh)
        self.btn_recalc.grid(row=0, column=4, padx=4, pady=4, sticky="e")

        # Tabla
        cols = ("attacker","item_att","move","cat","power","type","xef","xmod","min","max","min_pct","max_pct","ko","ohko_pct")
        self.tree = ttk.Treeview(nb_container, columns=cols, show="headings", height=18)
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0,8))
        set_style(self.tree); apply_zebra(self.tree)

        cfg = [
            ("attacker", 220, "Atacante"),
            ("item_att", 130, "Ítem (att)"),
            ("move",     160, "Mejor mov."),
            ("cat",       80, "Cat"),
            ("power",     70, "Poder"),
            ("type",      80, "Tipo"),
            ("xef",       60, "xEF"),
            ("xmod",      70, "xMOD"),
            ("min",       80, "Daño min"),
            ("max",       80, "Daño max"),
            ("min_pct",   80, "% min"),
            ("max_pct",   80, "% max"),
            ("ko",        80, "HKO"),
            ("ohko_pct",  80, "OHKO %"),
        ]
        for key,w,txt in cfg:
            self.tree.column(key, width=w, anchor="e" if key not in ("attacker","move","item_att","cat","type","ko") else "w")
            self.tree.heading(key, text=txt, command=lambda c=key: self.on_sort(c))

    # ---------------- Eventos/acciones ----------------
    def _reload_defenders(self):
        """Carga/recarga el combo con los sets guardados (como en Damage tab pero para defensor)."""
        self._defender_map.clear()
        labels = []
        Session = self.services["Session"]; engine = self.services["engine"]; list_sets = self.services["list_sets"]
        with Session(engine) as s:
            rows = list_sets(s, limit=None)
        for pset, sp in rows:
            label = f"{sp.name} (Lv{pset.level}/{pset.nature or '—'}) #{pset.id}"
            self._defender_map[label] = pset.id
            labels.append(label)
        self.cmb_defender["values"] = labels
        if labels:
            if not self.d_defender.get():
                self.d_defender.set(labels[0])
            self._on_defender_selected()   # permite ser llamada sin evento
        else:
            self.d_defender.set("")
            self._last_def_label = None

    def _on_defender_selected(self, event=None):
        label = (self.d_defender.get() or "").strip()
        self._last_def_label = label if label in self._defender_map else None
        # Mostrar item/stats básicos del defensor
        try:
            Session = self.services["Session"]; engine = self.services["engine"]
            from ...db.models import PokemonSet, Species
            set_id = self._defender_map.get(self._last_def_label)
            if not set_id:
                self.def_item_var.set("—"); self.def_stat_var.set("HP/Def/SpD —"); return
            with Session(engine) as s:
                dset = s.get(PokemonSet, set_id)
                sp   = s.get(Species, dset.species_id)
                self.def_item_var.set(dset.item or "—")

                compute_stats = self.services["compute_stats"]
                evs = _json.loads(dset.evs_json) or {}; ivs = _json.loads(dset.ivs_json) or {}
                base = {"HP": sp.base_hp, "Atk": sp.base_atk, "Def": sp.base_def, "SpA": sp.base_spa, "SpD": sp.base_spd, "Spe": sp.base_spe}
                tmp = type("Tmp", (), {"evs": evs, "level": dset.level, "nature": dset.nature})
                stats = compute_stats(tmp, base_stats=base, ivs=ivs)
                self.def_stat_var.set(f"HP {stats['HP']}/Def {stats['Def']}/SpD {stats['SpD']}")
        except Exception:
            pass
        self.refresh()

    def on_sort(self, col):
        self.sort_dir = "desc" if (self.sort_by == col and self.sort_dir == "asc") else "asc"
        self.sort_by = col
        self.refresh()

    def _clear_table(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)

    def refresh(self):
        """Recalcula lista de atacantes y su mejor movimiento vs el defensor seleccionado."""
        self._clear_table()
        label = (self.d_defender.get() or "").strip()
        if not label or label not in self._defender_map:
            return
        params = {
            "def_label": label,
            "weather": self.d_weather.get(),
            "terrain": self.d_terrain.get(),
            "reflect": bool(self.d_reflect.get()),
            "lightscreen": bool(self.d_lightscreen.get()),
            "veil": bool(self.d_veil.get()),
            "fmt_doubles": (self.d_format.get() == "Dobles"),
        }
        # cálculo “sin bloquear” la UI
        self.after(20, lambda: self._compute_defense(params))

    # ---------------- Cálculo ----------------
    def _compute_defense(self, params: dict):
        Session = self.services["Session"]; engine = self.services["engine"]
        list_sets = self.services["list_sets"]; compute_stats = self.services["compute_stats"]

        type_eff_fn = self.services.get("type_effectiveness")         # opcional: helper compartido
        item_mult_fn = self.services.get("attacker_item_multiplier_auto")  # opcional

        # leer defensor
        from ...db.models import PokemonSet, Species
        def_id = self._defender_map[params["def_label"]]
        with Session(engine) as s:
            defender = s.get(PokemonSet, def_id)
            def_sp = s.get(Species, defender.species_id)

            # tipos del defensor (considera Tera OFF aquí; puedes agregar selector Tera si quieres)
            types_fn = self.services.get("get_species_types")
            if types_fn:
                try:
                    def_types = types_fn(def_sp.name, defender.gender)
                except Exception:
                    def_types = []
            else:
                def_types = []

            D_evs = _json.loads(defender.evs_json) or {}
            D_ivs = _json.loads(defender.ivs_json) or {}
            D_base = {"HP": def_sp.base_hp,"Atk": def_sp.base_atk,"Def": def_sp.base_def,"SpA": def_sp.base_spa,"SpD": def_sp.base_spd,"Spe": def_sp.base_spe}
            D_tmp = type("Tmp", (), {"evs": D_evs, "level": defender.level, "nature": defender.nature})
            d_stats = compute_stats(D_tmp, base_stats=D_base, ivs=D_ivs)
            hp_stat = d_stats["HP"]

            # Traer todos los atacantes
            atk_rows = list_sets(s, limit=None)

        items = []
        for aset, asp in atk_rows:
            # Datos del atacante
            att_item = (aset.item or "").strip()
            att_evs = _json.loads(aset.evs_json) or {}; att_ivs = _json.loads(aset.ivs_json) or {}
            att_base = {"HP": asp.base_hp,"Atk": asp.base_atk,"Def": asp.base_def,"SpA": asp.base_spa,"SpD": asp.base_spd,"Spe": asp.base_spe}
            A_tmp = type("Tmp", (), {"evs": att_evs, "level": aset.level, "nature": aset.nature})
            att_stats = compute_stats(A_tmp, base_stats=att_base, ivs=att_ivs)

            # Tipos del atacante (para STAB y terreno)
            try:
                get_types = self.services.get("get_species_types")
                att_types = get_types(asp.name, aset.gender) if get_types else []
            except Exception:
                att_types = []

            # Movimientos del atacante
            moves = self._iter_attacker_moves(aset)

            best = None  # guardará dict del mejor movimiento
            for mv in moves:
                m = self._move_info(mv)
                if not m or (m.get("power") or 0) <= 0:
                    continue
                power = int(m.get("power") or 0)
                mcat = (m.get("category") or "physical").lower()
                mtype = (m.get("type") or "Normal").capitalize()
                
                name_norm = (m.get("name","") or "").strip().lower()
                if name_norm in ("tera blast", "tera-blast"):
                    # categoría por stat mayor del atacante (como en Damage)
                    mcat = "physical" if att_stats["Atk"] >= att_stats["SpA"] else "special"
                    # tipo: en Defense no hay toggle de Tera atacante → deja el tipo “Normal” del cache
                    # (si más adelante agregas selector de Tera atacante, aquí puedes cambiar mtype)

                # --- stat de ataque/defensa según categoría (ya lo tienes) ---
                atk_stat = att_stats["Atk"] if mcat == "physical" else att_stats["SpA"]
                def_stat = d_stats["Def"] if mcat == "physical" else d_stats["SpD"]

                # --- EFECTIVIDAD por tipos (ANTES de usar eff_mult en bayas) ---
                eff_mult = 1.0
                if type_eff_fn:
                    try:
                        eff_mult = float(type_eff_fn(mtype, def_types))
                    except Exception:
                        eff_mult = 1.0

                # --- ÍTEM del defensor: Assault Vest (def_mult) + Bayas (eff_adj) ---
                def_item = (defender.item or "")
                def_mult, eff_adj = self.services["defender_item_effects_auto"](def_item, mcat, mtype, eff_mult)
                def_stat = int(def_stat * def_mult)           # AV u otros sobre el stat
                eff_total = eff_mult * eff_adj                # eficacia final (incluye baya)

                # --- Boost defensivo por CLIMA (aplícalo ANTES de base_damage) ---
                def_stat = int(def_stat * self.services["defender_stat_weather_boost"](
                    [t.capitalize() for t in def_types],
                    "special" if mcat != "physical" else "physical",
                    params["weather"]
                ))

                # --- base damage (sin roll), con def_stat ya definitivo ---
                L = aset.level
                base_damage = (((2 * L / 5) + 2) * power * atk_stat / max(1, def_stat)) / 50 + 2

                # --- MOD global (sin tipo): STAB + items atacante + spread + pantallas + clima ofensivo + terreno ---
                mod = 1.0

                # STAB
                if mtype in [t.capitalize() for t in att_types]:
                    mod *= 1.5

                # Ítems del atacante (usa eff_mult, NO eff_total; Expert Belt depende de ser SE, no de la baya)
                if item_mult_fn:
                    try:
                        mod *= float(item_mult_fn(att_item, mcat, eff_mult, mtype))
                    except Exception:
                        pass
                else:
                    if att_item in {"Life Orb","Life-Orb","LifeOrb"}: mod *= 1.3
                    if att_item in {"Choice Band"} and mcat=="physical": mod *= 1.5
                    if att_item in {"Choice Specs"} and mcat=="special": mod *= 1.5
                    if att_item in {"Expert Belt"} and eff_mult > 1.0: mod *= 1.2

                # Spread en Dobles
                if params["fmt_doubles"] and self._is_spread_move(m.get("name","")):
                    mod *= 0.75

                # Pantallas (service: maneja Singles/Doubles y Veil)
                mod *= self.services["screen_multiplier"](
                    category=("physical" if mcat == "physical" else "special"),
                    is_singles=not params["fmt_doubles"],
                    reflect=params["reflect"],
                    lightscreen=params["lightscreen"],
                    veil=params["veil"],
                )

                # Clima ofensivo (Fire/Water en Sol/Lluvia)
                mod *= self.services["weather_move_multiplier"](mtype, params["weather"])

                # Terreno
                mod *= self.services["terrain_xmod"](params["terrain"], mtype, m.get("name",""))

                # --- xMOD final = (no-tipo) * (tipo con bayas) ---
                xmod_val = mod * eff_total

                # Rango por roll e info de KO
                dmin = int(base_damage * 0.85 * xmod_val)
                dmax = int(base_damage * 1.00 * xmod_val)
                min_hits, max_hits, exp_hits, _mode = self.services["resolve_hits"](m.get("name",""), "Auto", att_item)
                tdmin = int(dmin * min_hits); tdmax = int(dmax * max_hits)
                min_pct = round(tdmin * 100.0 / hp_stat, 1)
                max_pct = round(tdmax * 100.0 / hp_stat, 1)

                kb, kw = self.services["ko_hits_bounds"](hp_stat, dmin, dmax, min_hits, max_hits)
                ko_label = "OHKO" if kb<=1 and kw<=1 else (f"{kb}HKO" if kb==kw else f"{kb}–{kw}HKO")

                per_hit = self.services["single_hit_roll_dist"](base_damage, xmod_val)
                weights = self.services["hits_weights_for_selector"]("Auto", min_hits, max_hits)
                ohko    = self.services["ohko_probability_from_dist"](per_hit, hp_stat, weights)
                ohko_pct = round(100.0 * ohko, 1)

                cand = {
                    "attacker": f"{asp.name} (Lv{aset.level}/{aset.nature or '—'})",
                    "item_att": att_item or "—",
                    "move": m.get("name", mv),
                    "cat": mcat.capitalize(),
                    "power": power,
                    "type": mtype,
                    "xef": f"×{eff_total:g}",
                    "xmod": f"×{xmod_val:.2f}",
                    "xmod_val": xmod_val,
                    "min": dmin, "max": dmax,
                    "min_pct": min_pct, "max_pct": max_pct,
                    "ko": ko_label,
                    "ohko_pct": ohko_pct,
                }
                # elegir el mejor por max_pct (o por tdmax)
                if (best is None) or (cand["max_pct"] > best["max_pct"]):
                    best = cand

            if best:
                items.append(best)

        # orden
        key = self.sort_by; reverse = (self.sort_dir == "desc")
        def sort_key(r):
            if key in ("xef","xmod"):
                try: return float(r.get(key, "×1").replace("×",""))
                except Exception: return 1.0
            return r.get(key, -999999)
        items.sort(key=sort_key, reverse=reverse)
        

        # pintar
        for r in items:
            insert_with_zebra(self.tree, values=(r["attacker"], r["item_att"], r["move"],
                            r["cat"], r["power"], r["type"], r["xef"], r["xmod"],
                            r["min"], r["max"], r["min_pct"], r["max_pct"], r["ko"], f"{r['ohko_pct']:.1f}%"))

        autosize_columns(self.tree)
        update_sort_arrows(self.tree, self.sort_by, "asc" if not reverse else "desc")
    # fin _compute_defense


    # ---------------- Helpers de datos ----------------
    def _iter_attacker_moves(self, aset):
        """Devuelve la lista de movimientos declarados en el set (máx 4)."""
        try:
            mv = _json.loads(aset.moves_json) or []
            return [m for m in mv if (m or "").strip()]
        except Exception:
            return []

    def _move_info(self, name: str):
        """
        Intenta resolver info del movimiento:
        - services.get('get_move_info')(name) si está
        - tabla Move en BD (si existe)
        - fallback: solo nombre
        Devuelve dict con: name, power, type, category
        """
        nm = (name or "").strip()
        if not nm:
            return None

        svc = self.services.get("get_move_info")
        if svc:
            try:
                data = svc(nm)
                if data: return data
            except Exception:
                pass

        # BD fallback
        try:
            Session = self.services["Session"]; engine = self.services["engine"]
            with Session(engine) as s:
                from ...db.models import Move
                mv = s.query(Move).filter(Move.name.ilike(nm)).first()
                if mv:
                    cat = (getattr(mv, "category", "") or "").capitalize()  # Physical/Special/Status
                    return {
                        "name": mv.name, "power": int(getattr(mv, "power", 0) or 0),
                        "type": (getattr(mv, "type", "Normal") or "Normal"),
                        "category": ("Physical" if cat.startswith("P") else "Special" if cat.startswith("S") else "Status")
                    }
        except Exception:
            pass

        # mínimo
        return {"name": nm, "power": 0, "type": "Normal", "category": "Status"}

    # Usa tu método real si lo tienes; aquí versiones seguras/no-op
    def _get_species_types(self, species_name: str, gender: str|None):
        """Debe devolver lista de tipos capitalizados. Usa tu util real si la tienes."""
        # TIP: si en damage_tab tienes un helper, impórtalo y llámalo aquí.
        return []
    
    def _is_spread_move(self, move_name: str) -> bool:
        spread = {
            "rock slide","earthquake","bulldoze","heat wave","dazzling gleam","blizzard",
            "muddy water","discharge","snarl","hyper voice","surf","icy wind",
            "eruption","lava plume","sludge wave","parabolic charge","petal blizzard"
        }
        return (move_name or "").strip().lower() in spread


# Fin DefenseTab
