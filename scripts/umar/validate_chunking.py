"""
Run greatdatachunking.py's exact processing logic (uniform-filter baseline
size 25000, no matched filter, prominence as 10x the chunk's own noise
standard deviation, distance 25000, capped at 5 peaks per chunk) against the
labelled Big pieces reference recording.

Every parameter is copied directly from scripts/jonne/greatdatachunking.py.
This is what produced the 55 detections against a true count of 60, with
water (true 0) at 12 and every real region undercounting, reported in
docs/chunking-validation-findings.md.

Usage:
    python validate_chunking.py "Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
"""
import sys

import numpy as np
import pandas as pd
from scipy.signal import find_peaks
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


def analyze_peaks(signal, chunk_offset):
    noise_std = np.std(signal)
    min_prom = noise_std * 10.0  # exact rule, relative to this chunk only
    min_distance = 25000

    peaks, props = find_peaks(signal, height=0, distance=min_distance, prominence=min_prom)

    max_peaks_per_chunk = 5  # exact cap from greatdatachunking.py
    if len(peaks) > max_peaks_per_chunk:
        highest_indices = np.argsort(props["peak_heights"])[-max_peaks_per_chunk:]
        peaks = np.sort(peaks[highest_indices])

    return (peaks + chunk_offset) / FS


def main(path):
    all_times = []
    row_offset = 0
    chunk_number = 1
    for chunk in pd.read_csv(path, chunksize=CHUNK_SIZE):
        col = chunk.iloc[:, 1].to_numpy(dtype=np.float32)  # adc2, the signal channel
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
