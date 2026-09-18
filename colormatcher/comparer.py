

N = 1
threshold = 0.8

def set_threshold(value: float):
    global threshold
    threshold = value

# Returns top N blush choices
def compare_single(json, db_name, user_id, category, preference_profile_id="personal"):
    with SQLiteStorage(db_name) as storage:
        # skin tone isn't a "preference" — it's measured input, but stored the same way
        skin_events = storage.get_ratings(user_id, "skin_tone", preference_profile_id)
        input_colors = [(e.color[0], e.color[1], e.color[2]) for e in skin_events]

        preferred_events = storage.get_ratings(user_id, category, preference_profile_id)
        preferred_colors = [
            {"color": {"L": e.color[0], "a": e.color[1], "b": e.color[2]}, "score": e.rating}
            for e in preferred_events
        ]

    topN = []
    for entry in json:
        colorDB = entry["color"]
        db_color = (colorDB["L"], colorDB["a"], colorDB["b"])

        matches = []
        for candidate in preferred_colors:
            c = candidate["color"]
            cand_color = (c["L"], c["a"], c["b"])
            sim = color_similarity(db_color, cand_color)
            if sim < threshold:
                continue

            pref = (candidate["score"] + 1) / 2  # -1/1 -> 0/1
            coh = coherence(input_colors + [db_color]) if input_colors else 1.0
            combined = sim * pref * coh

            matches.append({**candidate, "similarity": sim, "coherence": coh, "combined_score": combined})

        if not matches:
            continue

        matches.sort(key=lambda m: m["combined_score"], reverse=True)
        topN.append({**entry, "matches": matches[:N]})

    return topN