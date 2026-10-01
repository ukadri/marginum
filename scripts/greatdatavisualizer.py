"""
GreatDataVisualizer.py
----------------------
Executes the data conversion script in a background process, displays its 
live terminal output in a dedicated GUI log window, and renders the processed 
signal channels using PyQtGraph.
"""

import os
import sys
import subprocess
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets

# Set platform backend for PyQt
os.environ["QT_QPA_PLATFORM"] = "xcb"

app = QtWidgets.QApplication(sys.argv)

# 1. Create a dedicated GUI window for real-time processing logs
log_window = QtWidgets.QDialog()
log_window.setWindowTitle("Data Processing Status")
log_window.resize(550, 350)

layout = QtWidgets.QVBoxLayout(log_window)
text_box = QtWidgets.QTextEdit()
text_box.setReadOnly(True)  # Read-only log view
layout.addWidget(text_box)

log_window.show()
app.processEvents()  # Refresh GUI to render the log window immediately

# 2. Launch GreatDataConversionSGF.py and stream output in real time
process = subprocess.Popen(
    [sys.executable, "GreatDataConversionSGF.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

# Read and display stdout stream line by line
for line in iter(process.stdout.readline, ''):
    if line:
        text_box.append(line.strip())
        app.processEvents()  # Maintain GUI responsiveness during processing

process.stdout.close()
process.wait()

text_box.append("\n=== Opening Signal Visualizer... ===")
app.processEvents()

# 3. Memory-map binary files for efficient memory usage
y1_data = np.memmap("channel1.dat", dtype='float32', mode='r')
y2_data = np.memmap("channel2.dat", dtype='float32', mode='r')

# 4. Initialize main visualization window
win = pg.GraphicsLayoutWidget(show=True, title="Large 2-Channel Signal Visualizer")

# Add subplots with synchronized x-axes
p1 = win.addPlot(row=0, col=0, title="Channel 1 (Filtered)")
p2 = win.addPlot(row=1, col=0, title="Channel 2 (Filtered)")
p2.setXLink(p1)  # Link zoom and pan operations between subplots

# Plot Channel 1 (Green)
curve1 = p1.plot(pen='g')
curve1.setDownsampling(ds=True, auto=True, method='peak')
curve1.setData(y1_data)

# Plot Channel 2 (Blue)
curve2 = p2.plot(pen='b')
curve2.setDownsampling(ds=True, auto=True, method='peak')
curve2.setData(y2_data)

if __name__ == '__main__':
    QtWidgets.QApplication.instance().exec()