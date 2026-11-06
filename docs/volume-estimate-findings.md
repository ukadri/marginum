# Volume estimate, HIGH concentration only

Measured 6 November 2026, building on the overview GUI in
`docs/chunking-validation-findings.md`. Prompted by two asks, hover/region
level stats and an estimated volume (ml), from the most recent meeting.

## Data used

`Test signals from previous years/2025-10-29 Suction data for tumor size
estimation.7z`, extracted locally to
`data/Suction data for tumor size estimation/Suction data/`. Nine CSV
files, each one suction of a known volume (1, 2, 3 or 4 ml) at a known
concentration (HIGH or MIDDLE), some repeated 1 to 3 more times
("resuction"). `Info on measurements.odt` in that folder gives the table
mapping filename to concentration, volume and resuction count, reproduced
here:

| file | concentration | ml | resuctions |
|---|---|---|---|
| 1. LONG_suction_HIGH_CONC_4ml | HIGH | 4 | 3 |
| 2. suction_HIGH_CONC_4ml | HIGH | 4 | 2 |
| 3. suction_HIGH_CONC_2ml | HIGH | 2 | 2 |
| 4. suction_HIGH_CONC_1ml | HIGH | 1 | 2 |
| 5. suction_HIGH_CONC_1ml_no_resuction | HIGH | 1 | 0 |
| 6. suction_MIDDLE_CONC_3ml | MIDDLE | 3 | 0 |
| 7. suction_MIDDLE_CONC_2ml | MIDDLE | 2 | 1 |
| 8. suction_MIDDLE_CONC_1ml | MIDDLE | 1 | 0 |
| 9. suction_MIDDLE_CONC_1ml (2) | MIDDLE | 1 | 0 |

The CSV columns are just `adc1,adc2`, no volume or concentration label
inside the data itself, only the filename and this table say what each
file is.

## What a single suction action looks like

Ran the same fixed detection already validated against the labelled Big
pieces recording (prominence 100, distance 25000, uniform filter baseline
25000) against all nine files. One suction or resuction action is not one
peak, it is a burst of anywhere from 1 to over 120 small peaks close
together in time. That ruled out the idea of calibrating a single peak's
height to a single ml value, which is what the hardcoded table already in
`greatdatachunking.py` (`calib_heights = [120, 230, 350, 490]` to
`calib_ml = [1, 2, 3, 4]`) assumes.

## What does track volume, within one concentration level

Summed peak height over a suction action, divided by the total ml actually
suctioned (`volume x (resuctions + 1)`, since each resuction repeats the
same nominal volume), channel 1, HIGH concentration files:

```
file 5 (1ml, 0 resuctions):  4073.1 / 1ml  = 4073.1
file 4 (1ml, 2 resuctions): 15468.5 / 3ml  = 5156.2
file 3 (2ml, 2 resuctions): 28079.7 / 6ml  = 4680.0
file 2 (4ml, 2 resuctions): 49815.2 / 12ml = 4151.3
```

A fairly tight band across four different files at four different total
volumes, average 4515.1. Channel 2 over the same four files:

```
file 5:  18673.8 / 1ml  = 18673.8
file 4:  88336.6 / 3ml  = 29445.5
file 3: 142174.3 / 6ml  = 23695.7
file 2: 265980.2 / 12ml = 22165.0
```

Noisier but still the same order of magnitude across the four, average
23495.0.

The same check against the MIDDLE concentration files gives a completely
different, much noisier band, channel 1: 720.1, 563.3, 180.6, 398.6 for
files 6, 7, 8, 9. An order of magnitude lower than the HIGH concentration
band and not consistent with each other either. Concentration changes the
signal's scale independently of volume, matching what the labelled
high/middle/low/zero recording already showed for detection. One fixed
linear equation across every concentration, which is what the existing
hardcoded calibration does, is not supported by this data.

## What got built

`VOLUME_CALIB_CH1 = 4515.1` and `VOLUME_CALIB_CH2 = 23495.0` in
`greatdatachunking_overview.py`, the average of the four HIGH concentration
ratios above, one per channel. Estimated volume is sum of detected peak
heights divided by that constant, shown per channel for the whole file and
for whatever window the scroller is currently showing (reusing the same
peak buffers as the in view counts below, filtered the same way, no new
detection). Labelled "HIGH conc. calibration" in the GUI so it is clear
this number is not valid on MIDDLE, LOW or zero concentration data.

Checked against file 5 directly (1ml, no resuction, true answer known),
run end to end rather than just read from the four calibration points:
whole file estimate came out 0.90 ml on channel 1, 0.79 ml on channel 2,
against a true 1 ml. Reasonable given this is an average over only four
calibration points, not a large validated model.

## Also built, same pass

An "in view" count per channel, low/med/high and total, for whatever
window the scroller is currently showing, next to the whole-file running
total already in the legend. Filters the same peak buffers, no new
detection, updates on region drag, detail plot zoom, or new chunks
streaming in while that window is already on screen. Verified by an
independent count over the same buffers at three different windows plus
after a direct zoom, all matching exactly. Screenshot in
`docs/images/volume-and-inview.png`.

## Checked against the tumor gram-weight archive

`Tumor 1 gr - 2 gr - 3 gr with resuction.7z`, extracted to `data/Tumor 1
gr - 2 gr - 3 gr with resuction/`, ten files, all HIGH concentration
(no MIDDLE/LOW variant in this archive), three independent 1 gram trials
plus a 2 gram and a 3 gram trial, each with its own separate `_resuc` file
(a second recording, not a second cluster inside the same file like the ml
archive). No odt or readme in this archive, only the filenames say what
each file is.

Same detection, summed peak height divided by known gram weight for the
five initial (non-resuc) files:

```
high_1gr_1  5827.2 / 1gr        high_1gr_2  8608.2 / 1gr
high_1gr_3  8824.7 / 1gr        high_2gr    9133.8 / 2gr (per gram)
high_3gr    9085.1 / 3gr (per gram)
```

Four of the five cluster tightly, 8608 to 9134, same order of magnitude as
the ml-derived constant above (4515.1), a reasonable independent
cross-check from a different session and a different physical unit.
Every `_resuc` file came out lower than its matching initial file, all
five pairs, read as the resuction recovering less material than the first
pass rather than repeating the same amount, though that's inferred from
the pattern, not confirmed by documentation. This archive is all HIGH
concentration, so it doesn't add MIDDLE/LOW calibration points, only
strengthens confidence in the existing HIGH one.

## Concentration detection, so the estimate doesn't assume HIGH

Added `classify_concentration()`, comparing a window's median peak height
against thresholds taken from the one recording where every concentration
level is known, the labelled Big pieces reference recording. Per-region
median peak height there, channel 1 / channel 2:

```
high    424.0 / 1073.2
middle  167.1 /  529.6
low     103.2 /  209.3
zero/water  no ch1 detections at all / 45-49
```

Thresholds are the geometric mean between each neighbouring pair. The
volume field now only shows a number when the window's detected
concentration is HIGH, otherwise it says what was detected instead.
Checked against three pure-region windows of Big pieces itself (93-150s
high, 12-76s middle, 158-212s low), each correctly labelled, and against a
MIDDLE concentration suction file, correctly withheld the volume number.

**Caveat worth being upfront about:** that last check also showed the
limitation. The MIDDLE suction file's own peak heights (channel 1 median
104, channel 2 median 208) landed in Big pieces' "low" band, not "middle",
even though the file is unambiguously labelled MIDDLE concentration. The
thresholds are self-consistent on the recording they were measured from,
confirmed by the three Big pieces checks above, but don't necessarily
transfer across different recording sessions, which likely have different
absolute gain or setup. So this gates the volume estimate correctly
within a single session, but a cross-session "is this really HIGH"
answer should be treated as approximate, not definitive.

## Still open

Making the volume estimate work across concentration levels needs more
calibration points per concentration than the two to four available here.
Making concentration detection reliable across recording sessions, not
just self-consistent within one, likely needs a relative measure (scaled
against that same session's own known reference point) rather than
absolute height thresholds. Neither started.
