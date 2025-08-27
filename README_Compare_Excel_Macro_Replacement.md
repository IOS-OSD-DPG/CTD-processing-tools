Compare Excel Macro Replacement

Author: Tyler (Dongping) Zhang

Date: Aug 5th, 2025







**Description:**



This script generates an interactive best-fit line plot for comparing data between primary and secondary sensors produced by iosshell compare.

Users can click on individual data points to toggle their inclusion in the regression.

The plot dynamically updates to reflect the selected subset of data, recalculating the linear fit and displaying updated slope and intercept values.







**Input Files:**



CSV file produced by IOSShell compare storing primary and secondary sensor value

Plot and Axis titles

Data pairs for comparison











**Dependencies:**



* pandas
* numpy
* tkinter
* matplotlib



Install them via pip if needed:  pip install pandas

