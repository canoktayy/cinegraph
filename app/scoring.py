"""Small pure functions used by import, analytics and recommendation tests."""

import math
import re
import unicodedata


def normalize_tag(text: str) -> str:
    """Collapse whitespace and Unicode-equivalent tags while retaining raw text elsewhere."""
    return " ".join(unicodedata.normalize("NFKC", text).split()).casefold()


def parse_year(title: str) -> int | None:
    """Extract only an unambiguous terminal four-digit year."""
    found = re.search(r"\((\d{4})\)\s*$", title)
    return int(found.group(1)) if found else None


def validate_rating(value: float) -> float:
    """Reject impossible or nonfinite source ratings."""
    if not math.isfinite(value) or not 0.5 <= value <= 5.0 or value * 2 != int(value * 2):
        raise ValueError("Rating must be a half-star value between 0.5 and 5.0")
    return value


def shrunk_jaccard(left: set, right: set, beta: float = 5) -> tuple[float, int]:
    """Penalize apparently strong similarities supported by very few users."""
    if beta <= 0:
        raise ValueError("beta must be positive")
    support = len(left & right)
    union = len(left | right)
    return (support / union * support / (support + beta) if union else 0.0), support


def bayesian_rating(count: int, mean: float, global_mean: float, strength: float = 20) -> float:
    """Shrink sparse movie means toward the catalog average."""
    return (count * mean + strength * global_mean) / (count + strength)
