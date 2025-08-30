# pokemon_app/gui/ui/treeview_kit.py
import tkinter as tk
from tkinter import ttk, font as tkfont

# ---------- Estilo base ----------
def apply_style(root, variant: str = "dark", theme: str = "clam"):
    """
    Aplica un estilo consistente para todos los Treeview.
    Llama esto una vez al iniciar la app o al construir la primera pestaña.
    variant: "light" | "dark"
    """
    style = ttk.Style(root)
    try:
        style.theme_use(theme)
    except Exception:
        pass

    if variant == "dark":
        palette = {
            "bg": "#1f2937", "fg": "#e5e7eb", "field": "#111827",
            "sel_bg": "#0ea5e9", "sel_fg": "#0b1020",
            "head_bg": "#111827", "head_fg": "#f3f4f6",
            "grid": "#374151", "hover": "#0b6fa1",
        }
    else:
        palette = {
            "bg": "#ffffff", "fg": "#222222", "field": "#ffffff",
            "sel_bg": "#e6f2ff", "sel_fg": "#0b3d91",
            "head_bg": "#f5f5f5", "head_fg": "#333333",
            "grid": "#dddddd", "hover": "#ececec",
        }

    font_row  = tkfont.nametofont("TkDefaultFont").copy()
    font_row.configure(size=6)
    font_head = tkfont.nametofont("TkHeadingFont").copy()
    font_head.configure(size=6, weight="bold")

    style.configure(
        "Poke.Treeview",
        font=font_row,
        rowheight=20,
        background=palette["bg"],
        fieldbackground=palette["field"],
        foreground=palette["fg"],
        bordercolor=palette["grid"],
        lightcolor=palette["grid"],
        darkcolor=palette["grid"],
    )
    style.map(
        "Poke.Treeview",
        background=[("selected", palette["sel_bg"])],
        foreground=[("selected", palette["sel_fg"])],
    )
    style.configure(
        "Poke.Treeview.Heading",
        font=font_head,
        background=palette["head_bg"],
        foreground=palette["head_fg"],
        bordercolor=palette["grid"],
    )
    style.map(
        "Poke.Treeview.Heading",
        background=[("active", palette["hover"])],
    )

def set_style(tree: ttk.Treeview):
    """Aplica el style unificado a un Treeview ya creado."""
    tree.configure(style="Poke.Treeview")

# ---------- Cebra ----------
def apply_zebra(tree: ttk.Treeview, odd="#fafafa", even="#ffffff"):
    tree.tag_configure("odd",  background=odd)
    tree.tag_configure("even", background=even)

def insert_with_zebra(tree: ttk.Treeview, values, **kwargs):
    """Inserta una fila alternando 'even'/'odd' automáticamente."""
    idx = len(tree.get_children(""))
    base_tags = set(kwargs.pop("tags", ()))
    base_tags.add("even" if idx % 2 == 0 else "odd")
    return tree.insert("", "end", values=values, tags=tuple(base_tags), **kwargs)

# ---------- Autosize ----------
def autosize_columns(tree: ttk.Treeview, pad=24, min_w=60, max_w=360):
    f = tkfont.nametofont("TkDefaultFont")
    for col in tree["columns"]:
        header = tree.heading(col, "text") or ""
        width = f.measure(header) + pad
        for iid in tree.get_children(""):
            val = str(tree.set(iid, col))
            width = max(width, f.measure(val) + pad)
        tree.column(col, width=max(min_w, min(width, max_w)))

# ---------- Flechas de orden ----------
def update_sort_arrows(tree: ttk.Treeview, col: str, direction: str):
    """direction: 'asc' o 'desc'"""
    for c in tree["columns"]:
        txt = tree.heading(c, "text") or ""
        txt = txt.replace(" ▲", "").replace(" ▼", "")
        tree.heading(c, text=txt)
    arrow = "▲" if direction == "asc" else "▼"
    base = tree.heading(col, "text") or col
    tree.heading(col, text=f"{base} {arrow}")

# ---------- Menú contextual ----------
def attach_right_click_menu(tree: ttk.Treeview, items):
    """
    items: lista de (label, callback_sin_args).
    Retorna el menú por si quieres añadir más acciones luego.
    """
    menu = tk.Menu(tree, tearoff=0)
    for label, cmd in items:
        menu.add_command(label=label, command=cmd)

    def _popup(e):
        row = tree.identify_row(e.y)
        if row:
            tree.selection_set(row)
            tree.focus(row)
            menu.tk_popup(e.x_root, e.y_root)
    tree.bind("<Button-3>", _popup, add="+")
    return menu

# ---------- Tags útiles para Daños (opcional) ----------
def apply_damage_tags(tree: ttk.Treeview):
    """Colores suaves según KO; úsalo en la pestaña Daños si quieres destacar."""
    tree.tag_configure("ko_ohko", background="#e8f9e8")
    tree.tag_configure("ko_2hko", background="#fff9e6")
    tree.tag_configure("ko_4hko", background="#fdeaea")
    # Ej. 'pinned' si reusas el concepto:
    # tree.tag_configure("pinned", font=(tkfont.nametofont("TkDefaultFont").actual("family"), 10, "bold"))
