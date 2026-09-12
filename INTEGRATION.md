# Teammate integration guide

## Current status

The UI now supports manual extraction and automatic lip/blush detection in both reference sets. Clicking Auto-detect sends the resized photo to Flask, without saving the image. Detection fills review checkboxes; Continue saves likes.

`onboarding/vision.py` provides lip extraction and a cheek-only blush sampler. Blush samples visible skin-plus-makeup appearance, not isolated pigment. Skin and iris helpers remain separate. Install the optional `requirements-vision.txt` dependencies in the teammate's compatible environment and supply `facetracker/face_landmarker.task`. Real model detection remains unvalidated here because those dependencies and the model are missing. Missing setup produces a manual fallback message.

## RGB contract

Return a list of up to 12 distinct representative lip shades:

```python
[[180, 80, 100], [195, 105, 125]]
```

Each triplet must be **sRGB**, channel order **R, G, B**, with Python integers from **0 to 255**. Convert NumPy values with `.tolist()` for JSON. OpenCV often uses BGR: swap channels before returning. If your model returns normalized 0–1 values, convert them to 0–255 integers first. Do not send linear RGB, CIELAB or OKLab through this RGB interface.

RGB is sufficient for this MVP. A bounding box, mask, confidence and pixel coverage are optional future additions, not required. Return `[]` if no usable lip colors are found; never use `[0, 0, 0]` as an error value. For multiple faces, initially return no result and ask the user to crop to one face, unless the team explicitly agrees on a selection rule. Do not silently combine people's lip shades.

The proposed request supplies the oriented, resized **full reference image as PNG bytes**. The detector owns image decoding, lip segmentation and shade extraction. Inspect the resized input quality when integrating; the current browser limits the long edge to 800 pixels. If the model needs higher resolution, agree on that before changing the upload contract.

## How to change the detector

1. Update `detect_lip_shades` or `detect_blush_shades` in `onboarding/vision.py`, preserving the RGB contract. Imports are lazy so manual use does not require CV packages.
2. Alternatively pass `create_app(detect_shades=your_function)`. It takes `(image_bytes, category)` and returns the RGB list.
3. `POST /api/detect-shades` accepts multipart fields `image` (PNG) and `category` (`lip` or `blush`). It checks upload size, PNG header/dimensions (up to 800 pixels per side) and returned RGB values. The detector decodes the image. Success returns `{"shades": [...]}`; setup or detector failure returns a 503 error with manual fallback guidance.
4. `detectReferenceShades` uploads and populates `showReferenceShades`. Empty/error results preserve existing shades. Responses are ignored after removal, manual extraction, crop changes, profile/category changes or freezing. No ratings are created by detection.
5. Validate actual photos in the teammate's environment. The landmark detector accepts exactly one face, rejecting no-face and multiple-face results.

The old rectangle-only `/api/detect-region` route remains for compatibility, unused by the UI. Experimental `colormatcher` functions remain separate from preference ranking.

## Manual extraction explained

`extract` in `onboarding/app.js` samples the chosen rectangle at up to 160 × 160 pixels. `palette` in `onboarding/colors.js` then:

1. Ignores pixels whose alpha is below 250.
2. Converts each sampled RGB pixel to normalized OKLab.
3. Places pixels in small OKLab bins (0.025 units along each axis).
4. Sorts bins by pixel count.
5. Computes the arithmetic mean RGB of each candidate bin, rounding to integers.
6. Selects up to three shades, skipping ones within 0.045 OKLab distance of a previously selected shade.

So this is a frequent-color-bin method with a mean **within each bin**, not a median or a mean of the entire rectangle. It does not identify lip pixels: teeth, skin or reflections can win if included in the crop. The CV model can improve precisely that separation. Both methods feed the same RGB review helper and preference model.

## Connect CVD assessment

The color vision form is stage 3, after aesthetic references and before stage 4 (balance). Saving advances to balance; Back returns to the aesthetic stage. Both new and existing profiles returned by `get_cvd_profile` and the HTTP API include `severity_level`: **mild = 1, moderate = 2, severe = 3**. The mapping lives in `SEVERITY_LEVELS` in `onboarding/cvd_profile.py`. The label remains stored; the level is derived to avoid two fields disagreeing. This is an ordinal code only, not a clinically calibrated numerical severity or a 0–1 simulation parameter. The CVD teammate should define any model-specific conversion separately.

The site now collects **user-entered diagnosis details** in a separate `cvd_profiles` SQLite table: type (`deutan`, `protan`, `tritan`, `other`), severity (`mild`, `moderate`, `severe`), source (`user_entered_diagnosis`), and update timestamp. This is not independently verified. Unsure is a disabled UI placeholder and rejected by the API until supported. An unfilled profile remains absent; no severity is guessed.

Read it in your adapter with `from onboarding.cvd_profile import get_cvd_profile`, then `get_cvd_profile(user_id)` (or pass your database path as the second argument). Other diagnosed types must be treated as unsupported unless your method supports them. Never map severity labels to numerical simulation values without defining that mapping. Saving this profile creates no preference events and does not activate CVD scoring.

`GET /api/cvd-profile?user_id=...` returns `{"profile": null}` or the saved record. `POST /api/cvd-profile` accepts `user_id`, `type`, and `severity` and updates that user's record. As with the rest of this local prototype, this is not an authenticated account system.

```python
from onboarding.integrations import AccessibilityAssessment

def assess_accessibility(user_id, category, color):
    profile = your_existing_cvd_store.get(user_id)
    if profile is None:
        return None
    # color is a normalized OKLab (L, a, b) tuple.
    score, explanation = your_cvd_function(profile, category, color)
    return AccessibilityAssessment(score, explanation)
```

Your adapter owns retrieving existing CVD information and converting color coordinates if needed. This project does not infer CVD from preference feedback. Return a finite score from 0 to 1 (higher means more accessible under your documented metric) and a nonempty explanation. `None` means unavailable, not zero accessibility. If your method needs background/reference colors, obtain them in your adapter or extend this contract together; do not invent a distinguishability score from an isolated color.

Ranked candidates receive an `accessibility` object, shown separately in the UI. Missing assessments are `null`. A failing adapter leaves preference recommendations available with an accessibility-unavailable message. Scores, ordering, personal/aesthetic weights and stored ratings are not changed. Deciding whether to filter or reorder by accessibility is a separate recommendation policy to agree on later.

## Flask and CVD wiring

The manual site runs with `python -m onboarding.server` using your virtual-environment Python. `create_app(assess_accessibility=your_function)` connects CVD assessment independently of CV. For example, a future team entry point can use:

```python
from onboarding.server import create_app
from your_cvd_module import assess_accessibility

app = create_app(assess_accessibility=assess_accessibility)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
```

Replace the example CVD module name with the actual module. Shade detection is connected independently through `/api/detect-shades`. The pulled vision implementation still needs validation; connecting it does not require a new database or additional framework, and detection should not automatically create ratings.
