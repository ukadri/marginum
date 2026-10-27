"""
Sweep a fixed, absolute prominence threshold against greatdatachunking.py's
baseline (uniform filter, size 25000), full resolution, no matched filter,
no chunk-relative threshold, no per-chunk cap, to find the value used as
PEAK_PROMINENCE in validate_chunking_fixed.py and in the v1 update posted to
Jonne (not committed here, see docs/chunking-validation-findings.md).

Usage:
    python sweep_chunking.py "Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
"""
import sys

import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from scipy.ndimage import uniform_filter1d

FS = 50_000
CHUNK_SIZE = 1_000_000
DISTANCE = 25000

REGIONS = [
    ("middle", 12, 76, 15),
    ("high", 93, 150, 15),
    ("low", 158, 212, 15),
    ("zero", 222, 267, 15),
    ("water", 282, 340, 0),
]


def main(path):
    flat_chunks = []
    for chunk in pd.read_csv(path, chunksize=CHUNK_SIZE):
        col = chunk.iloc[:, 1].to_numpy(dtype=np.float32)
        base = uniform_filter1d(col, size=25000)
        flat_chunks.append(col - base)
    flat = np.concatenate(flat_chunks)
    print(f"{flat.size:,} samples, overall std {np.std(flat):.1f}\n")

    print("expected: " + " ".join(f"{e:>7}" for *_, e in REGIONS))
    header = " ".join(f"{n:>7}" for n, *_ in REGIONS)
    print(f"{'promin.':>8} {header}  total")
    for prom in (20, 30, 40, 50, 60, 80, 100, 130, 160, 200):
        peaks, _ = find_peaks(flat, prominence=prom, distance=DISTANCE)
        times = peaks / FS
        counts = [int(((times >= s) & (times < e)).sum()) for _, s, e, _ in REGIONS]
        print(f"{prom:8d} " + " ".join(f"{c:7d}" for c in counts) + f"  {len(peaks):5d}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
