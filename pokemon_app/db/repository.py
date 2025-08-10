from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, Tuple, List, Optional
from sqlalchemy import select, asc, desc, func, delete
from sqlalchemy.orm import Session
from .base import Base, engine, session_scope
from .models import Species, PokemonSet, SpeedPreset

def init_db():
    Base.metadata.create_all(bind=engine)

def upsert_species(name: str, base_stats: Dict[str, int]) -> Species:
    with session_scope() as s:
        stmt = select(Species).where(Species.name == name)
        sp = s.scalar(stmt)
        if not sp:
            sp = Species(
                name=name,
                base_hp=base_stats["HP"],
                base_atk=base_stats["Atk"],
                base_def=base_stats["Def"],
                base_spa=base_stats["SpA"],
                base_spd=base_stats["SpD"],
                base_spe=base_stats["Spe"],
            )
            s.add(sp)
            s.flush()
        return sp

def save_pokemon_set(
    name: str,
    gender: str | None,
    item: str | None,
    ability: str | None,
    level: int,
    tera_type: str | None,
    nature: str | None,
    evs: Dict[str, int],
    ivs: Dict[str, int],
    moves: list[str],
    base_stats_registry: Dict[str, Dict[str, int]],
    raw_text: str | None = None,
) -> tuple[Species, PokemonSet]:
    sp = upsert_species(name, base_stats_registry[name])
    with session_scope() as s:
        sp = s.merge(sp)
        pset = PokemonSet(
            species_id=sp.id,
            gender=gender,
            item=item,
            ability=ability,
            level=level,
            tera_type=tera_type,
            nature=nature,
            evs_json=json.dumps(evs, ensure_ascii=False),
            ivs_json=json.dumps(ivs, ensure_ascii=False),
            moves_json=json.dumps(moves, ensure_ascii=False),
            raw_text=raw_text,
        )
        s.add(pset)
        s.flush()
        return sp, pset

def list_sets(
    session: Session,
    only_species: Optional[str] = None,
    limit: Optional[int] = None,
    nature: Optional[str] = None,
    item: Optional[str] = None,
    ability: Optional[str] = None,
    tera: Optional[str] = None,
    level_min: Optional[int] = None,
    level_max: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    move_contains: Optional[list[str]] = None,
    order_by: Optional[str] = None,
    order_dir: str = "desc",
    offset: Optional[int] = None,
):
    stmt = select(PokemonSet, Species).join(Species, PokemonSet.species_id == Species.id)
    if only_species:
        stmt = stmt.where(Species.name.ilike(only_species))
    if nature:
        stmt = stmt.where(PokemonSet.nature.ilike(nature))
    if item:
        stmt = stmt.where(PokemonSet.item.ilike(item))
    if ability:
        stmt = stmt.where(PokemonSet.ability.ilike(ability))
    if tera:
        stmt = stmt.where(PokemonSet.tera_type.ilike(tera))
    if level_min is not None:
        stmt = stmt.where(PokemonSet.level >= level_min)
    if level_max is not None:
        stmt = stmt.where(PokemonSet.level <= level_max)
    if date_from is not None:
        stmt = stmt.where(PokemonSet.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(PokemonSet.created_at <= date_to)
    if move_contains:
        for token in move_contains:
            stmt = stmt.where(PokemonSet.moves_json.ilike(token))
    ob = (order_by or "created").lower()
    use_dir = desc if (order_dir or "desc").lower() == "desc" else asc
    if ob == "id":
        stmt = stmt.order_by(use_dir(PokemonSet.id))
    elif ob == "species":
        stmt = stmt.order_by(use_dir(Species.name))
    elif ob == "level":
        stmt = stmt.order_by(use_dir(PokemonSet.level))
    elif ob == "nature":
        stmt = stmt.order_by(use_dir(PokemonSet.nature))
    elif ob == "tera":
        stmt = stmt.order_by(use_dir(PokemonSet.tera_type))
    elif ob == "item":
        stmt = stmt.order_by(use_dir(PokemonSet.item))
    elif ob == "ability":
        stmt = stmt.order_by(use_dir(PokemonSet.ability))
    else:
        stmt = stmt.order_by(use_dir(PokemonSet.created_at))
    if offset is not None:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return session.execute(stmt).all()

def count_sets(
    session: Session,
    only_species: Optional[str] = None,
    nature: Optional[str] = None,
    item: Optional[str] = None,
    ability: Optional[str] = None,
    tera: Optional[str] = None,
    level_min: Optional[int] = None,
    level_max: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    move_contains: Optional[list[str]] = None,
) -> int:
    stmt = select(func.count(PokemonSet.id)).join(Species, PokemonSet.species_id == Species.id)
    if only_species:
        stmt = stmt.where(Species.name.ilike(only_species))
    if nature:
        stmt = stmt.where(PokemonSet.nature.ilike(nature))
    if item:
        stmt = stmt.where(PokemonSet.item.ilike(item))
    if ability:
        stmt = stmt.where(PokemonSet.ability.ilike(ability))
    if tera:
        stmt = stmt.where(PokemonSet.tera_type.ilike(tera))
    if level_min is not None:
        stmt = stmt.where(PokemonSet.level >= level_min)
    if level_max is not None:
        stmt = stmt.where(PokemonSet.level <= level_max)
    if date_from is not None:
        stmt = stmt.where(PokemonSet.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(PokemonSet.created_at <= date_to)
    if move_contains:
        for token in move_contains:
            stmt = stmt.where(PokemonSet.moves_json.ilike(token))
    return int(session.execute(stmt).scalar_one())

def delete_sets(session: Session, ids: list[int]) -> int:
    if not ids:
        return 0
    res = session.execute(delete(PokemonSet).where(PokemonSet.id.in_(ids)))
    session.commit()
    return int(res.rowcount or 0)

def get_set(session: Session, set_id: int):
    stmt = select(PokemonSet, Species).join(Species, PokemonSet.species_id == Species.id).where(PokemonSet.id == set_id)
    return session.execute(stmt).first()

def update_set(session: Session, set_id: int, *, level: int | None = None, nature: str | None = None,
               tera_type: str | None = None, item: str | None = None, ability: str | None = None,
               evs: dict | None = None, ivs: dict | None = None, moves: list[str] | None = None) -> int:
    ps = session.get(PokemonSet, set_id)
    if not ps:
        return 0
    if level is not None:
        ps.level = level
    if nature is not None:
        ps.nature = nature
    if tera_type is not None:
        ps.tera_type = tera_type
    if item is not None:
        ps.item = item
    if ability is not None:
        ps.ability = ability
    import json as _json
    if evs is not None:
        ps.evs_json = _json.dumps(evs, ensure_ascii=False)
    if ivs is not None:
        ps.ivs_json = _json.dumps(ivs, ensure_ascii=False)
    if moves is not None:
        ps.moves_json = _json.dumps(moves, ensure_ascii=False)
    session.commit()
    return 1

def list_speed_presets(session: Session) -> list[SpeedPreset]:
    stmt = select(SpeedPreset).order_by(SpeedPreset.name.asc())
    return [row[0] if isinstance(row, tuple) else row for row in session.execute(stmt).all()]

def get_speed_preset(session: Session, name: str) -> SpeedPreset | None:
    stmt = select(SpeedPreset).where(SpeedPreset.name == name)
    return session.scalar(stmt)

def save_speed_preset(session: Session, name: str, *, stage: int, tailwind: bool, para: bool, scarf: bool, ability_label: str) -> SpeedPreset:
    sp = get_speed_preset(session, name)
    if not sp:
        sp = SpeedPreset(name=name)
        session.add(sp)
    sp.stage = int(stage)
    sp.tailwind = 1 if tailwind else 0
    sp.para = 1 if para else 0
    sp.scarf = 1 if scarf else 0
    sp.ability_label = ability_label or "—"
    session.commit()
    return sp

def delete_speed_preset(session: Session, name: str) -> int:
    sp = get_speed_preset(session, name)
    if not sp:
        return 0
    session.delete(sp)
    session.commit()
    return 1
