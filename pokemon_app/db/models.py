from __future__ import annotations
from datetime import datetime
from sqlalchemy import Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

class Species(Base):
    __tablename__ = "species"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    base_hp: Mapped[int] = mapped_column(Integer)
    base_atk: Mapped[int] = mapped_column(Integer)
    base_def: Mapped[int] = mapped_column(Integer)
    base_spa: Mapped[int] = mapped_column(Integer)
    base_spd: Mapped[int] = mapped_column(Integer)
    base_spe: Mapped[int] = mapped_column(Integer)

    sets: Mapped[list["PokemonSet"]] = relationship(back_populates="species", cascade="all, delete-orphan")

class PokemonSet(Base):
    __tablename__ = "pokemon_sets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    species_id: Mapped[int] = mapped_column(ForeignKey("species.id"), index=True)
    gender: Mapped[str | None] = mapped_column(String(1), nullable=True)
    item: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ability: Mapped[str | None] = mapped_column(String(128), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=50)
    tera_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    nature: Mapped[str | None] = mapped_column(String(32), nullable=True)

    evs_json: Mapped[str] = mapped_column(Text)
    ivs_json: Mapped[str] = mapped_column(Text)
    moves_json: Mapped[str] = mapped_column(Text)

    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    species: Mapped[Species] = relationship(back_populates="sets")

class SpeedPreset(Base):
    __tablename__ = "speed_presets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # parámetros guardados
    stage: Mapped[int] = mapped_column(Integer, default=0)
    tailwind: Mapped[int] = mapped_column(Integer, default=0)   # 0/1
    para: Mapped[int] = mapped_column(Integer, default=0)       # 0/1
    scarf: Mapped[int] = mapped_column(Integer, default=0)      # 0/1
    ability_label: Mapped[str] = mapped_column(String(64), default="—")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
