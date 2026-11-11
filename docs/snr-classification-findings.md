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

## Wired into the live GUI, 11 November 2026

`greatdatachunking_overview.py` now detects with this, candidates proposed
at `CANDIDATE_PROMINENCE=20`, kept at `SNR_THRESHOLD=11.0`, replacing the
old fixed `PEAK_PROMINENCE=100`. `VOLUME_CALIB_CH1/CH2` and both
`CONCENTRATION_THRESHOLDS` were remeasured against it, not carried over,
using `recalibrate_snr.py` (scratch script, not committed, reproduced from
this doc's numbers if needed) run against the Big pieces reference
recording and the four HIGH suction archive files, same chunk size
(1,000,000 rows) as the live script.

Per-region median peak height, channel 1 / channel 2 (15 expected per
region):

| region | ch1 n | ch1 median | ch2 n | ch2 median |
|---|---|---|---|---|
| middle | 14 | 167.1 | 15 | 529.6 |
| high | 15 | 424.0 | 15 | 1073.2 |
| low | 12 | 77.2 | 12 | 208.5 |
| zero | 1 | 26.6 | 11 | 46.3 |
| water | 0 | -- | 1 | 35.9 |

High and middle medians are unchanged from the amplitude-only version on
both channels, those peaks clear both the old fixed prominence and the new
SNR filter identically. Low's channel 1 median dropped from 103.2 to 77.2,
a slightly different, weaker set of 12 peaks survives now. New
concentration thresholds (geometric mean of neighbouring bands):
`CH1_CONCENTRATION_THRESHOLDS = [('high', 266.2), ('middle', 113.6), ('low', 0.0)]`,
`CH2_CONCENTRATION_THRESHOLDS = [('high', 753.9), ('middle', 332.3), ('low', 98.3), ('zero_or_water', 0.0)]`,
both barely moved from the amplitude-only version's thresholds.

Volume calibration, same four HIGH suction files, sum of SNR-surviving
peak heights per ml actually suctioned:

| file | total ml | ch1 sum | ch1/ml | ch2 sum | ch2/ml |
|---|---|---|---|---|---|
| 5 (1ml, 0 resuc) | 1 | 932.1 | 932.1 | 3291.6 | 3291.6 |
| 4 (1ml, 2 resuc) | 3 | 3168.7 | 1056.2 | 31338.3 | 10446.1 |
| 3 (2ml, 2 resuc) | 6 | 3414.2 | 569.0 | 26386.6 | 4397.8 |
| 2 (4ml, 2 resuc) | 12 | 6847.7 | 570.6 | 39131.0 | 3260.9 |

`VOLUME_CALIB_CH1 = 782.0`, `VOLUME_CALIB_CH2 = 5349.1` (averages). Both
ratios are noisier than the amplitude-only version (channel 1 was a tight
4151 to 5156 across the same four files), smaller suctioned volumes seem
to keep proportionally more SNR-surviving peaks.

**Known regression, found while checking this against file 5 (1ml, no
resuction, true answer known).** Under the amplitude-only version this
file read 0.90 ml channel 1, 0.79 ml channel 2 (`docs/volume-estimate-findings.md`).
Under local SNR detection, channel 1's whole-file median peak height comes
out 210.5, below the new 266.2 HIGH threshold, so it's classified MIDDLE
and the volume field is withheld entirely instead of showing a number.
Channel 2 still classifies correctly as HIGH but reads 0.62 ml, further
from the true 1.0 ml than before. Only 5 candidate peaks survive on
channel 1 for this file (4 on channel 2), this is the smallest file in the
archive and may simply not have many strong impacts, but it means the
fix that solved zero and water on channel 2 made this particular
known-answer cross-check worse, not better. Kept as the live default
anyway since the total-error case across the full labelled recording is
still the best result found so far (see the sweep table above), but this
is a real tradeoff, not a strict improvement, and worth more calibration
data before trusting a single volume reading from it.
