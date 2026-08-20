import os
import sys
from PyQt5 import QtWidgets, QtCore
import ios_shell
import pandas as pd
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure



os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"  # Enable High DPI scaling


# =====================================================================
# Helpers: turn a parsed ShellFile into a DataFrame with unique,
# human-readable column labels ("Name [units]"), built straight from
# pf.data / pf.file.channels rather than relying on ShellFile.to_pandas()
# so we control column naming ourselves (duplicate channel names, such
# as the two "Oxygen:Dissolved:SBE" channels in different units, are
# common in these files and need to stay distinguishable).
# =====================================================================

def channel_label(channel):
    """Build a display label for a single Channel: 'Name [units]'."""
    name = (channel.name or "unnamed").strip()
    units = (channel.units or "").strip().strip("'").strip()
    if units and units.lower() not in ("n/a", ""):
        return f"{name} [{units}]"
    return name


def shellfile_to_dataframe(pf):
    """
    Convert a parsed ios_shell.ShellFile into (DataFrame, labels).

    Column order matches pf.file.channels order, which matches the
    column order of pf.data (guaranteed once the file has been
    processed, i.e. process_data=True, the default for fromfile()).
    Duplicate labels get a '#2', '#3', ... suffix so every column
    name stays unique and selectable.
    """
    channels = pf.file.channels
    labels = []
    seen = {}
    for ch in channels:
        label = channel_label(ch)
        if label in seen:
            seen[label] += 1
            label = f"{label} #{seen[label]}"
        else:
            seen[label] = 1
        labels.append(label)

    df = pd.DataFrame(pf.data, columns=labels)
    df = df.apply(pd.to_numeric, errors="coerce")
    return df, labels


def common_variables(labels_a, labels_b):
    """Labels present (by exact 'Name [units]' match) in both files."""
    set_b = set(labels_b)
    return [lbl for lbl in labels_a if lbl in set_b]


def guess_default_pressure(labels):
    for lbl in labels:
        if "pressure" in lbl.lower():
            return lbl
    return labels[0] if labels else None



class MainWindowUI(QtWidgets.QMainWindow):
    """Hand-coded replacement for main.ui — builds the same widgets/layout
    that uic.loadUi('main.ui', self) used to produce."""

    def __init__(self, DefaultShow=None):
        super(MainWindowUI, self).__init__()
        self.resize(496, 331)
        self.setWindowTitle("MainWindow")

        centralwidget = QtWidgets.QWidget(self)
        self.setCentralWidget(centralwidget)

        self.FilePickerButton = QtWidgets.QPushButton(centralwidget)
        self.FilePickerButton.setObjectName("FilePickerButton")
        self.FilePickerButton.setGeometry(QtCore.QRect(440, 160, 25, 23))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        self.FilePickerButton.setSizePolicy(sizePolicy)
        self.FilePickerButton.setMinimumSize(QtCore.QSize(5, 0))
        self.FilePickerButton.setMaximumSize(QtCore.QSize(25, 16777215))
        self.FilePickerButton.setText("...")

        self.SelectVariableButton = QtWidgets.QPushButton(centralwidget)
        self.SelectVariableButton.setObjectName("SelectVariableButton")
        self.SelectVariableButton.setGeometry(QtCore.QRect(390, 230, 75, 23))
        self.SelectVariableButton.setText("Enter")

        self.FilePathLineEntry = QtWidgets.QLineEdit(centralwidget)
        self.FilePathLineEntry.setObjectName("FilePathLineEntry")
        self.FilePathLineEntry.setGeometry(QtCore.QRect(30, 160, 401, 19))

        self.Icon_Label = QtWidgets.QLabel(centralwidget)
        self.Icon_Label.setObjectName("Icon_Label")
        self.Icon_Label.setGeometry(QtCore.QRect(30, 50, 281, 81))
        self.Icon_Label.setText('<html><head/><body><p><span style=" font-size:30pt;">CTD Compare</span></p></body></html>')
        self.Icon_Label.setTextFormat(QtCore.Qt.RichText)
        self.Icon_Label.setScaledContents(True)

        if DefaultShow == True:
            self.show()


app = QtWidgets.QApplication(sys.argv)  # Create an instance of QtWidgets.QApplication
Main_Window = MainWindowUI(DefaultShow=True)


File_Picker_Button = Main_Window.findChild(QtWidgets.QPushButton, 'FilePickerButton')
File_Path_Entry = Main_Window.findChild(QtWidgets.QLineEdit, 'FilePathLineEntry')
Select_Variable_Button = Main_Window.findChild(QtWidgets.QPushButton, 'SelectVariableButton')

# Keep references so windows aren't garbage collected once opened
Variable_Window = None
Plot_Window = None


def file_picker():
    global Selected_File_Paths
    file_paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
        Main_Window, "Select up to 2 files", "")
    if not file_paths:
        return
    if len(file_paths) > 2:
        QtWidgets.QMessageBox.warning(Main_Window, "Too many files selected", "Please select at most 2 files. Only the first 2 will be used.")
        file_paths = ""

    Selected_File_Paths = file_paths
    File_Path_Entry.setText("; ".join(file_paths))


def parse_input_files():
    global Parsed_Shell_Files, Variable_Window

    file_path = File_Path_Entry.text()
    if not file_path:
        QtWidgets.QMessageBox.warning(Main_Window, "No files selected", "Please select a file first.")
        return

    paths = [p.strip() for p in file_path.split("; ") if p.strip()]
    if len(paths) != 2:
        QtWidgets.QMessageBox.warning(Main_Window, "Select two files", "Please select exactly 2 files to compare.")
        return

    parsed = []
    for path in paths:
        try:
            pf = ios_shell.ShellFile.fromfile(filename=path)
            parsed.append(pf)
        except Exception as e:
            QtWidgets.QMessageBox.warning(Main_Window, "Error parsing file", f"Could not parse:\n{path}\n\n{e}")
            return

    Parsed_Shell_Files = parsed

    Variable_Window = VariableSelectionWindow(Parsed_Shell_Files[0], Parsed_Shell_Files[1])
    Variable_Window.show()


File_Picker_Button.clicked.connect(file_picker)
Select_Variable_Button.clicked.connect(parse_input_files)


class VariableSelectionWindow(QtWidgets.QDialog):

    def __init__(self, shell_file_a, shell_file_b):
        super().__init__()
        self.setWindowTitle("Select Comparison Variables")
        self.resize(420, 340)

        # File A / File B are parsed as given; self.order (set below)
        # decides which one is treated as Primary vs Secondary.
        self.file_lookup = {
            shell_file_a.filename: shell_file_a,
            shell_file_b.filename: shell_file_b,
        }

        self.df_lookup = {}
        self.labels_lookup = {}
        for name, pf in self.file_lookup.items():
            df, labels = shellfile_to_dataframe(pf)
            self.df_lookup[name] = df
            self.labels_lookup[name] = labels

        layout = QtWidgets.QVBoxLayout(self)

        # Primary / Secondary picker: two big buttons
        instructions = QtWidgets.QLabel("Click a button to swap Primary / Secondary")
        layout.addWidget(instructions)

        self.order = [shell_file_a.filename, shell_file_b.filename]

        pri_sec_row = QtWidgets.QHBoxLayout()

        self.primary_button = QtWidgets.QPushButton()
        self.primary_button.setMinimumHeight(70)
        self.primary_button.setStyleSheet("font-weight: bold;")
        self.primary_button.clicked.connect(self.swap_primary_secondary)

        self.secondary_button = QtWidgets.QPushButton()
        self.secondary_button.setMinimumHeight(70)
        self.secondary_button.setStyleSheet("font-weight: bold;")
        self.secondary_button.clicked.connect(self.swap_primary_secondary)

        pri_sec_row.addWidget(self.primary_button)
        pri_sec_row.addWidget(self.secondary_button)
        layout.addLayout(pri_sec_row)

        role_row = QtWidgets.QHBoxLayout()
        role_row.addWidget(QtWidgets.QLabel("Primary"), alignment=QtCore.Qt.AlignCenter)
        role_row.addWidget(QtWidgets.QLabel("Secondary"), alignment=QtCore.Qt.AlignCenter)
        layout.addLayout(role_row)

        self.update_pri_sec_buttons()

        labels_a = self.labels_lookup[shell_file_a.filename]
        labels_b = self.labels_lookup[shell_file_b.filename]
        self.common = common_variables(labels_a, labels_b)

        # Alignment axis dropdown
        layout.addWidget(QtWidgets.QLabel("Alignment axis:"))
        self.axis_dropdown = QtWidgets.QComboBox()
        self.axis_dropdown.addItems(self.common)
        default_axis = guess_default_pressure(self.common)
        if default_axis:
            self.axis_dropdown.setCurrentText(default_axis)
        layout.addWidget(self.axis_dropdown)

        # Comparing variable dropdown
        layout.addWidget(QtWidgets.QLabel("Comparing variable:"))
        self.variable_dropdown = QtWidgets.QComboBox()
        layout.addWidget(self.variable_dropdown)

        # Plot button
        self.plot_button = QtWidgets.QPushButton("Plot")
        self.plot_button.clicked.connect(self.on_plot_clicked)
        layout.addWidget(self.plot_button)

        self.axis_dropdown.currentTextChanged.connect(self.refresh_comparing_dropdown)
        self.refresh_comparing_dropdown()

    def current_order(self):
        return self.order[0], self.order[1]

    def update_pri_sec_buttons(self):
        self.primary_button.setText(os.path.basename(self.order[0]))
        self.secondary_button.setText(os.path.basename(self.order[1]))

    def swap_primary_secondary(self):
        self.order = [self.order[1], self.order[0]]
        self.update_pri_sec_buttons()


    def refresh_comparing_dropdown(self, *args):
        axis_variable = self.axis_dropdown.currentText()
        options = [v for v in self.common if v != axis_variable]

        prev = self.variable_dropdown.currentText()
        # remember what the user had selected (if anything), the goal is to retain existing selection after refreshing
        self.variable_dropdown.blockSignals(True)
        self.variable_dropdown.clear()
        self.variable_dropdown.addItems(options)
        if prev in options:
            self.variable_dropdown.setCurrentText(prev)
        self.variable_dropdown.blockSignals(False)

    def on_plot_clicked(self):
        global Plot_Window

        primary_name, secondary_name = self.current_order()
        axis_variable = self.axis_dropdown.currentText()
        compare_variable = self.variable_dropdown.currentText()

        if not axis_variable or not compare_variable:
            QtWidgets.QMessageBox.warning(self, "Missing selection", "Please select both an alignment axis and a comparing variable.")
            return

        df_primary = self.df_lookup[primary_name]
        df_secondary = self.df_lookup[secondary_name]

        Plot_Window = ComparisonPlotWindow(
            primary_name, secondary_name,
            df_primary, df_secondary,
            axis_variable, compare_variable,
        )
        Plot_Window.show()



class ComparisonPlotWindow(QtWidgets.QMainWindow):

    CLICK_RADIUS_PX = 8  # hit-test radius in screen pixels

    def __init__(self, primary_name, secondary_name, df_primary, df_secondary, axis_variable, compare_variable):
        super().__init__()
        primary_name = os.path.basename(primary_name)
        secondary_name = os.path.basename(secondary_name)
        self.setWindowTitle(f"{secondary_name} - {primary_name}: {compare_variable}")
        self.resize(900, 650)

        self.axis_variable = axis_variable
        self.compare_variable = compare_variable
        self.secondary_name = secondary_name
        self.primary_name = primary_name

        self.x_vals, self.y_vals = self.build_diff_series(df_primary, df_secondary, axis_variable, compare_variable)
        self.is_good = np.ones(len(self.x_vals), dtype=bool)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        vbox = QtWidgets.QVBoxLayout(central)

        self.figure = Figure(figsize=(9, 6))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        vbox.addWidget(self.canvas)

        self.canvas.mpl_connect('button_press_event', self.on_click)
        self.update_plot()

    def build_diff_series(self, df_primary, df_secondary, axis_variable, compare_variable):
        """
        Align Primary onto Secondary's axis values via linear interpolation,
        then compute Secondary - Primary at each Secondary sample.
        Points where Secondary's axis value falls outside Primary's axis
        range (interpolation not possible) are dropped.
        """
        p = df_primary[[axis_variable, compare_variable]].dropna()
        s = df_secondary[[axis_variable, compare_variable]].dropna()

        # np.interp requires the x-coordinates (primary axis) to be sorted
        p_sorted = p.sort_values(axis_variable)
        p_axis = p_sorted[axis_variable].values
        p_val = p_sorted[compare_variable].values

        s_axis = s[axis_variable].values
        s_val = s[compare_variable].values

        primary_interp = np.interp(s_axis, p_axis, p_val, left=np.nan, right=np.nan)
        diff = s_val - primary_interp

        valid = ~np.isnan(diff)
        return s_val[valid], diff[valid]

    def update_plot(self):
        self.ax.clear()
        good_mask = self.is_good
        bad_mask = ~self.is_good

        self.ax.scatter(self.x_vals[good_mask], self.y_vals[good_mask],
                         color='steelblue', alpha=0.7, label="Included Data")
        self.ax.scatter(self.x_vals[bad_mask], self.y_vals[bad_mask],
                         color='red', alpha=0.7, label="Excluded Data")

        if np.sum(good_mask) > 1:
            slope, intercept = np.polyfit(self.x_vals[good_mask], self.y_vals[good_mask], deg=1)
            x_fit = np.linspace(self.x_vals.min(), self.x_vals.max(), 100)
            y_fit = slope * x_fit + intercept
            self.ax.plot(x_fit, y_fit, 'darkred', linestyle='--',
                         label=f"Fit: y = {slope:.3g}x + {intercept:.3g}")

        self.ax.set_xlabel(f"Secondary ({self.secondary_name}) {self.compare_variable}")
        self.ax.set_ylabel(f"Difference (Secondary - Primary), {self.compare_variable}")
        self.ax.set_title(f"{self.compare_variable}: Secondary - Primary vs Secondary, aligned on {self.axis_variable}")
        self.ax.legend()
        self.ax.grid(True)
        self.canvas.draw_idle()

    def on_click(self, event):
        if event.inaxes != self.ax or event.xdata is None:
            return

        # Hit-test in pixel space so the click radius is independent of
        # the data's units/scale.
        click_px = self.ax.transData.transform((event.xdata, event.ydata))
        points_px = self.ax.transData.transform(np.column_stack([self.x_vals, self.y_vals]))
        dists = np.hypot(points_px[:, 0] - click_px[0], points_px[:, 1] - click_px[1])

        closest_idx = np.argmin(dists)
        if dists[closest_idx] < self.CLICK_RADIUS_PX:
            self.is_good[closest_idx] = not self.is_good[closest_idx]
            self.update_plot()


app.exec_()