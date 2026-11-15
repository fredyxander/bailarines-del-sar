"""Máscara de agua y área en km² sobre la grilla nativa.

Water mask and area on the native projected grid, before any Web Mercator warp.
Otsu's threshold is computed on finite dB values. Water is the low mode:
pixels strictly below that threshold. Area uses the pixel parallelogram of the
native affine (|a·e − b·d|) and requires a projected CRS in metres.
"""

from __future__ import annotations

import numpy as np

_METRE_UNITS = {"metre", "meter", "m"}


def otsu_threshold(db: np.ndarray, bins: int = 256) -> float:
    """Otsu threshold (dB) of finite values. Constant input returns that value."""
    values = np.asarray(db, dtype=np.float64).ravel()
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("no hay valores finitos en dB para el umbral de Otsu")
    lo = float(values.min())
    hi = float(values.max())
    if not hi > lo:
        return hi

    counts, edges = np.histogram(values, bins=int(bins), range=(lo, hi))
    counts = counts.astype(np.float64)
    if counts.sum() == 0:
        raise ValueError("no hay valores finitos en dB para el umbral de Otsu")
    centers = (edges[:-1] + edges[1:]) / 2.0
    weight1 = np.cumsum(counts)
    weight2 = np.cumsum(counts[::-1])[::-1]
    with np.errstate(invalid="ignore", divide="ignore"):
        mean1 = np.cumsum(counts * centers) / weight1
        mean2 = (np.cumsum((counts * centers)[::-1]) / weight2[::-1])[::-1]
        variance = weight1[:-1] * weight2[1:] * (mean1[:-1] - mean2[1:]) ** 2
    variance = np.where(np.isfinite(variance), variance, -1.0)
    if not np.any(variance >= 0):
        return hi
    return float(centers[int(np.argmax(variance))])


def water_mask(db: np.ndarray, threshold_db: float) -> np.ndarray:
    """True on finite pixels strictly below the threshold. Nodata stays False."""
    db = np.asarray(db, dtype=np.float64)
    return np.isfinite(db) & (db < float(threshold_db))


def pixel_area_m2(transform, crs) -> float:
    """Area of one native pixel in m². Rejects geographic and non-metre CRS."""
    if crs is None or not getattr(crs, "is_projected", False):
        raise ValueError("el área de agua exige un CRS proyectado en metros")
    units = str(getattr(crs, "linear_units", "") or "").strip().lower()
    if units not in _METRE_UNITS:
        raise ValueError(
            f"el área de agua exige un CRS en metros, no en {units or 'unidades desconocidas'}"
        )
    area = abs(float(transform.a) * float(transform.e) - float(transform.b) * float(transform.d))
    if not np.isfinite(area) or area <= 0:
        raise ValueError("el área del píxel nativo no es positiva")
    return float(area)


def water_area_km2(mask: np.ndarray, transform, crs) -> float:
    """km² of True pixels. The mask must already exclude nodata."""
    n = int(np.asarray(mask, dtype=bool).sum())
    return n * pixel_area_m2(transform, crs) / 1_000_000.0


def _to_db(linear: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        return 10.0 * np.log10(np.asarray(linear, dtype=np.float64))


def measure_water(linear: np.ndarray, transform, crs) -> dict:
    """Threshold and km² for one speckle-filtered scene in linear power.

    Non-finite, zero and negative samples are excluded from the histogram
    and from the area.
    """
    db = _to_db(linear)
    threshold = otsu_threshold(db)
    mask = water_mask(db, threshold)
    return {
        "threshold_db": float(threshold),
        "km2": float(water_area_km2(mask, transform, crs)),
        "pixels": int(mask.sum()),
    }
