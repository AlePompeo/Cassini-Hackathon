"""Sentinel-1 SAR processing pipeline for oil spill detection.

The pipeline follows the standard marine oil surveillance workflow:
  1. Lee speckle filter
  2. Dark spot detection (reduced backscatter threshold)
  3. Look-alike elimination (size/shape heuristics)
  4. Area estimation

Input is a SAR sigma-naught (σ°) image in dB units (negative values over sea).
Oil slicks appear as anomalously dark patches compared to surrounding wind-roughened
water surface.
"""

import numpy as np
from scipy.ndimage import label, uniform_filter

from exceptions import ProcessingError


def lee_filter(image: np.ndarray, window_size: int = 7) -> np.ndarray:
    """Apply the Lee adaptive speckle filter to a SAR intensity image.

    The Lee filter reduces multiplicative speckle noise while preserving
    edges. It uses local statistics (mean and variance) within a sliding
    window to compute a weighted blend between the pixel value and the
    local mean.

    Args:
        image: SAR sigma-naught in linear (not dB) scale.
        window_size: Side length of the square filter window (must be odd).

    Returns:
        Speckle-filtered image, same shape as input.

    Raises:
        ProcessingError: If window_size is even.
    """
    if window_size % 2 == 0:
        raise ProcessingError("Lee filter window_size must be odd.")

    img = image.astype(np.float64)
    mean = uniform_filter(img, size=window_size)
    mean_sq = uniform_filter(img**2, size=window_size)

    variance = mean_sq - mean**2
    # ENL (equivalent number of looks) for Sentinel-1 IW ~ 4.4
    noise_var = np.mean(variance) / 4.4
    # Lee weighting coefficient
    with np.errstate(divide="ignore", invalid="ignore"):
        k = np.where(variance > 0, 1.0 - noise_var / variance, 0.0)
        k = np.clip(k, 0.0, 1.0)

    return mean + k * (img - mean)


def detect_dark_spots(
    sigma0_db: np.ndarray,
    threshold_db: float = -18.0,
) -> np.ndarray:
    """Detect anomalously dark pixels indicative of oil slicks or look-alikes.

    Args:
        sigma0_db: SAR backscatter in dB. Typical open-ocean values range
            from -25 dB (calm/oily water) to -5 dB (rough sea).
        threshold_db: Pixels below this value are flagged as dark spots.
            Default -18 dB is conservative for moderate wind conditions.

    Returns:
        Boolean mask, True where potential oil/look-alike present.
    """
    return sigma0_db < threshold_db


def eliminate_look_alikes(
    mask: np.ndarray,
    min_area_pixels: int = 50,
    max_aspect_ratio: float = 12.0,
) -> np.ndarray:
    """Remove dark-spot detections that are likely look-alikes.

    Look-alikes include low-wind zones, rain cells, and biogenic films.
    They are typically very small, very elongated, or lack the characteristic
    elongated-tongue shape of real oil slicks.

    Args:
        mask: Boolean detection mask from detect_dark_spots.
        min_area_pixels: Connected components smaller than this are removed
            (noise / rain cells).
        max_aspect_ratio: Components with width/height ratio above this
            threshold are removed (unlikely to be real slicks at this scale).

    Returns:
        Cleaned boolean mask with look-alikes removed.
    """
    labeled, num_features = label(mask)
    cleaned = np.zeros_like(mask, dtype=bool)

    for region_id in range(1, num_features + 1):
        region = labeled == region_id
        area = region.sum()

        if area < min_area_pixels:
            continue

        rows = np.any(region, axis=1)
        cols = np.any(region, axis=0)
        height = rows.sum()
        width = cols.sum()

        if height == 0 or width == 0:
            continue

        aspect = max(width, height) / max(min(width, height), 1)
        if aspect > max_aspect_ratio:
            continue

        cleaned |= region

    return cleaned


def estimate_area_km2(mask: np.ndarray, pixel_size_m: float = 10.0) -> float:
    """Estimate the total area of detected oil pixels.

    Args:
        mask: Boolean detection mask (True = oil pixel).
        pixel_size_m: Ground sampling distance in metres. Sentinel-1 GRD
            products are typically 10 m (IW) or 25 m (EW).

    Returns:
        Total detected area in km².
    """
    pixel_area_km2 = (pixel_size_m / 1000.0) ** 2
    return float(mask.sum()) * pixel_area_km2


def process_sar_image(
    sigma0_db: np.ndarray,
    window_size: int = 7,
    threshold_db: float = -18.0,
    pixel_size_m: float = 10.0,
) -> dict:
    """Run the complete SAR oil spill detection pipeline.

    Pipeline: Lee filter → dark-spot detection → look-alike elimination →
    area estimation.

    Args:
        sigma0_db: Raw SAR sigma-naught in dB. Must be a 2-D float array.
        window_size: Lee filter kernel size.
        threshold_db: Dark-pixel detection threshold in dB.
        pixel_size_m: Pixel ground resolution in metres.

    Returns:
        Dictionary with keys:
            'filtered'  — Lee-filtered sigma0 dB image
            'raw_mask'  — initial dark-spot boolean mask
            'clean_mask'— look-alike-eliminated mask
            'area_km2'  — estimated oil-covered area
            'num_slicks'— number of distinct detected slicks
    """
    if sigma0_db.ndim != 2:
        raise ProcessingError("SAR sigma0 input must be a 2-D array.")

    # Convert dB to linear for filtering, then back
    sigma0_linear = 10.0 ** (sigma0_db / 10.0)
    filtered_linear = lee_filter(sigma0_linear, window_size=window_size)
    filtered_db = 10.0 * np.log10(np.clip(filtered_linear, 1e-10, None))

    raw_mask = detect_dark_spots(filtered_db, threshold_db=threshold_db)
    clean_mask = eliminate_look_alikes(raw_mask)
    area = estimate_area_km2(clean_mask, pixel_size_m=pixel_size_m)

    labeled, num_slicks = label(clean_mask)

    return {
        "filtered": filtered_db,
        "raw_mask": raw_mask,
        "clean_mask": clean_mask,
        "area_km2": area,
        "num_slicks": num_slicks,
    }
