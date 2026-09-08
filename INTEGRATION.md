# Teammate integration guide

Keep the three responsibilities separate:

```text
Photo -> lip detector -> suggested rectangle -> user reviews crop
      -> current palette extraction -> confirmed color likes -> preference model

Candidate colors -> preference ranking -> attach CVD assessment -> display
```

The preference model never receives images or CVD data. Flask is only the HTTP layer. There are no abstract base classes, plugin registries, queues, or new databases.

## Files

- `onboarding/server.py`: Flask routes and two optional integration functions.
- `onboarding/actions.py`: existing rating persistence and preference request handling.
- `onboarding/integrations.py`: two small return-value dataclasses with validation.
- `preference/`: existing SQLite preference model; unchanged by Flask/CV/CVD integration.
- `onboarding/app.js`: guided upload flow, manual crop, optional detection button, results.

## Connect the lip detector

Write a function with this signature:

```python
from onboarding.integrations import MakeupRegion

def detect_region(image_bytes: bytes, category: str) -> MakeupRegion | None:
    # Decode PNG, run your model, get image dimensions W/H and bbox x/y/w/h.
    # Validate actual decoded image contents in your detector.
    # Return None if no usable region is detected.
    return MakeupRegion(x / W, y / H, w / W, h / H)
```

The variables in the example come from your model, not this project. Coordinates are fractions in [0, 1], measured from the top-left of the **supplied image**, with positive width/height and the rectangle entirely inside the image. The browser sends its oriented, resized canvas as PNG, so the returned box aligns with the visible reference. Do not return original-photo pixel coordinates or EXIF-rotated coordinates.

Flask calls this through `POST /api/detect-region`, multipart field `image`. Current category is `lip`. A valid response is `{"region": {"x": 0.3, "y": 0.6, "width": 0.4, "height": 0.15}}`. A missing detector or no detection returns `region: null`. Adapter exceptions/invalid boxes return 503 with a manual-crop message. Images are held in memory, not saved by this app. If your detector uses an external service, document that data transfer before enabling it.

Once connected, each reference gets a **Suggest lip region** button. Users can adjust the result and must still extract/review shades before saving preferences. Detection itself creates no likes. Existing manual crop and palette extraction keep working. Segmentation masks and model-specific preprocessing stay inside your CV code; this first adapter only exchanges a rectangle.

## Connect CVD assessment

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

## Wire both functions in one place

Create a team entry point such as `team_app.py` at the project root:

```python
from onboarding.server import create_app
from your_vision_module import detect_region
from your_cvd_module import assess_accessibility

app = create_app(
    detect_region=detect_region,
    assess_accessibility=assess_accessibility,
)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
```

Replace those two example module names with your teammates' actual modules. Both arguments are optional; `python -m onboarding.server` runs the app with manual cropping and no CVD assessment. Flask's `create_app(database=...)` parameter lets tests use temporary SQLite files. `/api/capabilities` tells the browser which integrations are connected. See [Flask's quickstart](https://flask.palletsprojects.com/en/stable/quickstart/) for the HTTP framework basics.
