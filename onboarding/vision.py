"""Teammate shade extraction. Requires optional CV dependencies and model file.

Not connected to the UI yet; the manual flow does not import this module.
"""
from facetracker.facecolorextractor import find_color, FaceLandmark

# Predefined points
LIP_SAMPLE_POINTS = {
    "upper_lip": FaceLandmark.UPPER_LIP_CENTER,
    "lower_lip": FaceLandmark.LOWER_LIP_CENTER,
    "left_corner": FaceLandmark.LEFT_MOUTH_CORNER,
    "right_corner": FaceLandmark.RIGHT_MOUTH_CORNER,
}

SKIN_SAMPLE_POINTS = {
    "left_cheek": FaceLandmark.LEFT_CHEEK,
    "right_cheek": FaceLandmark.RIGHT_CHEEK,
    "forehead": FaceLandmark.FOREHEAD_CENTER,
    "nose_bridge": FaceLandmark.NOSE_BRIDGE,
    "chin": FaceLandmark.CHIN,
}

EYE_SAMPLE_POINTS = {
    "left_iris": FaceLandmark.LEFT_IRIS_CENTER,
    "right_iris": FaceLandmark.RIGHT_IRIS_CENTER,
}


def detect_skin_shades(image_bytes: bytes) -> list[list[int]]:
    """Return distinct skin shades as sRGB [R, G, B] integers in 0..255.

    Input: the browser's oriented/resized full reference image, encoded as PNG.
    Return [] when no usable skin/shades are detected. Do not return black as
    an error placeholder. Convert OpenCV BGR output to RGB before returning.
    Detection and shade extraction both belong in this function.
    """
    results = find_color(image_bytes, SKIN_SAMPLE_POINTS)

    if not results:
        return []

    shades = [r["color_rgb"] for r in results]
    return _dedupe_shades(shades)


def detect_lip_shades(image_bytes: bytes) -> list[list[int]]:
    """Return distinct lip shades as sRGB [R, G, B] integers in 0..255.

    Input: the browser's oriented/resized full reference image, encoded as PNG.
    Return [] when no usable lips/shades are detected. Do not return black as
    an error placeholder. Convert OpenCV BGR output to RGB before returning.
    Detection and shade extraction both belong in this function.
    """

    results = find_color(image_bytes, LIP_SAMPLE_POINTS)
    if not results:
        return []
    shades = [r["color_rgb"] for r in results]
    return _dedupe_shades(shades)


def detect_eye_shades(image_bytes: bytes) -> list[list[int]]:
    """Return distinct iris shades as sRGB [R, G, B] integers in 0..255.

    Input: the browser's oriented/resized full reference image, encoded as PNG.
    Return [] when no usable eye/shades are detected. Do not return black as
    an error placeholder. Convert OpenCV BGR output to RGB before returning.
    Detection and shade extraction both belong in this function.
    """
    results = find_color(image_bytes, EYE_SAMPLE_POINTS)
    if not results:
        return []
    shades = [r["color_rgb"] for r in results]
    return _dedupe_shades(shades)


def _dedupe_shades(shades: list[list[int]], threshold: int = 10) -> list[list[int]]:
    """Collapse near-identical RGB shades (e.g. upper/lower lip nearly the same color)."""
    distinct = []
    for shade in shades:
        is_duplicate = False
        for existing in distinct:
            diff = sum(abs(a - b) for a, b in zip(shade, existing))
            if diff < threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            distinct.append(shade)
    return distinct
