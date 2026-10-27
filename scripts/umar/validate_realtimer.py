"""
Run greatdatarealtimer.py's exact processing logic (uniform-filter baseline,
size 25000, matched filter template unchanged at 100 samples/std 15,
prominence as 6x the chunk's own noise standard deviation, distance 5000)
against the labelled Big pieces reference recording.

Every parameter is copied directly from scripts/jonne/greatdatarealtimer.py.
This is what produced the 166 detections against a true count of 60 reported
in docs/chunking-validation-findings.md.

Usage:
    python validate_realtimer.py "Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
"""
import sys

import numpy as np
import pandas as pd
from scipy.signal import find_peaks, correlate
import scipy.signal.windows as windows
from scipy.ndimage import uniform_filter1d

FS = 50_000
CHUNK_SIZE = 1_000_000

REGIONS = [
    ("middle", 12, 76, 15),
    ("high", 93, 150, 15),
    ("low", 158, 212, 15),
    ("zero", 222, 267, 15),
    ("water", 282, 340, 0),
]


def main(path):
    template = windows.gaussian(100, std=15)  # unchanged from greatdatarealtime.py

    all_times = []
    row_offset = 0
    for chunk in pd.read_csv(path, chunksize=CHUNK_SIZE):
        col = chunk.iloc[:, 1].to_numpy(dtype=np.float32)  # adc2, the signal channel

        base = uniform_filter1d(col, size=25000)  # exact param
        flat = col - base
        mf = correlate(flat, template, mode="same", method="fft") / np.sum(template)

        noise_std = np.std(mf)
        min_prom = noise_std * 6.0  # exact rule, relative to this chunk only
        min_distance = 5000  # exact param
        peaks, _ = find_peaks(mf, height=0, distance=min_distance, prominence=min_prom)
        all_times.extend(((peaks + row_offset) / FS).tolist())
        row_offset += len(chunk)

    all_times = np.array(all_times)
    print(f"total samples processed: {row_offset:,} ({row_offset / FS:.1f} s)")
    print(f"total peaks detected across whole file: {len(all_times)}\n")
    print(f"{'region':8} {'expected':>8} {'detected':>8}")
    for name, start, end, expected in REGIONS:
        n = int(((all_times >= start) & (all_times < end)).sum())
        print(f"{name:8} {expected:8d} {n:8d}")
    outside = int(
        (~np.any([(all_times >= a) & (all_times < b) for _, a, b, _ in REGIONS], axis=0)).sum()
    )
    print(f"{'outside':8} {'':>8} {outside:8d}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
