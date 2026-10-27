"""
GreatDataRealTime.py, fixed
----------------------------
Jonne's greatdatachunking.py (27 October) unchanged except in one function,
analyze_peaks. Two changes there, both measured against the labelled Big
pieces reference recording, see docs/chunking-validation-findings.md.

1. The threshold was 10x each chunk's own noise standard deviation, which
   moves depending on what happens to be in that chunk. Replaced with a
   fixed value, PEAK_PROMINENCE, found by sweeping against the labelled
   recording.
2. The cap of 5 peaks per chunk is removed. It was clipping real detections
   whenever more than 5 real events fell inside one 20 second chunk, which
   happens throughout the labelled recording since its events are packed
   much closer together than the four hour recordings this cap was sized
   for.

Everything else, baseline removal, spacing, calibration, plotting, is
unchanged from his version.
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
# against the labelled Big pieces reference recording, see
# docs/chunking-validation-findings.md for the full table.
PEAK_PROMINENCE = 100


# 1. BACKGROUND THREAD (Processing)

class ProcessingWorker(QtCore.QThread):
    log_msg = QtCore.Signal(str)
    new_data = QtCore.Signal(np.ndarray, np.ndarray)
    new_peaks = QtCore.Signal(np.ndarray, np.ndarray, np.ndarray, np.ndarray)
    finished = QtCore.Signal()
    error = QtCore.Signal(str)

    def run(self):
        try:
            # File Name Here
            csv_path = Path("2Gb signal.csv")

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

                if len(peaks) > 0:
                    h = props['peak_heights']
                    stats['total'] += len(peaks)

                    local_max = np.max(signal)
                    stats['low'] += np.sum(h < 0.33 * local_max)
                    stats['med'] += np.sum((h >= 0.33 * local_max) & (h < 0.66 * local_max))
                    stats['high'] += np.sum(h >= 0.66 * local_max)

                return peaks, peak_times, peak_heights

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
                p1_idx, p1_times, p1_heights = analyze_peaks(col_0_base, ch1_stats, chunk_offset)
                p2_idx, p2_times, p2_heights = analyze_peaks(col_1_base, ch2_stats, chunk_offset)

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
                self.new_peaks.emit(p1_times, p1_heights, p2_times, p2_heights)

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
        self.resize(1200, 800)

        layout = QtWidgets.QVBoxLayout(self)

        self.text_box = QtWidgets.QTextEdit()
        self.text_box.setReadOnly(True)
        self.text_box.setMaximumHeight(200)
        layout.addWidget(self.text_box)

        self.plot_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.plot_widget)

        self.p1 = self.plot_widget.addPlot(row=0, col=0, title="Channel 1 (Physical Base Level)")
        self.p2 = self.plot_widget.addPlot(row=1, col=0, title="Channel 2 (Physical Base Level)")
        self.p2.setXLink(self.p1)

        # Name axes (Time in seconds)
        self.p1.setLabel('bottom', 'Time', units='s')
        self.p2.setLabel('bottom', 'Time', units='s')
        self.p1.setLabel('left', 'Amplitude')
        self.p2.setLabel('left', 'Amplitude')

        # Disable automatic "k" (kilo) prefix on the X-axis
        self.p1.getAxis('bottom').enableAutoSIPrefix(False)
        self.p2.getAxis('bottom').enableAutoSIPrefix(False)

        # Signal plots (lines)
        self.curve1 = self.p1.plot(pen='g')
        self.curve2 = self.p2.plot(pen='b')

        # Marker Peaks (Red crosses at peak locations)
        pen_red = pg.mkPen('r', width=2)
        self.scatter1 = pg.ScatterPlotItem(size=14, pen=pen_red, symbol='x')
        self.scatter2 = pg.ScatterPlotItem(size=14, pen=pen_red, symbol='x')
        self.p1.addItem(self.scatter1)
        self.p2.addItem(self.scatter2)

        # Memory buffers for the plot
        self.y1_plot_data = np.array([], dtype=np.float32)
        self.y2_plot_data = np.array([], dtype=np.float32)

        self.p1_peak_times = np.array([], dtype=float)
        self.p1_peak_heights = np.array([], dtype=np.float32)
        self.p2_peak_times = np.array([], dtype=float)
        self.p2_peak_heights = np.array([], dtype=np.float32)

        # Start background thread
        self.worker = ProcessingWorker()
        self.worker.log_msg.connect(self.append_log)
        self.worker.new_data.connect(self.update_plot)
        self.worker.new_peaks.connect(self.update_peaks)
        self.worker.error.connect(self.handle_error)
        self.worker.start()

    def append_log(self, text):
        self.text_box.append(text)

    def update_plot(self, new_y1, new_y2):
        self.y1_plot_data = np.concatenate([self.y1_plot_data, new_y1])
        self.y2_plot_data = np.concatenate([self.y2_plot_data, new_y2])

        # Create time vector (0.01s steps, because ds_factor = 500)
        time_x = np.arange(len(self.y1_plot_data)) * 0.01

        self.curve1.setData(x=time_x, y=self.y1_plot_data)
        self.curve2.setData(x=time_x, y=self.y2_plot_data)

    def update_peaks(self, t1, h1, t2, h2):
        # Update red cross positions
        if len(t1) > 0:
            self.p1_peak_times = np.concatenate([self.p1_peak_times, t1])
            self.p1_peak_heights = np.concatenate([self.p1_peak_heights, h1])
            self.scatter1.setData(x=self.p1_peak_times, y=self.p1_peak_heights)

        if len(t2) > 0:
            self.p2_peak_times = np.concatenate([self.p2_peak_times, t2])
            self.p2_peak_heights = np.concatenate([self.p2_peak_heights, h2])
            self.scatter2.setData(x=self.p2_peak_times, y=self.p2_peak_heights)

    def handle_error(self, err_text):
        self.text_box.append("\n!!! FATAL ERROR !!!\n")
        self.text_box.append(err_text)

if __name__ == '__main__':
    # Wayland workaround for potential warnings
    import os
    os.environ["QT_QPA_PLATFORM"] = "xcb"

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
