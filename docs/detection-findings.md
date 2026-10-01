# Detection findings from the labelled reference recording

Measured 1 October 2026 using `scripts/validate_detection.py`.

## Why this recording matters

`Big pieces reference data.7z`, from the data posted 24 September 2026, is the only dataset we have where the correct answer is known. The archive holds three files.

| File | What it is |
|---|---|
| `Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv` | 16 823 552 rows, 336.5 s, columns `adc1,adc2` |
| `EXPLANATION [...].png` | The same signal with the five concentration regions marked and labelled |
| `Big pieces [...].png` | The same plot unannotated, very wide |

The filename states 15 suction events each at high, middle, low and zero fluorophore concentration, followed by a water section containing no pieces.

**The region order in the data is not the order in the filename.** The filename lists high first, but the recording runs middle, high, low, zero, water. Region boundaries read off the explanation image are in `REGIONS` in the validation script.

This gives us two things nothing else in the data provides. Known peak counts to tune a detector against, and labelled negative sections, zero and water, against which false positives can actually be measured.

## Result

Baseline removal by rolling median over 0.5 s blocks, Savitzky-Golay smoothing with window 501 and order 3, then `scipy.signal.find_peaks` with a minimum spacing of 0.25 s, sweeping the prominence threshold.

| prominence | middle | high | low | zero | water |
|---|---|---|---|---|---|
| expected | 15 | 15 | 15 | 15 | 0 |
| 20 | 28 | 29 | 17 | 21 | 73 |
| 40 | 17 | 19 | 16 | 12 | 24 |
| 60 | 16 | 18 | 16 | 5 | 7 |
| 80 | 15 | 16 | 16 | 3 | 7 |
| 100 | 14 | 15 | 14 | 2 | 2 |
| 130 | 14 | 15 | 12 | 0 | 0 |
| 160 | 14 | 15 | 9 | 0 | 0 |
| 200 | 14 | 15 | 6 | 0 | 0 |
| 250 | 14 | 15 | 1 | 0 | 0 |
| 300 | 12 | 15 | 1 | 0 | 0 |

## What it means

**A single amplitude threshold cannot solve this.** There is no prominence value that recovers the known counts while keeping the water section clean. At 130 the false positives disappear, water and zero both reach zero, but low concentration has already fallen to 12 of 15. At 80, where middle and low are close to correct, water still yields 7 false peaks. The two requirements never hold at the same threshold.

The prominence distributions show why. Water artefacts reach 105 and the zero section reaches 127, while genuine low concentration peaks start at 27 with a median of 173. **Low concentration peaks and artefacts occupy overlapping amplitude ranges**, so no amplitude cut separates them.

This is exactly the question the Marginum brief asks, how to differentiate true peaks from artefacts and noise. The answer from this recording is that amplitude is not sufficient on its own, and a second discriminating feature is required, such as peak shape, width, rise and fall asymmetry, or frequency content. That is the justification for the classification step in Objective 2 of the brief.

**Where the signal is strong the method already works.** High concentration returns exactly 15 across the whole range from prominence 100 to 300, which is a stable and correct result. The difficulty is confined to the low concentration end.

## Caveats

These numbers come from one naive pipeline with parameters chosen by hand. They are a baseline to improve on, not a result. In particular the baseline estimator, the smoothing window and the minimum spacing were not tuned, and no attempt was made at overlapping peak separation.

The zero section is ambiguous. Those are real suction events with no fluorophore in them, so whether a detector should report 15 or 0 there depends on whether we are counting suction events or fluorescence responses. This is worth clarifying with Marginum, because it changes what "correct" means.

## Practical gotchas

Both of these have already cost time.

- **Polars reads square brackets as a glob pattern.** These filenames are full of them, so `pl.read_csv(path, glob=False)` is required or the file is silently not found.
- **macOS `unzip` fails on the `½` character** in `Data for suction of known volumes + 4½ h hours [2025].7z`, reporting "Illegal byte sequence". Extract through Finder, or `ditto -x -k`, or Python's `zipfile`.
