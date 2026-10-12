"""
Validate peak detection against the labelled reference recording.

`Big pieces reference data` is a recording with known contents. It contains 15
suction events each at high, middle, low and zero fluorophore concentration,
followed by a water section with no pieces in it. The regions are marked in
`EXPLANATION [...].png` inside the same archive.

That makes it the only dataset we have where the correct answer is known, so it
is what a detector should be tuned and measured against.

Note that the region order in the data is NOT the order in the filename. The
filename lists high first, but the recording runs middle, high, low, zero,
water.

Usage:
    python validate_detection.py "Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
"""

import sys

import numpy as np
import polars as pl
from scipy.signal import find_peaks, savgol_filter

SAMPLE_RATE = 50_000

# Region boundaries in seconds, read off EXPLANATION [...].png.
# `expected` is the number of suction events the filename states for each.
REGIONS = [
    ("middle", 12, 76, 15),
    ("high", 93, 150, 15),
    ("low", 158, 212, 15),
    ("zero", 222, 267, 15),
    ("water", 282, 340, 0),
]

BASELINE_BLOCK = SAMPLE_RATE // 2  # 0.5 s
SMOOTH_WINDOW = 501
SMOOTH_ORDER = 3
MIN_SPACING = SAMPLE_RATE // 4  # 0.25 s


def load_signal(path):
    """Read the second column, which is the sensor carrying the signal.

    `glob=False` matters. These filenames contain square brackets and Polars
    otherwise reads them as a glob pattern and finds nothing.
    """
    df = pl.read_csv(path, glob=False)
    return df.to_series(1).to_numpy().astype(np.float64)


def remove_baseline(signal):
    """Subtract a rolling median baseline.

    The base level drifts during a measurement by more than the height of the
    smaller peaks, so a fixed global threshold cannot work without this.
    """
    block_starts = np.arange(0, signal.size, BASELINE_BLOCK)
    medians = np.array(
        [np.median(signal[i : i + BASELINE_BLOCK]) for i in block_starts]
    )
    baseline = np.interp(np.arange(signal.size), block_starts, medians)
    return signal - baseline


def detect(signal, prominence):
    smoothed = savgol_filter(signal, SMOOTH_WINDOW, SMOOTH_ORDER)
    peaks, _ = find_peaks(smoothed, prominence=prominence, distance=MIN_SPACING)
    return peaks / SAMPLE_RATE


def main(path):
    signal = load_signal(path)
    print(f"{signal.size:,} samples, {signal.size / SAMPLE_RATE:.1f} s")

    flattened = remove_baseline(signal)

    header = f"{'promin.':>8} " + " ".join(f"{name:>7}" for name, *_ in REGIONS)
    print("\nexpected: " + " ".join(f"{exp:>7}" for *_, exp in REGIONS))
    print(header)

    for prominence in (20, 40, 60, 80, 100, 130, 160, 200, 250, 300):
        times = detect(flattened, prominence)
        counts = [
            int(((times >= start) & (times < end)).sum())
            for _, start, end, _ in REGIONS
        ]
        print(f"{prominence:8d} " + " ".join(f"{c:7d}" for c in counts))

    print(
        "\nNo single prominence reproduces 15/15/15 while keeping water at zero.\n"
        "Low concentration peaks and water artefacts overlap in amplitude, so\n"
        "amplitude alone cannot separate them. See docs/detection-findings.md."
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
