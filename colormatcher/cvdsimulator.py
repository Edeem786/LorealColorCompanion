"""Machado CVD simulation for personal matching, using prototype severity presets."""
from preference.models import validate_color

SEVERITY_MAP = {1: 0.33, 2: 0.66, 3: 1.0}
DEFICIENCY_NAMES = {
    "protan": "Protanomaly",
    "deutan": "Deuteranomaly",
    "tritan": "Tritanomaly",
}


def make_cvd_transform(cvd_type, severity_level):
    """Build one matrix and return a color -> simulated OKLab function.

    Presets are not measured severity. Tritan is particularly approximate.
    Imports are lazy so missing optional packages don't prevent Flask startup.
    """
    if cvd_type not in DEFICIENCY_NAMES:
        raise ValueError("This color vision type is not supported by the simulator.")
    if type(severity_level) is not int or severity_level not in SEVERITY_MAP:
        raise ValueError("Severity level must be 1, 2, or 3.")
    import numpy as np
    import colour

    matrix = colour.matrix_cvd_Machado2009(
        DEFICIENCY_NAMES[cvd_type], SEVERITY_MAP[severity_level])

    def transform(oklab_color):
        color = validate_color(oklab_color)
        xyz = colour.Oklab_to_XYZ(color)
        # Matrix expects linear RGB, not gamma-encoded photo RGB.
        linear_rgb = colour.XYZ_to_RGB(xyz, "sRGB", apply_cctf_encoding=False)
        # Catalog estimates may be outside display gamut. Use clipped sRGB
        # appearance consistently for both product and reference simulations.
        simulated_rgb = np.clip(matrix @ np.clip(linear_rgb, 0, 1), 0, 1)
        simulated_xyz = colour.RGB_to_XYZ(simulated_rgb, "sRGB", apply_cctf_decoding=False)
        simulated = colour.XYZ_to_Oklab(simulated_xyz)
        if not np.all(np.isfinite(simulated)):
            raise ValueError("Simulation produced invalid coordinates.")
        # Guard tiny conversion roundoff at white/black.
        simulated[0] = np.clip(simulated[0], 0, 1)
        return validate_color(simulated)

    return transform


def simulate_cvd_oklab(oklab_color, cvd_type, severity_level):
    """Convenience for a single color; ranking reuses make_cvd_transform()."""
    return make_cvd_transform(cvd_type, severity_level)(oklab_color)
