"""Domain records. Colors are normalized OKLab vectors, not color labels."""

from dataclasses import dataclass, field
from datetime import datetime
import math
from typing import Sequence

Color = tuple[float, float, float]


def validate_color(value: Sequence[float]) -> Color:
    if isinstance(value, (str, bytes)):
        raise ValueError("Color must contain three finite numbers.")
    try:
        parts = tuple(value)
        if len(parts) != 3 or any(isinstance(x, (bool, str, bytes)) for x in parts):
            raise ValueError
        color = tuple(float(x) for x in parts)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Color must contain three finite numbers.") from exc
    if not all(math.isfinite(x) for x in color) or not 0 <= color[0] <= 1:
        raise ValueError("OKLab components must be finite and L must be in [0, 1].")
    return color


def validate_key(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string.")
    return value


@dataclass(frozen=True)
class PreferenceEvent:
    user_id: str
    category: str
    color_vector: Color
    rating: int
    timestamp: datetime
    preference_profile_id: str = "personal"


@dataclass(frozen=True)
class ComparisonEvent:
    user_id: str
    category: str
    color_a: Color
    color_b: Color
    preferred: str
    timestamp: datetime
    preference_profile_id: str = "personal"


@dataclass
class CategoryPreference:
    ratings: list[PreferenceEvent] = field(default_factory=list)
    comparisons: list[ComparisonEvent] = field(default_factory=list)

    @property
    def liked_colors(self) -> list[Color]:
        return [event.color_vector for event in self.ratings if event.rating == 1]

    @property
    def disliked_colors(self) -> list[Color]:
        return [event.color_vector for event in self.ratings if event.rating == -1]


@dataclass
class UserPreferenceProfile:
    user_id: str
    categories: dict[str, CategoryPreference] = field(default_factory=dict)
    preference_profile_id: str = "personal"
