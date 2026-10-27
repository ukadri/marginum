"""
GreatDataRealTime.py
--------------------
For reading massive CSV data in chunks in a background thread, applies Matched Filter,
saves full resolution to .dat files, and plots a lightweight version in REAL-TIME.
"""

import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore

from scipy.signal import find_peaks, correlate
import scipy.signal.windows as windows
#from scipy.ndimage import gaussian_filter1d
from scipy.ndimage import uniform_filter1d

# ==========================================
# 1. BACKGROUND THREAD (Applies heavy calculation)
# ==========================================
class ProcessingWorker(QtCore.QThread):
    # Signal (Due to the level of PyQtGraph's compatibility)
    log_msg = QtCore.Signal(str)
    new_data = QtCore.Signal(np.ndarray, np.ndarray)
    finished = QtCore.Signal()
    error = QtCore.Signal(str)

    def run(self):
        try:
            # Name of Datafile
            csv_path = Path("2Gb signal.csv")
            
            self.log_msg.emit(f"1. Preparing to process: {csv_path.name}")
            
            if not csv_path.exists():
                raise FileNotFoundError(f"File not found at path: {csv_path.resolve()}")

            # Clear (or create) the .dat files at the beginning
            open("channel1.dat", "wb").close()
            open("channel2.dat", "wb").close()

            template = windows.gaussian(100, std=15)
            
            # Statistics
            ch1_stats = {'total': 0, 'low': 0, 'med': 0, 'high': 0}
            ch2_stats = {'total': 0, 'low': 0, 'med': 0, 'high': 0}

            def analyze_peaks(signal, stats):
                # 1. Calculate the background noise (standard deviation) for long pauses
                noise_std = np.std(signal)
                
                # 2. Strict threshold: The peak must rise to at least 6 times the level of the background noise.
                min_prom = noise_std * 6.0
                
                # 3. Safety distance within clusters (e.g., 5000 = 0.1 seconds)
                min_distance = 5000 
                
                peaks, props = find_peaks(signal, height=0, distance=min_distance, prominence=min_prom)
                
                if len(peaks) > 0:
                    h = props['peak_heights']
                    stats['total'] += len(peaks)
                    
                    local_max = np.max(signal)
                    stats['low'] += np.sum(h < 0.33 * local_max)
                    stats['med'] += np.sum((h >= 0.33 * local_max) & (h < 0.66 * local_max))
                    stats['high'] += np.sum(h >= 0.66 * local_max)

            # ---  ---
            chunk_size = 1_000_000
            chunk_number = 1
            start_time = time.time()
            
            self.log_msg.emit("2. Starting chunked processing & live plotting...")
                

            for chunk in pd.read_csv(csv_path, chunksize=chunk_size):
                col_0 = chunk.iloc[:, 0].to_numpy(dtype=np.float32)
                col_1 = chunk.iloc[:, 1].to_numpy(dtype=np.float32)

                # Filters
#               base_0 = gaussian_filter1d(col_0, sigma=500)
#               base_1 = gaussian_filter1d(col_1, sigma=500)
                base_0 = uniform_filter1d(col_0, size=25000)
                base_1 = uniform_filter1d(col_1, size=25000)
                col_0_base = col_0 - base_0
                col_1_base = col_1 - base_1

                col_0_mf = correlate(col_0_base, template, mode='same', method='fft') / np.sum(template)
                col_1_mf = correlate(col_1_base, template, mode='same', method='fft') / np.sum(template)

                # Analysis
                analyze_peaks(col_0_mf, ch1_stats)
                analyze_peaks(col_1_mf, ch2_stats)

                # Save FULL-QUALITY data to disk
                with open("channel1.dat", "ab") as f1, open("channel2.dat", "ab") as f2:
                    col_0_mf.astype(np.float32).tofile(f1)
                    col_1_mf.astype(np.float32).tofile(f2)

                # SEND LIGHTER DATA TO THE USER INTERFACE (Downsampling 500x)
                ds_factor = 500
                self.new_data.emit(col_0_mf[::ds_factor], col_1_mf[::ds_factor])

                self.log_msg.emit(f"   -> Chunk {chunk_number} processed ({(chunk_number * chunk_size):,} rows).")
                chunk_number += 1

            # Summary
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
# 2. MAIN USER INTERFACE (Log + Graph)
# ==========================================
class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Real-Time Signal Processor & Visualizer")
        self.resize(1000, 800)

        # Layout
        layout = QtWidgets.QVBoxLayout(self)

        # Log window at the top
        self.text_box = QtWidgets.QTextEdit()
        self.text_box.setReadOnly(True)
        self.text_box.setMaximumHeight(200)
        layout.addWidget(self.text_box)

        # Graph window at the bottom
        self.plot_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.plot_widget)

        self.p1 = self.plot_widget.addPlot(row=0, col=0, title="Channel 1 (Live Matched Filter)")
        self.p2 = self.plot_widget.addPlot(row=1, col=0, title="Channel 2 (Live Matched Filter)")
        self.p2.setXLink(self.p1)

        self.curve1 = self.p1.plot(pen='g')
        self.curve2 = self.p2.plot(pen='b')

        # Vectors to which new data is added on the screen
        self.y1_plot_data = np.array([], dtype=np.float32)
        self.y2_plot_data = np.array([], dtype=np.float32)

        # Starting a worker thread
        self.worker = ProcessingWorker()
        self.worker.log_msg.connect(self.append_log)
        self.worker.new_data.connect(self.update_plot)
        self.worker.error.connect(self.handle_error)
        self.worker.start()

    def append_log(self, text):
        self.text_box.append(text)

    def update_plot(self, new_y1, new_y2):
        self.y1_plot_data = np.concatenate([self.y1_plot_data, new_y1])
        self.y2_plot_data = np.concatenate([self.y2_plot_data, new_y2])
        self.curve1.setData(self.y1_plot_data)
        self.curve2.setData(self.y2_plot_data)

    def handle_error(self, err_text):
        self.text_box.append("\n!!! FATAL ERROR !!!\n")
        self.text_box.append(err_text)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())