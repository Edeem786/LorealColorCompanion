# Teammate integration guide

## Current status

The UI now supports manual extraction and automatic lip/blush detection in both reference sets. Clicking Auto-detect sends the resized photo to Flask, without saving the image. Detection fills review checkboxes; Continue saves likes.

`onboarding/vision.py` provides lip extraction and a cheek-only blush sampler. Blush samples visible skin-plus-makeup appearance, not isolated pigment. Skin extraction is also used by the separate skin-tone step; the iris helper remains separate. Install the optional `requirements-vision.txt` dependencies in the teammate's compatible environment and supply `facetracker/face_landmarker.task`. Real model detection remains unvalidated here because those dependencies and the model are missing. Missing setup produces a manual fallback message.

## RGB contract

Return a list of up to 12 distinct representative lip shades:

```python
[[180, 80, 100], [195, 105, 125]]
```

Each triplet must be **sRGB**, channel order **R, G, B**, with Python integers from **0 to 255**. Convert NumPy values with `.tolist()` for JSON. OpenCV often uses BGR: swap channels before returning. If your model returns normalized 0–1 values, convert them to 0–255 integers first. Do not send linear RGB, CIELAB or OKLab through this RGB interface.

RGB is sufficient for this MVP. A bounding box, mask, confidence and pixel coverage are optional future additions, not required. Return `[]` if no usable lip colors are found; never use `[0, 0, 0]` as an error value. For multiple faces, initially return no result and ask the user to crop to one face, unless the team explicitly agrees on a selection rule. Do not silently combine people's lip shades.

The request supplies the oriented, resized **full reference image as PNG bytes**. The detector owns image decoding, lip segmentation and shade extraction. Inspect the resized input quality when integrating; the current browser limits the long edge to 800 pixels. If the model needs higher resolution, agree on that before changing the upload contract.

## How to change the detector

1. Update `detect_lip_shades` or `detect_blush_shades` in `onboarding/vision.py`, preserving the RGB contract. Imports are lazy so manual use does not require CV packages.
2. Alternatively pass `create_app(detect_shades=your_function)`. It takes `(image_bytes, category)` and returns the RGB list.
3. `POST /api/detect-shades` accepts multipart fields `image` (PNG) and `category` (`lip`, `blush` or `skin_tone`). It checks upload size, PNG header/dimensions (up to 800 pixels per side) and returned RGB values. The detector decodes the image. Success returns `{"shades": [...]}`; setup or detector failure returns a 503 error with manual fallback guidance.
4. `detectReferenceShades` uploads and populates `showReferenceShades`. Empty/error results preserve existing shades. Responses are ignored after removal, manual extraction, crop changes, profile/category changes or freezing. No ratings are created by detection.
5. Validate actual photos in the teammate's environment. The landmark detector accepts exactly one face, rejecting no-face and multiple-face results.

The old rectangle-only endpoint, separate lip/skin endpoints and accessibility-score adapter have been removed. Skin extraction is used for skin-tone measurements; iris extraction remains a Python helper. `colormatcher/colormath.py` remains experimental; `cvdsimulator.py` is connected to personal ranking.

## Manual extraction explained

`extract` in `onboarding/app.js` samples the chosen rectangle at up to 160 × 160 pixels. `palette` in `onboarding/colors.js` then:

1. Ignores pixels whose alpha is below 250.
2. Converts each sampled RGB pixel to normalized OKLab.
3. Places pixels in small OKLab bins (0.025 units along each axis).
4. Sorts bins by pixel count.
5. Computes the arithmetic mean RGB of each candidate bin, rounding to integers.
6. Selects up to three shades, skipping ones within 0.045 OKLab distance of a previously selected shade.

So this is a frequent-color-bin method with a mean **within each bin**, not a median or a mean of the entire rectangle. It does not identify lip pixels: teeth, skin or reflections can win if included in the crop. The CV model can improve precisely that separation. Both methods feed the same RGB review helper and preference model.

## CVD personal matching

The form saves diagnosis type and severity in `cvd_profiles`, separate from ratings. Labels map to ordinal levels: mild=1, moderate=2, severe=3. `colormatcher/cvdsimulator.py` maps those to the hackathon simulation presets **0.33, 0.66, 1.0**. These presets are not measured severity. Unsure stays disabled. Other diagnosed types are stored but not simulated.

On each `/api/recommend` request:

1. Flask reads the saved profile and calls `make_cvd_transform(type, severity_level)` to build one Machado matrix.
2. `PreferenceService.recommend(..., personal_transform=transform)` copies and transforms personal rating colors once (including explicit dislikes, when present).
3. For each catalog product, it transforms the candidate and compares it with transformed personal references. The aesthetic comparison uses original candidate and reference colors.
4. Existing strongest-match scoring, cutoff, unknown handling and weighting apply. At zero personal weight, the engine skips transformation.
5. SQLite records, catalog coordinates and displayed swatches remain original. No additional accessibility score is generated.

The simulator converts OKLab → XYZ → linear sRGB → Machado matrix → XYZ → OKLab. Encoding/decoding transfer functions are explicitly disabled around linear RGB. Out-of-gamut RGB is clipped before and after the simulation, consistently for candidates and references. This can collapse distinct estimated catalog colors to similar appearances. The same OKLab neighborhood cutoff is used as a prototype; it still needs user evaluation after simulation.

`make_cvd_transform` returns a plain callable taking one OKLab triplet and returning one simulated triplet. `simulate_cvd_oklab(color, type, level)` is a convenience for standalone single-color use. Severity input is strictly an integer level 1, 2, or 3, not an ambiguous raw strength.

Install the smaller simulation dependency set with:

```powershell
python -m pip install -r requirements-cvd.txt
```

The real simulation has been checked using the project's separate `.venv-cvd` environment. The original MSYS2 `.venv` remains unchanged. Computer vision model extraction still requires its separate dependencies and model file.

Missing diagnosis, unsupported types, missing packages or simulation failure produce recommendations using original colors with an explicit `cvd.applied: false` and explanation. Successful simulation returns `cvd.applied: true`, type and numerical preset. The browser displays this message above results. Aesthetic-only results state that only original colors are used. Tritan simulation is explicitly identified as particularly approximate, following the library's warning.

Sources: [Machado matrix implementation](https://colour.readthedocs.io/en/v0.4.7/generated/colour.matrix_cvd_Machado2009.html), [linear RGB conversion](https://colour.readthedocs.io/en/develop/generated/colour.XYZ_to_RGB.html).

## Skin samples

The skin-tone stage follows CVD and precedes balance. The shared detector routes `skin_tone` to `detect_skin_shades`; manual cropping is also available. `POST /api/skin-tone` replaces confirmed samples in category `skin_tone`, personal profile, without changing makeup preference events. `GET /api/skin-tone` reloads them. `colors: []` clears stored samples.

Blush ranking uses the existing `coherence` helper on original skin and product colors as a multiplicative factor for positive preference scores. Unknown and negative scores retain their previous meaning. `use_skin_tone: false` skips it for a request; lip ranking always skips it. This connects the existing heuristic without switching the app to the experimental `compare_single()` path.
