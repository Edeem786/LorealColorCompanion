"""Small contracts for teammates. No CV or CVD model is implemented here."""
from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True)
class MakeupRegion:
    """Rectangle in the supplied image: fractions of width/height, from top-left."""
    x: float
    y: float
    width: float
    height: float

    def to_dict(self):
        values = (self.x, self.y, self.width, self.height)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError("Region coordinates must be finite numbers.")
        if not (0 <= self.x < 1 and 0 <= self.y < 1 and self.width > 0 and self.height > 0
                and self.x + self.width <= 1 and self.y + self.height <= 1):
            raise ValueError("Region must fit inside the image.")
        return asdict(self)


@dataclass(frozen=True)
class AccessibilityAssessment:
    """Separate accessibility estimate; never a beauty or preference score."""
    score: float
    reason: str

    def to_dict(self):
        if (isinstance(self.score, bool) or not isinstance(self.score, (int, float))
                or not math.isfinite(self.score) or not 0 <= self.score <= 1):
            raise ValueError("Accessibility score must be in [0, 1].")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("An accessibility explanation is required.")
        return asdict(self)


# Inject ordinary functions into create_app:
# detect_region(image_bytes: bytes, category: str) -> MakeupRegion | None
# assess_accessibility(user_id: str, category: str, color: tuple) -> AccessibilityAssessment | None
# None means no detection/profile/evidence, not zero accessibility.
# The accessibility adapter owns loading the user's existing CVD data.
