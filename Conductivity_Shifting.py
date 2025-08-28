"""
author: Tyler(Dongping) Zhang
date: July. 23, 2025
about: This script is for batch generating TS plots with multiple shifting factors using data stored in del files.
"""


import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from scipy.interpolate import interp1d
import gsw
import glob
import shutil

### Set 'file_path' to the folder that contains all .del files.
### Non-integer Shifting values are supported (maximum of 5 shift values).
### A positive value advances the conductivity signal, a negative value delays it.
### Output plots will be saved in the same folder as the DEL file.
folder_path = "C:/Users/ZHANGD/Desktop/DEL_file_sample"
Shift_Factor_List = [0, -0.65, 0.8,1, 1.9]




def format_processing_plot(
        ax: plt.Axes,
        x_var_name: str,
        x_var_units,
        y_var_name: str,
        y_var_units: str,
        plot_title: str,
        invert_yaxis: bool,
        add_legend: bool = False,
) -> None:
    """
    Format a plot that has already been initialized.
    inputs:
        - ax: from fig, ax = plt.subplots()
        - var_name: one of Temperature, Conductivity, Salinity,
                    Fluorescence, Oxygen, Oxygen_mL_L, Oxygen_umol_kg
        - var_units: the units corresponding to the selected var_name
        - plot_title: Should indicate which processing step the plots are at
        - add_legend: If True then add a legend to the plot, default False
    """
    if invert_yaxis:
        ax.invert_yaxis()
    ax.xaxis.set_label_position("top")
    ax.xaxis.set_ticks_position("top")

    # Add ticks to top and right sides of the plot, like IOS Shell does
    ax.tick_params(
        bottom=True,
        top=True,
        left=True,
        right=True,
        labelbottom=True,
        labeltop=True,
        labelleft=True,
        labelright=True,
    )

    # For Oxygen_mL_L and Oxygen_umol_kg, remove the units at the end of the var_name
    # since the units will go in brackets after
    x_var_name = x_var_name.split("_")[0]

    if x_var_units is not None:
        ax.set_xlabel(f"{x_var_name} ({x_var_units})")
    else:
        ax.set_xlabel(f"{x_var_name}")
    ax.set_ylabel(f"{y_var_name} ({y_var_units})")
    ax.set_title(plot_title, fontsize=5)
    if add_legend:
        ax.legend()
    plt.tight_layout()
    return

def do_ts_plot_with_Color(
        figure_dir: str, plot_title: str, figure_filename: str, cast_d: dict, cast_u=None,
):
    """Do T-S plot with isopycnal lines
    Reference: https://github.com/larsonjl/earth_data_tools/
    """
    fig, ax = plt.subplots()

    cast_numbers = [cast_i for cast_i in cast_d.keys()]

    # Initialize the min / max values for plotting isopycnals
    t_min = cast_d[cast_numbers[0]].Temperature.astype(float).min()
    t_max = cast_d[cast_numbers[0]].Temperature.astype(float).max()
    s_min = cast_d[cast_numbers[0]].Salinity.astype(float).min()
    s_max = cast_d[cast_numbers[0]].Salinity.astype(float).max()

    # Plot each cast
    # Define colors only once
    colors = ['black', 'blue', 'red', 'green', 'yellow']
    alphas = [1.0, 0.8, 0.6, 0.5, 0.4]

    # Plot each cast with its own color and label
    for i, cast_i in enumerate(cast_numbers):
        ax.plot(
            cast_d[cast_i].Salinity,
            cast_d[cast_i].Temperature,
            color=colors[i],
            alpha=alphas[i],
            label=str(cast_i)  # this will be used in legend
        )

        # Update temperature and salinity ranges
        t_min = min(t_min, cast_d[cast_i].Temperature.astype(float).min())
        t_max = max(t_max, cast_d[cast_i].Temperature.astype(float).max())
        s_min = min(s_min, cast_d[cast_i].Salinity.astype(float).min())
        s_max = max(s_max, cast_d[cast_i].Salinity.astype(float).max())

        if cast_u is not None:
            ax.plot(cast_u[cast_i].Salinity, cast_u[cast_i].Temperature, color="b")

            # Update temperature and salinity ranges
            t_min = min(t_min, cast_u[cast_i].Temperature.astype(float).min())
            t_max = max(t_max, cast_u[cast_i].Temperature.astype(float).max())
            s_min = min(s_min, cast_u[cast_i].Salinity.astype(float).min())
            s_max = max(s_max, cast_u[cast_i].Salinity.astype(float).max())

    # Finalize the min / max values for plotting isopycnals
    t_min -= 1
    t_max += 1
    s_min -= 1
    s_max += 1

    # Calculate how many gridcells we need in the x and y dimensions
    xdim = int(np.ceil(s_max - s_min) / 0.1)
    ydim = int(np.ceil(t_max - t_min))
    dens = np.zeros((ydim, xdim))

    # Create temp and salt vectors of appropriate dimensions
    ti = np.linspace(0, ydim, ydim) + t_min
    si = np.linspace(1, xdim, xdim) * 0.1 + s_min

    # Loop to fill in grid with densities
    for j in range(0, int(ydim)):
        for i in range(0, int(xdim)):
            dens[j, i] = gsw.rho(si[i], ti[j], 0)

    # Subtract 1000 to convert to sigma-t
    sigmat = dens - 1000

    # Add the isopycnal contour lines to the plot
    CS = ax.contour(si, ti, sigmat, linestyles='dashed', colors='k')
    plt.clabel(CS, fontsize=12, inline=1, fmt='%.2f')  # Label every second level

    # Do final plot formatting
    format_processing_plot(
        ax,
        x_var_name="Salinity",
        x_var_units="PSS-78",
        y_var_name="Temperature",
        y_var_units="C",
        plot_title=plot_title,
        invert_yaxis=False,
        add_legend=True

    )
    plt.savefig(os.path.join(figure_dir, figure_filename))
    plt.close(fig)
    return


# Step 1: Find the line number of "*END OF HEADER"
def find_header_end_line(file_path):
    with open(file_path, 'r') as f:
        for i, line in enumerate(f):
            if "*END OF HEADER" in line:
                return i + 1  # skip this line too


#Step 2: Extract column name
def extract_channel_names(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    channel_names = []
    inside_table = False
    for line in lines:
        if line.strip().startswith("$TABLE: CHANNELS"):
            inside_table = True
            continue
        if inside_table:
            if line.strip().startswith("$END"):
                break
            if line.strip().startswith("!"):
                continue  # skip comment lines
            if line.strip():  # if line isn't empty
                # Example: "  1 Scan_Number           n/a     ..."
                parts = line.strip().split()
                if len(parts) >= 2:
                    channel_names.append(parts[1])
    return channel_names



def SHIFT_CONDUCTIVITY_IOSSHELL(file_path, shift_Factor):

    #Parsing Data from DEL files into a dataframe using Channel as Column
    if file_path.startswith("file:///"):
        file_path = file_path.replace("file:///", "")
    elif file_path.endswith('"'):
        file_path = file_path.replace('"', "")
    else:
        file_path = file_path

    skip_rows = find_header_end_line(file_path)
    df = pd.read_csv(file_path, skiprows=skip_rows, delim_whitespace=True)
    channels = extract_channel_names(file_path)

    df.columns = channels  # Set as column headers
    df = df.reset_index(drop=True)

    # This section is to split upcast with downcast, but DEL files likely don't have upcast data
    idx_max_pressure = np.where(df['Pressure'] == df['Pressure'].max())[0][0]
    df['Cast_direction'] = ['u'] * len(df['Pressure'])
    df.loc[:idx_max_pressure, 'Cast_direction'] = 'd'

    # Rename primary T and S channel
    df = df.rename(columns={"Temperature:Primary": "Temperature"})
    df = df.rename(columns={"Salinity:T0:C0": "Salinity"})
    df = df.rename(columns={"Conductivity:Primary": "Conductivity"})


    df = df[(df["Salinity"] != -99.0) & (df["Temperature"] != -99.0)]
    df = df.reset_index(drop=True)



    #Shifting Section

    # positive shift advance the conductivity signal, shift up/value appear earlier
    # Fill the gap with the first value (same logic as SHIFT_CONDUCTIVITY() from RBR script )
    # In the RBR SHIFT_CONDUCTIVITY() function, filled value is always uses first value, even for negative shift(bottom gap), could be optimized in the future

    conductivity_shifted = False  #Flag for shifting
    if isinstance(shift_Factor, int): #If the shifting factor is an integer use RBR SHIFT_CONDUCTIVITY() function logic
        if shift_Factor != 0:
            conductivity_shifted = True
            if shift_Factor > 0:
                fill_val = df['Conductivity'].iloc[-1]  #Positive shift advance the signal, create a gap at the bottom, fill with the last value
            else:
                fill_val = df['Conductivity'].iloc[0]

            df['Conductivity'] = df['Conductivity'].shift(periods= shift_Factor* -1, fill_value=fill_val)  #pd.shift positive moves down, if positive shift advance the signal, need to multiply shift_Factor by -1

    else: #If shifting factor is NOT an integer
        conductivity_shifted = True

        x = np.arange(len(df))
        y = df['Conductivity'].values

        f_interp = interp1d(x, y, kind='linear', fill_value='extrapolate')

        shifted_x = x + shift_Factor  # advancing if shift_Factor > 0, delaying if < 0
        shifted_conductivity = f_interp(shifted_x)

        df['Conductivity'] = shifted_conductivity


    #Re-Calculate Salinity using shifted conductivity
    if conductivity_shifted:
        df['Salinity'] = gsw.SP_from_C(
            df['Conductivity'].astype(float).values* 10, #Convert from S/m to mS/cm
            df['Temperature'].astype(float).values,
            df['Pressure'].astype(float).values
        )




    # this line is in place is because do_ts_plot_with_Color() is expecting a dict with cast number, 001 is added as a dummy cast:
    cast_d = {str(shift_Factor): df[df["Cast_direction"] == "d"].copy()}   # 001 is the key of this dict, dict is required as an input for do_ts_plot_with_Color()


    cast_number = (os.path.basename(file_path)).split(".")[0]
    folder_name= os.path.basename(file_path).split(".")[0]

    do_ts_plot_with_Color(
        figure_dir = os.path.dirname(file_path)+"/"+ folder_name,
        plot_title="Shifting Factor:" + f"_{shift_Factor}",
        figure_filename=cast_number+ f"_{shift_Factor}_TS_Plot.png",
        cast_d=cast_d,
        cast_u=None  # Optional: provide if upcast is present
    )


del_files = glob.glob(os.path.join(folder_path, "*.del"))

for j in del_files:
    folder_name= os.path.basename(j).split(".")[0]
    target_folder = folder_path +"/"+ folder_name

    if os.path.isdir(target_folder):  #check to see if the folder exist, if so remove and recreate
        shutil.rmtree(target_folder)
    os.makedirs(target_folder)

    #Generating TS Plot Individually
    for i in Shift_Factor_List:
        SHIFT_CONDUCTIVITY_IOSSHELL(j, shift_Factor=i)





    #Generating TS Plots with different shifting factors in one plot
    combined_casts = {}

    for shift in Shift_Factor_List:
        # Run SHIFT_CONDUCTIVITY_IOSSHELL but collect cast instead of plotting

        skip_rows = find_header_end_line(j)
        df = pd.read_csv(j, skiprows=skip_rows, sep="\s+")
        channels = extract_channel_names(j)
        df.columns = channels
        df = df.reset_index(drop=True)

        idx_max_pressure = np.where(df['Pressure'] == df['Pressure'].max())[0][0]
        df['Cast_direction'] = ['u'] * len(df['Pressure'])
        df.loc[:idx_max_pressure, 'Cast_direction'] = 'd'

        df = df.rename(columns={"Temperature:Primary": "Temperature"})
        df = df.rename(columns={"Salinity:T0:C0": "Salinity"})
        df = df.rename(columns={"Conductivity:Primary": "Conductivity"})

        df = df[(df["Salinity"] != -99.0) & (df["Temperature"] != -99.0)]
        df = df.reset_index(drop=True)

        # Shift conductivity
        if isinstance(shift, int):
            if shift > 0:
                fill_val = df['Conductivity'].iloc[-1]
            else:
                fill_val = df['Conductivity'].iloc[0]
            df['Conductivity'] = df['Conductivity'].shift(periods=shift * -1, fill_value=fill_val)
        else:
            x = np.arange(len(df))
            y = df['Conductivity'].values
            f_interp = interp1d(x, y, kind='linear', fill_value='extrapolate')
            df['Conductivity'] = f_interp(x + shift)

        # Recalculate salinity
        df['Salinity'] = gsw.SP_from_C(df['Conductivity'] * 10, df['Temperature'], df['Pressure'])

        # Store downcast with label as key
        combined_casts[f"{shift:.2f}"] = df[df["Cast_direction"] == "d"].copy()


    cast_number = (os.path.basename(j)).split(".")[0]   #eg.2023-080-0010

    do_ts_plot_with_Color(
        figure_dir = os.path.dirname(j)+"/"+ folder_name,
        plot_title=cast_number + " - All Shifted TS Plot",
        figure_filename=cast_number + "_All_Shifts_TS_Plot.png",
        cast_d=combined_casts,
        cast_u=None
    )
