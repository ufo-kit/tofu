"""Dimension-independent Fourier correlation post-processing (float64)."""

import numpy as np

GEOMETRIC_MIN_SAMPLES = 10


def information_threshold(counts: np.ndarray, criterion: str = "one-bit") -> np.ndarray:
    bits = {"half-bit": 0.5, "one-bit": 1.0}[criterion]
    counts = np.asarray(counts, dtype=np.float64)
    result = np.full(counts.shape, np.nan)
    valid = np.isfinite(counts) & (counts > 0)
    root = np.sqrt(counts[valid])
    s = (2.0**bits - 1.0) / 2.0
    h = 2.0 * np.sqrt(s)
    result[valid] = (s * root + h + 1.0) / ((s + 1.0) * root + h)
    return result


def half_bit_threshold(counts: np.ndarray) -> np.ndarray:
    return information_threshold(counts, "half-bit")


def normalize(cross, first, second, counts) -> np.ndarray:
    first, second = np.asarray(first, dtype=np.float64), np.asarray(
        second, dtype=np.float64
    )
    result = np.full(first.shape, np.nan)
    valid = (np.asarray(counts) > 0) & (first > 0) & (second > 0)
    np.divide(
        np.asarray(cross, dtype=np.float64),
        np.sqrt(first * second),
        out=result,
        where=valid,
    )
    return result


def geometric_bound(statistics) -> np.ndarray:
    minimum = statistics.minimum_magnitude.astype(np.float64)
    maximum = statistics.maximum_magnitude.astype(np.float64)
    result = np.full(minimum.shape, np.nan)
    valid = (
        (statistics.n_shell > GEOMETRIC_MIN_SAMPLES)
        & np.isfinite(minimum)
        & np.isfinite(maximum)
        & (minimum >= 0)
        & (maximum > 0)
        & (minimum <= maximum)
    )
    ratio = minimum[valid] / maximum[valid]
    result[valid] = 2.0 * np.sqrt(ratio) / (1.0 + ratio)
    return result


def first_curve_crossing(frequency, correlation, threshold) -> float | None:
    frequency, correlation, threshold = np.broadcast_arrays(
        frequency, correlation, threshold
    )
    difference = correlation - threshold
    for i in range(1, len(frequency)):
        if (
            np.isfinite(frequency[i - 1 : i + 1]).all()
            and np.isfinite(difference[i - 1 : i + 1]).all()
            and difference[i - 1] > 0 >= difference[i]
        ):
            fraction = difference[i - 1] / (difference[i - 1] - difference[i])
            return float(
                frequency[i - 1] + fraction * (frequency[i] - frequency[i - 1])
            )
    return None
