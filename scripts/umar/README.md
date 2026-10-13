# umar/

Scripts that test detection against the one recording where the correct
answer is known, `Big pieces reference data`, and an alternative, rescaled
version of Jonne's realtime streaming detector. Anyone should be able to
follow this file and reproduce every number quoted here and in
`docs/detection-findings.md` and `docs/realtime-validation-findings.md`.

## Setup

```
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install numpy pandas polars scipy
```

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

## Findings, in one table

| | total detected | water (true 0) | time | peak memory |
|---|---|---|---|---|
| expected | 60 | 0 | | |
| Jonne's `greatdatarealtime.py`, as shared | 19,520 | 3,686 | 11.86 s | 299 MB |
| `realtime_detect.py`, rescaled | 53 | 7 | 2.24 s | 343 MB |

Both process the full 336.5 s file with memory bounded by chunk size, not
file size, which is the point of the streaming architecture and holds for
either version. Rescaling the template and baseline took the water false
positive count down by about 500x and brought every real region within 2 of
its true count, but did not solve the deeper problem, amplitude alone
cannot fully separate real low concentration peaks from artefacts, see
`docs/detection-findings.md`. That is still open and is what the
classification step of Objective 2 needs to address next.
