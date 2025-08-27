"""
author: Tyler(Dongping) Zhang
date: August 1st, 2025
about: This script generates an interactive best-fit line plot for comparing data between primary and secondary sensors produced by iosshell compare.
Users can click on individual data points to toggle their inclusion in the regression.
The plot dynamically updates to reflect the selected subset of data, recalculating the linear fit and displaying updated slope and intercept values.

"""


import csv
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from tkinter import ttk


csv_path = "C:/Users/ZHANGD/Downloads/2024-002-dox-comp1.csv"

# Axis Name
plot_title = "Interactive Oxygen Difference Plot"
Axis_Title_X = "Secondary OXY_SBE Avg"
Axis_Title_Y = "Oxygen Difference (S - P)"
Data_Pairs = [2,3,4,5,6,7]

# Read header rows to form column names
with open(csv_path, newline='') as f:
    reader = csv.reader(f)
    lines = list(reader)

row8, row9, row10 = lines[7], lines[8], lines[9]
max_len = max(len(row8), len(row9), len(row10))
row8 += [''] * (max_len - len(row8))
row9 += [''] * (max_len - len(row9))
row10 += [''] * (max_len - len(row10))
column_names = [f"{a} {b} {c}".strip().replace("  ", " ") for a, b, c in zip(row8, row9, row10)]

# Handle duplicate "(S-P) Diff"
diff_indices = [i for i, name in enumerate(column_names) if name == "(S-P) Diff"]
if len(diff_indices) == 2:
    for idx in diff_indices:
        prev = column_names[idx - 1]
        suffix = prev.split()[1]
        column_names[idx] = f"(S-P) Diff {suffix}"


# === Plotting Logic ===
def plot_Best_Fit(csv_file, plotting_axis_list):
    df = pd.read_csv(csv_file, skiprows=10)
    df.columns = column_names      # Parsing CSV with correct column names
    df = df.dropna().reset_index(drop=True)


    # Regroup df and put into a dict using the first column: Primary File name
    # Iterate through the groups, (_, g) means ignore the default group name just use the group data itself
    # Note the i+1 as group name means dict group start from 1 not 0
    group_column = df.columns[0]
    split_dict = {i + 1: g.reset_index(drop=True) for i, (_, g) in enumerate(df.groupby(group_column, sort=False))}
    groups_to_plot = Data_Pairs
    combined_df = pd.concat([split_dict[k] for k in groups_to_plot if k in split_dict], ignore_index=True)

    x_vals = combined_df[plotting_axis_list[0]].values
    y_vals = combined_df[plotting_axis_list[1]].values
    y_err = combined_df[plotting_axis_list[2]].values
    is_good = np.ones(len(x_vals), dtype=bool)

    fig, ax = plt.subplots(figsize=(10, 6))
    return fig, ax, x_vals, y_vals, y_err, is_good

def update_plot(ax, x_vals, y_vals, y_err, is_good):
    ax.clear()
    good_mask = is_good
    bad_mask = ~is_good

    ax.errorbar(x_vals[good_mask], y_vals[good_mask], yerr=y_err[good_mask],
                fmt='o', color='steelblue', ecolor='gray', capsize=3, alpha=0.7, label="Included Data")
    ax.errorbar(x_vals[bad_mask], y_vals[bad_mask], yerr=y_err[bad_mask],
                fmt='o', color='red', ecolor='lightcoral', capsize=3, alpha=0.7, label="Excluded Data")

    if np.sum(good_mask) > 1:
        slope, intercept = np.polyfit(x_vals[good_mask], y_vals[good_mask], deg=1)
        x_fit = np.linspace(x_vals.min(), x_vals.max(), 100)
        y_fit = slope * x_fit + intercept
        ax.plot(x_fit, y_fit, 'darkred', linestyle='--', label=f"Fit: y = {slope:.3g}x + {intercept:.3g}")

    ax.set_xlabel(Axis_Title_X)
    ax.set_ylabel(Axis_Title_Y)
    ax.set_title(plot_title)
    ax.legend()
    ax.grid(True)
    ax.figure.canvas.draw_idle()

def create_onclick_handler(ax, x_vals, y_vals, y_err, is_good):
    def on_click(event): # mpl_connect expects a single-argument function that takes a MouseEvent
        if event.inaxes != ax:  #filter out clicks outside of the plot
            return

        x_click, y_click = event.xdata, event.ydata

        # Find the closest point
        min_dist = np.inf  # minimum distance starts at infinity so that any real distance will be smaller and replace it
        closest_idx = None  # placeholder for the index of the closest point to the click


        for i, (x_pt, y_pt) in enumerate(zip(x_vals, y_vals)):  # loop through all points to find the closest point to the click
            dist = np.hypot(x_click - x_pt, y_click - y_pt)  # calculate distance from click to point
            if dist < min_dist:  # compare with the current closest point and update if closer
                min_dist = dist
                closest_idx = i

        if min_dist < 0.05:  # if click is close enough(within 0.05 unit of the point), then the point is clicked and toggled.
            is_good[closest_idx] = not is_good[closest_idx]
            update_plot(ax, x_vals, y_vals, y_err, is_good)

    return on_click  #return the nested on_click() function
                     #Because mpl_connect expects a single-argument function that takes a MouseEvent.
                     #But on_click also needs access to ax, x_vals, y_vals, etc., which are not passed by mpl_connect.


# === Tkinter UI ===
root = tk.Tk()
root.title("Plotting Tool")
root.geometry("370x180")

tk.Label(root, text="x-axis:").grid(row=0, column=0, padx=10, pady=5, sticky='e')
tk.Label(root, text="y-axis:").grid(row=1, column=0, padx=10, pady=5, sticky='e')
tk.Label(root, text="Error bar:").grid(row=2, column=0, padx=10, pady=5, sticky='e')

dropdown_x = ttk.Combobox(root, values=column_names[3:], state="readonly", width=30)
dropdown_y = ttk.Combobox(root, values=column_names[3:], state="readonly", width=30)
dropdown_err = ttk.Combobox(root, values=column_names[3:], state="readonly", width=30)

dropdown_x.grid(row=0, column=1, padx=10, pady=5)
dropdown_y.grid(row=1, column=1, padx=10, pady=5)
dropdown_err.grid(row=2, column=1, padx=10, pady=5)

# Plot Button Function
def plot_graph():
    x_col = dropdown_x.get()
    y_col = dropdown_y.get()
    err_col = dropdown_err.get()

    if not all([x_col, y_col, err_col]):
        print("Please select all three axes.")
        return

    plotting_axis_list = [x_col, y_col, err_col]

    fig, ax, x_vals, y_vals, y_err, is_good = plot_Best_Fit(csv_path, plotting_axis_list)
    update_plot(ax, x_vals, y_vals, y_err, is_good)
    fig.canvas.mpl_connect('button_press_event',
                           create_onclick_handler(ax, x_vals, y_vals, y_err, is_good))
    plt.tight_layout()
    plt.show()

plot_button = tk.Button(root, text="Plot", command=plot_graph, width=10, height=1)
plot_button.place(x=250, y=120)

root.mainloop()
