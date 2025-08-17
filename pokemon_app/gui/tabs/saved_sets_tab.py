import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json as _json
from datetime import datetime

# Naturalezas por si quieres un combo (opcional)
NATURES = sorted(list({
    'Adamant','Lonely','Brave','Naughty',
    'Impish','Bold','Relaxed','Lax',
    'Modest','Mild','Quiet','Rash',
    'Calm','Gentle','Sassy','Careful',
    'Jolly','Hasty','Naive','Timid',
    'Serious','Bashful','Docile','Hardy','Quirky'
}))

class SavedSetsTab:
    """
    Pestaña 'Sets Guardados'.
    services esperados:
      - Session, engine
      - list_sets(session, only_species=None, nature=None, item=None, limit=None, offset=None, order_by=None, order_dir=None)
        (si tu list_sets no soporta algunos args, hay try/except para fallback)
      - compute_stats (opcional, para futuras columnas)
    """
    def __init__(self, master, services: dict):
        self.master = master
        self.services = services

        # estado
        self.sort_by = "species"
        self.sort_dir = "asc"
        self.page_size = 50
        self.page = 0

        self._build_ui()

    def get_frame(self):
        return self.master

    # ---------- UI ----------
    def _build_ui(self):
        # Filtros
        top = ttk.LabelFrame(self.master, text="Filtros")
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="Especie:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.f_species = tk.StringVar()
        ttk.Entry(top, textvariable=self.f_species, width=20).grid(row=0, column=1, sticky="w", padx=2, pady=4)

        ttk.Label(top, text="Naturaleza:").grid(row=0, column=2, sticky="w", padx=8, pady=4)
        self.f_nature = tk.StringVar()
        ttk.Combobox(top, textvariable=self.f_nature, width=14, values=[""] + NATURES, state="readonly")\
            .grid(row=0, column=3, sticky="w", padx=2, pady=4)

        ttk.Label(top, text="Item:").grid(row=0, column=4, sticky="w", padx=8, pady=4)
        self.f_item = tk.StringVar()
        self.cmb_item = ttk.Combobox(top, textvariable=self.f_item, width=22, state="readonly", values=[""])
        self.cmb_item.grid(row=0, column=5, sticky="w", padx=2, pady=4)
        self.cmb_item.bind("<<ComboboxSelected>>", lambda e: self.on_search())

        ttk.Label(top, text="Orden:").grid(row=0, column=6, sticky="e", padx=8)
        self.f_order = tk.StringVar(value="species")
        ttk.Combobox(top, textvariable=self.f_order, width=14, state="readonly",
                     values=["species","nature","item","updated_at","created_at"])\
            .grid(row=0, column=7, sticky="w", padx=2)

        ttk.Label(top, text="Dir:").grid(row=0, column=8, sticky="e", padx=8)
        self.f_order_dir = tk.StringVar(value="asc")
        ttk.Combobox(top, textvariable=self.f_order_dir, width=8, state="readonly",
                     values=["asc","desc"]).grid(row=0, column=9, sticky="w", padx=2)

        ttk.Label(top, text="Tamaño pág:").grid(row=0, column=10, sticky="e", padx=8)
        self.f_pagesize = tk.StringVar(value=str(self.page_size))
        ttk.Combobox(top, textvariable=self.f_pagesize, width=6, state="readonly",
                     values=["10","25","50","100"]).grid(row=0, column=11, sticky="w")

        ttk.Button(top, text="Buscar", command=self.on_search).grid(row=0, column=12, padx=8)
        ttk.Button(top, text="Limpiar", command=self.on_clear).grid(row=0, column=13, padx=2)
        
        ttk.Label(top, text="Ability:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.f_ability = tk.StringVar()
        self.cmb_ability = ttk.Combobox(top, textvariable=self.f_ability, width=22, state="readonly", values=[""])
        self.cmb_ability.grid(row=1, column=1, sticky="w", padx=2, pady=4)
        self.cmb_ability.bind("<<ComboboxSelected>>", lambda e: self.on_search())

        ttk.Label(top, text="Tera:").grid(row=1, column=2, sticky="w", padx=8, pady=4)
        self.f_tera = tk.StringVar()
        self.cmb_tera = ttk.Combobox(top, textvariable=self.f_tera, width=16, state="readonly", values=[""])
        self.cmb_tera.grid(row=1, column=3, sticky="w", padx=2, pady=4)
        self.cmb_tera.bind("<<ComboboxSelected>>", lambda e: self.on_search())


        # Tabla
        cols = ("id","species","nature","item","ability","tera","level","evs","ivs","moves","updated")
        self.tree = ttk.Treeview(self.master, columns=cols, show="headings", height=18, selectmode="browse")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0,8))

        def _col(name, w, anchor="w"):
            self.tree.column(name, width=w, anchor=anchor)
        _col("id",      25, "e")
        _col("species", 150)
        _col("nature",  80)
        _col("item",    120)
        _col("ability", 120)
        _col("tera",    65)
        _col("level",   40, "e")
        _col("evs",     160)
        _col("ivs",     160)
        _col("moves",   260)
        _col("updated", 140)

        for c, label in [
            ("id","ID"),("species","Especie"),("nature","Naturaleza"),
            ("item","Item"),("ability","Habilidad"),("tera","Tera"),
            ("level","Lvl"),("evs","EVs"),("ivs","IVs"),("moves","Movs"),("updated","Actualizado")
        ]:
            self.tree.heading(c, text=label, command=lambda col=c: self.on_sort(col))

        # Barra inferior: paginación + acciones
        bottom = ttk.Frame(self.master); bottom.pack(fill="x", padx=8, pady=(0,8))

        self.lbl_page = ttk.Label(bottom, text="Página 1")
        self.lbl_page.pack(side="left")

        ttk.Button(bottom, text="⟨ Anterior", command=self.on_prev).pack(side="left", padx=6)
        ttk.Button(bottom, text="Siguiente ⟩", command=self.on_next).pack(side="left", padx=6)

        ttk.Separator(bottom, orient="vertical").pack(side="left", fill="y", padx=12)

        ttk.Button(bottom, text="Copiar Showdown", command=self.on_copy).pack(side="right", padx=6)
        ttk.Button(bottom, text="Exportar Showdown", command=self.on_export).pack(side="right", padx=6)
        ttk.Button(bottom, text="Editar", command=self.on_edit).pack(side="right", padx=6)
        ttk.Button(bottom, text="Eliminar", command=self.on_delete).pack(side="right", padx=6)
        ttk.Button(bottom, text="Refrescar", command=self.refresh).pack(side="right", padx=6)


        # Binds rápidos
        for w in top.winfo_children():
            if isinstance(w, (ttk.Entry, ttk.Combobox)):
                w.bind("<Return>", lambda e: self.on_search())

        # Primera carga
        self.refresh()
        self._reload_filter_options()


    # ---------- Acciones ----------
    def on_search(self):
        try:
            self.page_size = int(self.f_pagesize.get())
        except Exception:
            self.page_size = 25
        self.page = 0
        self.sort_by = self.f_order.get() or "species"
        self.sort_dir = self.f_order_dir.get() or "asc"
        self.refresh()
        self._reload_filter_options()


    def on_clear(self):
        self.f_species.set("")
        self.f_nature.set("")
        self.f_item.set("")
        self.f_order.set("species")
        self.f_order_dir.set("asc")
        self.f_pagesize.set("25")
        self.f_ability.set("")
        self.f_tera.set("")
        self.page = 0
        self.refresh()
        self._reload_filter_options()


    def on_prev(self):
        if self.page > 0:
            self.page -= 1
            self.refresh()
            self._reload_filter_options()


    def on_next(self):
        if "count_sets" not in self.services:
            self.page += 1
            self.refresh()
            self._reload_filter_options()
            return

        # con contador
        Session = self.services["Session"]; engine = self.services["engine"]
        count_sets = self.services["count_sets"]

        species_like = (self.f_species.get().strip() or "")
        if species_like and "%" not in species_like:
            species_like = f"%{species_like}%"
        nature = (self.f_nature.get().strip() or None)
        item   = (self.f_item.get().strip() or None)
        ability= (self.f_ability.get().strip() or None)
        tera   = (self.f_tera.get().strip() or None)

        with Session(engine) as s:
            try:
                total = count_sets(s, only_species=species_like or None, nature=nature, item=item, ability=ability, tera=tera)
            except TypeError:
                total = None

        if total is None:
            self.page += 1
        else:
            max_page = max(0, (total-1)//self.page_size)
            if self.page < max_page:
                self.page += 1

        self.refresh()
        self._reload_filter_options()



    def on_sort(self, col: str):
        if self.sort_by == col:
            self.sort_dir = "asc" if self.sort_dir == "desc" else "desc"
        else:
            self.sort_by = col
            self.sort_dir = "asc" if col in ("species","nature","item","ability","tera","moves") else "desc"
        self.refresh()
        self._reload_filter_options()


    def refresh(self):
        # limpiar
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        Session = self.services["Session"]
        engine  = self.services["engine"]
        list_sets = self.services["list_sets"]

        species_like = (self.f_species.get().strip() or "")
        if species_like and "%" not in species_like:
            species_like = f"%{species_like}%"
        nature = (self.f_nature.get().strip() or None)
        item   = (self.f_item.get().strip() or None)
        
        ability = (self.f_ability.get().strip() or None)
        tera    = (self.f_tera.get().strip() or None)
        limit = self.page_size
        offset = self.page * self.page_size

        # Traer filas
        with Session(engine) as s:
            rows = []
            try:
                rows = list_sets(
                    s,
                    only_species=species_like or None,
                    nature=nature,
                    item=item,
                    ability=ability,
                    tera=tera,
                    limit=limit,
                    offset=offset,
                    order_by=self.sort_by,
                    order_dir=self.sort_dir
                )
            except TypeError:
                rows = list_sets(s, only_species=species_like or None, nature=nature, item=item)


        # Si no hay filas y estamos en una página > 0, retrocede una
        if self.page > 0 and not rows:
            self.page -= 1
            self.refresh()
            return

        # Pintar
        for pset, sp in rows:
            try:
                evs = _json.loads(pset.evs_json) or {}
                ivs = _json.loads(pset.ivs_json) or {}
                moves = _json.loads(pset.moves_json) or []
            except Exception:
                evs, ivs, moves = {}, {}, []

            evs_str = " / ".join([f"{k}:{evs.get(k,0)}" for k in ["HP","Atk","Def","SpA","SpD","Spe"]])
            ivs_str = " / ".join([f"{k}:{ivs.get(k,31)}" for k in ["HP","Atk","Def","SpA","SpD","Spe"]])
            moves_str = ", ".join(moves)

            updated_txt = ""
            if getattr(pset, "updated_at", None):
                try:
                    # por si ya es datetime
                    if isinstance(pset.updated_at, datetime):
                        updated_txt = pset.updated_at.strftime("%Y-%m-%d %H:%M")
                    else:
                        updated_txt = str(pset.updated_at)[:16]
                except Exception:
                    updated_txt = str(pset.updated_at)

            self.tree.insert(
                "", "end",
                iid=str(pset.id),
                values=(
                    pset.id,
                    sp.name,
                    pset.nature or "—",
                    pset.item or "—",
                    pset.ability or "—",
                    pset.tera_type or "—",
                    pset.level,
                    evs_str,
                    ivs_str,
                    moves_str,
                    updated_txt
                )
            )

        total_txt = ""
        if "count_sets" in self.services:
            with Session(engine) as s:
                try:
                    total = self.services["count_sets"](s,
                        only_species=species_like or None,
                        nature=nature, item=item,
                        ability=ability, tera=tera)
                    total_txt = f" / {total} sets"
                except Exception:
                    total_txt = ""
        self.lbl_page.config(text=f"Página {self.page + 1}{total_txt}")


    def _selected_set_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def on_delete(self):
        set_id = self._selected_set_id()
        if not set_id:
            messagebox.showinfo("Eliminar", "Selecciona un set.")
            return
        if not messagebox.askyesno("Eliminar", f"¿Eliminar set ID {set_id}?"):
            return

        Session = self.services["Session"]
        engine  = self.services["engine"]
        # Si tienes un repo delete_set, úsalo; si no, borro directo con ORM
        with Session(engine) as s:
            try:
                from ...db.models import PokemonSet
                obj = s.get(PokemonSet, set_id)
                if obj:
                    s.delete(obj); s.commit()
            except Exception as e:
                s.rollback()
                messagebox.showerror("Eliminar", f"No se pudo eliminar:\n{e}")
                return
        self.refresh()
        self._reload_filter_options()


    def on_export(self):
        set_id = self._selected_set_id()
        if not set_id:
            messagebox.showinfo("Exportar", "Selecciona un set.")
            return

        Session = self.services["Session"]
        engine  = self.services["engine"]
        with Session(engine) as s:
            try:
                from ...db.models import PokemonSet, Species
                p = s.get(PokemonSet, set_id)
                sp = s.get(Species, p.species_id) if p else None
            except Exception as e:
                messagebox.showerror("Exportar", f"No se pudo cargar el set:\n{e}")
                return

        if not p or not sp:
            messagebox.showerror("Exportar", "No se encontró el set.")
            return

        # reconstruir Showdown text sencillo
        try:
            evs = _json.loads(p.evs_json) or {}
            ivs = _json.loads(p.ivs_json) or {}
            moves = _json.loads(p.moves_json) or []
        except Exception:
            evs, ivs, moves = {}, {}, []

        lines = []
        header = sp.name
        if p.item:
            header += f" @ {p.item}"
        lines.append(header)
        if p.ability:
            lines.append(f"Ability: {p.ability}")
        if p.level and p.level != 100:
            lines.append(f"Level: {p.level}")
        if p.tera_type:
            lines.append(f"Tera Type: {p.tera_type}")
        # EVs
        ev_order = ["HP","Atk","Def","SpA","SpD","Spe"]
        ev_parts = [f"{evs.get(k,0)} {k}" for k in ev_order if evs.get(k,0)]
        if ev_parts:
            lines.append("EVs: " + " / ".join(ev_parts))
        # IVs (sólo las que no son 31 para no ensuciar)
        iv_parts = [f"{ivs.get(k,31)} {k}" for k in ev_order if ivs.get(k,31) != 31]
        if iv_parts:
            lines.append("IVs: " + " / ".join(iv_parts))
        if p.nature:
            lines.append(f"{p.nature} Nature")
        for mv in moves:
            lines.append(f"- {mv}")

        text = "\n".join(lines)

        # guardar a archivo
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All Files", "*.*")],
            initialfile=f"{sp.name}_set.txt"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            messagebox.showerror("Exportar", f"No se pudo guardar el archivo:\n{e}")
            return
        messagebox.showinfo("Exportar", f"Guardado en:\n{path}")
        
    def on_edit(self):
        set_id = self._selected_set_id()
        if not set_id:
            messagebox.showinfo("Editar", "Selecciona un set.")
            return

        Session = self.services["Session"]; engine = self.services["engine"]
        with Session(engine) as s:
            try:
                from ...db.models import PokemonSet, Species
                p = s.get(PokemonSet, set_id)
                sp = s.get(Species, p.species_id) if p else None
            except Exception as e:
                messagebox.showerror("Editar", f"No se pudo cargar el set:\n{e}")
                return

        if not p or not sp:
            messagebox.showerror("Editar", "No se encontró el set.")
            return

        EditSetDialog(self.master, self.services, p.id, on_saved=lambda: (self.refresh(), self._reload_filter_options()))


    def on_copy(self):
        """Copiar el set seleccionado al portapapeles en formato Showdown."""
        set_id = self._selected_set_id()
        if not set_id:
            messagebox.showinfo("Copiar", "Selecciona un set.")
            return

        Session = self.services["Session"]; engine = self.services["engine"]
        with Session(engine) as s:
            try:
                from ...db.models import PokemonSet, Species
                p = s.get(PokemonSet, set_id)
                sp = s.get(Species, p.species_id) if p else None
            except Exception as e:
                messagebox.showerror("Copiar", f"No se pudo cargar el set:\n{e}")
                return

        if not p or not sp:
            messagebox.showerror("Copiar", "No se encontró el set.")
            return

        try:
            import json as _json
            evs = _json.loads(p.evs_json) or {}
            ivs = _json.loads(p.ivs_json) or {}
            moves = _json.loads(p.moves_json) or []
        except Exception:
            evs, ivs, moves = {}, {}, []

        lines = []
        header = sp.name + (f" @ {p.item}" if p.item else "")
        lines.append(header)
        if p.ability: lines.append(f"Ability: {p.ability}")
        if p.level and p.level != 100: lines.append(f"Level: {p.level}")
        if p.tera_type: lines.append(f"Tera Type: {p.tera_type}")
        ev_order = ["HP","Atk","Def","SpA","SpD","Spe"]
        ev_parts = [f"{evs.get(k,0)} {k}" for k in ev_order if evs.get(k,0)]
        if ev_parts: lines.append("EVs: " + " / ".join(ev_parts))
        iv_parts = [f"{ivs.get(k,31)} {k}" for k in ev_order if ivs.get(k,31) != 31]
        if iv_parts: lines.append("IVs: " + " / ".join(iv_parts))
        if p.nature: lines.append(f"{p.nature} Nature")
        for mv in moves: lines.append(f"- {mv}")

        text = "\n".join(lines)
        try:
            self.master.clipboard_clear()
            self.master.clipboard_append(text)
            self.master.update()  # asegura que el portapapeles se actualice
        except Exception:
            pass
        messagebox.showinfo("Copiar", "Set copiado al portapapeles.")
        
    def _reload_filter_options(self):
        """Rellena los combos de Ability y Tera con los valores distintos presentes en la DB."""
        Session = self.services["Session"]; engine = self.services["engine"]
        abilities, teras, items = set(), set(), set()
        try:
            from ...db.models import PokemonSet
        except Exception:
            # si falla el import, deja combos en blanco
            for combo in ("cmb_ability","cmb_tera","cmb_item"):
                if hasattr(self, combo):
                    getattr(self, combo)["values"] = [""]
            return

        # Leer valores distintos con SQLAlchemy
        try:
            from sqlalchemy import select, distinct
            with Session(engine) as s:
                # ability
                q1 = select(distinct(PokemonSet.ability)).where(PokemonSet.ability.isnot(None))
                for (val,) in s.execute(q1):
                    v = (val or "").strip()
                    if v:
                        abilities.add(v)
                # tera_type
                q2 = select(distinct(PokemonSet.tera_type)).where(PokemonSet.tera_type.isnot(None))
                for (val,) in s.execute(q2):
                    v = (val or "").strip()
                    if v:
                        teras.add(v)
                
                q3 = select(distinct(PokemonSet.item)).where(PokemonSet.item.isnot(None))
                for (val,) in s.execute(q3):
                    v = (val or "").strip()
                    if v:
                        items.add(v)
        except Exception:
            # Fallback muy simple si tu versión no tiene select/distinct cómodos
            with Session(engine) as s:
                rows = s.query(PokemonSet).all()
                for p in rows:
                    v1 = (getattr(p, "ability", None) or "").strip()
                    if v1: abilities.add(v1)
                    v2 = (getattr(p, "tera_type", None) or "").strip()
                    if v2: teras.add(v2)
                    v3 = (getattr(p, "item", None) or "").strip()
                    if v3: items.add(v3)

        # Mantener selecciones si siguen existiendo
        sel_ability = self.f_ability.get()
        sel_tera    = self.f_tera.get()
        sel_item    = self.f_item.get()

        ability_list = [""] + sorted(abilities, key=str.casefold)
        tera_list    = [""] + sorted(teras, key=str.casefold)
        item_list    = [""] + sorted(items, key=str.casefold)

        if hasattr(self, "cmb_ability"):
            self.cmb_ability["values"] = ability_list
        if hasattr(self, "cmb_tera"):
            self.cmb_tera["values"] = tera_list
        if hasattr(self, "cmb_item"):
            self.cmb_item["values"] = item_list

        self.f_ability.set(sel_ability if sel_ability in ability_list else "")
        self.f_tera.set(sel_tera if sel_tera in tera_list else "")
        self.f_item.set(sel_item if sel_item in item_list else "")


class EditSetDialog(tk.Toplevel):
    """Diálogo para editar un PokemonSet completo (nivel, naturaleza, item, ability, tera, EV/IV, moves)."""
    def __init__(self, master, services: dict, set_id: int, on_saved=None):
        super().__init__(master)
        self.services = services
        self.set_id = set_id
        self.on_saved = on_saved
        self.title(f"Editar Set #{set_id}")
        self.resizable(False, False)

        self._build_ui()
        self._load()

        self.transient(master)
        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _build_ui(self):
        frm = ttk.Frame(self); frm.pack(fill="both", expand=True, padx=10, pady=10)

        r = 0
        ttk.Label(frm, text="Especie:").grid(row=r, column=0, sticky="e", padx=4, pady=4)
        self.var_species = tk.StringVar(value=""); ttk.Label(frm, textvariable=self.var_species).grid(row=r, column=1, sticky="w")
        ttk.Label(frm, text="Nivel:").grid(row=r, column=2, sticky="e", padx=4, pady=4)
        self.var_level = tk.StringVar(value="100"); ttk.Entry(frm, textvariable=self.var_level, width=6).grid(row=r, column=3, sticky="w"); r+=1

        ttk.Label(frm, text="Naturaleza:").grid(row=r, column=0, sticky="e")
        self.var_nature = tk.StringVar(value="")
        ttk.Combobox(frm, textvariable=self.var_nature, width=16, values=[""] + list(NATURES), state="readonly").grid(row=r, column=1, sticky="w")

        ttk.Label(frm, text="Item:").grid(row=r, column=2, sticky="e")
        self.var_item = tk.StringVar(value=""); ttk.Entry(frm, textvariable=self.var_item, width=18).grid(row=r, column=3, sticky="w"); r+=1

        ttk.Label(frm, text="Ability:").grid(row=r, column=0, sticky="e")
        self.var_ability = tk.StringVar(value=""); ttk.Entry(frm, textvariable=self.var_ability, width=18).grid(row=r, column=1, sticky="w")

        ttk.Label(frm, text="Tera Type:").grid(row=r, column=2, sticky="e")
        self.var_tera = tk.StringVar(value="")
        # Tipos Tera: intenta importar desde services; si no, usa fallback local
        try:
            from ...services.types import ALL_TYPES as _ALL_TYPES
        except Exception:
            _ALL_TYPES = [
                "Normal","Fire","Water","Electric","Grass","Ice",
                "Fighting","Poison","Ground","Flying","Psychic","Bug",
                "Rock","Ghost","Dragon","Dark","Steel","Fairy"
                # Si usas Tera Stellar, agrega: "Stellar"
            ]

        ttk.Combobox(
            frm, textvariable=self.var_tera, width=16,
            values=[""] + list(_ALL_TYPES), state="readonly"
        ).grid(row=r, column=3, sticky="w"); r += 1

        # EVs / IVs
        ev_order = ["HP","Atk","Def","SpA","SpD","Spe"]
        ttk.Label(frm, text="EVs (0-252):").grid(row=r, column=0, sticky="e"); r+=1
        self.vars_evs = {}
        for i,stat in enumerate(ev_order):
            ttk.Label(frm, text=stat).grid(row=r, column=0 + (i%3)*2, sticky="e")
            v = tk.StringVar(value="0"); self.vars_evs[stat] = v
            ttk.Entry(frm, textvariable=v, width=6).grid(row=r, column=1 + (i%3)*2, sticky="w")
            if i%3==2: r+=1
        if i%3!=2: r+=1

        ttk.Label(frm, text="IVs (0-31):").grid(row=r, column=0, sticky="e"); r+=1
        self.vars_ivs = {}
        for i,stat in enumerate(ev_order):
            ttk.Label(frm, text=stat).grid(row=r, column=0 + (i%3)*2, sticky="e")
            v = tk.StringVar(value="31"); self.vars_ivs[stat] = v
            ttk.Entry(frm, textvariable=v, width=6).grid(row=r, column=1 + (i%3)*2, sticky="w")
            if i%3==2: r+=1
        if i%3!=2: r+=1

        ttk.Label(frm, text="Moves (uno por línea, máx 4):").grid(row=r, column=0, sticky="nw", padx=4, pady=(8,4))
        self.txt_moves = tk.Text(frm, width=36, height=6)
        self.txt_moves.grid(row=r, column=1, columnspan=3, sticky="w", pady=(8,4)); r+=1

        btns = ttk.Frame(frm); btns.grid(row=r, column=0, columnspan=4, sticky="e", pady=(8,0))
        ttk.Button(btns, text="Guardar", command=self._save).pack(side="right", padx=6)
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="right", padx=6)

    def _load(self):
        Session = self.services["Session"]; engine = self.services["engine"]
        with Session(engine) as s:
            from ...db.models import PokemonSet, Species
            p = s.get(PokemonSet, self.set_id)
            sp = s.get(Species, p.species_id) if p else None

        if not p or not sp:
            messagebox.showerror("Editar", "No se encontró el set.")
            self.destroy(); return

        import json as _json
        self.var_species.set(sp.name)
        self.var_level.set(str(p.level or 100))
        self.var_nature.set(p.nature or "")
        self.var_item.set(p.item or "")
        self.var_ability.set(p.ability or "")
        self.var_tera.set(p.tera_type or "")

        evs = {}
        ivs = {}
        moves = []
        try:
            evs = _json.loads(p.evs_json) or {}
            ivs = _json.loads(p.ivs_json) or {}
            moves = _json.loads(p.moves_json) or []
        except Exception:
            pass

        for k,v in self.vars_evs.items():
            v.set(str(evs.get(k, 0)))
        for k,v in self.vars_ivs.items():
            v.set(str(ivs.get(k, 31)))
        self.txt_moves.delete("1.0","end")
        self.txt_moves.insert("1.0", "\n".join(moves[:4]))

    def _save(self):
        # recolectar y validar
        def _safe_int(s, default=0):
            try: return int(str(s).strip())
            except Exception: return default

        level = _safe_int(self.var_level.get(), 100)
        nature = (self.var_nature.get() or "").strip() or None
        item = (self.var_item.get() or "").strip() or None
        ability = (self.var_ability.get() or "").strip() or None
        tera = (self.var_tera.get() or "").strip() or None

        evs = {k: max(0, min(252, _safe_int(v.get(), 0))) for k,v in self.vars_evs.items()}
        ivs = {k: max(0, min(31,  _safe_int(v.get(), 31))) for k,v in self.vars_ivs.items()}
        moves = [ln.strip() for ln in self.txt_moves.get("1.0","end").splitlines() if ln.strip()][:4]

        # validaciones suaves
        ev_total = sum(evs.values())
        if ev_total > 510:
            if not messagebox.askyesno("Validación EVs", f"EVs suman {ev_total} (>510). ¿Guardar de todas formas?"):
                return

        Session = self.services["Session"]; engine = self.services["engine"]
        from datetime import datetime
        with Session(engine) as s:
            try:
                from ...db.models import PokemonSet
                p = s.get(PokemonSet, self.set_id)
                if not p:
                    raise RuntimeError("Set no encontrado.")

                import json as _json
                p.level = level
                p.nature = nature
                p.item = item
                p.ability = ability
                p.tera_type = tera
                p.evs_json = _json.dumps(evs, ensure_ascii=False)
                p.ivs_json = _json.dumps(ivs, ensure_ascii=False)
                p.moves_json = _json.dumps(moves, ensure_ascii=False)
                if hasattr(p, "updated_at"):
                    p.updated_at = datetime.now()

                s.add(p); s.commit()
            except Exception as e:
                s.rollback()
                messagebox.showerror("Guardar", f"No se pudo guardar:\n{e}")
                return

        if callable(self.on_saved):
            try: self.on_saved()
            except Exception: pass
        # además refresca combos:
        try:
            # master aquí es la SavedSetsTab; usamos su método si existe
            parent = self.master  # Toplevel.master es el frame; SavedSetsTab es el dueño de ese frame
        except Exception:
            parent = None
        # Lo fácil: pide a la pestaña que recargue opciones antes/después del refresh que ya llamas
        self.destroy()
