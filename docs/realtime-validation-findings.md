# Testing greatdatarealtime.py against the labelled reference recording

Measured 12 October 2026, using the same `Big pieces reference data` file and
`REGIONS` ground truth as `docs/detection-findings.md`. Full method there.

## Why this script

Jonne shared `greatdatarealtime.py` on the forum on 8 October. It is a real
architectural step forward on Objective 1, it streams the CSV through
`pandas.read_csv(chunksize=...)` instead of materialising the whole file,
which is what our supervisor asked for in the last meeting. Nobody had yet
checked what its detection logic actually finds, so before deciding whether
to extend it or branch off, it was run against the one recording where the
right answer is known.

## Result, Jonne's logic unchanged

Its matched filter template is 100 samples (2 ms), baseline removal is a
Gaussian with sigma 300 samples (6 ms), peak spacing is 50 samples (1 ms),
and the prominence threshold is 5% of each chunk's own local maximum,
recomputed every million rows. None of these are compared against the
measured peak width, median 1166 samples, 23.3 ms, from `signal-measurements.md`.

| region | expected | detected |
|---|---|---|
| middle | 15 | 2,325 |
| high | 15 | 2,060 |
| low | 15 | 1,009 |
| zero | 15 | 3,032 |
| water | 0 | 3,686 |

19,520 peaks total against a true count of 60. Water, which has no suction
events in it at all, produced more false detections than any real
concentration region. The template is roughly 11.6x narrower than the real
peak, so it responds to ripples inside a peak and to noise rather than to
the peak shape, the baseline sigma is narrower than the peak so it risks
tracking the peak rather than only drift, the spacing is too small to stop
that ripple being counted many times over, and the threshold moves with
whatever happens to be in the current chunk rather than being a fixed
physical value.

What this script gets right, worth separating from the above, is the
architecture. Streaming it processed 16,823,552 rows, 336.5 s of signal, in
11.86 s with peak memory at 299,483,136 bytes, about 299 MB. That number does
not grow with file size, so it genuinely addresses "the code should be able
to handle large files."

## scripts/umar/realtime_detect.py

Same two stage shape, chunked filtering with the result written to disk, but
rescaled. Template length 3000 with std 500, full width at half maximum
about 1178 samples, matching the measured peak instead of being 11.6x
narrower than it. Baseline removal is a 0.5 s block median, the same choice
already validated in `validate_detection.py`, rather than a 6 ms Gaussian.
Peak spacing is 0.25 s. The threshold is a fixed value, not a fraction of
the current chunk, and detection runs as a second pass over the filtered
file in overlapping windows sized to one chunk, so memory stays bounded by
the window on that pass too, not just on the filtering pass.

| prominence | middle | high | low | zero | water | total |
|---|---|---|---|---|---|---|
| expected | 15 | 15 | 15 | 15 | 0 | 60 |
| 10 | 19 | 16 | 16 | 13 | 31 | 96 |
| 15 | 15 | 15 | 13 | 6 | 15 | 65 |
| 20 | 15 | 15 | 13 | 2 | 7 | 53 |
| 25 | 14 | 15 | 13 | 2 | 5 | 50 |
| 30 | 14 | 15 | 13 | 2 | 3 | 48 |

Shipped with `PROMINENCE = 20`. Rescaling the template and baseline alone
took water from 3,686 false detections down to 7, about a 500x reduction,
and brought every real region within 2 of its true count. Timed the same
way, 11.86 s / 299 MB for the original architecture, this version processed
the same file in 2.24 s with 342,851,584 bytes (about 343 MB) peak memory,
bounded the same way, by chunk and window size, not by file size.

**This does not solve the problem found in `docs/detection-findings.md`.**
Water still produces false detections at every threshold tried, and the
known overlap between low concentration peaks and water or zero artefacts in
amplitude is still there, raising the threshold to clear water further
starts costing real low concentration peaks the same way it did in the
original sweep. Fixing the scale mismatch removes most of the damage, it
does not remove the need for a second feature beyond amplitude, which is
still the open part of Objective 2.

## What this means for the two scripts

`scripts/jonne/greatdatarealtime.py` is kept as shared, unchanged, same as
the other two. `scripts/umar/realtime_detect.py` is the alternative,
rescaled version. Both live in the repo so the comparison above stays
reproducible. Once the group agrees on parameters, or on a further feature
for the classification step, one pipeline should replace both rather than
keeping two permanently.
