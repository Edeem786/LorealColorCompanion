"""Teammate-owned lip shade detection. Not connected to the UI yet."""


def detect_lip_shades(image_bytes: bytes) -> list[list[int]]:
    """Return distinct lip shades as sRGB [R, G, B] integers in 0..255.

    Input: the browser's oriented/resized full reference image, encoded as PNG.
    Return [] when no usable lips/shades are detected. Do not return black as
    an error placeholder. Convert OpenCV BGR output to RGB before returning.
    Detection and shade extraction both belong in this function.
    """
    raise NotImplementedError("Lip shade detection will be implemented by the CV teammate.")
