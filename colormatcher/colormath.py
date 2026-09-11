import math
import itertools

def hue_angle(color):
    L, a, b = color
    return math.degrees(math.atan2(b, a)) % 360

def chroma(color):
    L, a, b = color
    return math.sqrt(a**2 + b**2)

def circular_hue_distance(angle1, angle2):
    diff = abs(angle1 - angle2) % 360
    return min(diff, 360 - diff)

def suitability(skin_color, candidate_color, bandwidth=35, neutral_chroma_threshold=0.05):
    if chroma(skin_color) < neutral_chroma_threshold:
        return 0.9  # flat high suitability for neutral undertones
    dist = circular_hue_distance(hue_angle(skin_color), hue_angle(candidate_color))
    return math.exp(-0.5 * (dist / bandwidth) ** 2)

def coherence(colors):
    # colors: list of (L, a, b) tuples, one per palette item
    weighted_x, weighted_y, total_weight = 0.0, 0.0, 0.0
    for color in colors:
        angle = math.radians(hue_angle(color))
        weight = chroma(color)          # near-neutral colors barely vote
        weighted_x += weight * math.cos(angle)
        weighted_y += weight * math.sin(angle)
        total_weight += weight

    if total_weight == 0:
        return 1.0  # everything's neutral — nothing to clash

    x = weighted_x / total_weight
    y = weighted_y / total_weight
    return math.sqrt(x**2 + y**2)

def combined_item_score(preference_score, suitability_score):
    """
    preference_score: float in [-1, 1] from predict_preference
    suitability_score: float in [0, 1] from suitability()
    """
    if preference_score <= suitability_score:
        return preference_score, "preference"
    return suitability_score, "suitability"

def generate_candidate_palettes(shortlists):
    """
    shortlists: dict of category -> list of scored product dicts
                (already top-N per category from the combined preference+suitability step)
    """
    categories = list(shortlists.keys())
    for combo in itertools.product(*(shortlists[c] for c in categories)):
        palette = dict(zip(categories, combo))
        colors = [product["color"] for product in palette.values()]
        palette_coherence = coherence(colors)
        yield palette, palette_coherence

def palette_score(palette, coherence_score):
    item_scores = [product["combined_score"] for product in palette.values()]
    return min(min(item_scores), coherence_score)