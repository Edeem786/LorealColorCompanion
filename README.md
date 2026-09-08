# Individual color preferences

## Guided reference flow

Color vision is a separate stage after aesthetic inspiration and before the balance slider. Save the diagnosed type and severity to continue. Details are saved per user, separately from preferences. “Unsure” is disabled for now. Profiles include numeric `severity_level`: mild = 1, moderate = 2, severe = 3. This is an ordinal encoding, not a measured severity or simulation strength. Original labels are retained, and existing profiles get the derived number when read. These details do not change recommendations until a CVD adapter is connected; see [INTEGRATION.md](INTEGRATION.md).

The site now uses Flask; the core preference model still uses only the standard library. The CV and CVD integration guide is in [INTEGRATION.md](INTEGRATION.md).

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

1. Choose a makeup category, then upload your personal reference set (up to six images at once or added incrementally). Select the matching makeup region by dragging or using its keyboard crop sliders. Extract up to three shades per photo and uncheck shades you do not want to use. One **Use these shades & continue** action saves all checked shades as likes. No per-shade Like/Dislike loop is required; unchecked shades are ignored, not disliked.
2. Answer **Would you like to add an aesthetic reference?** Choose No for personal-only suggestions, or Yes to name an influence and upload a second set. Confirm that set in the same way. It represents your estimate of an audience's taste or a chosen aesthetic, not verified feedback from others.
3. Choose your balance. With a confirmed second set the slider starts at 60% personal / 40% aesthetic and allows 0–100% in five-point steps. Without a second set it is locked to 100% personal. Click **Suggest my shades**; change the slider and click again to compare results. Back buttons retain this session's reference sets without resaving completed events.

Photos remain in the browser and disappear on refresh during manual cropping. The **Auto-detect lip shades** button is currently a disabled placeholder: it sends no image and changes no preferences. The teammate skeleton in `onboarding/vision.py` will return sRGB shades; [INTEGRATION.md](INTEGRATION.md) explains the future connection. JPEG/PNG/WebP up to 10 MB and 40 megapixels are accepted. Images are scaled to at most 800 pixels on the long edge; a crop is sampled at up to 160 × 160. A deterministic OKLab histogram chooses frequent separated shades, excluding pixels with alpha below 250. There is no automatic lip detection. The sRGB conversion follows [the OKLab reference](https://bottosson.github.io/posts/oklab/). Colors are approximate appearances affected by lighting, filters, skin, teeth and reflections.

Selected color ratings are saved in SQLite, not images. Cards are frozen after confirmation begins. Stable event IDs allow retrying a partially saved set without duplicate writes. Each event commits separately; a failed set can have some saved ratings. There is no undo UI. Previous feedback under the same user/profile remains part of the model. Changing user clears the current sets; naming a different aesthetic selects a different history. The weight is a session choice, not persisted.

## Weighted suggestions

`rank_weighted` scores both profiles separately, then uses:

```text
score = personal_weight * personal_score
      + (1 - personal_weight) * aesthetic_score
```

It sorts by the weighted score, not by an intersection-first rule. This permits a user-chosen tradeoff; a positive combined score does not establish that both parties like the shade. Results with positive nearby evidence in both profiles are labeled accordingly. If a profile with nonzero weight lacks nearby evidence, the blended score is `null` and is listed after scored candidates. A zero-weight profile cannot block a result. Nearby evidence means a liked/disliked mean similarity of at least 0.1, a prototype threshold rather than calibrated confidence. Missing aesthetic history forces 100% personal; omitting the second set in the UI also ignores any prior aesthetic history.

```python
result = model.rank_weighted(
    "alice", "lip", candidates, personal_weight=0.6,
    environment_profile_id="environment:Friends",
)
```

`result` contains ranked `results`, the effective weights and rating counts. Each candidate contains its score, both evidence explanations, and a shared-match flag. `/api/rank` accepts `mode: "weighted"`, `personal_weight` (0–1), and optional `environment_profile_id`. The older `personal` and `shared` modes remain available for callers; `rank_shared` still implements the earlier minimum-score intersection heuristic.

The site now recommends products from `catalogs/<category>.json`, showing the top 12 with product names, shade names and estimated previews. The supplied 26-item blush list is in `catalogs/blush.json`; `catalogs/lip.json` contains the supplied 52 lipsticks (source category `lipstick` mapped to `lip`). Add more files using the format in [catalogs/README.md](catalogs/README.md), then refresh the browser. Empty categories are disabled. Switching category clears the current reference session; saved ratings remain separated by category.

`GET /api/catalogs` lists available categories and counts. `POST /api/recommend` accepts the usual user/profile weights plus `category`; it loads candidates on the server and ignores any client-supplied candidates. The existing `/api/rank` remains available for testing arbitrary colors. Both support up to 1,000 candidates. `/api/rating` now accepts `category` (legacy default `lip`). The site explicitly supplies its selected category, and the CVD adapter receives that category too.

Catalog colors are treated as normalized OKLab and retained exactly as supplied. Their source is estimated, not independently measured. CSS OKLab swatches are approximate and may clip colors outside the display gamut. Catalog inclusion is not live availability verification. Unknown/distant evidence remains unknown, rather than inventing a confident recommendation. The model still evaluates individual colors, not complete-look compatibility. CVD stays separate.

## Profiles and local operation

Core rating, comparison, prediction and profile methods accept `preference_profile_id`, defaulting to `personal`. It is separate from user and makeup category. The UI uses `environment:` plus the trimmed, case-sensitive aesthetic name. Existing databases migrate additively and old feedback becomes personal. `/api/rating` accepts `user_id`, `event_id`, `color`, `rating`, and optional `preference_profile_id`; the browser confirms positive ratings, while the core still supports dislikes and comparisons.

This is a loopback-only local prototype with no authentication. Labels, keyboard crop controls and live feedback support accessible operation; it has not undergone a full accessibility evaluation. Optional JavaScript checks: `node tests/test_colors.cjs`. Node is not required to run the app.

## Run

Use Python 3.10 or newer from the repository root. Install requirements.txt in your virtual environment first; Flask is needed for web tests.

```sh
.\.venv\bin\python.exe -m unittest discover -s tests -v
python -m examples.demo
```

## API

```python
from preference import PreferenceService, SQLiteStorage

with SQLiteStorage("data/preferences.db") as storage:
    model = PreferenceService(storage, bandwidth=0.1, neighbors=3)
    model.add_rating("user-1", category="blush", color=[0.7, 0.12, 0.04], rating=1)
    model.add_rating("user-1", category="blush", color=[0.5, 0.25, 0.15], rating=-1)
    model.add_comparison(
        "user-1", category="lip",
        color_a=[0.6, 0.1, 0.04], color_b=[0.4, 0.2, 0.1], preferred="a",
    )
    score = model.predict_preference("user-1", "blush", [0.71, 0.12, 0.05])
    explanation = model.explain_preference("user-1", "blush", [0.71, 0.12, 0.05])
    ranked = model.rank_colors("user-1", "blush", [
        {"name": "Sample 01", "color": [0.71, 0.12, 0.05], "finish": "matte"},
        {"name": "Sample 02", "color": [0.51, 0.24, 0.15]},
    ])
    profile = model.get_profile("user-1")
    liked = profile.categories["blush"].liked_colors
```

Colors must be three finite numeric components in **normalized OKLab** (`L` from 0 to 1). The `a` and `b` axes may be negative. No RGB/hex conversion or display-gamut validation is provided. Do not pass CIELAB or RGB values as OKLab. Categories are arbitrary nonempty, case-sensitive strings representing makeup roles; callers should use consistent identifiers such as `lip`, `blush`, `eyeshadow`, and `foundation`. They are not color labels.

`predict_preference` returns a float in [-1, 1]. Positive means evidence toward liking; negative means evidence toward disliking. This is **not a probability**. Zero can indicate no feedback, distant evidence, or a balance of conflicting feedback.

`explain_preference` returns `score`, a human-readable `reason` list, and `evidence`. For liked and disliked evidence separately, it reports the total rating count, number used, mean similarity, and selected examples with distance, similarity, and UTC timestamp. `rank_colors` preserves candidate metadata, adds these fields, and sorts descending; ties retain input order. Existing `score`, `reason`, and `evidence` fields are replaced. Other metadata is not used to score.

## Heuristic

For a candidate, fetch only that user's ratings in the requested category. Separately select up to three nearest positive events and three nearest negative events by Euclidean distance:

```text
distance = sqrt((L1-L2)^2 + (a1-a2)^2 + (b1-b2)^2)
similarity = exp(-0.5 * (distance / bandwidth)^2)
score = mean(liked similarities) - mean(disliked similarities)
```

An empty side contributes zero. Similarities are in [0, 1], so the difference stays in [-1, 1]. Distant evidence contributes close to zero. Local neighbors reduce dilution from many unrelated favorites, though up to two unrelated neighbors can still dilute an isolated favorite. The default `0.1` bandwidth and three neighbors are prototype choices, not empirically validated parameters. Explanations flag weak evidence below similarity 0.1 and conflict when both sides reach 0.1 and their difference is below 0.1; these are descriptive thresholds, not confidence estimates.

Replace the distance through `PreferenceService(storage, distance=your_function)`. The function accepts two color tuples and must return a finite nonnegative number. Changing metrics requires checking coordinate conventions and retuning bandwidth. CIEDE2000 would require conversion to CIELAB as well as its distance calculation; it cannot consume OKLab directly.

## Structure and storage

- `preference/models.py`: rating/comparison records and user/category profile snapshots.
- `preference/storage.py`: SQLite persistence and profile reconstruction.
- `preference/distance.py`: default distance function.
- `preference/service.py`: predictions, explanations, and ranking.
- `tests/`: synthetic behavior and persistence tests.

SQLite contains append-only `ratings` and `comparisons` tables, indexed by `(user_id, category)`. Each event includes user, category, color coordinates, feedback, and a timezone-aware UTC timestamp. Comparisons retain both vectors and the chosen side for future ranking approaches. Choosing A over B does not mean A is liked or B disliked, so comparisons do not currently affect predictions.

Calls commit writes before returning. Unknown users require no registration and receive neutral predictions. Profiles are snapshots; mutating them does not save changes. Repeated ratings are separate evidence and can occupy multiple neighbor slots. There is no deduplication, revision policy, or recency decay. Use the context manager to close connections. Each storage instance is intended for one thread; this is not a service-scale connection pool. Ranking fetches ratings once per call, then scores each candidate. Prediction scans/sorts the relevant history, appropriate for a small prototype.

## Scope and limitations

This predicts preferences for individual colors in a makeup role. It does **not** evaluate complete looks: liking A, B, and C separately does not imply liking them together. It contains no CVD profile, accessibility scoring, audience appeal, skin-tone rules, finish effects, or cross-product compatibility. Foundation suitability in particular cannot be inferred from color liking alone.

Scores depend on bandwidth and sparse/noisy self-reported feedback. Duplicate events can dominate local neighborhoods. Conflicting feedback is retained and may cancel out. There is no calibrated uncertainty, population prior, or claim of objective attractiveness. Synthetic tests validate behavior, not real-user recommendation quality. SQLite is local, unencrypted storage; user identifiers and feedback remain in the chosen file.

## Future extensions

- Bradley–Terry or another ranking model can learn relative preferences from the stored comparisons.
- Bayesian preference learning can represent uncertainty and guide which feedback to request.
- Contextual bandits can explore options with user consent and incorporate occasions or product attributes.
- Collaborative filtering can use feedback across consenting users once enough data exists, while retaining individual control.
- Complete-look preferences need separate feedback on combinations, with makeup roles and context recorded.
- Audience appeal needs actual ratings from a defined audience, with sample counts and uncertainty. It should remain distinct from personal preference and CVD accessibility.

These extensions are intentionally not implemented. Evaluate the heuristic with user feedback before choosing a more complex model.
