import itertools
from colormatcher.colormath import coherence, color_similarity

N = 5
threshold = 0.8

def set_threshold(value: float):
    global threshold
    threshold = value

def compare_single(json, preferred_colors, input_colors=None):
    topN = []
    for entry in json:
        colorDB = entry["color"]
        db_color = (colorDB["L"], colorDB["a"], colorDB["b"])

        matches = []
        for candidate in preferred_colors:
            if candidate.get("score") is None:
                continue  # insufficient_evidence, skip
            c = candidate["color"]
            cand_color = (c["L"], c["a"], c["b"])
            sim = color_similarity(db_color, cand_color)
            if sim < threshold:
                continue

            pref = (candidate["score"] + 1) / 2  # [-1,1] -> [0,1]
            matches.append({**candidate, "similarity": sim, "combined_score": sim * pref})

        if not matches:
            continue

        matches.sort(key=lambda m: m["combined_score"], reverse=True)

        if input_colors is None:
            topN.append({**entry, "matches": matches[:N]})
            continue

        input_tuples = [(c["L"], c["a"], c["b"]) for c in input_colors]
        for m in matches:
            pref = (m["score"] + 1) / 2
            m["coherence"] = coherence(input_tuples + [db_color])
            m["combined_score"] = m["coherence"] * pref
        matches.sort(key=lambda m: m["combined_score"], reverse=True)
        topN.append({**entry, "matches": matches[:N]})

    return topN

def compare_multi(json_list, preferred_colors_list, input_colors_list):
    # Stage 1: shortlist per category (like compare_single, but flattened across all db entries)
    shortlists = []
    for json_cat, preferred_cat, input_cat in zip(json_list, preferred_colors_list, input_colors_list):
        input_tuples = [(c["L"], c["a"], c["b"]) for c in input_cat]
        category_matches = []

        for entry in json_cat:
            colorDB = entry["color"]
            db_color = (colorDB["L"], colorDB["a"], colorDB["b"])

            for candidate in preferred_cat:
                if candidate.get("score") is None:
                    continue
                c = candidate["color"]
                cand_color = (c["L"], c["a"], c["b"])
                sim = color_similarity(db_color, cand_color)
                if sim < threshold:
                    continue

                pref = (candidate["score"] + 1) / 2
                coh = coherence(input_tuples + [db_color])  # match vs. lips/skin
                combined = sim * pref * coh

                category_matches.append({**entry, "candidate": candidate,
                                          "similarity": sim, "coherence": coh,
                                          "combined_score": combined})

        category_matches.sort(key=lambda m: m["combined_score"], reverse=True)
        shortlists.append(category_matches[:N])

    # Stage 2: combine one pick per category, score cross-category coherence
    palettes = []
    for combo in itertools.product(*shortlists):
        color_tuples = [(m["color"]["L"], m["color"]["a"], m["color"]["b"]) for m in combo]
        cross_coherence = coherence(color_tuples)  # lipstick vs blush, etc.
        item_scores = [m["combined_score"] for m in combo]
        final_score = min(min(item_scores), cross_coherence)  # bottleneck

        palettes.append({"items": combo, "cross_coherence": cross_coherence, "score": final_score})

    palettes.sort(key=lambda p: p["score"], reverse=True)
    return palettes[:N]