"""
GreatDataRealTime.py, with a full-file overview, colour coded peaks and a
time axis in minutes and seconds

Builds on greatdatachunking.py (27 October). Baseline removal, detection and
the calibration are unchanged.

1. Two extra plots, one per channel, showing the whole file at once as a
   min/max envelope (same idea as the M4 paper cited in the orientation
   task post, keep the minimum and maximum of each group so narrow peaks
   never disappear). They grow as chunks stream in and cover the full
   recording once processing finishes. Each has a draggable region that
   pans and zooms the detail plots above, so together they work as the
   scroller the supervisor asked about too, it's the same feature. The two
   regions, and the detail view, are kept in sync with each other, drag
   either one and both update.

2. The time axis on every plot now reads minutes and seconds instead of
   raw seconds.

3. Peak markers are coloured low/med/high instead of all being plain red,
   using the same 0.33/0.66 of each chunk's own max split his script
   already computed for the end of run text summary, just made visible on
   the chart, with a legend showing a live running count per category.
   Because the split is relative to each chunk, not a fixed amplitude, the
   same absolute height can land in a different category in a quiet chunk
   than in a busy one, worth knowing before reading too much into a colour.

4. A Reset View button. A stray click-drag directly on a detail plot (as
   opposed to dragging the overview region, which is meant to be dragged)
   can pull an axis to a strange range, for example one channel's peaks
   compressing down to what looks like a flat line because the axis got
   dragged out to 10x the real range. The button puts both axes back to
   fit the actual data without needing to restart the script.
"""

import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore

from scipy.signal import find_peaks
from scipy.ndimage import uniform_filter1d

# Fixed prominence, not relative to any one chunk. Picked by sweeping
# against the labelled Big pieces reference recording.
PEAK_PROMINENCE = 100

# Overview bucket size. 25000 samples (0.5 s) matches the baseline window
# and minimum spacing already used elsewhere in this script, so the same
# timescale means the same thing everywhere.
OVERVIEW_BUCKET = 25000

# Peak categories, low/med/high, a yellow to red scale matching the
# amplitude split Jonne's script already computes (0.33 and 0.66 of each
# chunk's own max) for the text log, just made visible on the chart too.
CATEGORY_NAMES = ['low', 'med', 'high']
CATEGORY_COLORS = [(230, 210, 40), (255, 140, 0), (230, 30, 30)]


class TimeAxisItem(pg.AxisItem):
    """Shows tick labels as minutes:seconds instead of raw seconds."""

    def tickStrings(self, values, scale, spacing):
        out = []
        for v in values:
            v = max(v, 0)
            minutes, seconds = divmod(v, 60)
            out.append(f"{int(minutes):02d}:{seconds:05.2f}")
        return out


# 1. BACKGROUND THREAD (Processing)

class ProcessingWorker(QtCore.QThread):
    log_msg = QtCore.Signal(str)
    new_data = QtCore.Signal(np.ndarray, np.ndarray)
    new_peaks = QtCore.Signal(np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray)
    new_overview = QtCore.Signal(np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray)
    finished = QtCore.Signal()
    error = QtCore.Signal(str)

    def run(self):
        try:
            # CSV path as a command line argument, defaulting to the
            # filename Jonne's scripts expect, so it still works with no
            # arguments but isn't locked to that one file.
            csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("2Gb signal.csv")

            self.log_msg.emit(f"1. Preparing to process: {csv_path.name}")

            if not csv_path.exists():
                raise FileNotFoundError(f"File not found at path: {csv_path.resolve()}")

            # Clear (or create) .dat files at the start
            open("channel1.dat", "wb").close()
            open("channel2.dat", "wb").close()

            ch1_stats = {'total': 0, 'low': 0, 'med': 0, 'high': 0}
            ch2_stats = {'total': 0, 'low': 0, 'med': 0, 'high': 0}


            # LINEAR DEPENDENCE (CALIBRATION)
            # Enter known test points here (Height -> Milliliters)
            calib_heights = np.array([120, 230, 350, 490])
            calib_ml = np.array([1.0, 2.0, 3.0, 4.0])

            # np.polyfit(x, y, 1) calculates the linear equation (y = kx + b)
            # k = slope, b = intercept
            k_val, b_val = np.polyfit(calib_heights, calib_ml, 1)
            self.log_msg.emit(f"-> Calibration loaded. Linear equation: ml = {k_val:.4f} * height + {b_val:.4f}")
            # =========================================================

            def analyze_peaks(signal, stats, chunk_offset):
                # Fixed threshold, see PEAK_PROMINENCE at the top of the file.
                min_prom = PEAK_PROMINENCE

                # Safe distance: 25000 = 0.5 seconds of silence between impacts
                min_distance = 25000

                peaks, props = find_peaks(signal, height=0, distance=min_distance, prominence=min_prom)

                # No per-chunk cap, see the module docstring for why.

                # Convert indices to seconds (50,000 Hz)
                peak_times = (peaks + chunk_offset) / 50000.0
                peak_heights = signal[peaks] if len(peaks) > 0 else np.array([])
                # 0 = low, 1 = med, 2 = high, relative to this chunk's own
                # max, same boundaries as the stats below, so the colours
                # on the chart match the counts logged at the end.
                peak_categories = np.zeros(len(peaks), dtype=int)

                if len(peaks) > 0:
                    h = props['peak_heights']
                    stats['total'] += len(peaks)

                    local_max = np.max(signal)
                    is_med = (h >= 0.33 * local_max) & (h < 0.66 * local_max)
                    is_high = h >= 0.66 * local_max
                    peak_categories[is_med] = 1
                    peak_categories[is_high] = 2
                    stats['low'] += np.sum(h < 0.33 * local_max)
                    stats['med'] += np.sum(is_med)
                    stats['high'] += np.sum(is_high)

                return peaks, peak_times, peak_heights, peak_categories

            def overview_envelope(signal, chunk_offset):
                """Min and max of each OVERVIEW_BUCKET samples, same idea as
                the M4 paper, so the full-file view never hides a peak that
                a plain stride would miss."""
                n_buckets = len(signal) // OVERVIEW_BUCKET
                usable = n_buckets * OVERVIEW_BUCKET
                blocks = signal[:usable].reshape(n_buckets, OVERVIEW_BUCKET)
                mins = blocks.min(axis=1)
                maxs = blocks.max(axis=1)
                bucket_starts = chunk_offset + np.arange(n_buckets) * OVERVIEW_BUCKET
                times = bucket_starts / 50000.0
                return times, mins, maxs

            # One chunk is 1,000,000 rows (20 seconds of data at a time)
            chunk_size = 1_000_000
            chunk_number = 1
            start_time = time.time()

            self.log_msg.emit("2. Starting chunked processing & live plotting...")

            for chunk in pd.read_csv(csv_path, chunksize=chunk_size):
                col_0 = chunk.iloc[:, 0].to_numpy(dtype=np.float32)
                col_1 = chunk.iloc[:, 1].to_numpy(dtype=np.float32)

                # Baseline removal (Uniform filter, fast C-optimized moving average)
                base_0 = uniform_filter1d(col_0, size=25000)
                base_1 = uniform_filter1d(col_1, size=25000)
                col_0_base = col_0 - base_0
                col_1_base = col_1 - base_1

                chunk_offset = (chunk_number - 1) * chunk_size

                # Find peaks
                p1_idx, p1_times, p1_heights, p1_cats = analyze_peaks(col_0_base, ch1_stats, chunk_offset)
                p2_idx, p2_times, p2_heights, p2_cats = analyze_peaks(col_1_base, ch2_stats, chunk_offset)

                # Log Channel 1 found peaks and calibrated volumes
                for p_time, p_height in zip(p1_times, p1_heights):
                    volume_ml = (k_val * p_height) + b_val
                    self.log_msg.emit(f"   [CH1 EVENT] Time: {p_time:.2f} s | Height: {p_height:.1f} -> Calculated volume: {volume_ml:.2f} ml")

                # Log Channel 2 found peaks and calibrated volumes
                for p_time, p_height in zip(p2_times, p2_heights):
                    volume_ml = (k_val * p_height) + b_val
                    self.log_msg.emit(f"   [CH2 EVENT] Time: {p_time:.2f} s | Height: {p_height:.1f} -> Calculated volume: {volume_ml:.2f} ml")

                # Save FULL QUALITY data to disk
                with open("channel1.dat", "ab") as f1, open("channel2.dat", "ab") as f2:
                    col_0_base.astype(np.float32).tofile(f1)
                    col_1_base.astype(np.float32).tofile(f2)

                # Send downsampled data (500x) to the GUI
                ds_factor = 500
                self.new_data.emit(col_0_base[::ds_factor], col_1_base[::ds_factor])
                self.new_peaks.emit(p1_times, p1_heights, p1_cats, p2_times, p2_heights, p2_cats)

                # Send the full-file overview envelope for this chunk, both channels
                ov_times, ov_mins1, ov_maxs1 = overview_envelope(col_0_base, chunk_offset)
                _, ov_mins2, ov_maxs2 = overview_envelope(col_1_base, chunk_offset)
                self.new_overview.emit(ov_times, ov_mins1, ov_maxs1, ov_mins2, ov_maxs2)

                self.log_msg.emit(f"   -> Chunk {chunk_number} processed ({(chunk_number * chunk_size):,} rows).")
                chunk_number += 1

            self.log_msg.emit("\n3. Finalizing Analysis...\n")
            self.log_msg.emit("--- Channel 1 Peaks ---")
            self.log_msg.emit(f"Total: {ch1_stats['total']} (High: {ch1_stats['high']}, Med: {ch1_stats['med']}, Low: {ch1_stats['low']})")
            self.log_msg.emit("--- Channel 2 Peaks ---")
            self.log_msg.emit(f"Total: {ch2_stats['total']} (High: {ch2_stats['high']}, Med: {ch2_stats['med']}, Low: {ch2_stats['low']})")

            elapsed = time.time() - start_time
            self.log_msg.emit(f"\n=== Processing Complete in {elapsed:.2f} seconds ===")
            self.finished.emit()

        except Exception as e:
            err_text = f"ERROR: {type(e).__name__}\n{e}\n{traceback.format_exc()}"
            self.error.emit(err_text)

# ==========================================
# 2. MAIN GUI (Logger + Plotter)
# ==========================================
class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Real-Time Signal Processor & Visualizer")
        self.resize(1200, 900)

        layout = QtWidgets.QVBoxLayout(self)

        self.text_box = QtWidgets.QTextEdit()
        self.text_box.setReadOnly(True)
        self.text_box.setMaximumHeight(200)
        layout.addWidget(self.text_box)

        # A stray click-drag directly on a plot (as opposed to the overview
        # region) can drag an axis to a strange range, this undoes that.
        self.reset_button = QtWidgets.QPushButton("Reset View")
        self.reset_button.clicked.connect(self.reset_view)
        layout.addWidget(self.reset_button)

        self.plot_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.plot_widget)

        self.p1 = self.plot_widget.addPlot(
            row=0, col=0, title="Channel 1 (Physical Base Level)",
            axisItems={'bottom': TimeAxisItem(orientation='bottom')},
        )
        self.p2 = self.plot_widget.addPlot(
            row=1, col=0, title="Channel 2 (Physical Base Level)",
            axisItems={'bottom': TimeAxisItem(orientation='bottom')},
        )
        self.p2.setXLink(self.p1)

        # Name axes (Time in minutes:seconds)
        self.p1.setLabel('bottom', 'Time')
        self.p2.setLabel('bottom', 'Time')
        self.p1.setLabel('left', 'Amplitude')
        self.p2.setLabel('left', 'Amplitude')

        # Signal plots (lines)
        self.curve1 = self.p1.plot(pen='g')
        self.curve2 = self.p2.plot(pen=pg.mkPen((255, 50, 170), width=1))  # bright pink, distinct from the orange/red peak categories

        # Marker Peaks, colour coded low/med/high (same chunk-relative
        # split Jonne's script already computed for the text log, just
        # made visible here too), with a live count in the legend.
        self.legend1 = self.p1.addLegend(offset=(10, 10))
        self.legend2 = self.p2.addLegend(offset=(10, 10))
        self.scatters1, self.labels1 = self._build_category_scatters(self.p1, self.legend1)
        self.scatters2, self.labels2 = self._build_category_scatters(self.p2, self.legend2)
        self.counts1 = {'low': 0, 'med': 0, 'high': 0}
        self.counts2 = {'low': 0, 'med': 0, 'high': 0}

        # Overview strips, whole file, one per channel, min/max envelope.
        # Both regions and the detail view are kept in sync, drag any one
        # of the three and the other two follow.
        self.p_overview1 = self.plot_widget.addPlot(
            row=2, col=0, title="Overview, whole file (Channel 1)",
            axisItems={'bottom': TimeAxisItem(orientation='bottom')},
        )
        self.p_overview2 = self.plot_widget.addPlot(
            row=3, col=0, title="Overview, whole file (Channel 2)",
            axisItems={'bottom': TimeAxisItem(orientation='bottom')},
        )
        self._syncing = False
        self.ov_times = np.array([], dtype=float)
        self.ov1_mins = np.array([], dtype=np.float32)
        self.ov1_maxs = np.array([], dtype=np.float32)
        self.ov2_mins = np.array([], dtype=np.float32)
        self.ov2_maxs = np.array([], dtype=np.float32)

        self.ov1_curve_min, self.ov1_curve_max, self.region1 = self._build_overview(self.p_overview1, (60, 200, 60))
        self.ov2_curve_min, self.ov2_curve_max, self.region2 = self._build_overview(self.p_overview2, (255, 50, 170))

        self.region1.sigRegionChanged.connect(lambda: self.region_changed(self.region1))
        self.region2.sigRegionChanged.connect(lambda: self.region_changed(self.region2))
        self.p1.sigRangeChanged.connect(self.detail_range_changed)

        # Memory buffers for the plot
        self.y1_plot_data = np.array([], dtype=np.float32)
        self.y2_plot_data = np.array([], dtype=np.float32)

        self.peak_buf1 = {name: (np.array([]), np.array([], dtype=np.float32)) for name in CATEGORY_NAMES}
        self.peak_buf2 = {name: (np.array([]), np.array([], dtype=np.float32)) for name in CATEGORY_NAMES}

        self._region_initialized = False

        # Start background thread
        self.worker = ProcessingWorker()
        self.worker.log_msg.connect(self.append_log)
        self.worker.new_data.connect(self.update_plot)
        self.worker.new_peaks.connect(self.update_peaks)
        self.worker.new_overview.connect(self.update_overview)
        self.worker.error.connect(self.handle_error)
        self.worker.start()

    def _build_category_scatters(self, plot, legend):
        scatters = {}
        labels = {}
        for name, color in zip(CATEGORY_NAMES, CATEGORY_COLORS):
            scatter = pg.ScatterPlotItem(size=14, pen=pg.mkPen(color, width=2), symbol='x')
            plot.addItem(scatter)
            legend.addItem(scatter, f"{name.capitalize()}: 0")
            scatters[name] = scatter
            labels[name] = legend.items[-1][1]
        return scatters, labels

    def _build_overview(self, plot, color):
        plot.setLabel('bottom', 'Time')
        plot.setMaximumHeight(120)
        curve_min = plot.plot(pen=pg.mkPen(color, width=1))
        curve_max = plot.plot(pen=pg.mkPen(color, width=1))
        fill = pg.FillBetweenItem(curve_min, curve_max, brush=pg.mkBrush(*color, 150))
        plot.addItem(fill)
        region = pg.LinearRegionItem()
        plot.addItem(region)
        return curve_min, curve_max, region

    def append_log(self, text):
        self.text_box.append(text)

    def update_plot(self, new_y1, new_y2):
        self.y1_plot_data = np.concatenate([self.y1_plot_data, new_y1])
        self.y2_plot_data = np.concatenate([self.y2_plot_data, new_y2])

        # Create time vector (0.01s steps, because ds_factor = 500)
        time_x = np.arange(len(self.y1_plot_data)) * 0.01

        self.curve1.setData(x=time_x, y=self.y1_plot_data)
        self.curve2.setData(x=time_x, y=self.y2_plot_data)

    def update_peaks(self, t1, h1, c1, t2, h2, c2):
        self._accumulate_peaks(t1, h1, c1, self.peak_buf1, self.scatters1, self.counts1, self.labels1)
        self._accumulate_peaks(t2, h2, c2, self.peak_buf2, self.scatters2, self.counts2, self.labels2)

    def _accumulate_peaks(self, t, h, c, buf, scatters, counts, labels):
        if len(t) == 0:
            return
        for i, name in enumerate(CATEGORY_NAMES):
            mask = c == i
            if not np.any(mask):
                continue
            times, heights = buf[name]
            buf[name] = (np.concatenate([times, t[mask]]), np.concatenate([heights, h[mask]]))
            counts[name] += int(mask.sum())
            scatters[name].setData(x=buf[name][0], y=buf[name][1])
            labels[name].setText(f"{name.capitalize()}: {counts[name]}")

    def update_overview(self, times, mins1, maxs1, mins2, maxs2):
        if len(times) == 0:
            return
        self.ov_times = np.concatenate([self.ov_times, times])
        self.ov1_mins = np.concatenate([self.ov1_mins, mins1])
        self.ov1_maxs = np.concatenate([self.ov1_maxs, maxs1])
        self.ov2_mins = np.concatenate([self.ov2_mins, mins2])
        self.ov2_maxs = np.concatenate([self.ov2_maxs, maxs2])

        self.ov1_curve_min.setData(x=self.ov_times, y=self.ov1_mins)
        self.ov1_curve_max.setData(x=self.ov_times, y=self.ov1_maxs)
        self.ov2_curve_min.setData(x=self.ov_times, y=self.ov2_mins)
        self.ov2_curve_max.setData(x=self.ov_times, y=self.ov2_maxs)

        # Pin each overview's own range to the full extent seen so far,
        # rather than relying on auto-range, which doesn't reliably pick up
        # a pen=None curve's bounds. It grows as more chunks arrive and
        # settles on the whole file once streaming finishes.
        self.p_overview1.setXRange(0, self.ov_times[-1], padding=0.01)
        self.p_overview1.setYRange(self.ov1_mins.min(), self.ov1_maxs.max(), padding=0.05)
        self.p_overview2.setXRange(0, self.ov_times[-1], padding=0.01)
        self.p_overview2.setYRange(self.ov2_mins.min(), self.ov2_maxs.max(), padding=0.05)

        if not self._region_initialized:
            # Start the scroller showing the first 20 seconds
            self.region1.setRegion((0, 20))
            self.region2.setRegion((0, 20))
            self._region_initialized = True

    def region_changed(self, region):
        if self._syncing:
            return
        self._syncing = True
        lo, hi = region.getRegion()
        self.p1.setXRange(lo, hi, padding=0)
        other = self.region2 if region is self.region1 else self.region1
        other.setRegion((lo, hi))
        self._syncing = False

    def detail_range_changed(self):
        if self._syncing:
            return
        self._syncing = True
        lo, hi = self.p1.viewRange()[0]
        self.region1.setRegion((lo, hi))
        self.region2.setRegion((lo, hi))
        self._syncing = False

    def reset_view(self):
        # Detail plots: fit the Y axis to whatever's currently loaded,
        # keep showing whatever time window the region currently marks.
        self.p1.enableAutoRange(axis=pg.ViewBox.YAxis)
        self.p2.enableAutoRange(axis=pg.ViewBox.YAxis)
        lo, hi = self.region1.getRegion()
        self.p1.setXRange(lo, hi, padding=0)

        # Overview plots: back to the full file, same as every normal update.
        if len(self.ov_times) > 0:
            self.p_overview1.setXRange(0, self.ov_times[-1], padding=0.01)
            self.p_overview1.setYRange(self.ov1_mins.min(), self.ov1_maxs.max(), padding=0.05)
            self.p_overview2.setXRange(0, self.ov_times[-1], padding=0.01)
            self.p_overview2.setYRange(self.ov2_mins.min(), self.ov2_maxs.max(), padding=0.05)

    def handle_error(self, err_text):
        self.text_box.append("\n!!! FATAL ERROR !!!\n")
        self.text_box.append(err_text)

if __name__ == '__main__':
    # No platform override here, forcing xcb breaks this on macOS (only
    # offscreen, minimal and cocoa are available there). Qt picks the
    # right backend per OS on its own.
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
