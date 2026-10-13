"""
Run greatdatarealtime.py's exact processing logic, chunked Gaussian baseline
removal, matched filter, chunk-relative prominence and distance, against the
labelled Big pieces reference recording, and compare detected counts per
region to the known truth (15/15/15/15/0).

Every parameter here, sigma 300, template 100 samples with std 15,
prominence as 5% of the current chunk's own maximum, distance 50, is copied
directly from scripts/jonne/greatdatarealtime.py, not chosen by us. This is
what produced the 19,520 detections against a true count of 60 reported in
docs/realtime-validation-findings.md.

Usage:
    python validate_realtime.py "Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
"""
import sys

import numpy as np
import pandas as pd
from scipy.signal import find_peaks, correlate
import scipy.signal.windows as windows
from scipy.ndimage import gaussian_filter1d

FS = 50_000
CHUNK_SIZE = 1_000_000

# Region boundaries in seconds, read off EXPLANATION [...].png, same as
# validate_detection.py. `expected` is the number of suction events the
# filename states for each.
REGIONS = [
    ("middle", 12, 76, 15),
    ("high", 93, 150, 15),
    ("low", 158, 212, 15),
    ("zero", 222, 267, 15),
    ("water", 282, 340, 0),
]


def main(path):
    template = windows.gaussian(100, std=15)  # exact params from greatdatarealtime.py

    all_times = []
    row_offset = 0
    for chunk in pd.read_csv(path, chunksize=CHUNK_SIZE):
        col = chunk.iloc[:, 1].to_numpy(dtype=np.float32)  # adc2, the signal channel

        base = gaussian_filter1d(col, sigma=300)  # exact param
        flat = col - base
        mf = correlate(flat, template, mode="same", method="fft") / np.sum(template)

        local_max = np.max(mf)
        if local_max > 0:
            min_prom = local_max * 0.05  # exact rule, relative to this chunk only
            peaks, _ = find_peaks(mf, height=0, distance=50, prominence=min_prom)
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
