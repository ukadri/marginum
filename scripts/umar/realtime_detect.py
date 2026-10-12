"""
Streaming peak detector calibrated against the measured peak width.

Same two stage shape as greatdatarealtime.py, chunked baseline removal and
matched filtering with the filtered signal written to disk, but the
template, baseline window, spacing and threshold are scaled to the peak
width measured on Signal 1 (median 1166 samples, 23.3 ms) instead of being
roughly 10x narrower than it, and the threshold is an absolute value instead
of a fraction of each chunk's own local maximum.

Detection runs as a second pass over the filtered file in overlapping
windows, so memory stays bounded by the window size on both passes rather
than by the file size, which is what "handle large files" requires.

See docs/realtime-validation-findings.md for how PROMINENCE was chosen and
what it does and does not fix.

Usage:
    python realtime_detect.py path/to/signal.csv
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import find_peaks, correlate
from scipy.signal.windows import gaussian
from scipy.ndimage import median_filter

FS = 50_000
CHUNK = 1_000_000
BASELINE_BLOCK = FS // 2         # 0.5 s, matches validate_detection.py
TEMPLATE_LEN = 3000
TEMPLATE_STD = 500                # FWHM about 1178 samples, matches the measured peak width
MIN_SPACING = FS // 4             # 0.25 s, matches validate_detection.py
PROMINENCE = 20
WINDOW_PAD = MIN_SPACING + TEMPLATE_LEN // 2


def filter_to_disk(csv_path, out_path, column=1):
    """Pass 1. Stream the CSV, remove baseline, matched filter, write float32.

    Memory use is bounded by chunk size, not file size, same as
    greatdatarealtime.py. Column 1 is the second CSV column, the sensor that
    carries the signal.
    """
    template = gaussian(TEMPLATE_LEN, std=TEMPLATE_STD)
    n = 0
    with open(out_path, "wb") as f:
        for chunk in pd.read_csv(csv_path, chunksize=CHUNK):
            col = chunk.iloc[:, column].to_numpy(dtype=np.float32)
            baseline = median_filter(col, size=BASELINE_BLOCK, mode="nearest")
            flat = col - baseline
            mf = correlate(flat, template, mode="same", method="fft") / np.sum(template)
            mf.astype(np.float32).tofile(f)
            n += len(chunk)
    return n


def detect_from_disk(dat_path, n_samples, prominence=PROMINENCE):
    """Pass 2. Read the filtered signal in overlapping windows and detect peaks.

    A plain per-chunk find_peaks would miss or double count peaks near a
    chunk edge, since both prominence and `distance` need context on both
    sides. Padding each window by one spacing and half a template width,
    then keeping only peaks whose index falls inside the unpadded centre,
    avoids that while keeping memory bounded by the window size, not the
    file size.
    """
    mf = np.memmap(dat_path, dtype=np.float32, mode="r", shape=(n_samples,))
    peaks_all = []
    for start in range(0, n_samples, CHUNK):
        end = min(start + CHUNK, n_samples)
        win_start = max(0, start - WINDOW_PAD)
        win_end = min(n_samples, end + WINDOW_PAD)
        window = np.asarray(mf[win_start:win_end])
        peaks, _ = find_peaks(window, prominence=prominence, distance=MIN_SPACING)
        abs_peaks = peaks + win_start
        keep = (abs_peaks >= start) & (abs_peaks < end)
        peaks_all.append(abs_peaks[keep])
    return np.concatenate(peaks_all)


def main(csv_path):
    csv_path = Path(csv_path)
    dat_path = csv_path.with_suffix(".filtered.dat")
    start = time.time()
    n = filter_to_disk(csv_path, dat_path)
    peaks = detect_from_disk(dat_path, n)
    elapsed = time.time() - start
    print(f"{n:,} rows, {n / FS:.1f} s of signal")
    print(f"{len(peaks)} peaks detected at prominence {PROMINENCE}")
    print(f"done in {elapsed:.2f} s")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
