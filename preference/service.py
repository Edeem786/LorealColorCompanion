"""Online, local-neighbor preference estimates without model training."""

import math
from typing import Callable

from .distance import euclidean_distance
from .models import Color, validate_color
from .storage import SQLiteStorage


class PreferenceService:
    def __init__(self, storage: SQLiteStorage, *, bandwidth: float = 0.1,
                 neighbors: int = 3, distance: Callable[[Color, Color], float] = euclidean_distance):
        if isinstance(bandwidth, bool) or not math.isfinite(bandwidth) or bandwidth <= 0:
            raise ValueError("bandwidth must be finite and positive.")
        if isinstance(neighbors, bool) or not isinstance(neighbors, int) or neighbors < 1:
            raise ValueError("neighbors must be a positive integer.")
        self.storage = storage
        self.bandwidth = bandwidth
        self.neighbors = neighbors
        self.distance = distance

    def add_rating(self, user_id, category, color, rating, preference_profile_id="personal"):
        return self.storage.add_rating(user_id, category, color, rating, preference_profile_id)

    def add_comparison(self, user_id, category, color_a, color_b, preferred, preference_profile_id="personal"):
        return self.storage.add_comparison(user_id, category, color_a, color_b, preferred, preference_profile_id)

    def get_profile(self, user_id, preference_profile_id="personal"):
        return self.storage.get_profile(user_id, preference_profile_id)

    def predict_preference(self, user_id, category, color_vector, preference_profile_id="personal") -> float:
        return self.explain_preference(user_id, category, color_vector, preference_profile_id)["score"]

    def explain_preference(self, user_id, category, color_vector, preference_profile_id="personal") -> dict:
        color = validate_color(color_vector)
        return self._explain(color, self.storage.get_ratings(user_id, category, preference_profile_id))

    def _explain(self, color, events):
        evidence = {}
        for label, rating in (("liked", 1), ("disliked", -1)):
            matches = []
            for event in events:
                if event.rating != rating:
                    continue
                distance = float(self.distance(color, event.color_vector))
                if not math.isfinite(distance) or distance < 0:
                    raise ValueError("Distance function must return a finite nonnegative number.")
                ratio = distance / self.bandwidth
                similarity = math.exp(-0.5 * ratio * ratio)
                matches.append({"color": list(event.color_vector), "distance": distance,
                                "similarity": similarity, "timestamp": event.timestamp.isoformat()})
            nearest = sorted(matches, key=lambda match: match["distance"])[:self.neighbors]
            evidence[label] = {"total_count": len(matches), "used_count": len(nearest),
                               "mean_similarity": sum(m["similarity"] for m in nearest) / len(nearest) if nearest else 0.0,
                               "nearest": nearest}
        liked = evidence["liked"]["mean_similarity"]
        disliked = evidence["disliked"]["mean_similarity"]
        if not events:
            reason = ["No individual color ratings in this category; preference is unknown."]
        else:
            reason = [f"Mean similarity to {evidence[label]['used_count']} nearest {label} rating(s): "
                      f"{evidence[label]['mean_similarity']:.3f}." for label in ("liked", "disliked")]
            if max(liked, disliked) < 0.1:
                reason.append("Little nearby evidence; preference is uncertain.")
            elif liked >= 0.1 and disliked >= 0.1 and abs(liked - disliked) < 0.1:
                reason.append("Nearby liked and disliked evidence conflicts.")
        return {"score": liked - disliked, "reason": reason, "evidence": evidence}

    def rank_colors(self, user_id, category, candidate_colors, preference_profile_id="personal") -> list[dict]:
        events = self.storage.get_ratings(user_id, category, preference_profile_id)
        ranked = []
        for candidate in candidate_colors:
            if not isinstance(candidate, dict) or "name" not in candidate or "color" not in candidate:
                raise ValueError("Each candidate must have name and color fields.")
            explanation = self._explain(validate_color(candidate["color"]), events)
            ranked.append({**candidate, **explanation})
        return sorted(ranked, key=lambda candidate: candidate["score"], reverse=True)

    def rank_shared(self, user_id, category, candidate_colors, environment_profile_id):
        """Rank shared matches first. Weak/missing evidence has no overlap score."""
        if environment_profile_id == "personal":
            raise ValueError("Choose an environment profile distinct from personal.")
        personal_events = self.storage.get_ratings(user_id, category, "personal")
        environment_events = self.storage.get_ratings(user_id, category, environment_profile_id)
        results = []
        for candidate in candidate_colors:
            if not isinstance(candidate, dict) or "name" not in candidate or "color" not in candidate:
                raise ValueError("Each candidate must have name and color fields.")
            color = validate_color(candidate["color"])
            personal = self._explain(color, personal_events)
            environment = self._explain(color, environment_events)
            for explanation in (personal, environment):
                explanation["has_nearby_evidence"] = max(
                    side["mean_similarity"] for side in explanation["evidence"].values()) >= 0.1
            known = personal["has_nearby_evidence"] and environment["has_nearby_evidence"]
            overlap = min(personal["score"], environment["score"]) if known else None
            shared = known and personal["score"] > 0 and environment["score"] > 0
            results.append({**candidate, "personal": personal, "environment": environment,
                            "overlap_score": overlap, "shared_match": shared,
                            "status": "shared_match" if shared else "no_shared_match" if known else "insufficient_evidence"})
        return sorted(results, key=lambda item: (item["shared_match"], item["overlap_score"] is not None,
                                                item["overlap_score"] if item["overlap_score"] is not None else 0), reverse=True)

    def rank_weighted(self, user_id, category, candidate_colors, *, personal_weight=1.0,
                      environment_profile_id=None):
        """User-controlled tradeoff; unknown active evidence has no blended score."""
        if (isinstance(personal_weight, bool) or not isinstance(personal_weight, (int, float))
                or not math.isfinite(personal_weight) or not 0 <= personal_weight <= 1):
            raise ValueError("personal_weight must be a number between 0 and 1.")
        if environment_profile_id == "personal":
            raise ValueError("Environment must be distinct from personal.")
        personal_events = self.storage.get_ratings(user_id, category)
        environment_events = (self.storage.get_ratings(user_id, category, environment_profile_id)
                              if environment_profile_id is not None else [])
        weight = personal_weight if environment_events else 1.0
        results = []
        for candidate in candidate_colors:
            if not isinstance(candidate, dict) or "name" not in candidate or "color" not in candidate:
                raise ValueError("Each candidate must have name and color fields.")
            color = validate_color(candidate["color"])
            personal, environment = self._explain(color, personal_events), self._explain(color, environment_events)
            for explanation in (personal, environment):
                explanation["has_nearby_evidence"] = max(side["mean_similarity"] for side in explanation["evidence"].values()) >= 0.1
            known = ((weight == 0 or personal["has_nearby_evidence"])
                     and (weight == 1 or environment["has_nearby_evidence"]))
            score = weight * personal["score"] + (1 - weight) * environment["score"] if known else None
            both = all(e["has_nearby_evidence"] and e["score"] > 0 for e in (personal, environment))
            results.append({**candidate, "score": score, "personal": personal, "environment": environment,
                            "shared_match": both, "status": "scored" if known else "insufficient_evidence"})
        results.sort(key=lambda r: (r["score"] is not None, r["score"] if r["score"] is not None else 0), reverse=True)
        return {"results": results, "personal_weight": weight, "environment_weight": 1 - weight,
                "personal_rating_count": len(personal_events), "environment_rating_count": len(environment_events)}
