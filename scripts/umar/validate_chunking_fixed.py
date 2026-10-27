"""
Run greatdatachunking_fixed.py's exact logic (fixed prominence 100, no
per-chunk cap), chunked exactly as the real script would run it, against the
labelled Big pieces reference recording.

This is what produced the 48 detections against a true count of 60 reported
in docs/chunking-validation-findings.md, the closest any version has come.

Usage:
    python validate_chunking_fixed.py "Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
"""
import sys

import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from scipy.ndimage import uniform_filter1d

FS = 50_000
CHUNK_SIZE = 1_000_000
PEAK_PROMINENCE = 100  # must match scripts/jonne... scripts/umar/greatdatachunking_fixed.py

REGIONS = [
    ("middle", 12, 76, 15),
    ("high", 93, 150, 15),
    ("low", 158, 212, 15),
    ("zero", 222, 267, 15),
    ("water", 282, 340, 0),
]


def analyze_peaks(signal, chunk_offset):
    peaks, _ = find_peaks(signal, height=0, distance=25000, prominence=PEAK_PROMINENCE)
    return (peaks + chunk_offset) / FS


def main(path):
    all_times = []
    row_offset = 0
    chunk_number = 1
    for chunk in pd.read_csv(path, chunksize=CHUNK_SIZE):
        col = chunk.iloc[:, 1].to_numpy(dtype=np.float32)
        base = uniform_filter1d(col, size=25000)
        flat = col - base
        chunk_offset = (chunk_number - 1) * CHUNK_SIZE
        times = analyze_peaks(flat, chunk_offset)
        all_times.extend(times.tolist())
        row_offset += len(chunk)
        chunk_number += 1

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
