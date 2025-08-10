from typing import Dict

NATURE_EFFECTS = {
    "Adamant": ("Atk", "SpA"),
    "Lonely": ("Atk", "Def"),
    "Brave": ("Atk", "Spe"),
    "Naughty": ("Atk", "SpD"),
    "Impish": ("Def", "SpA"),
    "Bold": ("Def", "Atk"),
    "Relaxed": ("Def", "Spe"),
    "Lax": ("Def", "SpD"),
    "Modest": ("SpA", "Atk"),
    "Mild": ("SpA", "Def"),
    "Quiet": ("SpA", "Spe"),
    "Rash": ("SpA", "SpD"),
    "Calm": ("SpD", "Atk"),
    "Gentle": ("SpD", "Def"),
    "Sassy": ("SpD", "Spe"),
    "Careful": ("SpD", "SpA"),
    "Jolly": ("Spe", "SpA"),
    "Hasty": ("Spe", "Def"),
    "Naive": ("Spe", "SpD"),
    "Timid": ("Spe", "Atk"),
    "Serious": (None, None),
    "Bashful": (None, None),
    "Docile": (None, None),
    "Hardy": (None, None),
    "Quirky": (None, None),
}

def nature_multipliers(nature: str | None) -> Dict[str, float]:
    mults = {k: 1.0 for k in ["Atk", "Def", "SpA", "SpD", "Spe"]}
    if not nature:
        return mults
    up, down = NATURE_EFFECTS.get(nature, (None, None))
    if up:
        mults[up] = 1.1
    if down:
        mults[down] = 0.9
    return mults
