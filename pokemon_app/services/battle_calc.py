# pokemon_app/services/battle_calc.py
from collections import Counter
import math

# ---------- Terreno ----------
def terrain_xmod(terrain: str, move_type: str, move_name: str = "") -> float:
    t = (terrain or "").strip().lower()
    mt = (move_type or "").strip().lower()
    mv = (move_name or "").strip().lower()

    # boosts
    if t in {"electric", "electric terrain", "eléctrico", "electrico", "electric/campo", "campo electrico"}:
        if mt in {"electric", "eléctrico", "electrico"}:
            return 1.3
    if t in {"psychic", "psychic terrain", "psíquico", "psiquico", "campo psiquico"}:
        if mt in {"psychic", "psíquico", "psiquico"}:
            return 1.3
    if t in {"grassy", "grassy terrain", "hierba", "campo hierba", "planta"}:
        mod = 1.0
        if mt in {"grass", "grassy", "hierba", "planta"}:
            mod *= 1.3
        # reducción de movimientos sísmicos en Grassy
        if mv in {"earthquake", "bulldoze", "magnitude"}:
            mod *= 0.5
        return mod
    if t in {"misty", "misty terrain", "niebla", "campo niebla"}:
        # dragón reducido
        if mt.startswith("dragon"):
            return 0.5
    return 1.0

# ---------- Pantallas / clima / boosts defensivos ----------
def screen_multiplier(category: str, is_singles: bool, reflect: bool, lightscreen: bool, veil: bool) -> float:
    base = 0.5 if is_singles else (2/3)  # gen9 aproximado
    if (category == "physical" and reflect) or (category == "special" and lightscreen) or veil:
        return base
    return 1.0

def weather_move_multiplier(move_type: str, weather: str) -> float:
    mt = (move_type or "").capitalize()
    w  = (weather or "")
    if w == "Lluvia" and mt in ("Water","Fire"):
        return 1.5 if mt == "Water" else 0.5
    if w == "Sol" and mt in ("Water","Fire"):
        return 0.5 if mt == "Water" else 1.5
    return 1.0

def defender_stat_weather_boost(def_types_uc: list[str], category: str, weather: str) -> float:
    if category == "special" and weather == "Tormenta Arena" and "Rock" in def_types_uc:
        return 1.5
    if category == "physical" and weather == "Nieve" and "Ice" in def_types_uc:
        return 1.5
    return 1.0

# ---------- STAB / Tera ----------
def tera_stab_multiplier(move_type: str, attacker_types: list[str], tera_on: bool, tera_type: str) -> float:
    mt = (move_type or "").capitalize()
    atts = [t.capitalize() for t in (attacker_types or [])]
    tt = (tera_type or "").capitalize()
    if not tera_on:
        return 1.5 if mt in atts else 1.0
    if mt == tt and mt in atts:
        return 2.0  # doble STAB
    if mt == tt and mt not in atts:
        return 1.5
    if mt != tt and mt in atts:
        return 1.5
    return 1.0

# ---------- Ítems ----------
def attacker_item_multiplier_auto(item_label: str, category: str, eff_mult: float, move_type: str) -> float:
    s = (item_label or "").strip().lower()
    if not s:
        return 1.0
    # Choice
    if "choice band" in s and category == "physical": return 1.5
    if "choice specs" in s and category == "special":  return 1.5
    # Life Orb
    if "life orb" in s: return 1.3
    # Expert Belt si es SE
    if "expert belt" in s and eff_mult > 1.0: return 1.2
    # Muscle/Wise
    if "muscle band" in s and category == "physical": return 1.1
    if "wise glasses" in s and category == "special": return 1.1
    # potenciadores de tipo
    type_item_map = {
        "charcoal":"Fire","mystic water":"Water","magnet":"Electric","miracle seed":"Grass",
        "never-melt ice":"Ice","black belt":"Fighting","poison barb":"Poison","soft sand":"Ground",
        "sharp beak":"Flying","twisted spoon":"Psychic","silver powder":"Bug","hard stone":"Rock",
        "spell tag":"Ghost","dragon fang":"Dragon","black glasses":"Dark","metal coat":"Steel",
        "pixie plate":"Fairy"
    }
    for key, t in type_item_map.items():
        if key in s and (move_type or "").capitalize() == t:
            return 1.2
    return 1.0

_RESIST_BERRY_BY_TYPE = {
    "Fire":"Occa Berry","Water":"Passho Berry","Electric":"Wacan Berry","Grass":"Rindo Berry",
    "Ice":"Yache Berry","Fighting":"Chople Berry","Poison":"Kebia Berry","Ground":"Shuca Berry",
    "Flying":"Coba Berry","Psychic":"Payapa Berry","Bug":"Tanga Berry","Rock":"Charti Berry",
    "Ghost":"Kasib Berry","Dragon":"Haban Berry","Dark":"Colbur Berry","Steel":"Babiri Berry",
    "Fairy":"Roseli Berry","Normal":"Chilan Berry",
}
def defender_item_effects_auto(item_label: str, category: str, move_type: str, eff_mult: float) -> tuple[float,float]:
    s = (item_label or "").strip().lower()
    def_mult, eff_adj = 1.0, 1.0
    if not s: return def_mult, eff_adj
    if "assault vest" in s and category == "special":
        def_mult *= 1.5
    wanted = _RESIST_BERRY_BY_TYPE.get((move_type or "").capitalize())
    if wanted and wanted.lower() in s and eff_mult > 1.0:
        eff_adj *= 0.5
    return def_mult, eff_adj

# ---------- Multi-golpe ----------
def resolve_hits(picked_move: str, hits_sel: str, att_item: str):
    mv = (picked_move or "").strip().lower()
    item = (att_item or "").strip().lower()
    sel = (hits_sel or "Auto").strip().lower()

    PRESETS = {
        # fijos 2
        "double hit":(2,2),"double kick":(2,2),"dual chop":(2,2),"bonemerang":(2,2),
        "twinneedle":(2,2),"dragon darts":(2,2),
        # fijos 3
        "surging strikes":(3,3),"triple kick":(3,3),"triple axel":(3,3),
        # 2–5
        "bullet seed":(2,5),"icicle spear":(2,5),"rock blast":(2,5),"arm thrust":(2,5),
        "fury swipes":(2,5),"pin missile":(2,5),"scale shot":(2,5),"water shuriken":(2,5),
        # 2–10
        "population bomb":(2,10),
    }

    # selección manual
    if sel in {"1","2","3","4","5","10"}:
        n = int(sel); return (n, n, float(n), "fixed")
    if sel.startswith("2-5"):
        if "loaded dice" in item:
            return (4, 5, 4.5, "range")
        return (2, 5, 3.0, "range")  # 37.5/37.5/12.5/12.5
    if mv in PRESETS:
        lo = "loaded dice" in item and PRESETS[mv] == (2,5)
        return (4,5,4.5,"auto") if lo else (*PRESETS[mv], 3.0 if PRESETS[mv]==(2,5) else float(PRESETS[mv][0]), "auto")

    # por defecto: 1 golpe
    return (1, 1, 1.0, "auto")

def hits_weights_for_selector(selector_text: str, min_hits: int, max_hits: int) -> dict[int,float]:
    sel = (selector_text or "Auto").strip().lower()
    if min_hits == max_hits:
        return {min_hits: 1.0}
    if min_hits == 4 and max_hits == 5:
        return {4: 0.5, 5: 0.5}
    if sel.startswith("2-5"):
        return {2:0.375, 3:0.375, 4:0.125, 5:0.125}
    # Auto (2–5 sin Loaded Dice)
    if (min_hits, max_hits) == (2,5):
        return {2:0.35, 3:0.35, 4:0.15, 5:0.15}
    return {min_hits: 1.0}

# ---------- Rolls y prob. KO ----------
def single_hit_roll_dist(base_damage: float, xmod: float) -> Counter:
    rolls = [0.85 + i*0.01 for i in range(16)]
    vals = [int(base_damage * r * xmod) for r in rolls]
    return Counter(vals)

def ohko_probability_from_dist(per_hit_dist: Counter, hp: int, hits_weights: dict[int,float]) -> float:
    total_prob = 0.0
    cache: dict[int, Counter] = {}
    for hits, w in hits_weights.items():
        if hits <= 0 or w <= 0:
            continue
        if hits == 1:
            dist_h = per_hit_dist
        else:
            dist_h = cache.get(hits)
            if dist_h is None:
                dist_h = per_hit_dist
                for _ in range(1, hits):
                    new = Counter()
                    for s1, c1 in dist_h.items():
                        for v, c2 in per_hit_dist.items():
                            new[s1 + v] += c1 * c2
                    dist_h = new
                cache[hits] = dist_h
        tot = sum(dist_h.values()) or 1
        ko_count = sum(c for dmg, c in dist_h.items() if dmg >= hp)
        total_prob += w * (ko_count / tot)
    return max(0.0, min(1.0, total_prob))

def ko_hits_bounds(hp: int, dmin: int, dmax: int, min_hits: int, max_hits: int) -> tuple[int,int]:
    tdmin, tdmax = dmin*min_hits, dmax*max_hits
    n_best  = 999 if tdmax <= 0 else math.ceil(hp / max(1, dmax))
    n_worst = 999 if tdmin <= 0 else math.ceil(hp / max(1, dmin))
    return n_best, n_worst

# battle_calc.py (helper)
def variable_power(move_name: str, defender_weight_kg: float | None) -> int | None:
    mv = (move_name or "").strip().lower()
    if mv in ("low kick", "grass knot"):
        w = defender_weight_kg or 0.0
        # Tiers estándar (Gen 9): 20/40/60/80/100/120
        if w < 10:   return 20
        if w < 25:   return 20
        if w < 50:   return 40
        if w < 100:  return 60
        if w < 200:  return 80
        if w < 1000: return 100
        return 120
    return None
