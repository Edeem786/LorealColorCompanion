"""Distance can be replaced by passing a callable to PreferenceService."""

from math import dist
from .models import Color


def euclidean_distance(color_a: Color, color_b: Color) -> float:
    return dist(color_a, color_b)
