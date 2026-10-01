# Scripts

Working drafts shared on the group forum by Jonne Huovinen, committed **unchanged** so that the starting point is recorded before anyone edits them. The issues below are observations for the group to decide on, not changes that have been made.

## What they do

`greatdataconversionSGF.py` reads a CSV with Polars, applies a Savitzky-Golay filter to both channels, writes the result as float32 to `channel1.dat` and `channel2.dat`, then z-normalises both channels and computes a Dynamic Time Warping distance between them.

`greatdatavisualizer.py` opens a log window, runs the conversion script as a subprocess while streaming its output into that window, then memory maps the two `.dat` files and plots them as two vertically stacked charts with linked x axes.

## What is right about them

The pyqtgraph call `setDownsampling(ds=True, auto=True, method='peak')` is the correct choice. Peak mode keeps the minimum and maximum of each bin, which preserves narrow peaks at any zoom level. This is the single most important detail in a viewer for this kind of data, and it matches the approach argued for in the M4 paper referenced in `docs/data-inventory.md`.

Stacking the two channels on separate plots with `setXLink` is also right. Putting both on one shared y axis wastes most of the vertical range, because the two channels occupy very different ranges.

## Known issues

### Stops the scripts running

1. **`greatdatavisualizer.py:17` forces `QT_QPA_PLATFORM = "xcb"`.** This is Linux X11 only. On macOS it aborts with "Could not find the Qt platform plugin xcb in ''", since the available platforms there are `offscreen`, `minimal` and `cocoa`. Deleting the line is the whole fix. Qt selects the correct backend per operating system on its own.

2. **`greatdatavisualizer.py:36` launches `"GreatDataConversionSGF.py"`** with capital letters, but the file is named `greatdataconversionSGF.py`. This fails on Linux, where filenames are case sensitive, and happens to work on macOS, where they are not.

3. **`greatdataconversionSGF.py:8` hardcodes a filename.** The input CSV should be a command line argument so the scripts work on any recording.

### Design decisions worth discussing

4. **The conversion overwrites the raw data with the filtered version.** `channel1.dat` and `channel2.dat` contain the Savitzky-Golay output, so the raw values exist only in the original CSV. Changing filter parameters later means reconverting from CSV, which is the slow step. Filtering is cheap by comparison, so storing raw and filtering on read is the cheaper order. Alternatively write both under separate names.

5. **The data is stored as float32 where int16 would do.** Every measured value is a positive integer below 1100, so float32 doubles the file size for no benefit. For a 4 hour recording that is 5.4 GB rather than 2.7 GB.

6. **Streaming is still not enabled.** The comment at line 16 notes this. `.collect()` without streaming materialises the whole column, and the measured peak memory was 357 MB for a 67 MB CSV. Extrapolated to a 7.59 GB recording that will not run on a laptop. `collect(engine="streaming")` is the fix.

7. **The Savitzky-Golay window is very small relative to the peaks.** `window_length=21` at 50 kHz is 0.42 ms, while measured peaks are 23.3 ms wide at half height, so the window is roughly 56 times narrower than a peak. It will not clip peaks, which is what was intended, but it only removes very high frequency noise. If the goal is to make peaks more prominent for detection, the relevant scale is hundreds of samples. Measured on Signal 1, so other recordings may differ.

### Questions about the DTW section

8. **DTW is being run between channel 1 and channel 2.** Those are two different sensors measuring different things. On Signal 1, adc1 is almost flat with a standard deviation of 3.5 while adc2 carries the signal at 50.9. Z-normalising makes them superficially comparable, but the result compares the shape of noise against the shape of signal. There is no reason to expect the two channels to be identical, so the distance is difficult to interpret.

   Where DTW would genuinely help is **matched filtering**, which is already in the group project plan, comparing a candidate peak against a template peak shape. It may also help in Objective 3, comparing recordings across tumour sizes.

9. **The interpretation thresholds at lines 53 to 56** do not appear to come from a published source. They would need a citation or removal before going into the report.

10. **The DTW runs on `[::100]` decimated data.** Reducing data before analysing it is the pattern to avoid. It is less damaging for shape comparison than for peak counting, but the habit is worth breaking early. Decimation belongs in the drawing path only.
