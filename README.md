# L’Oréal Color Companion

An accessibility-focused makeup discovery prototype built for a L’Oréal hackathon. Color Companion learns color preferences from makeup reference photos and suggests products from a local catalog of L’Oréal lip and blush shades.

Users can add a second reference set representing an aesthetic or an audience’s taste, choose how much each set matters, and supply a diagnosed color-vision profile for approximate personal color matching.

## Features

- Guided flow: personal references, optional aesthetic inspiration, color vision, optional skin tone, and recommendations.
- Manual cropping and shade extraction, with optional automatic lip, cheek, and skin detection.
- Separate personal and aesthetic preference histories with an adjustable balance.
- Approximate Machado CVD simulation for supported profiles.
- Optional skin-tone color-coherence factor for blush.
- Local SQLite storage, a Flask backend, and a responsive HTML/CSS/JavaScript frontend.

## Quick start

Use a standard CPython installation. Python 3.12 has been used to verify the Flask and CVD setup. No frontend build step or npm installation is required.

From the repository root:

### Windows (PowerShell)

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m onboarding.server
~~~

### macOS / Linux

~~~sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m onboarding.server
~~~

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Stop the server with Ctrl+C. This uses Flask’s local development server.

The base installation supports manual shade extraction and original-color matching.

### Optional CVD simulation

Using the same activated environment that runs Flask:

~~~sh
python -m pip install -r requirements-cvd.txt
~~~

On Windows, use the environment’s Scripts/python.exe directly if it is not activated. CVD matching needs colour-science and NumPy, but no face model. If pip attempts to compile NumPy under MSYS2, use a separate standard CPython environment.

### Optional automatic detection

~~~sh
python -m pip install -r requirements-vision.txt
~~~

Provide a compatible MediaPipe Face Landmarker model at **facetracker/face_landmarker.task**, then restart Flask. The model is not included in the repository.

The vision dependency set and real-photo accuracy require validation in the target environment. Manual cropping remains available when detection is unavailable. See [INTEGRATION.md](INTEGRATION.md) for detector interfaces and setup details.

## Using the app

1. **Choose a profile ID and makeup category.** Upload up to six personal reference images. Crop the relevant makeup area or use automatic detection, then review the shades. Continuing saves checked shades as likes; unchecked shades are ignored.
2. **Optionally add aesthetic inspiration.** Name an influence, such as friends or a workplace, and upload another reference set. This represents your estimate of that audience’s taste, not feedback collected from them.
3. **Enter your diagnosed color-vision type and severity.** Saved details load for the selected profile ID. New profiles have no diagnosis selected. The “Unsure” option is not implemented.
4. **Optionally add skin samples.** Upload one photo of bare skin in even lighting, extract samples, and review them. These measurements affect blush only. Samples can be reused, replaced, removed, or skipped.
5. **Set your balance and request suggestions.** With aesthetic references, the slider starts at 60% personal and 40% aesthetic. Without them, it uses 100% personal. After changing the balance, request suggestions again.

The initial profile ID is **demo-user**. Reusing an ID loads its saved history, including color-vision details. Choose a different ID for a separate person. IDs are local identifiers, not authenticated accounts.

Supported images: JPEG, PNG, and WebP, up to 10 MB and 40 megapixels per image.

## How recommendations work

The engine scores every product in the selected catalog and displays the top 12.

Each reference supports nearby colors in OKLab, a perceptual color space. Candidates are compared with individual references rather than their average: liking black and white does not automatically imply liking gray.

For each preference profile:

~~~text
similarity = exp(-0.5 × (distance / bandwidth)²)
profile score = strongest liked similarity − strongest disliked similarity
~~~

Similarity is zero outside twice the bandwidth. The default bandwidth is 0.1. The engine supports dislikes, but the current interface collects likes only.

Personal and aesthetic scores are combined using the selected weights. A required profile without nearby evidence produces an unknown score, which sorts after supported matches. Scores are heuristic similarities, not probabilities of liking a product.

For supported CVD profiles, both personal references and candidate products are simulated before measuring their distance. Aesthetic matching uses original colors. Mild, moderate, and severe map to prototype strengths of **0.33, 0.66, and 1.0**, not calibrated severity measurements. Unsupported profiles or unavailable simulation use original-color matching with an explanation.

For blush, optional skin samples apply a hue/chroma coherence factor to positive preference scores. This is experimental and does not establish cosmetic suitability. Product previews show original catalog colors.

## Data and privacy

- Preferences, skin samples, and entered diagnosis details are saved locally in **data/preferences.db**.
- Manual cropping processes photos in the browser. Automatic detection sends a resized photo to the app server for processing in memory; photos are not saved.
- Refreshing clears uploaded images. Previously confirmed preferences remain saved.
- Lip and blush histories are separate. Skin samples are stored separately from preferences.
- Saving new skin samples replaces previous samples. Skipping keeps them stored but excludes them from the current suggestions.

The application has no authentication and is intended for local prototype use.

## Product catalogs

Product data lives in **catalogs/**, with one JSON file per category. See [catalogs/README.md](catalogs/README.md) for the format and instructions for adding shades or categories.

Catalog colors are estimates. The app does not check live stock, prices, or purchasing availability.

## Project structure

| Path | Purpose |
| --- | --- |
| onboarding/server.py | Flask entry point and API routes |
| onboarding/index.html, style.css | Page structure and responsive styling |
| onboarding/app.js, colors.js | Reference review, cropping, color conversion, and results |
| onboarding/cvd-form.js, skin-form.js | Color-vision and skin-tone steps |
| preference/ | Preference scoring, validation, and SQLite storage |
| onboarding/vision.py, facetracker/ | Automatic shade extraction |
| colormatcher/ | CVD simulation and color-coherence helpers |
| catalogs/ | Product shade data |
| tests/ | Backend and frontend checks |

The frontend uses rose and ivory surfaces, burgundy actions, serif headings, and native form controls. Fonts are local system fonts; no external font service is required.

For API contracts and extension points, see [INTEGRATION.md](INTEGRATION.md). The preference engine can also be used independently through PreferenceService and SQLiteStorage; see [examples/demo.py](examples/demo.py).

## Tests

With the project environment activated:

~~~sh
python -m unittest discover -s tests -v
python -m examples.demo
node tests/test_app.cjs
node tests/test_colors.cjs
~~~

Node.js is needed only for frontend checks. Tests cover scoring, profile separation, request validation, saving and retry behavior, and frontend interactions. They do not establish real-world extraction accuracy or preference prediction quality.

## Limitations

This is a hackathon prototype, not a diagnostic tool or a validated cosmetic suitability assessment. It assumes users already have a diagnosis. CVD simulation, particularly tritan simulation, is approximate.

Photo lighting, filters, skin, and reflections influence extracted shades. Cheek detection samples visible skin plus makeup rather than isolating blush pigment. Matching individual colors does not model finish, wear, or compatibility across an entire makeup look. A weighted compromise does not guarantee that the user or their chosen audience will like the result.
