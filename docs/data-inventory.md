# Measurement data inventory

The measurement data is **not stored in this repository**. It runs to several gigabytes and a single uncompressed recording reaches 7.59 GB, so it is excluded by `.gitignore`. This document records what exists, where it comes from, and how to verify a download.

## Where to get it

Moodle, IDP2026 → **Phase 2: Experimentation** → **Marginum Measurement Data**.

The folder description there states three things worth repeating, because they are easy to get wrong.

- The detector has **two sensors**, so the CSV files have two columns and **both are sensor readings**. The first column is not a timestamp.
- The sampling rate is **50 000 samples per second**.
- One minute of signal is three million samples per channel.

## Data posted 24 September 2026

Announced by Joni Hyttinen in the News forum. Suctions described as "resuctions" are cases where a sample was suctioned once, recovered from the vacuum collector, and suctioned again.

| Archive | Contents | SHA256 |
|---|---|---|
| `Big pieces reference data.7z` | Suctioning large phantom pieces at high, middle and low fluorophore concentration, then fluorophore free pieces, then water | `8f3789d215341341d7f686e0261ae66ae36e42d74b4a27be24ad4b5e3daf0206` |
| `Data for suction of known volumes + 4½ h hours [2025].7z` | Suctions across various concentrations and tumour phantom sizes | `3cb2ada0ca03ed32e834cc5d09923592e92a81a7b846d8331ba97decc5cf5a05` |
| `Measurements from demo sessions.7z` | Signals gathered during the Marginum demo sessions | `b7a1c11b8518279fb09d23141335dadb785629afaa383751a3953806d7c3307f` |
| `Tumor 1 gr - 2 gr - 3 gr with resuction.7z` | High concentration, varying tumour phantom sizes | `8189b764704edeb41fafe9f7ba6abdb961bac5ee7a4def8f6b13277fb32d8d6d` |

Note that the Moodle listing shows `Tumor 1 gr - 2 gr - 3 gr with resuction.7z` in two places, once at the top level and once under "Test signals from previous years". Confirm whether these are the same file.

### Verifying a download

```
shasum -a 256 "Big pieces reference data.7z"
```

Compare the output against the table above. On Linux use `sha256sum` instead.

## Data posted 17 September 2026

Announced as "Test signals from earlier years". Downloaded as a single 1.1 GB zip named `Marginum Measurement Data-20260918.zip`. No checksums were published for these.

| Archive | File inside | Uncompressed |
|---|---|---|
| `Signal 1.7z` | `IDP_signal_example_[sami_dmitry_september2023].csv` | 67 MB |
| `Signal 2.7z` | `2Gb signal.csv` | 2.13 GB |
| `Signal 3.7z` | `Only re-suction peaks.csv` | 134 MB |
| `Signal 4.7z` | `just water.csv` | 105 MB |
| `2025-10-29 Suction data for tumor size estimation.7z` | see below | up to 7.59 GB each |

### Inside the suction data archive

Nine recordings, each with a PNG alongside it, plus `Info on measurements.odt` and `peaks count 1.png`. The concentration and the phantom volume are encoded in each filename.

| File | Concentration | Volume | CSV size |
|---|---|---|---|
| `1. LONG_suction_HIGH_CONC_4ml_(and_3_times_resuction).csv` | high | 4 ml | 7.59 GB |
| `2. suction_HIGH_CONC_4ml_(and_2_times_resuction).csv` | high | 4 ml | 360 MB |
| `3. suction_HIGH_CONC_2ml_(and_2_times_resuction.csv` | high | 2 ml | 278 MB |
| `4. suction_HIGH_CONC_1ml_(and_2_times_resuction).csv` | high | 1 ml | 192 MB |
| `5. suction_HIGH_CONC_1ml_and_no_resuction.csv` | high | 1 ml | 31.7 MB |
| `6. suction_MIDDLE_CONC_3ml_(and_no_resuction).csv` | middle | 3 ml | 57.9 MB |
| `7. suction_MIDDLE_CONC_2ml_(and_1_times_resuction).csv` | middle | 2 ml | 133 MB |
| `8. suction_MIDDLE_CONC_1ml_(and_no_resuction).csv` | middle | 1 ml | 31.0 MB |
| `9. suction_MIDDLE_CONC_1ml_(and_no_resuction (2)).csv` | middle | 1 ml | 32.4 MB |

This is the dataset for **Objective 3**, estimating fluorophore concentration from tumour size and peak count. Two items in it have not been opened by anyone yet and may matter a great deal:

- `Info on measurements.odt`, the measurement documentation
- `peaks count 1.png`, which may contain reference peak counts. If it does, it gives us ground truth to validate detection against, which nothing else in the data provides.

## Measured characteristics of Signal 1

Signal 1 is the smallest file and the one used for early testing. Measured locally, reproduced twice.

| Property | Value |
|---|---|
| Rows | 8 413 184 |
| Duration at 50 kHz | 168.26 s |
| Header | `adc1,adc2` |
| adc1 | range 371 to 402, mean 385.1, standard deviation 3.5 |
| adc2 | range 542 to 1097, mean 668.9, standard deviation 50.9 |
| Peaks detected | 35, at prominence 30 and 0.25 s minimum spacing |
| Peak width at half height | median 1166 samples (23.3 ms), narrowest 342 samples (6.8 ms) |
| Baseline drift on adc2 | 10 second block medians span 574 to 729, a range of 155 counts |

adc1 is almost flat and behaves as a reference channel. adc2 carries the signal.

Every value is a positive integer below 1100, so `int16` is sufficient and `float32` doubles the storage for no benefit.

The baseline drift of 155 counts is large against peak heights of roughly 370 counts above baseline, over 40 percent. A fixed global threshold therefore cannot work and baseline removal is mandatory.

## Decimation, for drawing only

8.4 million samples cannot be drawn into roughly 2000 screen pixels, so the data has to be reduced before plotting. How it is reduced matters, and so does where in the pipeline it happens.

| Method | Points | Peak amplitude lost |
|---|---|---|
| Every 100th sample | 84 132 | 4 counts |
| Every 4207th sample | 2 000 | 42 counts |
| Minimum and maximum per group | 2 000 | 0 counts |

**Detection must always run on the full resolution data.** Only the picture is reduced, and the detected peaks are then drawn onto the reduced chart as markers. Running detection on already reduced data changes the count with the zoom level, losing real peaks in one direction and inventing false ones in the other.

The reasoning behind this, and the supporting measurements, follow Jugel, U., Jerzak, Z., Hackenbroich, G., & Markl, V. (2014). M4: A visualization-oriented time series data aggregation. *Proceedings of the VLDB Endowment, 7*(10), 797-808. http://www.vldb.org/pvldb/vol7/p797-jugel.pdf
