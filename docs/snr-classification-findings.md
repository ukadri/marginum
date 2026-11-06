# A second discriminating feature: local SNR

Measured 6 November 2026. Every version tested so far, from the original
`greatdatarealtime.py` through v1, uses amplitude alone, raw peak height
or a fraction of it, to decide what counts as a real peak. Every one of
those hit the same wall documented in `docs/detection-findings.md`: real
low concentration peaks and water/zero artefacts occupy overlapping
amplitude ranges, so no amplitude cut, however it's computed, can fully
separate them. That doc named the fix needed, "a second discriminating
feature... such as peak shape, width, rise and fall asymmetry, or
frequency content." This is that feature.

## What was tried

Four candidate features, extracted per detected peak from the labelled
Big pieces reference recording at a loose prominence (20, to catch plenty
of both real and false candidates to compare):

1. **Half-max width and base width.** Didn't separate low from water
   cleanly, both regions' distributions overlap heavily (water median
   half-width 14.2ms vs low's 8.9ms, but water's interquartile range,
   9.8 to 118ms, swallows low's entirely). Base width, measured from
   `find_peaks`' own left/right base properties, turned out not to be a
   local measure at all, it extends until the nearest taller neighbour,
   which can be most of a quiet section, not the width of one peak. Not
   usable as computed.

2. **Rise/fall asymmetry.** Real peaks cluster near 1.0 (symmetric), low
   region values mostly between 0.75 and 1.4. Water is noisier and more
   skewed, but a lot of it still falls in that same band by chance, a
   [0.9, 1.1] cut only keeps 10 of 17 low candidates while still letting
   through 20 of 94 water/zero candidates. Some signal, not enough on its
   own.

3. **Local SNR.** Peak height divided by the noise std measured in a 0.5s
   window around the peak (excluding a small 6ms core right at the peak
   itself, so the peak doesn't inflate its own noise estimate). This is
   the one that worked, see below.

4. **Energy concentration.** Energy in a narrow 12ms window around the
   peak divided by energy in a wider 60ms window. Also separates well
   (low median 0.998, water median 0.744) but local SNR was cleaner and
   simpler, not pursued further for now.

## Local SNR separates the regions well

Per-region median local SNR, from the exploratory pass:

```
high    25.2        low      36.8
middle  12.9        zero      8.2
                     water     3.2
```

Note zero sits between water and low, not with either one. These are real
suction events with no fluorophore (`docs/detection-findings.md`), and the
local SNR result says the suction itself does leave a measurable, locally
above-noise footprint, just a weaker one than a marked event, and clearly
different from a section with no event at all (water). That's a genuine
answer to the open question from `docs/detection-findings.md` about
whether zero should read 15 or 0, there is a real, separable signal there,
distinct from pure noise.

## Validated chunked, full region table

`scripts/umar/validate_snr.py` reproduces this chunked exactly as the real
script would run it (uniform filter baseline 25000, distance 25000, same
as v1), candidates proposed at a loose prominence 20 so SNR makes the real
decision, swept across threshold values:

| snr threshold | middle | high | low | zero | water | total |
|---|---|---|---|---|---|---|
| expected | 15 | 15 | 15 | 15 | 0 | 60 |
| 6 | 19 | 16 | 15 | 16 | 25 | 92 |
| 7 | 19 | 16 | 14 | 16 | 16 | 81 |
| 8 | 17 | 16 | 13 | 15 | 11 | 72 |
| 9 | 16 | 16 | 13 | 13 | 7 | 65 |
| 10 | 16 | 15 | 12 | 13 | 2 | 58 |
| 10.5 | 15 | 15 | 12 | 11 | 1 | 54 |
| 11 | 15 | 15 | 12 | 11 | 1 | 54 |
| 11.5 | 15 | 15 | 12 | 10 | 0 | 52 |
| 12 | 15 | 15 | 11 | 10 | 0 | 51 |

Compare against the best result from amplitude alone, v1
(`docs/chunking-validation-findings.md`): 48 total, middle 15, high 15,
low 13, zero 1, water 4.

At threshold 11, middle and high land exactly on 15/15, same as v1's best
result. Low is close, 12 vs v1's 13. The real difference is zero and
water. Zero jumps from 1 to 11, water drops from 4 to 1, both moving the
right direction at once, something no amplitude-only version managed.
Summed absolute error against the true counts (0+0+3+4+1=8) is well under
half of v1's (0+0+2+14+4=20), almost entirely because zero stopped being
almost completely missed.

Threshold 11.5 gets water to exactly 0 at the cost of one more zero
detection (10 instead of 11), same total error. Worth treating as a knob
rather than a single right answer, same as `PEAK_PROMINENCE` was for v1.

## Performance

Timed the same way as every other version, full 336.5s labelled file:
1.17s, 359MB peak memory. Effectively the same as v1 (1.16s, 335MB), the
SNR computation only runs on the small number of candidate peaks a loose
prominence proposes, not on every sample, so it doesn't change the
chunked architecture's speed or memory profile.

Also ran against the largest real file in the dataset, the same 7.59GB
suction recording used in `docs/chunking-validation-findings.md`, headless
(no GUI): 34.4s, 382MB peak memory. Confirms the SNR step doesn't change
the memory-bounded story even at that scale, 216 candidates survived
across the whole recording, nowhere near enough to matter for either
speed or memory.

## Caveats

The noise window (0.5s either side, 6ms core excluded) and the candidate
prominence (20) were picked by hand, not swept, same caveat as every
baseline window and spacing value in this project so far. Peaks very near
a chunk boundary could have an incomplete noise window, not specifically
checked.

This still doesn't resolve what "correct" means for the zero region,
whether a detector should count real-suction-no-fluorophore events, that
is a question for Marginum, not a detection problem. What it does show is
that the detector is now capable of consistently finding those events
while also rejecting water far better than before, which it wasn't
before, regardless of how that question gets answered.

**Not yet wired into `greatdatachunking_overview.py`.** That script's
volume calibration (`VOLUME_CALIB_CH1/CH2`) and concentration thresholds
(`classify_concentration`) were both measured against the old
`PEAK_PROMINENCE`-only detection. Switching detection logic changes which
peaks get found and their heights, so both would need remeasuring against
whatever the new candidate set looks like before this replaces the live
detection there. Kept as a validated standalone finding for now, not a
swapped-in replacement.
