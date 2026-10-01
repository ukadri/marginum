from pathlib import Path
import polars as pl
import numpy as np
from scipy.signal import savgol_filter
from fastdtw import fastdtw

#Let's define a path
csv_path = Path("Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv")

print("1. Let's read CSV-file...")

# scan_csv doesn´t load anything into memory, but creates LazyFrame an execution plan 
lazy_df = pl.scan_csv(csv_path, glob=False)

#Retrieve the columns and convert them to 1D Numpy-vector, float32 binary format.
# If the CSV is huge, it can be processed in streaming mode.(There is not s code yet,(add) ...collect(streaming=True).to_numpy()...)
#.squeeze() checks that a matrix is a pure 1D-vector for the filters
col_0 = lazy_df.select(pl.col(lazy_df.collect_schema().names()[0])).collect().to_numpy().squeeze().astype(np.float32)
col_1 = lazy_df.select(pl.col(lazy_df.collect_schema().names()[1])).collect().to_numpy().squeeze().astype(np.float32)

print("2. Noise filtering (Savitzky-Golay)...")
# Let's use moderate filtering (window_length 21, degree of the polynomial is 3)
# so that actual peaks are not excessively clipped. The `window_length` value can be adjusted if necessary.
col_0_smooth = savgol_filter(col_0, window_length=21, polyorder=3)
col_1_smooth = savgol_filter(col_1, window_length=21, polyorder=3)

print("3. Let's save filtered signals in binary format...")
# Let's save a binary on a disc so that GreatDataVisualizer.py can read these pure versions.
col_0_smooth.astype(np.float32).tofile("channel1.dat")
col_1_smooth.astype(np.float32).tofile("channel2.dat")

print("4. Normalize the signals for DTW calculation (Z-score)...")
# Mean to zero and standard deviation to one
col_0_norm = (col_0_smooth - np.mean(col_0_smooth)) / np.std(col_0_smooth)
col_1_norm = (col_1_smooth - np.mean(col_1_smooth)) / np.std(col_1_smooth)

print("5. Calculate the Dynamic Time Warping (DTW) distance...")
# We take only every 100th point so that the computer's RAM doesn't run out.
step = 100
s1_sub = col_0_norm[::step]
s2_sub = col_1_norm[::step]

# Let's calculate Dynamic Time Warping.
distance, path = fastdtw(s1_sub, s2_sub)

# Calculate the average normalized deviation per data point.
avg_diff = distance / len(path)

print("\n--- CONVERSION & ANALYSIS SUMMARY ---")
print("Conversion complete! channel1.dat and channel2.dat updated successfully.")
print(f"Downsampling factor used for DTW: Every {step}th sample ({len(s1_sub)} samples/channel)")
print(f"Average Z-score normalized DTW distance per point: {avg_diff:.4f}")
print("   Interpretation guide:")
print("   -> < 0.2  : Highly similar shapes")
print("   -> 0.2-0.5: Moderately similar shapes")
print("   -> > 1.0  : Significantly different shapes\n")