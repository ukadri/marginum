# Testing and fixing greatdatachunking.py

Measured 27 October 2026, same method and labelled recording as
`docs/detection-findings.md` and `docs/realtime-validation-findings.md`.

## Where this fits in Jonne's sequence of changes

Three versions now, all in `scripts/jonne/`, all tested against the same
labelled recording.

| Version | Shared | Baseline | Threshold | Total detected | Water (true 0) |
|---|---|---|---|---|---|
| `greatdatarealtime.py` | 8 October | Gaussian, sigma 300 (6 ms) | 5% of chunk's max | 19,520 | 3,686 |
| `greatdatarealtimer.py` | 15 October | Uniform filter, 25,000 (0.5 s) | 6x chunk's noise std | 166 | 77 |
| `greatdatachunking.py` | 27 October | Uniform filter, 25,000 (0.5 s) | 10x chunk's noise std, capped at 5/chunk | 55 | 12 |

Each version is a real improvement over the last. The baseline window and
spacing fixes between the first and second version did most of the work,
19,520 down to 166. Dropping the matched filter entirely in the third
version helped further, but something new shows up there too, every real
region now comes in under its true count (zero fell to 7 of 15, low to 11 of
15), while water is still producing false hits. That's the `max_peaks_per_chunk = 5`
cap. The labelled recording packs 15 events into about 50 to 65 seconds per
region, which is dense enough that more than 5 real events land inside a
single 20 second chunk, so the cap was discarding genuine detections. It was
sized for the sparser rate expected over a full recording (roughly 30 peaks
across 4 hours), which is reasonable for real data but not for this
validation file.

## What we changed

Two changes, applied to a local copy of his file, not committed here,
everything else, baseline removal, spacing, calibration, plotting, is
identical to Jonne's version.

1. **Fixed prominence instead of chunk-relative.** `noise_std * 10.0`,
   recomputed every chunk, replaced with a constant, `PEAK_PROMINENCE = 100`.
   Picked by sweeping fixed prominence values against the full labelled
   recording, baseline removal unchanged (uniform filter, 25,000):

   | prominence | middle | high | low | zero | water | total |
   |---|---|---|---|---|---|---|
   | expected | 15 | 15 | 15 | 15 | 0 | 60 |
   | 60 | 17 | 17 | 14 | 10 | 22 | 81 |
   | 80 | 16 | 16 | 14 | 4 | 9 | 60 |
   | 100 | 16 | 15 | 13 | 2 | 6 | 52 |
   | 130 | 14 | 15 | 12 | 1 | 0 | 42 |

   100 was picked as the balance point, water nearly clean without low
   concentration dropping too far.

2. **Removed the per-chunk cap.** With a fixed threshold doing the
   filtering, the cap no longer helps and only costs real detections in
   dense regions.

## Result, chunked, exactly as the real script would run it

```
total peaks detected across whole file: 48

region   expected detected
middle         15       15
high           15       15
low            15       13
zero           15        1
water           0        4
```

48 against a true 60. Middle and high now land exactly on the true count.
This is the closest any version has come, including our own earlier rescaled
matched filter attempt in `realtime_detect.py` (53 total, 15/15/13/2/7).
Timed the same way as the others, 1.16 s and 335 MB peak memory for the full
336.5 s file, still fast and still bounded regardless of file size.

**Still not a complete fix.** Water produces 4 false hits and zero comes in
at 1 instead of 15 (though whether zero should read 15 or 0 is still the
open question noted in `docs/detection-findings.md`, those are real suction
events with no fluorophore in them). The underlying overlap between weak
real peaks and artefacts hasn't gone away, this is a better-tuned version of
the same approach, not a different one.
