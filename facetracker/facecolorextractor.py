import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import cv2
import os

from enum import IntEnum

class FaceLandmark(IntEnum):
    """
    Key MediaPipe Face Landmarker indices for major face regions.
    Each name maps to a single representative point for that region —
    good for skin sampling, not a full outline of the region.
    """

    LEFT_CHEEK = 50
    RIGHT_CHEEK = 280

    FOREHEAD_CENTER = 151
    FOREHEAD_LEFT = 104
    FOREHEAD_RIGHT = 333

    NOSE_TIP = 1
    NOSE_BRIDGE = 6
    LEFT_NOSTRIL = 129
    RIGHT_NOSTRIL = 358

    CHIN = 175
    LEFT_JAW = 172
    RIGHT_JAW = 397

    LEFT_EYE_OUTER = 33
    LEFT_EYE_INNER = 133
    RIGHT_EYE_OUTER = 362
    RIGHT_EYE_INNER = 263

    LEFT_EYEBROW_INNER = 55
    LEFT_EYEBROW_OUTER = 46
    RIGHT_EYEBROW_INNER = 285
    RIGHT_EYEBROW_OUTER = 276

    UPPER_LIP_CENTER = 13
    LOWER_LIP_CENTER = 14
    LEFT_MOUTH_CORNER = 61
    RIGHT_MOUTH_CORNER = 291

    LEFT_UNDER_EYE = 145
    RIGHT_UNDER_EYE = 374


SKIN_SAMPLE_POINTS = {
    "left_cheek": FaceLandmark.LEFT_CHEEK,
    "right_cheek": FaceLandmark.RIGHT_CHEEK,
    "forehead": FaceLandmark.FOREHEAD_CENTER,
    "nose_bridge": FaceLandmark.NOSE_BRIDGE,
    "chin": FaceLandmark.CHIN,
}


def load_image(image_source):
    """Load an image into a BGR numpy array, from either a file path or raw bytes.

    image_source: str/path -> loaded via cv2.imread
                   bytes    -> decoded via cv2.imdecode (e.g. PNG/JPEG bytes in memory)
    Returns None if decoding/reading fails.
    """
    if isinstance(image_source, (bytes, bytearray)):
        arr = np.frombuffer(image_source, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    else:
        return cv2.imread(image_source)


def get_landmarks(image):
    """Detect face landmarks in an already-loaded BGR image array."""
    base_options = python.BaseOptions(model_asset_path="face_landmarker.task")
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        num_faces=1
    )
    detector = vision.FaceLandmarker.create_from_options(options)

    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB,
                         data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    result = detector.detect(mp_image)

    if not result.face_landmarks:
        return None

    h, w = image.shape[:2]
    landmarks = result.face_landmarks[0]
    points = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]

    return points


def visualize_point(image, points, index, color=(0, 255, 0)):
    x, y = points[index]
    cv2.circle(image, (x, y), 4, color, -1)
    cv2.putText(image, str(index), (x+5, y-5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)


def sample_patch(image, center, patch_size=15):
    x, y = center
    half = patch_size // 2
    h, w = image.shape[:2]

    x1, x2 = max(0, x - half), min(w, x + half)
    y1, y2 = max(0, y - half), min(h, y + half)

    return image[y1:y2, x1:x2]


def get_average_color(patch, color_space="LAB"):
    if color_space == "LAB":
        patch = cv2.cvtColor(patch, cv2.COLOR_BGR2LAB)
    pixels = patch.reshape(-1, 3)
    return np.mean(pixels, axis=0)


def get_robust_skin_color(patch):
    lab = cv2.cvtColor(patch, cv2.COLOR_BGR2LAB)
    pixels = lab.reshape(-1, 3).astype(np.float32)

    from sklearn.cluster import KMeans
    kmeans = KMeans(n_clusters=2, n_init=10, random_state=42)
    labels = kmeans.fit_predict(pixels)

    counts = np.bincount(labels)
    dominant_cluster = np.argmax(counts)

    return kmeans.cluster_centers_[dominant_cluster]


def extract_skin_color(image, sample_points=None):
    """image must already be a loaded BGR numpy array (see load_image)."""
    if sample_points is None:
        sample_points = SKIN_SAMPLE_POINTS

    points = get_landmarks(image)
    if points is None:
        raise ValueError("No face detected")

    results = []
    for name, idx in sample_points.items():
        if idx >= len(points):
            print(f"Warning: index {idx} ('{name}') is out of range for detected landmarks — skipping")
            continue

        patch = sample_patch(image, points[idx], patch_size=15)
        if patch.size == 0:
            continue
        color = get_robust_skin_color(patch)
        results.append({
            "name": name,
            "index": idx,
            "pixel_coords": points[idx],
            "color_lab": color
        })

    return results


def find_color(image_source, sample_points=None):
    """image_source: a file path (str) or raw image bytes."""
    image = load_image(image_source)
    if image is None:
        print(f"Could not load image from: {image_source!r}")
        return None

    try:
        results = extract_skin_color(image, sample_points)
    except ValueError as e:
        print(str(e))
        return None

    if not results:
        print("No valid patches sampled — check landmark indices / image size")
        return None

    for r in results:
        lab_patch = np.uint8([[r["color_lab"]]])
        rgb = cv2.cvtColor(lab_patch, cv2.COLOR_LAB2RGB)[0][0]
        r["color_rgb"] = rgb.tolist()
        r["color_lab"] = r["color_lab"].tolist()

    return results