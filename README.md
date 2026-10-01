# Marginum signal analysis

UEF Industrial Project 2026 (IDP2026), Group 10, Marginum 5 ECTS implementation.

## The problem

Marginum measure a signal from a two sensor detector at 50 000 samples per second. A recording can run for several hours and reach 7.59 GB as CSV, and within it there are only a limited number of real peaks. The signal carries noise and interference and its base level drifts during the measurement.

There is currently no standardised way to find those peaks, so counting depends on a person reading the plots by eye, which is slow and not repeatable. The project is to produce a method that detects the peaks automatically and reliably, separates true peaks from artefacts, and finally relates the peak count to a known tumour size in order to estimate the fluorophore concentration of a sample.

### Objectives

1. A signal visualiser that can display arbitrarily large signal files
2. An algorithm that detects and classifies peaks, covering baseline removal, smoothing, detection including overlapping peaks, quantification and classification
3. An estimate of fluorophore concentration from a known tumour size and the peak count from Objective 2

Deadline for the software is 2 December 2026.

## Repository layout

```
scripts/   experimental scripts, see scripts/README.md
docs/      data inventory and working notes
```

The measurement data is **not in this repository**. See [docs/data-inventory.md](docs/data-inventory.md) for what exists, where to download it and how to verify a download against the published checksums.

## Requirements

- Python 3.13 or newer
- Packages: `numpy`, `polars`, `scipy`, `pyqtgraph`, `pyside6`, `fastdtw`

Install into a virtual environment:

```
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install numpy polars scipy pyqtgraph pyside6 fastdtw
```

## Running

Place the CSV you want to work on in the working directory, then from `scripts/`:

```
python greatdatavisualizer.py
```

This runs the conversion first and then opens the viewer. See [scripts/README.md](scripts/README.md) for the known issues, because the scripts as committed do not run unmodified on every platform.

## Status

Early experimentation. The scripts here are working drafts shared on the group forum, committed unchanged so the starting point is recorded. Nothing has been settled on architecture yet.
