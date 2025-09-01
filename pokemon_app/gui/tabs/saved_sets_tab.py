import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont
import json as _json
from datetime import datetime
# --- para sprite desde PokeAPI ---
import io, base64
try:
    from PIL import Image, ImageTk   # recomendado
except Exception:
    Image = ImageTk = None
    
from pokemon_app.gui.ui.treeview_kit import set_style, apply_zebra, insert_with_zebra, autosize_columns, update_sort_arrows, attach_right_click_menu



# Naturalezas por si quieres un combo (opcional)
NATURES = sorted(list({
    'Adamant','Lonely','Brave','Naughty',
    'Impish','Bold','Relaxed','Lax',
    'Modest','Mild','Quiet','Rash',
    'Calm','Gentle','Sassy','Careful',
    'Jolly','Hasty','Naive','Timid',
    'Serious','Bashful','Docile','Hardy','Quirky'
}))

# Clase principal de la pestaña
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
        
        self._species_search_job = None


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
        # Búsqueda en vivo con debounce
        self.f_species.trace_add("write", lambda *_: self._on_species_changed())
        # Prueba por evento de teclado
        #self.f_species.bind("<KeyRelease>", lambda e: self._on_species_changed())

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
        self.tree = ttk.Treeview(self.master, columns=cols, show="headings", height=18, selectmode="browse", style="Poke.Treeview")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0,8))
        # Doble clic para editar
        self.tree.bind("<Double-1>", self._on_tree_double_click, add="+")
        set_style(self.tree)
        apply_zebra(self.tree)


        def _col(name, w, anchor="w"):
            self.tree.column(name, width=w, anchor=anchor)
        _col("id",      23, "e")
        _col("species", 150)
        _col("nature",  78)
        _col("item",    115)
        _col("ability", 120)
        _col("tera",    63)
        _col("level",   36, "e")
        _col("evs",     280)
        _col("ivs",     270)
        _col("moves",   285)

        for c, label in [
            ("id","ID"),("species","Especie"),("nature","Naturaleza"),
            ("item","Item"),("ability","Habilidad"),("tera","Tera"),
            ("level","Lvl"),("evs","EVs"),("ivs","IVs"),("moves","Movs"),
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

            #self.tree.insert("", "end",iid=str(pset.id),values=(pset.id,sp.name,pset.nature or "—",pset.item or "—",pset.ability or "—",pset.tera_type or "—",pset.level,evs_str,ivs_str,moves_str,updated_txt))
            insert_with_zebra(self.tree, values=(
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
                ))

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
        autosize_columns(self.tree)


    def _selected_set_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        item = sel[0]
        try:
            vals = self.tree.item(item, "values")
            # la primera columna es "id"
            return int(vals[0])
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

    def _on_tree_double_click(self, event=None):
        """Abre la pantalla de edición al hacer doble clic en una fila."""
        try:
            row = self.tree.identify_row(event.y) if event else None
        except Exception:
            row = None
        if not row:
            return  # doble clic en espacio vacío/encabezado: no hacer nada

        # Asegurar selección/foco en la fila clickeada
        try:
            self.tree.selection_set(row)
            self.tree.focus(row)
        except Exception:
            pass

        # Reusar la acción existente
        self.on_edit()
        
    def _on_species_changed(self):
        # cancelar job anterior (si existe)
        if getattr(self, "_species_search_job", None):
            try:
                self.master.after_cancel(self._species_search_job)
            except Exception:
                pass
            self._species_search_job = None

        # programar una búsqueda tras 250 ms usando el mismo widget (self.master)
        self._species_search_job = self.master.after(250, self._do_species_live_search)


    def _do_species_live_search(self):
        self._species_search_job = None
        # reiniciar a primera página y refrescar
        self.page = 0
        self.refresh()
        self._reload_filter_options()
        
    def apply_treeview_style(root):
        style = ttk.Style(root)

        # Elige un theme base disponible: 'vista' (Windows), 'clam' (cross), 'aqua' (macOS)
        try:
            style.theme_use("vista")
        except Exception:
            pass

        # Fuentes
        font_row = tkfont.nametofont("TkDefaultFont").copy()
        font_row.configure(size=10)
        font_head = tkfont.nametofont("TkHeadingFont").copy()
        font_head.configure(size=10, weight="bold")

        # Estilo filas
        style.configure(
            "Poke.Treeview",
            font=font_row,
            rowheight=24,              # altura de fila
            background="#ffffff",
            fieldbackground="#ffffff", # fondo del área
            foreground="#222222",
            bordercolor="#dddddd",
            lightcolor="#eeeeee",
            darkcolor="#dddddd"
        )

        # Selección más visible
        style.map(
            "Poke.Treeview",
            background=[("selected", "#e6f2ff")],
            foreground=[("selected", "#0b3d91")]
        )

        # Encabezados
        style.configure(
            "Poke.Treeview.Heading",
            font=font_head,
            background="#f5f5f5",
            foreground="#333333",
            bordercolor="#dddddd"
        )
        style.map(
            "Poke.Treeview.Heading",
            background=[("active", "#ececec")]
        )

        # (Opcional) quitar el borde punteado de focus en celdas
        style.layout("Poke.Treeview", style.layout("Treeview"))



#Clase para editar un set
class EditSetDialog(tk.Toplevel):
    """Diálogo para editar un PokemonSet completo (nivel, naturaleza, item, ability, tera, EV/IV, moves)."""
    def __init__(self, master, services: dict, set_id: int, on_saved=None):
        super().__init__(master)
        self.services = services
        self.set_id = set_id
        self.on_saved = on_saved
        self.title(f"Editar Set #{set_id}")
        self.resizable(False, False)
        
        self._pokeapi_moves_cache = {}
        self._pokeapi_abilities_cache = {}  # {slug: [labels]}
        self._sprite_mem_cache = {}         # {slug: bytes}

        self._build_ui()
        self._load()

        self.transient(master)
        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _build_ui(self):
        # === CONTENEDOR RAÍZ ===
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True, padx=8, pady=8)

        # Grid 2x2
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=0)
        root.rowconfigure(1, weight=1)

        # ---------------------------------------------------------

        # (0,0) SPRITE
        fr_sprite = ttk.LabelFrame(root, text="Sprite")
        fr_sprite.grid(row=0, column=0, sticky="nw", padx=(0,8), pady=(0,8))
        self.sprite_label = ttk.Label(fr_sprite, text="(sin sprite)", anchor="center", width=16)
        self.sprite_label.pack(padx=6, pady=6)
        self._sprite_img = None  # evitar GC

        # ---------------------------------------------------------

        # (0,1) DATOS (Especie, Nivel, Naturaleza, Ítem, Habilidad, Tera)
        fr_data = ttk.LabelFrame(root, text="Datos")
        fr_data.grid(row=0, column=1, sticky="new", padx=(8,0), pady=(0,8))
        for c in range(2):
            fr_data.columnconfigure(c, weight=1)

        # Usa tus propias StringVar si ya existen:
        self.var_species   = getattr(self, "var_species",   tk.StringVar())
        self.var_level     = getattr(self, "var_level",     tk.StringVar())
        self.var_nature    = getattr(self, "var_nature",    tk.StringVar())
        self.var_item      = getattr(self, "var_item",      tk.StringVar())
        self.var_ability   = getattr(self, "var_ability",   tk.StringVar())
        self.var_tera_type = getattr(self, "var_tera_type", tk.StringVar())
        
        ttk.Label(fr_data, text="Especie:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.var_species = tk.StringVar(value="")
        ttk.Label(fr_data, textvariable=self.var_species).grid(row=0, column=1, sticky="w")
        
        ttk.Label(fr_data, text="Nivel:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self.var_level = tk.StringVar(value="100")
        ttk.Entry(fr_data, textvariable=self.var_level, width=6).grid(row=1, column=1, sticky="w")

        ttk.Label(fr_data, text="Naturaleza:").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        self.var_nature = tk.StringVar(value="")
        ttk.Combobox(fr_data, textvariable=self.var_nature, width=16, values=[""] + list(NATURES), state="readonly").grid(row=2, column=1, sticky="w")

        ttk.Label(fr_data, text="Item:").grid(row=3, column=0, sticky="w", padx=4, pady=2)
        self.var_item = tk.StringVar(value="")
        ttk.Entry(fr_data, textvariable=self.var_item, width=18).grid(row=3, column=1, sticky="w")

        ttk.Label(fr_data, text="Habilidad:").grid(row=4, column=0, sticky="w", padx=4, pady=2)
        self.cmb_ability = ttk.Combobox(fr_data, textvariable=self.var_ability, state="readonly", values=["—"])
        self.cmb_ability.grid(row=4, column=1, sticky="w")

        ttk.Label(fr_data, text="Tera Type:").grid(row=5, column=0, sticky="w", padx=4, pady=2)
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
            fr_data, textvariable=self.var_tera, width=16,
            values=[""] + list(_ALL_TYPES), state="readonly"
        ).grid(row=5, column=1, sticky="w")

        # ---------------------------------------------------------
        
        # (1,0) ESTADÍSTICAS (EVs / IVs)
        fr_stats = ttk.LabelFrame(root, text="Estadísticas")
        fr_stats.grid(row=1, column=0, sticky="nsew", padx=(0,8), pady=(8,0))
        fr_stats.columnconfigure(0, weight=1)
        fr_stats.columnconfigure(1, weight=1)
        # Subcontenedores
        fr_evs = ttk.LabelFrame(fr_stats, text="EVs"); fr_evs.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        fr_ivs = ttk.LabelFrame(fr_stats, text="IVs"); fr_ivs.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)

        stats = ["HP","Atk","Def","SpA","SpD","Spe"]

        # Reutiliza tus StringVar si existen:
        self.evs_vars = getattr(self, "evs_vars", {k: tk.StringVar(value="0") for k in stats})
        self.ivs_vars = getattr(self, "ivs_vars", {k: tk.StringVar(value="31") for k in stats})

        for i, k in enumerate(stats):
            ttk.Label(fr_evs, text=k).grid(row=i, column=0, sticky="e", padx=4, pady=2)
            ttk.Entry(fr_evs, textvariable=self.evs_vars[k], width=6).grid(row=i, column=1, sticky="w", padx=4, pady=2)

            ttk.Label(fr_ivs, text=k).grid(row=i, column=0, sticky="e", padx=4, pady=2)
            ttk.Entry(fr_ivs, textvariable=self.ivs_vars[k], width=6).grid(row=i, column=1, sticky="w", padx=4, pady=2)

        
        # ---------------------------------------------------------

        # (1,1) MOVIMIENTOS (4 combobox, sin duplicados)
        fr_moves = ttk.LabelFrame(root, text="Movimientos (máx 4)")
        fr_moves.grid(row=1, column=1, sticky="nsew", padx=(8,0), pady=(8,0))
        fr_moves.columnconfigure(0, weight=1)

        self._move_vars = [tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()]
        self._move_combos = []
        for i, var in enumerate(self._move_vars):
            cb = ttk.Combobox(fr_moves, textvariable=var, state="readonly", values=[], width=28)
            cb.grid(row=i, column=0, sticky="ew", padx=4, pady=4)
            cb.bind("<<ComboboxSelected>>", self._on_move_changed)
            self._move_combos.append(cb)

        btns = ttk.Frame(root); btns.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8,0))
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

        for k,v in self.evs_vars.items():
            v.set(str(evs.get(k, 0)))
        for k,v in self.ivs_vars.items():
            v.set(str(ivs.get(k, 31)))
        # Construye el pool de movimientos disponibles para esta especie
        self._moves_pool = self._build_moves_pool(sp.id) or []

        # Garantiza que sea lista (por si algún helper devolviera set/tupla)
        if not isinstance(self._moves_pool, list):
            self._moves_pool = list(self._moves_pool)

        # Asegura que movimientos ya guardados estén presentes en el pool
        for mv in (moves or []):
            if mv and mv not in self._moves_pool:
                self._moves_pool.append(mv)

        # Preseleccionar los 4 (o menos) movimientos existentes
        for i in range(4):
            self._move_vars[i].set(moves[i] if i < len(moves) else "")

        # Aplicar la lógica de filtrado (evitar duplicados entre combos)
        self._refresh_move_values()
                
        # Cargar sprite por especie
        try: self._load_sprite(self.var_species.get())
        except Exception: pass
        
        # --- Habilidades disponibles para la especie ---
        try:
            abilities = self._build_ability_pool(sp.id) or []
        except Exception:
            abilities = []
        # asegura opción neutra
        if "—" not in abilities:
            abilities = ["—"] + abilities

        # preselección con la habilidad ya guardada (si existe)
        current_ability = (p.ability or "").strip()
        if current_ability and current_ability not in abilities:
            abilities = [current_ability] + abilities

        self.cmb_ability["values"] = abilities
        self.var_ability.set(current_ability or "—")

    # Fin de _load 

    # Guardar cambios
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

        evs = {k: int(self.evs_vars[k].get() or 0) for k in ["HP","Atk","Def","SpA","SpD","Spe"]}
        ivs = {k: int(self.ivs_vars[k].get() or 0) for k in ["HP","Atk","Def","SpA","SpD","Spe"]}
        moves = [v.get().strip() for v in self._move_vars if (v.get() or "").strip()][:4]
        # guardar como antes en JSON


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
    # Fin de _save
        
    # Lógica de movimientos: evitar duplicados entre los 4 combos    
    def _on_move_changed(self, event=None):
        """
        Mantiene movimientos únicos: si el usuario elige un movimiento ya elegido
        en otro combo, lo limpia de ese otro combo. Luego recalcula los 'values'.
        """
        try:
            widget = event.widget if event else None
            chosen = (widget.get() or "").strip() if widget else ""
        except Exception:
            widget, chosen = None, ""

        if chosen:
            # Unicidad: si otro combo ya tenía el mismo movimiento, lo vaciamos
            for cb, var in zip(self._move_combos, self._move_vars):
                if cb is not widget and (var.get() or "").strip().lower() == chosen.lower():
                    var.set("")

        self._refresh_move_values()
    # Fin de _on_move_changed

    # Refrescar las listas de opciones en los combos de movimientos
    def _refresh_move_values(self):
        """
        Recalcula la lista de opciones para cada combo, excluyendo lo ya elegido
        en los otros combos. Conserva el valor actual si está seteado.
        """
        if not hasattr(self, "_moves_pool"):
            self._moves_pool = []

        selected = [ (v.get() or "").strip() for v in self._move_vars ]
        selected_lower = [ s.lower() for s in selected if s ]

        for i, (cb, var) in enumerate(zip(self._move_combos, self._move_vars)):
            current = (var.get() or "").strip()
            current_lower = current.lower()

            # No permitir duplicados: excluye los elegidos por otros combos
            used_others = set(selected_lower)
            if current:
                # deja pasar el propio valor actual
                used_others.discard(current_lower)

            allowed = [m for m in self._moves_pool if m.lower() not in used_others]

            # Si el actual no está en la lista (p. ej., porque no está en pool), inclúyelo al inicio
            if current and current not in allowed:
                allowed = [current] + allowed

            cb["values"] = allowed
    # Fin de _refresh_move_values

    # Construir pool de movimientos posibles para la especie
    def _build_moves_pool(self, species_id: int):
        """
        Devuelve una lista ordenada de movimientos aprendibles para la especie.
        1) Intenta PokeAPI: /pokemon/{slug} o /pokemon-species/{slug} -> default variety
        2) Si falla, fallback: unión de movimientos observados en BD para esa especie.
        Los nombres se formatean como 'Ice Beam' (title con espacios).
        """
        import json as _json
        import unicodedata

        # --- helpers internos ---
        def _ascii_slug(s: str) -> str:
            # normaliza para endpoints pokeapi ('mr-mime', 'lycanroc-dusk', etc.)
            s = (s or "").strip().lower()
            s = s.replace("♀", "-f").replace("♂", "-m")
            s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
            for ch in ["'", ".", ":", "(", ")", ",", "!", "?"]:
                s = s.replace(ch, "")
            s = s.replace(" ", "-").replace("_", "-")
            # algunos alias comunes
            ALIAS = {
                "nidoran-f": "nidoran-f",
                "nidoran-m": "nidoran-m",
                "mr-mime": "mr-mime",
                "farfetchd": "farfetchd",
                "mime-jr": "mime-jr",
                "type-null": "type-null",
                "jangmo-o": "jangmo-o",
                "hakamo-o": "hakamo-o",
                "kommo-o": "kommo-o",
            }
            return ALIAS.get(s, s)

        def _pretty_move(name_slug: str) -> str:
            # 'ice-beam' -> 'Ice Beam' ; 'v-create' -> 'V Create'
            return name_slug.replace("-", " ").title()

        # --- obtener nombre de especie desde BD ---
        try:
            Session = self.services["Session"]; engine = self.services["engine"]
            from ...db.models import Species
            with Session(engine) as s:
                sp = s.get(Species, species_id)
            species_name = getattr(sp, "name", "") or ""
        except Exception:
            species_name = ""

        slug = _ascii_slug(species_name)
        if not slug:
            return self._build_moves_pool_fallback(species_id)

        # --- caché en memoria ---
        if slug in self._pokeapi_moves_cache:
            return list(self._pokeapi_moves_cache[slug])

        # --- intento PokeAPI ---
        moves = None
        try:
            try:
                import requests  # usar requests si está disponible
            except Exception:
                requests = None

            def _get(url: str):
                if requests:
                    r = requests.get(url, timeout=5)
                    r.raise_for_status()
                    return r.json()
                else:
                    # fallback mínimo con urllib
                    import urllib.request, json
                    with urllib.request.urlopen(url, timeout=5) as resp:
                        return json.loads(resp.read().decode("utf-8"))

            base = "https://pokeapi.co/api/v2"

            # 1) /pokemon/{slug}
            data = None
            try:
                data = _get(f"{base}/pokemon/{slug}")
            except Exception:
                data = None

            # 2) Si no existe, /pokemon-species/{slug} -> default variety
            if not data:
                spec = _get(f"{base}/pokemon-species/{slug}")
                varieties = spec.get("varieties", []) if isinstance(spec, dict) else []
                p_name = None
                # prioriza 'is_default'
                for v in varieties:
                    if v.get("is_default") and v.get("pokemon", {}).get("name"):
                        p_name = v["pokemon"]["name"]; break
                if not p_name and varieties:
                    p_name = varieties[0].get("pokemon", {}).get("name")
                if p_name:
                    data = _get(f"{base}/pokemon/{p_name}")

            # 3) Parsear movimientos (sin filtrar por version_group de momento)
            if data and isinstance(data, dict) and "moves" in data:
                pool = set()
                for m in data["moves"]:
                    name_slug = m.get("move", {}).get("name")
                    if name_slug:
                        pool.add(_pretty_move(name_slug))
                moves = sorted(pool, key=str.casefold)

        except Exception:
            moves = None  # fuerza fallback

        # --- guardar en caché o usar fallback ---
        if moves:
            self._pokeapi_moves_cache[slug] = list(moves)
            return moves

        # fallback a unión de movimientos vistos en BD
        return self._build_moves_pool_fallback(species_id)

    # Fin de _build_moves_pool

    # Fallback offline: unión de movimientos en sets guardados
    def _build_moves_pool_fallback(self, species_id: int):
        """Unión de movimientos observados en otros sets de la especie (fallback offline)."""
        import json as _json
        try:
            Session = self.services["Session"]; engine = self.services["engine"]
            from ...db.models import PokemonSet
            moves_set = set()
            with Session(engine) as s:
                q = s.query(PokemonSet).filter(PokemonSet.species_id == species_id)
                for row in q.all():
                    try:
                        mv_list = _json.loads(row.moves_json) or []
                    except Exception:
                        mv_list = []
                    for mv in mv_list:
                        mv = (mv or "").strip()
                        if mv:
                            moves_set.add(mv)
            return sorted(moves_set, key=str.casefold)
        except Exception:
            return []
    # Fin de _build_moves_pool_fallback

    # Cargar sprite desde PokeAPI
    def _species_slug(self, name: str) -> str:
        """Normaliza el nombre a slug PokeAPI ('lycanroc-dusk', 'mr-mime', etc.)."""
        import unicodedata
        s = (name or "").strip().lower()
        s = s.replace("♀", "-f").replace("♂", "-m")
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        for ch in ["'", ".", ":", "(", ")", ",", "!", "?"]:
            s = s.replace(ch, "")
        s = s.replace(" ", "-").replace("_", "-")
        # aliases mínimos comunes
        aliases = {
            "mime-jr": "mime-jr", "mr-mime": "mr-mime",
            "jangmo-o":"jangmo-o","hakamo-o":"hakamo-o","kommo-o":"kommo-o",
            "type-null":"type-null", "nidoran-f":"nidoran-f", "nidoran-m":"nidoran-m",
            "farfetchd":"farfetchd"
        }
        return aliases.get(s, s)
    # Fin de _species_slug

    # HTTP helpers
    def _http_get_json(self, url: str):
        try:
            import requests
            r = requests.get(url, timeout=6)
            r.raise_for_status()
            return r.json()
        except Exception:
            # fallback urllib
            import urllib.request, json
            with urllib.request.urlopen(url, timeout=6) as resp:
                return json.loads(resp.read().decode("utf-8"))
    # Fin de _http_get_json

    # HTTP helper para bytes (imágenes)
    def _http_get_bytes(self, url: str) -> bytes:
        try:
            import requests
            r = requests.get(url, timeout=6)
            r.raise_for_status()
            return r.content
        except Exception:
            import urllib.request
            with urllib.request.urlopen(url, timeout=6) as resp:
                return resp.read()
    # Fin de _http_get_bytes
    
    # Cache de sprites en disco (opcional)
    def _get_sprite_cache_dir(self):
        import os
        base = os.path.expanduser("~/.pokepy_cache/sprites")
        os.makedirs(base, exist_ok=True)
        return base
    # Fin de _get_sprite_cache_dir
    
    # Path para sprite cacheado
    def _sprite_cache_path(self, slug: str) -> str:
        import os
        return os.path.join(self._get_sprite_cache_dir(), f"{slug}.png")
    # Fin de _sprite_cache_path

    # Cargar y mostrar sprite
    def _load_sprite(self, species_name: str):
        """Muestra sprite con cache en memoria + disco (PokeAPI)."""
        import io, base64, os
        slug = self._species_slug(species_name)
        if not slug or not hasattr(self, "sprite_label"):
            return

        # 1) cache en memoria
        raw = self._sprite_mem_cache.get(slug)
        if raw is None:
            # 2) cache en disco
            fpath = self._sprite_cache_path(slug)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "rb") as fh:
                        raw = fh.read()
                except Exception:
                    raw = None

            # 3) descargar si no hay cache
            if raw is None:
                data = None
                # 3.1 /pokemon/{slug}
                try:
                    data = self._http_get_json(f"https://pokeapi.co/api/v2/pokemon/{slug}")
                except Exception:
                    data = None

                # 3.2 fallback: /pokemon-species/{slug} -> variedad por defecto -> /pokemon/{name}
                if not data:
                    try:
                        spec = self._http_get_json(f"https://pokeapi.co/api/v2/pokemon-species/{slug}")
                        varieties = spec.get("varieties", []) if isinstance(spec, dict) else []
                        p_name = None
                        for v in varieties:
                            if v.get("is_default") and v.get("pokemon", {}).get("name"):
                                p_name = v["pokemon"]["name"]; break
                        if not p_name and varieties:
                            p_name = varieties[0].get("pokemon", {}).get("name")
                        if p_name:
                            data = self._http_get_json(f"https://pokeapi.co/api/v2/pokemon/{p_name}")
                    except Exception:
                        data = None

                # 3.3 elegir URL de sprite
                url = None
                try:
                    if data and isinstance(data, dict):
                        spr = data.get("sprites", {}) or {}
                        other = spr.get("other", {}) or {}
                        url = (
                            (other.get("official-artwork") or {}).get("front_default")
                            or (other.get("home") or {}).get("front_default")
                            or (other.get("showdown") or {}).get("front_default")
                            or spr.get("front_default")
                        )
                except Exception:
                    url = None

                # 3.4 descargar imagen y guardar en disco
                if url:
                    try:
                        raw = self._http_get_bytes(url)
                        try:
                            with open(fpath, "wb") as fh:
                                fh.write(raw)
                        except Exception:
                            pass
                    except Exception:
                        raw = None

            # guarda en cache de memoria
            if raw is not None:
                self._sprite_mem_cache[slug] = raw

        # Mostrar en UI
        if raw:
            try:
                if Image and ImageTk:
                    im = Image.open(io.BytesIO(raw))
                    im.thumbnail((128, 128))
                    self._sprite_img = ImageTk.PhotoImage(im)
                    self.sprite_label.configure(image=self._sprite_img, text="")
                else:
                    import tkinter as tk
                    b64 = base64.b64encode(raw).decode("ascii")
                    self._sprite_img = tk.PhotoImage(data=b64)
                    self.sprite_label.configure(image=self._sprite_img, text="")
            except Exception:
                self.sprite_label.configure(text=species_name or "(sin sprite)", image="")
                self._sprite_img = None
        else:
            self.sprite_label.configure(text=species_name or "(sin sprite)", image="")
            self._sprite_img = None
    # Fin de _load_sprite


    # Construir pool de habilidades posibles para la especie
    def _build_ability_pool(self, species_id: int):
        """
        Lista de habilidades aprendibles por especie.
        1) PokeAPI /pokemon/{slug} (o variety por defecto)
        2) Fallback: unión de habilidades vistas en BD para esa especie.
        Devuelve nombres bonitos: 'Speed Boost', 'Intimidate', y marca ocultas '(Oculta)'.
        """
        import unicodedata
        from ...db.models import Species, PokemonSet

        # --- obtener nombre de especie ---
        Session = self.services["Session"]; engine = self.services["engine"]
        with Session(engine) as s:
            sp = s.get(Species, species_id)
        species_name = getattr(sp, "name", "") or ""
        slug = self._species_slug(species_name)
        if not slug:
            return self._build_ability_pool_fallback(species_id)

        # cache en memoria
        if slug in self._pokeapi_abilities_cache:
            return list(self._pokeapi_abilities_cache[slug])

        def _pretty(name_slug: str) -> str:
            # 'speed-boost' -> 'Speed Boost'
            return (name_slug or "").replace("-", " ").title()

        # --- intentar PokeAPI ---
        abilities = []
        try:
            data = None
            try:
                data = self._http_get_json(f"https://pokeapi.co/api/v2/pokemon/{slug}")
            except Exception:
                # species -> variety por defecto -> pokemon
                spec = self._http_get_json(f"https://pokeapi.co/api/v2/pokemon-species/{slug}")
                varieties = spec.get("varieties", []) if isinstance(spec, dict) else []
                p_name = None
                for v in varieties:
                    if v.get("is_default") and v.get("pokemon", {}).get("name"):
                        p_name = v["pokemon"]["name"]; break
                if not p_name and varieties:
                    p_name = varieties[0].get("pokemon", {}).get("name")
                if p_name:
                    data = self._http_get_json(f"https://pokeapi.co/api/v2/pokemon/{p_name}")

            if data and isinstance(data, dict) and "abilities" in data:
                pool = []
                seen = set()
                for a in data["abilities"]:
                    nm = a.get("ability", {}).get("name")
                    if not nm: 
                        continue
                    label = _pretty(nm)
                    if a.get("is_hidden"):
                        label += " (Oculta)"
                    key = label.lower()
                    if key not in seen:
                        seen.add(key)
                        pool.append(label)
                abilities = sorted(pool, key=str.casefold)
        except Exception:
            abilities = []

        if abilities:
            self._pokeapi_abilities_cache[slug] = list(abilities)
            return abilities

        # --- fallback BD ---
        return self._build_ability_pool_fallback(species_id)
    # Fin de _build_ability_pool

    # Fallback offline: habilidades ya usadas en sets guardados
    def _build_ability_pool_fallback(self, species_id: int):
        """Fallback: habilidades ya usadas en otros sets de esta especie (BD)."""
        import json as _json
        from ...db.models import PokemonSet
        Session = self.services["Session"]; engine = self.services["engine"]
        seen = set()
        with Session(engine) as s:
            q = s.query(PokemonSet).filter(PokemonSet.species_id == species_id)
            for row in q.all():
                ab = (row.ability or "").strip()
                if ab:
                    seen.add(ab)
        return sorted(seen, key=str.casefold)
    # Fin de _build_ability_pool_fallback