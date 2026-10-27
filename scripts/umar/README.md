# umar/

Scripts that test detection against the one recording where the correct
answer is known, `Big pieces reference data`, plus alternative or fixed
versions of Jonne's scripts. Anyone should be able to follow this file and
reproduce every number quoted here and in `docs/detection-findings.md`,
`docs/realtime-validation-findings.md` and `docs/chunking-validation-findings.md`.

## Setup

```
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install numpy pandas polars scipy pyqtgraph pyside6
```

`pyqtgraph` and `pyside6` are only needed for `greatdatachunking_overview.py`,
every other script here is plain numpy/pandas/polars/scipy.

## Get the labelled data

From Moodle, IDP2026 → Phase 2: Experimentation → Marginum Measurement Data,
download the archive posted 24 September 2026 and extract
`Big pieces reference data.7z`. See `docs/data-inventory.md` for the exact
archive name and its checksum.

Inside is one CSV and two PNGs. The CSV is what every command below needs,
for example:

```
"Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
```

It holds 15 suction events at high, middle and low fluorophore
concentration, 15 more at no concentration, then a water section with none
at all, 60 real events in total, 16,823,552 rows, 336.5 s. The `EXPLANATION
[...].png` in the same folder marks where each section starts and ends on
the chart. Note the recording order is middle, high, low, zero, water, not
the order the filename lists them in, that is what the `REGIONS` list in
each script below encodes.

## The scripts

### validate_detection.py

Our own baseline pipeline. Rolling median baseline removal, Savitzky-Golay
smoothing, then `find_peaks` with a swept prominence threshold. Not chunked,
reads the whole file at once.

```
python validate_detection.py "Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
```

Prints detected counts per region across ten prominence values. Full result
and interpretation in `docs/detection-findings.md`. Headline finding, no
single prominence threshold gets every region right at once, because low
concentration peaks and water or zero artefacts overlap in amplitude.

### validate_realtime.py

Reproduces `scripts/jonne/greatdatarealtime.py`'s exact logic, same chunked
Gaussian baseline removal, same matched filter template, same chunk-relative
prominence rule, same minimum spacing, run against the labelled file.

```
python validate_realtime.py "Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
```

Expect:

```
total peaks detected across whole file: 19520

region   expected detected
middle         15     2325
high           15     2060
low            15     1009
zero           15     3032
water           0     3686
```

Against a true total of 60. The water section, which has no real signal,
produces more false detections than any real region.

### realtime_detect.py

Same two-pass, chunked architecture, but the template, baseline window,
spacing and threshold are rescaled to the measured peak width (median 1166
samples, 23.3 ms) instead of being about 11.6x narrower than it, and the
threshold is a fixed value instead of a fraction of each chunk's own
maximum.

```
python realtime_detect.py "Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
```

Writes a `.filtered.dat` file next to the input and prints the total peak
count at the shipped threshold, `PROMINENCE = 20`, 53 against a true 60.
Full per-threshold table in `docs/realtime-validation-findings.md`, along
with the caveat that this does not remove the underlying overlap problem,
it only fixes the scale mismatch.

### validate_realtimer.py

Reproduces `scripts/jonne/greatdatarealtimer.py`'s exact logic, his 15
October reply to the `realtime_detect.py` findings. Baseline window widened
to 0.5 s and matched filter kept unchanged from the original.

```
python validate_realtimer.py "Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
```

166 total against a true 60, down from 19,520, but water still produces 77
false hits, the matched filter template was still untouched in this version.

### validate_chunking.py

Reproduces `scripts/jonne/greatdatachunking.py`'s exact logic, his 27
October version, which drops the matched filter entirely and adds a cap of
5 peaks per chunk.

```
python validate_chunking.py "Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
```

55 total against 60, water down to 12, but every real region now
undercounts, the per-chunk cap clips real detections whenever a chunk holds
more than 5 real events, which this densely packed recording does often.

### sweep_chunking.py and validate_chunking_fixed.py

`sweep_chunking.py` sweeps a fixed prominence against `greatdatachunking.py`'s
baseline to find a value that does not depend on any one chunk.
`validate_chunking_fixed.py` reproduces the result of applying that fix,
a fixed `PEAK_PROMINENCE = 100` instead of the chunk-relative threshold, and
the per-chunk cap removed, everything else unchanged. The actual patched
file, v1, was posted to Jonne directly rather than committed here, see
`docs/chunking-validation-findings.md`.

```
python sweep_chunking.py "Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
python validate_chunking_fixed.py "Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
```

48 total against 60, middle and high land exactly on 15, the closest of any
version tested so far. Full tables and the "still not solved" caveat in
`docs/chunking-validation-findings.md`.

### greatdatachunking_overview.py

Builds on `greatdatachunking.py` with a GUI addition, a full-file overview
strip for each channel, a min/max envelope of the whole recording (same
idea as the M4 paper cited in the orientation task post), each with a
draggable region that pans and zooms the detail plots above. Drag either
region, or zoom either detail plot directly, and all four stay in sync, so
together they work as the scroller. Also formats the time axis as minutes
and seconds instead of raw seconds, and colours peak markers low/med/high
with a legend showing a live running count per category, using the same
0.33/0.66 of each chunk's own max split his script already computed for the
end of run text summary, just made visible on the chart. Worth knowing that
split is relative to each chunk, not a fixed amplitude, so the same height
can land in a different category depending what else is in that chunk.
Detection, baseline removal and the calibration are unchanged from his
version. There's also a Reset View button, a stray click-drag directly on a
detail plot (not the overview region, which is meant to be dragged) can
pull an axis out to a strange range, the button puts both back to fit the
actual data without restarting.

Unlike his scripts, the CSV path is a command line argument, falling back
to `2Gb signal.csv` if none is given, and there's no platform override, so
it runs as committed on macOS as well as Linux.

```
python greatdatachunking_overview.py "Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
```

Tested by actually driving it, not just reading the code, dragging each
overview region and confirming the detail plots and the other region
follow, then zooming the detail plots directly and confirming both regions
follow back. Screenshot in `docs/images/overview-scroller.png`.

## Findings, in one table

| | total detected | water (true 0) | time | peak memory |
|---|---|---|---|---|
| expected | 60 | 0 | | |
| `greatdatarealtime.py`, 8 Oct, as shared | 19,520 | 3,686 | 11.86 s | 299 MB |
| `realtime_detect.py`, our rescale of the above | 53 | 7 | 2.24 s | 343 MB |
| `greatdatarealtimer.py`, 15 Oct, Jonne's reply | 166 | 77 | | |
| `greatdatachunking.py`, 27 Oct, as shared | 55 | 12 | | |
| v1, our update to the above, posted to Jonne | 48 | 4 | 1.16 s | 335 MB |

All versions process the full 336.5 s file with memory bounded by chunk
size, not file size, which is the point of the streaming architecture and
holds throughout. Each step along the way was a real improvement. The
deeper problem hasn't gone away though, amplitude alone cannot fully
separate real low concentration peaks from artefacts, see
`docs/detection-findings.md`. That is still open and is what the
classification step of Objective 2 needs to address next.
