# L’Oréal Color Companion

A local Flask app that learns color preferences from makeup reference photos and suggests L’Oréal lip and blush products. It uses SQLite for saved preferences, with optional computer vision for extracting reference shades.

## Guided reference flow

Color vision is a separate stage after aesthetic inspiration and before the balance slider. Save the diagnosed type and severity to continue. Details are saved per user, separately from preferences. “Unsure” is disabled for now. Profiles include numeric `severity_level`: mild = 1, moderate = 2, severe = 3. This is an ordinal encoding, not a measured severity or simulation strength. Original labels are retained, and existing profiles get the derived number when read. These details do not change recommendations until a CVD adapter is connected; see [INTEGRATION.md](INTEGRATION.md).

The site now uses Flask; the core preference model still uses only the standard library. The CV and CVD integration guide is in [INTEGRATION.md](INTEGRATION.md).

`requirements.txt` installs only Flask and its dependencies for the current site. The pulled face-extractor dependency pins are preserved separately in `requirements-vision.txt`; they are optional and have not been validated in this machine's MSYS2 Python environment. The CV teammate also needs to supply `facetracker/face_landmarker.task` (ignored by Git). The detector now resolves this path relative to its module rather than the terminal's working directory. Automatic lip and blush extraction is now connected. It requires the optional vision setup; the new `colormatcher` functions remain unused.

Frontend code is kept in one readable `onboarding/app.js`, grouped into state/helpers, crop and shade review, reference cards, file loading, saving, navigation, and recommendation rendering. `continuePersonalReferences`, `continueAestheticReferences`, and `requestRecommendations` are the main button handlers. `renderRecommendations` builds the result cards. Shared helpers also support `cvd-form.js`. Run `node tests/test_app.cjs` for lightweight frontend behavior checks, alongside the Python suite and `node tests/test_colors.cjs`.

On a standard Windows Python installation:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m onboarding.server
```

On this machine Python is from MSYS2, so the virtual environment uses `bin` instead of `Scripts`:

```powershell
.\.venv\bin\python.exe -m pip install -r requirements.txt
.\.venv\bin\python.exe -m onboarding.server
```

Open http://127.0.0.1:8000. Stop with Ctrl+C. Flask's local development server is used, with debugging off.

1. Choose a makeup category, then upload your personal reference set (up to six images at once or added incrementally). Click **Auto-detect lip shades** or **Auto-detect blush shades**, depending on the category. Alternatively, select a region by dragging or using the keyboard crop sliders and manually extract up to three shades. Review the results and uncheck shades you do not want to use. One **Use these shades & continue** action saves all checked shades as likes. No per-shade Like/Dislike loop is required; unchecked shades are ignored, not disliked.
2. Answer **Would you like to add an aesthetic reference?** Choose No for personal-only suggestions, or Yes to name an influence and upload a second set. Confirm that set in the same way. It represents your estimate of an audience's taste or a chosen aesthetic, not verified feedback from others.
3. Enter the color vision type and severity from your diagnosis. This is saved separately from taste preferences; it does not yet change recommendations.
4. Choose your balance. With a confirmed second set the slider starts at 60% personal / 40% aesthetic and allows 0–100% in five-point steps. Without a second set it is locked to 100% personal. Click **Suggest my shades**; change the slider and click again to compare results. Back buttons retain this session's reference sets without resaving completed events.

Photos remain in the browser and disappear on refresh during manual cropping. Auto-detection sends a resized photo to Flask for processing without saving it. Lip mode samples lip landmarks; blush mode samples cheek appearance (skin plus makeup). Results require review before Continue saves likes. Optional vision dependencies and the face model are required; see [INTEGRATION.md](INTEGRATION.md). JPEG/PNG/WebP up to 10 MB and 40 megapixels are accepted. Images are scaled to at most 800 pixels on the long edge; a crop is sampled at up to 160 × 160. A deterministic OKLab histogram chooses frequent separated shades, excluding pixels with alpha below 250. The sRGB conversion follows [the OKLab reference](https://bottosson.github.io/posts/oklab/). Colors are approximate appearances affected by lighting, filters, skin, teeth and reflections.

Selected color ratings are saved in SQLite, not images. Cards are frozen after confirmation begins. Stable event IDs allow retrying a partially saved set without duplicate writes. Each event commits separately; a failed set can have some saved ratings. There is no undo UI. Previous feedback under the same user/profile remains part of the model. Changing user clears the current sets; naming a different aesthetic selects a different history. The weight is a session choice, not persisted.

## Optional automatic detection setup

The manual site needs only `requirements.txt`. For automatic lip and blush extraction, use the CV teammate’s compatible Python environment and install:

```powershell
python -m pip install -r requirements-vision.txt
```

Here, `python` must be the interpreter that will run Flask. The vision dependency pins came from the teammate’s branch and have not been validated under this machine’s MSYS2 Python. Obtain the model from the CV teammate and place it at `facetracker/face_landmarker.task`, then restart Flask. The model is ignored by Git and is not included in the repository.

- **Lip:** samples the lip landmarks through the teammate’s extractor.
- **Blush:** samples the two cheeks. This estimates visible skin plus makeup, not isolated blush pigment.
- Detection expects one face. No usable result or a setup error leaves manual extraction available and preserves any existing shade review.
- Clicking detection sends the resized full photo to the app server for processing in memory. It does not save the photo or create preference ratings.

The frontend and server are connected, and automated tests cover the integration contract and stale-response handling. Actual photo detection still needs validation with the CV dependencies and model installed. See [INTEGRATION.md](INTEGRATION.md) for the RGB output contract and how to replace the detector.

## Recommendation engine

There is one public ranking method: `PreferenceService.recommend()`. It scores every supplied product and sorts the results. With no aesthetic references it uses personal preferences only; with an aesthetic profile it combines the two scores using the chosen weight.

```text
score = personal_weight * personal_score
      + (1 - personal_weight) * aesthetic_score
```

A profile with nonzero weight must have nearby evidence; otherwise the combined score is `null` (Python `None`) and sorts after known results. Missing aesthetic history forces 100% personal. Positive scores on both sides set `shared_match` to true. This is heuristic support, not verified audience approval or a probability.

The website loads products from `catalogs/<category>.json` and displays the top 12. Add products using [catalogs/README.md](catalogs/README.md). Changing category clears current reference images; saved feedback remains separated by category.

## Use from another Python program

Run from the repository root. The preference engine uses Python's standard library and SQLite; it does not require Flask or CV packages.

```python
from preference import PreferenceService, SQLiteStorage

with SQLiteStorage(":memory:") as storage:
    service = PreferenceService(storage, bandwidth=0.1)
    service.add_rating("alice", "lip", [0.7, 0.12, 0.04], 1)
    service.add_rating("alice", "lip", [0.65, 0.1, 0.03], 1,
                       preference_profile_id="environment:Friends")

    products = [
        {"name": "Rose", "color": [0.7, 0.12, 0.04]},
        {"name": "Soft rose", "color": [0.65, 0.1, 0.03]},
    ]
    result = service.recommend(
        "alice", "lip", products,
        personal_weight=0.6,
        environment_profile_id="environment:Friends",
    )
    for product in result["results"]:
        print(product["name"], product["score"])
```

Use a filename instead of `:memory:` to persist feedback. Repeating `add_rating()` appends events unless you reuse the optional `event_id` for an identical request. A reused ID with different feedback is rejected. The website requires an event ID so network retries cannot duplicate ratings.

Colors must be finite normalized **OKLab** triplets (`L` in 0..1), not RGB or CIELAB. Ratings are `1` for like or `-1` for dislike. The browser currently collects likes only; unchecked shades are ignored. Each history is identified by user, category, and preference profile. `add_rating()` defaults to `personal`; aesthetic ratings use the profile name supplied to `recommend()`.

`recommend()` returns a dictionary with `results`, effective weights and rating counts. Each product retains its metadata and gains its combined score, separate personal/environment explanations, and status. For a single color, pass a one-item product list. To read saved events directly, use `storage.get_ratings(user_id, category, preference_profile_id)`.

## How scoring works

`_score_color()` is the private calculation used for both profiles. It compares one product against every relevant rating:

```text
distance = Euclidean distance in OKLab
similarity = exp(-0.5 * (distance / bandwidth)^2) if distance < 2 * bandwidth else 0
score = strongest liked similarity - strongest disliked similarity
```

An empty side contributes zero. Each reference supports its own local neighborhood; unrelated favorites and duplicate likes do not dilute or amplify a match. Liking black and white does not imply liking gray. Close neighborhoods can overlap, and an unsupported color is unknown rather than disliked.

The default bandwidth is 0.1 and support ends at distance 0.2. This hard cutoff is a prototype parameter requiring user evaluation, not a perceptual indistinguishability threshold. Explanations show at most one nearest reference per side, its similarity and distance, plus saved event counts. A nearest reference can still be outside the cutoff with zero support. Scores range from -1 to 1; they are not probabilities.

CVD simulation is not yet applied to personal scoring. The proposed next change is to compare simulated product/reference colors for personal taste while keeping aesthetic comparisons in original OKLab. Original stored colors should remain unchanged.

## Website API

- `POST /api/rating`: save a rating with `user_id`, `category`, `color`, `rating`, `event_id`, and optional `preference_profile_id`.
- `POST /api/recommend`: send `user_id`, `category`, optional `personal_weight` and `environment_profile_id`. Products are loaded server-side; client-supplied products are ignored.
- `GET /api/catalogs`: available categories and product counts.
- `GET /api/cvd-profile` and `POST /api/cvd-profile`: read/save diagnosis details separately.

Flask calls the service directly. There is no dispatcher or ranking mode selector. The old `/api/rank` endpoint and old scoring/ranking methods have been removed; Python callers should use `recommend()` for custom product lists. The engine accepts up to 1,000 candidates.

## Files to follow

- `onboarding/app.js`: sends save/recommendation requests and displays results.
- `onboarding/server.py`: Flask routes calling the service.
- `preference/service.py`: `add_rating()`, `recommend()`, and private `_score_color()`.
- `preference/storage.py`: SQLite ratings, additive migration, and safe event retries.
- `preference/models.py`: rating record and input validation.
- `preference/distance.py`: Euclidean color distance.
- `onboarding/catalog.py`: loads product JSON.
- `onboarding/vision.py` and `facetracker/`: extraction wrappers and teammate CV implementation.
- `onboarding/cvd_profile.py` and `cvd-form.js`: diagnosis storage and form.
- `colormatcher/`: experimental color and CVD functions, separate from current ranking.

There is no longer an `onboarding/actions.py`. Comparison and profile-snapshot methods were removed because the current app does not need them. Existing comparison tables in old databases are left untouched; new databases do not create them. Existing ratings, CVD profiles and retry records are preserved. No database reset is needed.

## Checks

With your virtual environment active:

```powershell
python -m unittest discover -s tests -v
python -m examples.demo
node tests/test_app.cjs
node tests/test_colors.cjs
```

Node is only needed for the frontend checks. Tests cover scoring, profile separation, weights, request validation, retry protection and old-database preservation. They do not establish real-world CV extraction accuracy or preference prediction quality.

## Limits

This is a local prototype without authentication. SQLite stores feedback and diagnosis details locally; images are not stored. Product colors are estimated and previews may differ from real products. Ranking compares individual color appearances, not finish, skin suitability, availability, or complete-look compatibility. Photo lighting and skin influence extracted colors. An isolated noisy reference can dominate a match.

The optional accessibility adapter attaches an assessment separately and does not change ranking. CVD severity levels are ordinal labels, not calibrated simulation strengths. See [INTEGRATION.md](INTEGRATION.md) for teammate interfaces.
