"""Local preference islands: strongest nearby like minus strongest nearby dislike."""

import math
from dataclasses import replace

from .distance import euclidean_distance
from .models import validate_color
from .storage import SQLiteStorage


class PreferenceService:
    def __init__(self, storage: SQLiteStorage, *, bandwidth: float = 0.1):
        if isinstance(bandwidth, bool) or not isinstance(bandwidth, (int, float)) or not math.isfinite(bandwidth) or bandwidth <= 0:
            raise ValueError("bandwidth must be finite and positive.")
        self.storage = storage
        self.bandwidth = bandwidth
        self.support_radius = 2 * bandwidth

    def add_rating(self, user_id, category, color, rating, preference_profile_id="personal", *, event_id=None):
        """Save feedback. Reuse event_id when retrying the same browser request."""
        return self.storage.add_rating(user_id, category, color, rating, preference_profile_id, event_id=event_id)

    def _score_color(self, color, events):
        evidence = {}
        for label, rating in (("liked", 1), ("disliked", -1)):
            matches = []
            for event in events:
                if event.rating != rating:
                    continue
                distance = float(euclidean_distance(color, event.color_vector))
                if not math.isfinite(distance) or distance < 0:
                    raise ValueError("Distance function must return a finite nonnegative number.")
                ratio = distance / self.bandwidth
                # No preference is inferred outside this reference's local neighborhood.
                similarity = math.exp(-0.5 * ratio * ratio) if ratio < 2 else 0.0
                matches.append({"color": list(event.color_vector), "distance": distance,
                                "similarity": similarity, "timestamp": event.timestamp.isoformat()})
            nearest = sorted(matches, key=lambda match: match["distance"])[:1]
            strongest = nearest[0]["similarity"] if nearest else 0.0
            evidence[label] = {"total_count": len(matches),
                               "strongest_similarity": strongest,
                               "nearest": nearest}
        liked = evidence["liked"]["strongest_similarity"]
        disliked = evidence["disliked"]["strongest_similarity"]
        if not events:
            reason = ["No individual color ratings in this category; preference is unknown."]
        else:
            reason = [f"Strongest nearby {label} match: {evidence[label]['strongest_similarity']:.3f}."
                      for label in ("liked", "disliked") if evidence[label]["total_count"]]
            if max(liked, disliked) == 0:
                reason.append("Little nearby evidence; preference is unknown, not disliked.")
            elif liked > 0 and disliked > 0 and abs(liked - disliked) < 0.1:
                reason.append("Nearby liked and disliked evidence conflicts.")
        return {"score": liked - disliked, "reason": reason, "evidence": evidence,
                "has_nearby_evidence": max(liked, disliked) > 0,
                "support_radius": self.support_radius}

    def recommend(self, user_id, category, candidate_colors, *, personal_weight=1.0,
                      environment_profile_id=None, personal_transform=None):
        """User-controlled tradeoff; unknown active evidence has no blended score."""
        if not isinstance(candidate_colors, list) or len(candidate_colors) > 1000:
            raise ValueError("Provide up to 1000 candidates.")
        if (isinstance(personal_weight, bool) or not isinstance(personal_weight, (int, float))
                or not math.isfinite(personal_weight) or not 0 <= personal_weight <= 1):
            raise ValueError("personal_weight must be a number between 0 and 1.")
        if environment_profile_id == "personal":
            raise ValueError("Environment must be distinct from personal.")
        personal_events = self.storage.get_ratings(user_id, category)
        environment_events = (self.storage.get_ratings(user_id, category, environment_profile_id)
                              if environment_profile_id is not None else [])
        weight = personal_weight if environment_events else 1.0
        # Simulate each personal reference once, without changing saved events.
        if personal_transform is not None and weight > 0:
            personal_events = [replace(event, color_vector=validate_color(
                personal_transform(event.color_vector))) for event in personal_events]
        results = []
        for candidate in candidate_colors:
            if not isinstance(candidate, dict) or "name" not in candidate or "color" not in candidate:
                raise ValueError("Each candidate must have name and color fields.")
            color = validate_color(candidate["color"])
            personal_color = (validate_color(personal_transform(color))
                              if personal_transform is not None and weight > 0 else color)
            personal = self._score_color(personal_color, personal_events)
            environment = self._score_color(color, environment_events)
            known = ((weight == 0 or personal["has_nearby_evidence"])
                     and (weight == 1 or environment["has_nearby_evidence"]))
            score = weight * personal["score"] + (1 - weight) * environment["score"] if known else None
            both = all(e["has_nearby_evidence"] and e["score"] > 0 for e in (personal, environment))
            results.append({**candidate, "score": score, "personal": personal, "environment": environment,
                            "shared_match": both, "status": "scored" if known else "insufficient_evidence"})
        results.sort(key=lambda r: (r["score"] is not None, r["score"] if r["score"] is not None else 0), reverse=True)
        return {"results": results, "personal_weight": weight, "environment_weight": 1 - weight,
                "personal_rating_count": len(personal_events), "environment_rating_count": len(environment_events)}
