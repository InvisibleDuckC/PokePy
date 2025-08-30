from __future__ import annotations
import json
import tkinter as tk
import os
from tkinter import ttk, messagebox
from types import SimpleNamespace
from pokemon_app.utils.species_normalize import normalize_species_name
from pokemon_app.gui.ui.treeview_kit import set_style, apply_zebra, insert_with_zebra, autosize_columns, update_sort_arrows


class InputTab(ttk.Frame):
    """
    Tab para ingresar/parsear sets estilo Showdown y guardarlos en la DB.
    Requiere 'services' con:
      - parse_showdown_text
      - compute_stats
      - ensure_species_in_json
      - save_pokemon_set
      - Session, engine
    """

    def __init__(self, master, services: dict, on_saved=None):
        super().__init__(master)
        self.services = services
        self.on_saved = on_saved
        self.current_parsed = None   # dict con datos parseados
        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        # Layout: izquierda (textarea), derecha (datos parseados + stats), abajo (botones)
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # Izquierda: textarea
        lf_left = ttk.LabelFrame(self, text="Pega aquí el set estilo Showdown")
        lf_left.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        lf_left.rowconfigure(0, weight=1)
        lf_left.columnconfigure(0, weight=1)
        self.txt_input = tk.Text(lf_left, wrap="word", height=20)
        self.txt_input.grid(row=0, column=0, sticky="nsew")

        # Derecha: datos parseados y stats
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(0,8), pady=8)
        right.columnconfigure(0, weight=1)

        grp = ttk.LabelFrame(right, text="Datos Parseados")
        grp.grid(row=0, column=0, sticky="ew")
        labels = ["Name","Gender","Item","Ability","Level","Tera","Nature","EVs","IVs","Moves"]
        self.vars = {k: tk.StringVar(value="") for k in labels}
        r = 0
        for k in labels:
            ttk.Label(grp, text=k).grid(row=r, column=0, sticky="e", padx=4, pady=2)
            ttk.Entry(grp, textvariable=self.vars[k], width=48, state="readonly").grid(row=r, column=1, sticky="ew", padx=4, pady=2)
            r += 1

        grp2 = ttk.LabelFrame(right, text="Stats Calculadas")
        grp2.grid(row=1, column=0, sticky="ew", pady=(8,0))
        self.stat_vars = {k: tk.StringVar(value="-") for k in ["HP","Atk","Def","SpA","SpD","Spe"]}
        rr = 0
        for k in ["HP","Atk","Def","SpA","SpD","Spe"]:
            ttk.Label(grp2, text=k).grid(row=rr, column=0, sticky="e", padx=4, pady=2)
            ttk.Label(grp2, textvariable=self.stat_vars[k], width=10, relief="sunken", anchor="w").grid(row=rr, column=1, sticky="w", padx=4, pady=2)
            rr += 1
            
        # --- Otros ingresos de esta especie ---
        # Haz que la fila 2 del panel derecho pueda expandir (por scroll)
        right.rowconfigure(2, weight=1)

        rel = ttk.LabelFrame(self, text="Otros sets de esta especie")
        rel.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(0, 8))

        # contenedor con scrollbar
        rel_container = ttk.Frame(rel)
        rel_container.pack(fill="both", expand=True)

        cols = ("id", "level", "nature", "item", "ability", "evs", "moves")
        self.related_tree = ttk.Treeview(rel_container, columns=cols, show="headings", height=6)

        # Scrollbar vertical
        rel_scroll = ttk.Scrollbar(rel_container, orient="vertical", command=self.related_tree.yview)
        self.related_tree.configure(yscrollcommand=rel_scroll.set)
        rel_scroll.pack(side="right", fill="y")
        self.related_tree.pack(side="left", fill="both", expand=True)

        # Config columnas y headers
        self.related_tree.column("id",      width=60,  anchor="e")
        self.related_tree.column("level",   width=60,  anchor="e")
        self.related_tree.column("nature",  width=90,  anchor="w")
        self.related_tree.column("item",    width=140, anchor="w")
        self.related_tree.column("ability", width=140, anchor="w")
        self.related_tree.column("evs",   width=240, anchor="w")
        self.related_tree.column("moves",   width=240, anchor="w")

        self.related_tree.heading("id",      text="ID")
        self.related_tree.heading("level",   text="Lv")
        self.related_tree.heading("nature",  text="Naturaleza")
        self.related_tree.heading("item",    text="Ítem")
        self.related_tree.heading("ability", text="Habilidad")
        self.related_tree.heading("evs",     text="EVs") 
        self.related_tree.heading("moves",   text="Movimientos")

        set_style(self.related_tree)
        apply_zebra(self.related_tree)

        # Botones
        bot = ttk.Frame(self)
        bot.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0,8))
        ttk.Button(bot, text="Parsear", command=self.on_parse).pack(side="left", padx=4)
        ttk.Button(bot, text="Calcular Stats", command=self.on_calc).pack(side="left", padx=4)
        ttk.Button(bot, text="Guardar en DB", command=self.on_save).pack(side="left", padx=4)
        ttk.Button(bot, text="Limpiar", command=self.on_clear).pack(side="left", padx=4)

    # ---------- Acciones ----------
    def on_parse(self):
        text = self.txt_input.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Info", "Pega un set en el cuadro de texto.")
            return
        try:
            parsed_raw = self.services["parse_showdown_text"](text)
            p = self._as_parsed_dict(parsed_raw)  # ← normalizamos a dict
        except Exception as e:
            messagebox.showerror("Error al parsear", str(e))
            return

        # IVs: si no vinieron en el set, asumir 31
        ivs = p.get("ivs") or {"HP":31,"Atk":31,"Def":31,"SpA":31,"SpD":31,"Spe":31}
        p["ivs"] = ivs

        self.current_parsed = p
        self._update_parsed_view(p)
        
        # Mostrar otros sets de esta especie
        try:
            self._reload_related_sets(p.get("name"))
        except Exception:
            pass

        # limpiar stats calculadas
        for k in self.stat_vars:
            self.stat_vars[k].set("-")

    def on_calc(self):
        if not self.current_parsed:
            messagebox.showinfo("Info", "Primero parsea un set.")
            return

        p = self.current_parsed
        name = normalize_species_name(p.get("name"), p.get("ability"))
        if not name:
            messagebox.showwarning("Validación", "Falta el nombre de la especie.")
            return

        # nivel seguro
        try:
            level = int(p.get("level") or 50)
        except Exception:
            messagebox.showerror("Dato inválido", "El nivel no es un número válido.")
            return

        nature = p.get("nature")
        evs = p.get("evs") or {}
        ivs = p.get("ivs") or {"HP":31,"Atk":31,"Def":31,"SpA":31,"SpD":31,"Spe":31}
        gender = p.get("gender")  # puede ser None

        # 1) Asegurar base stats en cache JSON (si falla, avisamos pero seguimos)
        try:
            import os
            data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
            base_stats_path = os.path.join(data_dir, "base_stats.json")
            self.services["ensure_species_in_json"](name, gender, base_stats_path)
        except Exception as e:
            messagebox.showwarning("Base stats", f"No pude asegurar species en JSON:\n{e}")

        # 2) Construir base stats y calcular — TODO ADENTRO DEL TRY
        try:
            base_stats = self._get_base_stats(name)
            tmp = SimpleNamespace(evs=evs, level=level, nature=nature)
            stats = self.services["compute_stats"](tmp, base_stats=base_stats, ivs=ivs)
        except KeyError as e:
            # típico: especie sin base stats en el registro
            messagebox.showerror("Base stats faltantes", str(e))
            return
        except Exception as e:
            messagebox.showerror("Cálculo de stats", str(e))
            return

        # 3) Pintar resultados
        for k in ["HP","Atk","Def","SpA","SpD","Spe"]:
            self.stat_vars[k].set(str(stats[k]))


    def on_save(self):
        if not self.current_parsed:
            messagebox.showinfo("Info", "Primero parsea un set.")
            return

        p = self.current_parsed
        if not p.get("name"):
            messagebox.showwarning("Validación", "Falta el nombre de la especie.")
            return

        try:
            name = normalize_species_name(p.get("name"), p.get("ability"))
            level  = int(p.get("level") or 50)
            nature = p.get("nature")
            item   = p.get("item")
            ability= p.get("ability")
            gender = p.get("gender")
            tera   = p.get("tera")
            evs    = p.get("evs") or {}
            ivs    = p.get("ivs") or {"HP":31,"Atk":31,"Def":31,"SpA":31,"SpD":31,"Spe":31}
            moves  = p.get("moves") or []
            
            try:
                data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
                base_stats_path = os.path.join(data_dir, "base_stats.json")
                self.services["ensure_species_in_json"](name, gender, base_stats_path)
            except Exception:
                pass

            # base stats registry: el repo espera un dict {nombre_especie: base_stats}
            base_stats = self._get_base_stats(name)
            base_stats_registry = {name: base_stats}

            raw_text = self.txt_input.get("1.0", "end").strip() or None

            # Llamada POSICIONAL a la firma del repo:
            new_id = self.services["save_pokemon_set"](
                name, gender, item, ability, level, tera, nature,
                evs, ivs, moves, base_stats_registry, raw_text
            )


        except Exception as e:
            messagebox.showerror("DB", f"No pude guardar el set:\n{e}")
            return

        messagebox.showinfo("Guardado", f"Set guardado (id {new_id}).")
        if callable(self.on_saved):
            try:
                self.on_saved(new_id)
            except Exception:
                pass
            
        try:
            self._reload_related_sets(name)
        except Exception:
            pass



    def on_clear(self):
        self.txt_input.delete("1.0", "end")
        self.current_parsed = None
        for k in self.vars:
            self.vars[k].set("")
        for k in self.stat_vars:
            self.stat_vars[k].set("-")
        # limpiar tabla de "Otros sets"
        if hasattr(self, "related_tree"):
            self._clear_related_sets()


    # ---------- Helpers ----------
    def _update_parsed_view(self, p: dict):
        self.vars["Name"].set(p.get("name",""))
        self.vars["Gender"].set(p.get("gender","") or "")
        self.vars["Item"].set(p.get("item","") or "")
        self.vars["Ability"].set(p.get("ability","") or "")
        self.vars["Level"].set(str(p.get("level") or 50))
        self.vars["Tera"].set(p.get("tera","") or "")
        self.vars["Nature"].set(p.get("nature","") or "")
        # Formateo EVs / IVs / Moves
        evs = p.get("evs") or {}
        ivs = p.get("ivs") or {}
        ev_txt = " / ".join([f"{k}{evs.get(k,0)}" for k in ["HP","Atk","Def","SpA","SpD","Spe"] if evs.get(k,0)])
        iv_txt = " / ".join([f"{k}{ivs.get(k,31)}" for k in ["HP","Atk","Def","SpA","SpD","Spe"]])
        mv_txt = ", ".join(p.get("moves") or [])
        self.vars["EVs"].set(ev_txt)
        self.vars["IVs"].set(iv_txt)
        self.vars["Moves"].set(mv_txt)

    def _get_base_stats(self, species_name: str) -> dict:
        def _valid(bs: dict) -> bool:
            try:
                return all(isinstance(bs[k], int) and bs[k] > 0 for k in ["HP","Atk","Def","SpA","SpD","Spe"])
            except Exception:
                return False

        # 1) DB
        try:
            from ...db.models import Species
            Session = self.services["Session"]; engine = self.services["engine"]
            with Session(engine) as s:
                sp = s.query(Species).filter(Species.name == species_name).one_or_none()
                if sp:
                    db_bs = {
                        "HP": sp.base_hp, "Atk": sp.base_atk, "Def": sp.base_def,
                        "SpA": sp.base_spa, "SpD": sp.base_spd, "Spe": sp.base_spe
                    }
                    if _valid(db_bs):
                        return db_bs
        except Exception:
            pass

        # 2) JSON fallback (acepta mayúsculas o minúsculas)
        import os, json
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
        path = os.path.join(data_dir, "base_stats.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # buscar por clave exacta y, si no está, por normalización
            bs = data.get(species_name)
            if not bs:
                key_norm = species_name.strip().lower().replace(" ", "-")
                for k, v in data.items():
                    if k.strip().lower().replace(" ", "-") == key_norm:
                        bs = v
                        break

            if bs:
                # soporta JSON con "HP"/"Atk"/... o "hp"/"atk"/...
                def pick(d, up, low):
                    return d.get(up) if up in d else d.get(low)

                json_bs = {
                    "HP":  int(pick(bs, "HP",  "hp")  or 0),
                    "Atk": int(pick(bs, "Atk", "atk") or 0),
                    "Def": int(pick(bs, "Def", "def") or 0),
                    "SpA": int(pick(bs, "SpA", "spa") or 0),
                    "SpD": int(pick(bs, "SpD", "spd") or 0),
                    "Spe": int(pick(bs, "Spe", "spe") or 0),
                }
                if _valid(json_bs):
                    return json_bs
        except Exception:
            pass

        # 3) Último recurso
        return {"HP":1,"Atk":1,"Def":1,"SpA":1,"SpD":1,"Spe":1}
    
    def _as_parsed_dict(self, parsed_obj) -> dict:
        """
        Acepta un dict ya listo o un objeto estilo PokemonData y devuelve
        un dict con las claves esperadas por la pestaña.
        """
        if isinstance(parsed_obj, dict):
            return parsed_obj

        # Intentar mapear atributos comunes de PokemonData
        # Ajusta los nombres si tu clase usa otros (p.ej. item_name en vez de item)
        name    = getattr(parsed_obj, "name", None)
        gender  = getattr(parsed_obj, "gender", None)
        item    = getattr(parsed_obj, "item", None)
        ability = getattr(parsed_obj, "ability", None)
        level   = getattr(parsed_obj, "level", None)
        tera    = getattr(parsed_obj, "tera", None) or getattr(parsed_obj, "tera_type", None)
        nature  = getattr(parsed_obj, "nature", None)
        evs     = getattr(parsed_obj, "evs", None) or {}
        ivs     = getattr(parsed_obj, "ivs", None) or {}
        moves   = getattr(parsed_obj, "moves", None) or []

        # Si moves viene como objetos, extrae nombre
        try:
            if moves and not isinstance(moves[0], str):
                moves = [getattr(m, "name", str(m)) for m in moves]
        except Exception:
            pass

        return {
            "name": name,
            "gender": gender,
            "item": item,
            "ability": ability,
            "level": level,
            "tera": tera,
            "nature": nature,
            "evs": evs,
            "ivs": ivs,
            "moves": moves,
        }

    def _clear_related_sets(self):
        if hasattr(self, "related_tree"):
            for iid in self.related_tree.get_children():
                self.related_tree.delete(iid)

    def _reload_related_sets(self, species_name: str):
        """Carga otros sets guardados de la misma especie."""
        if not species_name or not hasattr(self, "related_tree"):
            return

        self._clear_related_sets()

        # Servicios / repositorio
        Session = self.services["Session"]
        engine  = self.services["engine"]
        list_sets = self.services.get("list_sets")
        if list_sets is None:
            # fallback directo al repo si no viene inyectado
            from ...db.repository import list_sets as _list_sets
            list_sets = _list_sets

        # patrón de búsqueda por nombre (ILIKE '%name%')
        species_like = species_name.strip()
        if species_like and "%" not in species_like:
            species_like = f"%{species_like}%"

        # Consultar (ordenar por actualizado/creado desc si está disponible)
        rows = []
        try:
            with Session(engine) as s:
                rows = list_sets(
                    s,
                    only_species=species_like,
                    order_by="updated_at",
                    order_dir="desc",
                    limit=50,
                )
        except TypeError:
            # Firma antigua de list_sets sin order/limit
            with Session(engine) as s:
                rows = list_sets(s, only_species=species_like)

        import json as _json

        def _fmt_evs(evs: dict) -> str:
            # Muestra solo los EVs > 0 en estilo Showdown: "252 HP / 4 Def / 252 Spe"
            order = ["HP","Atk","Def","SpA","SpD","Spe"]
            parts = []
            for k in order:
                try:
                    v = int(evs.get(k, 0))
                except Exception:
                    v = 0
                if v > 0:
                    parts.append(f"{v} {k}")
            return " / ".join(parts) if parts else "—"

        for pset, sp in rows:
            try:
                moves = ", ".join((_json.loads(pset.moves_json) or [])[:4])
            except Exception:
                moves = "—"

            try:
                evs_dict = _json.loads(pset.evs_json) or {}
            except Exception:
                evs_dict = {}
            evs_str = _fmt_evs(evs_dict)

            insert_with_zebra(self.related_tree, values=(
                    pset.id,
                    pset.level,
                    pset.nature or "—",
                    pset.item or "—",
                    pset.ability or "—",
                    evs_str,                 # << NUEVO campo EVs
                    moves or "—",
                ),)

