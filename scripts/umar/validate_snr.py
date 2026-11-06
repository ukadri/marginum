"""
Validate a local-SNR based classifier, chunked exactly as the real script
would run it, same conventions as validate_chunking_fixed.py (uniform
filter baseline 25000, distance 25000), but the pass/fail decision is
local SNR (peak height / noise std measured in a 0.5s window around the
peak, excluding a small core around the peak itself) instead of a fixed
absolute prominence. Candidate peaks are proposed with a loose prominence
(20) so SNR gets the real say, not the proposal stage.

Default threshold 11, picked by sweeping against the labelled recording,
see docs/snr-classification-findings.md for the full table and the
reasoning (water drops to 1 false hit, zero recovers from 1/15 under
amplitude-only detection to 11/15, middle and high stay exact).

Usage:
    python validate_snr.py "Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv" [snr_threshold]
"""
import sys

import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from scipy.ndimage import uniform_filter1d

FS = 50_000
CHUNK_SIZE = 1_000_000
CANDIDATE_PROMINENCE = 20
MIN_DISTANCE = 25000
CORE = int(0.006 * FS)
NOISE_WIN = int(0.25 * FS)

REGIONS = [
    ("middle", 12, 76, 15),
    ("high", 93, 150, 15),
    ("low", 158, 212, 15),
    ("zero", 222, 267, 15),
    ("water", 282, 340, 0),
]


def local_snr(flat, peaks):
    out = np.empty(len(peaks))
    for i, p in enumerate(peaks):
        lo = max(0, p - NOISE_WIN)
        hi = min(len(flat), p + NOISE_WIN)
        local = flat[lo:hi].copy()
        c0 = max(0, p - CORE - lo)
        c1 = min(len(local), p + CORE - lo)
        mask = np.ones(len(local), dtype=bool)
        mask[c0:c1] = False
        noise_std = local[mask].std() if mask.sum() > 10 else np.nan
        out[i] = flat[p] / noise_std if noise_std and noise_std > 0 else np.nan
    return out


def main(path, snr_threshold):
    all_times = []
    chunk_number = 1
    for chunk in pd.read_csv(path, chunksize=CHUNK_SIZE):
        col = chunk.iloc[:, 1].to_numpy(dtype=np.float32)
        base = uniform_filter1d(col, size=25000)
        flat = (col - base).astype(np.float64)
        chunk_offset = (chunk_number - 1) * CHUNK_SIZE

        peaks, _ = find_peaks(flat, height=0, distance=MIN_DISTANCE, prominence=CANDIDATE_PROMINENCE)
        if len(peaks):
            snr = local_snr(flat, peaks)
            keep = peaks[snr >= snr_threshold]
        else:
            keep = peaks
        times = (keep + chunk_offset) / FS
        all_times.extend(times.tolist())
        chunk_number += 1

    all_times = np.array(all_times)
    print(f"snr_threshold={snr_threshold}")
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
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    thr = float(sys.argv[2]) if len(sys.argv) == 3 else 11.0
    main(sys.argv[1], thr)
