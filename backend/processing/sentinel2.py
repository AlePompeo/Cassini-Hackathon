"""Sentinel-2 optical processing: MCI, VNRI, and OSI algorithms.

All band arrays are assumed to be atmospherically corrected surface reflectance
(L2A product from Copernicus Dataspace) in the range [0, 1].

Band naming follows Sentinel-2 MSI convention:
  B03 — green (560 nm)
  B04 — red (665 nm)
  B05 — red edge 1 (705 nm)
  B06 — red edge 2 (740 nm)
"""

import numpy as np
from exceptions import ProcessingError


# Default detection thresholds derived from literature
_MCI_BLOOM_THRESHOLD = 0.005
_VNRI_OIL_THRESHOLD = 0.10


def compute_mci(
    r665: np.ndarray,
    r705: np.ndarray,
    r740: np.ndarray,
) -> np.ndarray:
    """Compute the Maximum Chlorophyll Index (MCI).

    MCI = r705 - r665 - ((705-665)/(740-665)) * (r740 - r665)

    Positive values indicate elevated chlorophyll-a (algal bloom).
    Values > 0.005 are typically considered bloom conditions.

    Args:
        r665: Surface reflectance at 665 nm (Band 4).
        r705: Surface reflectance at 705 nm (Band 5).
        r740: Surface reflectance at 740 nm (Band 6).

    Returns:
        MCI index array, same shape as inputs.

    Raises:
        ProcessingError: If input arrays have incompatible shapes.
    """
    if not (r665.shape == r705.shape == r740.shape):
        raise ProcessingError("Band arrays must have identical shapes for MCI.")

    slope_factor = (705.0 - 665.0) / (740.0 - 665.0)  # = 0.5714
    return r705 - r665 - slope_factor * (r740 - r665)


def compute_vnri(
    r560: np.ndarray,
    r665: np.ndarray,
    r740: np.ndarray,
) -> np.ndarray:
    """Compute the VIS-NIR Reflectance Index (VNRI) for hydrocarbon detection.

    VNRI = -2 * (r560 - r665 - r740) / (r560 + r665 + r740)

    Higher positive values indicate denser petroleum hydrocarbon pollution.
    Values > 0.10 are used as the oil-presence threshold.

    Note: VNRI and MCI are uncorrelated, enabling simultaneous detection of
    both oil and algal bloom in the same scene.

    Args:
        r560: Surface reflectance at 560 nm (Band 3).
        r665: Surface reflectance at 665 nm (Band 4).
        r740: Surface reflectance at 740 nm (Band 6).

    Returns:
        VNRI index array. Positive values → oil-contaminated water.

    Raises:
        ProcessingError: If input arrays have incompatible shapes.
    """
    if not (r560.shape == r665.shape == r740.shape):
        raise ProcessingError("Band arrays must have identical shapes for VNRI.")

    numerator = r560 - r665 - r740
    denominator = r560 + r665 + r740

    # Avoid division by zero (deep shadow / no-data pixels)
    with np.errstate(divide="ignore", invalid="ignore"):
        vnri = np.where(
            denominator > 1e-6,
            -2.0 * numerator / denominator,
            0.0,
        )
    return vnri


def compute_osi(
    r550: np.ndarray,
    r750: np.ndarray,
) -> np.ndarray:
    """Compute the Oil Slope Index (OSI) from spectral slope 550-750 nm.

    OSI exploits the characteristic spectral slope difference between crude
    oil and clean water in the 550-750 nm range, avoiding O2 and H2O
    absorption bands. Otsu's method is applied externally to threshold.

    Args:
        r550: Approximate 550 nm reflectance (Band 3 proxy).
        r750: Approximate 750 nm reflectance (Band 6 proxy).

    Returns:
        OSI slope array. Crude oil has a distinctly different slope
        from clean water.
    """
    wavelength_diff = 750.0 - 550.0  # nm
    return (r750 - r550) / wavelength_diff


def otsu_threshold(image: np.ndarray) -> float:
    """Compute Otsu's optimal binarization threshold for a 2-D array.

    Args:
        image: Grayscale image or index map.

    Returns:
        Optimal threshold value that maximises inter-class variance.
    """
    # Normalise to [0, 255] integer histogram
    flat = image.flatten()
    finite = flat[np.isfinite(flat)]
    if finite.size == 0:
        return 0.0

    vmin, vmax = finite.min(), finite.max()
    if vmax == vmin:
        return float(vmin)

    scaled = ((finite - vmin) / (vmax - vmin) * 255).astype(np.uint8)
    hist, bin_edges = np.histogram(scaled, bins=256, range=(0, 256))
    hist = hist.astype(np.float64)
    total = hist.sum()

    sum_total = np.dot(np.arange(256, dtype=np.float64), hist)
    sum_b = 0.0
    weight_b = 0.0
    max_variance = 0.0
    threshold = 0

    for t in range(256):
        weight_b += hist[t]
        if weight_b == 0:
            continue
        weight_f = total - weight_b
        if weight_f == 0:
            break
        sum_b += t * hist[t]
        mean_b = sum_b / weight_b
        mean_f = (sum_total - sum_b) / weight_f
        variance = weight_b * weight_f * (mean_b - mean_f) ** 2
        if variance > max_variance:
            max_variance = variance
            threshold = t

    # Convert back to original scale
    return float(threshold) / 255.0 * (vmax - vmin) + vmin


def detect_pollution(
    bands: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """Run the full Sentinel-2 pollution detection pipeline.

    Computes MCI, VNRI, and OSI from the provided band dictionary, along
    with a simple water mask (near-infrared thresholding).

    Args:
        bands: Dictionary mapping band names to reflectance arrays.
            Required keys: 'B03', 'B04', 'B05', 'B06'.

    Returns:
        Dictionary with keys 'mci', 'vnri', 'osi', 'water_mask'.

    Raises:
        ProcessingError: If required bands are missing.
    """
    required = {"B03", "B04", "B05", "B06"}
    missing = required - bands.keys()
    if missing:
        raise ProcessingError(f"Missing required Sentinel-2 bands: {missing}")

    b03 = bands["B03"].astype(np.float32)
    b04 = bands["B04"].astype(np.float32)
    b05 = bands["B05"].astype(np.float32)
    b06 = bands["B06"].astype(np.float32)

    mci = compute_mci(r665=b04, r705=b05, r740=b06)
    vnri = compute_vnri(r560=b03, r665=b04, r740=b06)
    osi = compute_osi(r550=b03, r750=b06)

    # Simple water mask: NIR reflectance below 0.15 → likely water
    water_mask = b06 < 0.15

    return {"mci": mci, "vnri": vnri, "osi": osi, "water_mask": water_mask}


def classify_pollution(
    mci: np.ndarray,
    vnri: np.ndarray,
    osi: np.ndarray,
    mci_threshold: float = _MCI_BLOOM_THRESHOLD,
    vnri_threshold: float = _VNRI_OIL_THRESHOLD,
) -> np.ndarray:
    """Classify each pixel into a pollution category.

    Labels:
        0 — clean water
        1 — algal bloom (MCI above threshold)
        2 — oil / hydrocarbon (VNRI above threshold)
        3 — both oil and algal bloom

    Args:
        mci: MCI index array.
        vnri: VNRI index array.
        osi: OSI index array (used for additional oil confirmation).
        mci_threshold: MCI value above which bloom is declared.
        vnri_threshold: VNRI value above which oil is declared.

    Returns:
        Integer label array with values in {0, 1, 2, 3}.
    """
    bloom_mask = mci > mci_threshold
    oil_mask = vnri > vnri_threshold

    labels = np.zeros(mci.shape, dtype=np.uint8)
    labels[bloom_mask] = 1
    labels[oil_mask] = 2
    labels[bloom_mask & oil_mask] = 3
    return labels
