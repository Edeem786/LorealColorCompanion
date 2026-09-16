import numpy as np
import colour

# Map your ordinal severity levels (1-3) to the continuous [0,1] scale
# the Machado 2009 model expects. Tune these as your team calibrates.
SEVERITY_MAP = {
    1: 0.3,   # mild
    2: 0.6,   # moderate
    3: 1.0,   # severe (full dichromacy)
}

_DEFICIENCY_NAMES = {
    "protan": "Protanomaly",
    "deutan": "Deuteranomaly",
    "tritan": "Tritanomaly",
}


def simulate_cvd_oklab(oklab_color, cvd_type, severity_level, clip=True):
    """
    Simulate how a color in normalized OKLab space would appear to
    someone with a given type/severity of colour vision deficiency.

    Parameters
    ----------
    oklab_color : array_like, shape (3,)
        Color as (L, a, b) in your normalized OKLab space.
    cvd_type : str
        One of "protan", "deutan", "tritan".
    severity_level : int or float
        Either an ordinal level (1-3, mapped via SEVERITY_MAP) or
        a raw float already in [0, 1].
    clip : bool
        Whether to clip the simulated linear sRGB into [0, 1] before
        converting back to OKLab. Recommended — the CVD matrix can
        push colours slightly out of gamut.

    Returns
    -------
    ndarray, shape (3,)
        Simulated color, in the same normalized OKLab space.
    """
    oklab_color = np.asarray(oklab_color, dtype=float)

    # Resolve severity: accept either your ordinal scale or a raw float
    if isinstance(severity_level, int) and severity_level in SEVERITY_MAP:
        severity = SEVERITY_MAP[severity_level]
    else:
        severity = float(severity_level)
        if not 0.0 <= severity <= 1.0:
            raise ValueError("severity must resolve to a value in [0, 1]")

    deficiency = _DEFICIENCY_NAMES.get(cvd_type, cvd_type)

    # 1. OKLab -> linear sRGB (the CVD matrix operates on linear RGB)
    XYZ = colour.Oklab_to_XYZ(oklab_color)
    RGB_linear = colour.XYZ_to_RGB(
        XYZ,
        colorspace="sRGB",
    )

    # 2. Apply the Machado et al. (2009) CVD matrix
    M = colour.matrix_cvd_Machado2009(deficiency, severity)
    RGB_simulated = M @ RGB_linear

    if clip:
        RGB_simulated = np.clip(RGB_simulated, 0.0, 1.0)

    # 3. Back to OKLab
    XYZ_simulated = colour.RGB_to_XYZ(
        RGB_simulated,
        colorspace="sRGB",
    )
    oklab_simulated = colour.XYZ_to_Oklab(XYZ_simulated)

    return oklab_simulated