Batch TS Plot Generator with Conductivity Shifting



Author: Tyler (Dongping) Zhang

Date: July 23, 2025







**Description:**



This script batch-generates Temperature-Salinity (TS) plots from .del files by applying multiple conductivity shift values.

It supports non-integer shift factors and outputs individual and combined TS plots with isopycnal lines for visual comparison.







**Input Files:**



Place all your .del files inside the folder specified in folder\_path.









**Output:**



For each .del file, the script creates a folder with:



TS plots for each shift value and a combined TS plot showing all shifts for comparison.







**Shifting Logic:**



Positive shift values advance the conductivity signal (makes it appear earlier).



Negative shift values delay it.



Both integer and non-integer shift factors are supported (via interpolation).









**Dependencies:**



* pandas
* numpy
* matplotlib
* scipy
* gsw
* glob
* shutil
* os



Install them via pip if needed:  pip install pandas









**Plot Features:**



Temperature vs. Salinity curves for each shift factor

Isopycnal lines (equal density) overlaid using the Gibbs SeaWater (GSW) toolbox

Combined plots with color-coded lines and transparency

