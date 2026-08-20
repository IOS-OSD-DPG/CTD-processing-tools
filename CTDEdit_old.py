import os
import sys
import json
import re
import datetime
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtGui import *
#sys.path.append("C:/Users/ZHANGD/Desktop/All Git Repo/ios-shell")
import ios_shell
import yaml
import pandas as pd
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.widgets import RectangleSelector
import seawater as sw



os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1" #Enable High DPI scaling


class Ui(QtWidgets.QMainWindow):
    def __init__(self, path, DefaultShow=None):
        super(Ui, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi(path, self)  # Load the .ui file
        if DefaultShow==True:
            self.show()

app = QtWidgets.QApplication(sys.argv)  # Create an instance of QtWidgets.QApplication
Main_Window = Ui(path='main.ui',DefaultShow=True)

Main_Window.plot_windows = []
#adding an attribute to main window, later when plots window are created, reference/store here
#otherwise, python destroys an object when there are no references to it

File_Picker_Button = Main_Window.findChild(QtWidgets.QPushButton, 'FilePickerButton')
File_Path_Entry=Main_Window.findChild(QtWidgets.QLineEdit, 'FilePathLineEntry')
Select_Variable_Button = Main_Window.findChild(QtWidgets.QPushButton, 'SelectVariableButton')
File_Path_Entry.setText("C:/Users/ZHANGD/Downloads/2023-080-0041.del")

selected_columns = []

def file_picker():
    file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        Main_Window,"Select a file","","DEL Files (*.del *.delpred)")
    if file_path:
        File_Path_Entry.setText(file_path)



def show_column_selector():
    #Opens column selection window, when done selecting, close the window and plot the selected column

    global selected_columns

    file_path = File_Path_Entry.text()
    file_name = str(os.path.basename(file_path))

    if not file_path or not os.path.exists(file_path):
        QtWidgets.QMessageBox.warning(Main_Window, "Error", "Invalid file path")
        return

    try:
        pf = ios_shell.ShellFile.fromfile(filename=file_path)
        df = pf.to_pandas()

    except Exception as e:
        QtWidgets.QMessageBox.warning(Main_Window, "Error", f"Failed to read file:\n{e}")
        return

    units_map = {channel.name: channel.units for channel in pf.file.channels}

    # Replace pad values with NaN
    channel_details = pf.file.channel_details
    for i in range(min(len(df.columns), len(channel_details))):
        try:
            pad_val = float(channel_details[i].pad)
        except (TypeError, ValueError):
            continue  # non-numeric pad (e.g. status/flag channels) -- leave as-is
        col_vals = pd.to_numeric(df.iloc[:, i], errors="coerce")
        is_pad = np.isclose(col_vals.values, pad_val)
        df.iloc[is_pad, i] = np.nan

    # Create popup window
    dialog = QtWidgets.QDialog(Main_Window)
    dialog.setWindowTitle("Select Variables " + file_name)
    dialog.resize(300, 400)

    layout = QtWidgets.QVBoxLayout(dialog)

    # --- Y-axis selector section ---
    y_axis_label = QtWidgets.QLabel("Select Y Axis:")
    layout.addWidget(y_axis_label)

    y_axis_combo = QtWidgets.QComboBox()
    y_axis_combo.addItems(list(df.columns))
    if "Pressure" in df.columns:
        y_axis_combo.setCurrentText("Pressure")
    layout.addWidget(y_axis_combo)

    # Separator line
    separator = QtWidgets.QFrame()
    separator.setFrameShape(QtWidgets.QFrame.HLine)
    separator.setFrameShadow(QtWidgets.QFrame.Sunken)
    layout.addWidget(separator)

    # --- X-axis selector section ---
    x_axis_label = QtWidgets.QLabel("Select X Axis Variables:")
    layout.addWidget(x_axis_label)

    # Scroll area (important if many columns)
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll_content = QtWidgets.QWidget()
    scroll_layout = QtWidgets.QVBoxLayout(scroll_content)

    checkboxes = []

    for col in df.columns:
        cb = QtWidgets.QCheckBox(col)
        scroll_layout.addWidget(cb)
        checkboxes.append(cb)

    scroll_content.setLayout(scroll_layout)
    scroll.setWidget(scroll_content)

    layout.addWidget(scroll)

    btn_ok = QtWidgets.QPushButton("Plot")
    layout.addWidget(btn_ok)

    def on_Plot():
        global selected_columns
        selected_columns = [cb.text() for cb in checkboxes if cb.isChecked()]
        y_col = y_axis_combo.currentText()

        dialog.accept()

        open_plot_window(df, selected_columns, file_name, file_path,
                         pf.file.channel_details, y_col, units_map)


    btn_ok.clicked.connect(on_Plot)

    dialog.exec_()






def update_ax(ax, x_vals, y_vals, is_good, col_name, y_col="Pressure",
              show_mode="all", xlim=None, ylim=None, is_first=True, unit="", y_unit=""):
    ax.clear()

    good = is_good
    bad = ~is_good

    # Always plot the good (included) points
    ax.scatter(x_vals[good], y_vals[good], s=5, color='blue', label="Included")

    # Only plot the bad (excluded) points when show_mode is "all"
    if show_mode == "all":
        ax.scatter(x_vals[bad], y_vals[bad], s=5, color='red', label="Excluded")

    ax.set_title(col_name)
    ax.set_xlabel(unit if unit else " ")

    # Only the leftmost subplot shows the shared y-axis label and tick labels.
    # On the others, suppressing both removes the gap between panels.
    if is_first:
        ax.set_ylabel(f"{y_col} ({y_unit})" if y_unit else y_col)
        ax.invert_yaxis()         # With a shared y-axis, inverting once on the first subplot propagates to all the others.

        fig = ax.figure
        for lg in fig.legends[:]:  # remove any previous figure-level legend first to avoid stacking copies.
            lg.remove()
        handles, labels = ax.get_legend_handles_labels()
        fig.legend(handles, labels, loc="lower left",
                   bbox_to_anchor=(0.0, 0.0), fontsize=10, markerscale=2,
                   handletextpad=0.1, borderpad=0.2, labelspacing=0.2)
    else:
        ax.set_ylabel("")
        ax.tick_params(labelleft=False)
    ax.grid(True)

    # Apply explicit limits AFTER everything else so legend/tight_layout/etc.
    # can't trigger an autoscale snap-back.
    if xlim is not None:
        ax.set_xlim(xlim)
    if ylim is not None:
        ax.set_ylim(ylim)


def open_plot_window(df, selected_columns, file_name, file_path,
                     channel_details, y_col="Pressure", units_map=None):
    # Mutable container so nested functions can read/update the current mode
    view_state = {"mode": "all"}
    if units_map is None:
        units_map = {}
    y_unit = units_map.get(y_col, "")

    def on_scroll(event):
        if event.inaxes is None:
            return

        base_scale = 1.15
        if event.button == 'up':
            scale = 1 / base_scale  # zoom in
        elif event.button == 'down':
            scale = base_scale  # zoom out
        else:
            return

        def clamp_window(new_a, new_b, lo, hi):
            reversed_order = new_a > new_b
            w_min, w_max = (new_b, new_a) if reversed_order else (new_a, new_b)
            width = w_max - w_min
            allowed = hi - lo
            if width >= allowed:
                w_min, w_max = lo, hi
            elif w_min < lo:
                w_max += (lo - w_min)
                w_min = lo
            elif w_max > hi:
                w_min -= (w_max - hi)
                w_max = hi
            return (w_max, w_min) if reversed_order else (w_min, w_max)

        # Cursor's relative position (0-1) within the hovered axes' current
        # y-range. Used to anchor the y-zoom on whatever pressure the user
        # is actually pointing at, instead of always zooming toward the
        # center of the full data range.
        hovered_ax = event.inaxes
        hy_min, hy_max = hovered_ax.get_ylim()
        y_frac = (event.ydata - hy_min) / (hy_max - hy_min) if (hy_max - hy_min) != 0 else 0.5

        mode = view_state["mode"]

        for pdata in plot_data:
            ax = pdata["ax"]

            x_min, x_max = ax.get_xlim()
            y_min, y_max = ax.get_ylim()

            # Zoom the y (pressure) axis, anchored on the cursor's position
            # (mapped into this subplot's own current y-range, since all
            # subplots share the y-axis this is normally the same point).
            oy_min, oy_max = pdata["y_orig"]
            y_anchor = y_min + y_frac * (y_max - y_min)

            new_y_min = y_anchor + (y_min - y_anchor) * scale
            new_y_max = y_anchor + (y_max - y_anchor) * scale

            y_pad = (oy_max - oy_min) * 0.05 if oy_max > oy_min else 1.0
            new_y_min, new_y_max = clamp_window(
                new_y_min, new_y_max, oy_min - y_pad, oy_max + y_pad
            )

            # Auto-fit x to whatever data actually falls inside the new
            # y-window, so the x range recenters/rescales on the values
            # that are actually visible instead of just scaling around a
            # fixed anchor (which can push the visible data off to one side).
            y_lo, y_hi = sorted((new_y_min, new_y_max))
            y_vals = pdata["y"]
            x_vals = pdata["x"]
            visible_mask = (y_vals >= y_lo) & (y_vals <= y_hi)
            if mode == "good" and pdata["is_good"].any():
                visible_mask &= pdata["is_good"]
            xs_visible = x_vals[visible_mask]

            with np.errstate(all="ignore"):
                vx_min = np.nanmin(xs_visible) if xs_visible.size else np.nan
                vx_max = np.nanmax(xs_visible) if xs_visible.size else np.nan

            if np.isfinite(vx_min) and np.isfinite(vx_max):
                if vx_max > vx_min:
                    x_pad = (vx_max - vx_min) * 0.15
                else:
                    # Only one distinct x value visible — fall back to a
                    # small fixed padding based on the full data extent.
                    ox_min, ox_max = pdata["x_orig"]
                    x_pad = (ox_max - ox_min) * 0.05 if ox_max > ox_min else 1.0
                new_x_min, new_x_max = vx_min - x_pad, vx_max + x_pad
            else:
                # No data falls in this y-window — leave the x view as-is.
                new_x_min, new_x_max = x_min, x_max

            ax.set_xlim(new_x_min, new_x_max)
            ax.set_ylim(new_y_min, new_y_max)

        canvas.draw_idle()

    def on_zoom_top5():
        if not plot_data:
            return

        oy_min, _ = plot_data[0]["y_orig"]
        y_lo, y_hi = oy_min, oy_min + 5
        mode = view_state["mode"]

        for pdata in plot_data:
            ax = pdata["ax"]
            y_vals = pdata["y"]
            x_vals = pdata["x"]

            visible_mask = (y_vals >= y_lo) & (y_vals <= y_hi)
            if mode == "good" and pdata["is_good"].any():
                visible_mask &= pdata["is_good"]
            xs_visible = x_vals[visible_mask]

            with np.errstate(all="ignore"):
                vx_min = np.nanmin(xs_visible) if xs_visible.size else np.nan
                vx_max = np.nanmax(xs_visible) if xs_visible.size else np.nan

            if np.isfinite(vx_min) and np.isfinite(vx_max):
                if vx_max > vx_min:
                    x_pad = (vx_max - vx_min) * 0.15
                else:
                    ox_min, ox_max = pdata["x_orig"]
                    x_pad = (ox_max - ox_min) * 0.05 if ox_max > ox_min else 1.0
                ax.set_xlim(vx_min - x_pad, vx_max + x_pad)

            ax.set_ylim(y_hi, y_lo)

        canvas.draw_idle()


    PAN_STEP = 0.1  # fraction of current x/y range to shift per key press

    def pan_view(dx_step=0.0, dy_step=0.0):
        if not plot_data:
            return
        for pdata in plot_data:
            ax = pdata["ax"]
            x_min, x_max = ax.get_xlim()
            y_min, y_max = ax.get_ylim()
            x_shift = (x_max - x_min) * dx_step
            y_shift = (y_max - y_min) * dy_step
            ax.set_xlim(x_min + x_shift, x_max + x_shift)
            ax.set_ylim(y_min + y_shift, y_max + y_shift)
        canvas.draw_idle()

    def on_pan_left():
        pan_view(dx_step=-PAN_STEP)

    def on_pan_right():
        pan_view(dx_step=PAN_STEP)

    def on_pan_down():
        # y-axis is inverted (surface at top), so "up" means toward
        # smaller pressure values -> shift the window down in data terms.
        pan_view(dy_step=-PAN_STEP)

    def on_pan_up():
        pan_view(dy_step=PAN_STEP)





    # --- Undo/redo state for point flagging --------------------------------
    # Each history entry is a dict: {(pdata_idx, point_idx): (old_val, new_val)}.
    # Storing both old and new values (rather than just toggling) lets undo
    # work correctly across heterogeneous batch edits — e.g. when batch mode
    # propagates "set bad" to a subplot where the point was already bad,
    # that subplot's entry has old_val == new_val and undo is a no-op for it.
    undo_stack = []
    redo_stack = []

    # Tracks current state of the "Batch edit mode" checkbox.
    batch_state = {"enabled": False}

    # Tracks the currently-open T-S plot window (if any), so edits made in
    # the main plot windows can push a live refresh to it instead of it
    # only ever showing a snapshot from when it was opened.
    ts_plot_state = {"window": None, "canvas": None, "ax": None,
                      "sal_col": None, "temp_col": None,
                      "x_orig": None, "y_orig": None}
    ts_pan_state = {"active": False, "start_x": None, "start_y": None,
                     "start_xlim": None, "start_ylim": None}

    def apply_changes(changes, use="new"):
        """Apply a changes dict to df_flags and refresh affected subplots.

        changes: {(col_name, point_idx): (old_val, new_val)}
        use: "new" -> set to new_val (forward action / redo)
             "old" -> set to old_val (undo)
        """
        if not changes:
            return

        # Track which columns were modified, then map to plotted subplots.
        affected_cols = set()
        for (col_name, point_idx), (old_val, new_val) in changes.items():
            target = new_val if use == "new" else old_val
            df_flags[col_name][point_idx] = target
            affected_cols.add(col_name)

        # Redraw each currently-plotted subplot whose column was touched.
        affected_subplots = set()
        for col_name in affected_cols:
            for pdata_idx in col_to_pdata_idx.get(col_name, ()):
                affected_subplots.add(pdata_idx)

        for pdata_idx in affected_subplots:
            pdata = plot_data[pdata_idx]
            ax = pdata["ax"]
            is_good = pdata["is_good"]

            # In "good only" mode, recompute the scroll-zoom clamp range.
            if view_state["mode"] == "good":
                (gx_min, gx_max), (gy_min, gy_max) = compute_bounds(
                    pdata["x"], pdata["y"], is_good, "good"
                )
                pdata["x_orig"] = (gx_min, gx_max)
                pdata["y_orig"] = (gy_min, gy_max)

            update_ax(ax, pdata["x"], pdata["y"], is_good,
                      ax.get_title() if ax.get_title() else "",
                      y_col, show_mode=view_state["mode"],
                      xlim=ax.get_xlim(), ylim=ax.get_ylim(),
                      is_first=pdata["is_first"], unit=pdata["unit"], y_unit=y_unit)
            rebuild_selector(pdata_idx)

        canvas.draw_idle()

        # If the T-S window is open and either of its columns was just
        # edited, push a live refresh so it doesn't go stale.
        if ts_plot_state["window"] is not None and (
            ts_plot_state["sal_col"] in affected_cols
            or ts_plot_state["temp_col"] in affected_cols
        ):
            refresh_ts_plot()

    def build_changes(source_pdata_idx, point_indices, target_value):
        """Build a changes dict for setting given point indices to target_value.
        """
        changes = {}
        if batch_state["enabled"]:
            target_cols = list(df_flags.keys())
        else:
            target_cols = [plot_data[source_pdata_idx]["col"]]

        for col_name in target_cols:
            mask = df_flags[col_name]
            for point_idx in point_indices:
                old_val = bool(mask[point_idx])
                if old_val != target_value:
                    changes[(col_name, point_idx)] = (old_val, target_value)
        return changes

    def on_click(event):
        if event.inaxes is None:
            return

        # Ignore right click or middle click
        if event.button != 1:
            return

        # When box-select mode is on, the RectangleSelector handles left clicks
        # for drawing the selection box — don't also flag the click point.
        if box_state["enabled"]:
            return

        for pdata_idx, pdata in enumerate(plot_data):
            ax = pdata["ax"]

            if event.inaxes != ax:
                continue

            x_vals = pdata["x"]
            y_vals = pdata["y"]
            is_good = pdata["is_good"]

            x_click = event.xdata
            y_click = event.ydata

            # Normalize distance so x/y scale difference doesn't break clicking
            x_range = ax.get_xlim()[1] - ax.get_xlim()[0]
            y_range = ax.get_ylim()[1] - ax.get_ylim()[0]

            # In "good only" mode, restrict clicks to good points so the user
            # can't accidentally toggle hidden bad points they can't see.
            if view_state["mode"] == "good":
                mask = is_good
            else:
                mask = np.ones(len(x_vals), dtype=bool)

            if not mask.any():
                return

            dist_full = np.full(len(x_vals), np.inf)
            dist_full[mask] = np.sqrt(
                ((x_vals[mask] - x_click) / x_range) ** 2 +
                ((y_vals[mask] - y_click) / y_range) ** 2
            )

            closest_idx = np.argmin(dist_full)

            if dist_full[closest_idx] < 0.03:
                # Determine the new value: toggle the source point's value.
                # In batch mode, propagate that same target value to all subplots.
                source_old = bool(is_good[closest_idx])
                target_value = not source_old
                changes = build_changes(pdata_idx, [closest_idx], target_value)
                if changes:
                    apply_changes(changes, use="new")
                    undo_stack.append(changes)
                    redo_stack.clear()

    def on_undo():
        if not undo_stack:
            return
        changes = undo_stack.pop()
        apply_changes(changes, use="old")
        redo_stack.append(changes)

    def on_redo():
        if not redo_stack:
            return
        changes = redo_stack.pop()
        apply_changes(changes, use="new")
        undo_stack.append(changes)

    # --- Box-select  -----------------------------------
    box_state = {"enabled": False, "selectors": []}
    revive_state = {"enabled": False}

    def on_box_select_factory(pdata_idx):
        """Return a RectangleSelector callback bound to a specific subplot."""
        def callback(eclick, erelease):
            x0, x1 = sorted([eclick.xdata, erelease.xdata])
            y0, y1 = sorted([eclick.ydata, erelease.ydata])

            # Ignore degenerate boxes (a click without drag)
            if x1 - x0 == 0 or y1 - y0 == 0:
                return

            pdata = plot_data[pdata_idx]
            x_vals = pdata["x"]
            y_vals = pdata["y"]
            is_good = pdata["is_good"]

            # Revive mode flips bad -> good. Default mode flips good -> bad.
            # In both cases we only act on points whose current state differs
            # from the target, so unaffected points stay untouched.
            # nan-safe: NaN comparisons are False, which excludes NaN points.
            if revive_state["enabled"]:
                inside = (
                    (x_vals >= x0) & (x_vals <= x1) &
                    (y_vals >= y0) & (y_vals <= y1) &
                    ~is_good
                )
                target_value = True
            else:
                inside = (
                    (x_vals >= x0) & (x_vals <= x1) &
                    (y_vals >= y0) & (y_vals <= y1) &
                    is_good
                )
                target_value = False

            indices = np.flatnonzero(inside).tolist()
            if not indices:
                return

            # Build changes: set these indices to target_value in this subplot,
            # propagated to all subplots if batch mode is on.
            changes = build_changes(pdata_idx, indices, target_value=target_value)
            if changes:
                apply_changes(changes, use="new")
                undo_stack.append(changes)
                redo_stack.clear()

        return callback

    def make_selector(pdata_idx):
        """Create a fresh RectangleSelector for a given subplot. Returns it
        already configured but with active state set to current box mode."""
        ax = plot_data[pdata_idx]["ax"]
        common_kwargs = dict(
            useblit=True,
            button=[1],  # left mouse only
            minspanx=5, minspany=5,
            spancoords='pixels',
            interactive=False,
        )
        rect_style = dict(facecolor='yellow', edgecolor='orange',
                          alpha=0.3, fill=True)
        # Different matplotlib versions use different kwarg names
        # ('rectprops' before 3.5, 'props' from 3.5+).
        try:
            rs = RectangleSelector(
                ax, on_box_select_factory(pdata_idx),
                props=rect_style, **common_kwargs,
            )
        except TypeError:
            rs = RectangleSelector(
                ax, on_box_select_factory(pdata_idx),
                rectprops=rect_style, **common_kwargs,
            )
        rs.set_active(box_state["enabled"])
        return rs

    def setup_box_selectors():
        """Create one RectangleSelector per subplot. Initially disabled."""
        for pdata_idx in range(len(plot_data)):
            box_state["selectors"].append(make_selector(pdata_idx))

    def rebuild_selector(pdata_idx):
        """Rebuild the selector for one subplot (e.g. after ax.clear())."""
        if pdata_idx >= len(box_state["selectors"]):
            return  # selectors not set up yet (e.g. during initial draw)
        box_state["selectors"][pdata_idx] = make_selector(pdata_idx)

    def on_box_mode_changed(checked):
        box_state["enabled"] = bool(checked)
        for rs in box_state["selectors"]:
            rs.set_active(bool(checked))



    # --- Right-click drag to pan -------------------------------------------
    pan_state = {"active": False, "start_x": None, "start_y": None,
                 "start_lims": []}
    def on_pan_press(event):
        # Right-click only; ignore presses outside any axes
        if event.button != 3 or event.inaxes is None:
            return
        pan_state["active"] = True
        pan_state["start_x"] = event.xdata
        pan_state["start_y"] = event.ydata
        # Snapshot every axes' current limits keyed by index in plot_data
        pan_state["start_lims"] = [
            (pdata["ax"].get_xlim(), pdata["ax"].get_ylim())
            for pdata in plot_data
        ]
        # Switch cursor to a closed-hand to signal panning
        try:
            canvas.setCursor(QtCore.Qt.ClosedHandCursor)
        except Exception:
            pass

    def on_pan_motion(event):
        if not pan_state["active"]:
            return
        if event.xdata is None or event.ydata is None:
            # Cursor left the axes area, keep drag alive but skip this frame
            return

        hovered_ax = event.inaxes
        if hovered_ax is None:
            return

        hx_lim = hovered_ax.get_xlim()
        hy_lim = hovered_ax.get_ylim()
        hx_span = hx_lim[1] - hx_lim[0]
        hy_span = hy_lim[1] - hy_lim[0]
        if hx_span == 0 or hy_span == 0:
            return

        dx_frac = (event.xdata - pan_state["start_x"]) / hx_span
        dy_frac = (event.ydata - pan_state["start_y"]) / hy_span

        for pdata, (start_xlim, start_ylim) in zip(plot_data, pan_state["start_lims"]):
            ax = pdata["ax"]
            x_min0, x_max0 = start_xlim
            y_min0, y_max0 = start_ylim
            x_span = x_max0 - x_min0
            y_span = y_max0 - y_min0

            # Apply the shift in this axes' own units (preserves zoom level)
            shift_x = -dx_frac * x_span  # negative: drag right -> view moves left
            shift_y = -dy_frac * y_span

            # Clamp the shift so the view can't be dragged past the data bounds + padding.
            ox_min, ox_max = pdata["x_orig"]
            oy_min, oy_max = pdata["y_orig"]
            x_pad = (ox_max - ox_min) * 0.05 if ox_max > ox_min else 1.0
            y_pad = (oy_max - oy_min) * 0.05 if oy_max > oy_min else 1.0
            x_lo, x_hi = ox_min - x_pad, ox_max + x_pad
            y_lo, y_hi = oy_min - y_pad, oy_max + y_pad

            # X clamp
            if shift_x < x_lo - x_min0:
                shift_x = x_lo - x_min0
            if shift_x > x_hi - x_max0:
                shift_x = x_hi - x_max0

            # Y clamp — y limits are stored as (large, small) due to invert_yaxis,
            y_lower, y_upper = min(y_min0, y_max0), max(y_min0, y_max0)
            if shift_y < y_lo - y_lower:
                shift_y = y_lo - y_lower
            if shift_y > y_hi - y_upper:
                shift_y = y_hi - y_upper

            ax.set_xlim(x_min0 + shift_x, x_max0 + shift_x)
            ax.set_ylim(y_min0 + shift_y, y_max0 + shift_y)

        canvas.draw_idle()

    def on_pan_release(event):
        if event.button != 3:
            return
        pan_state["active"] = False
        pan_state["start_lims"] = []
        try:
            canvas.unsetCursor()
        except Exception:
            pass


    def compute_bounds(x_vals, y_vals, is_good, mode):
        """Return ((x_min, x_max), (y_min, y_max)) for the given mode.

        Uses nan-safe min/max. Falls back to the full range if the
        good-only subset is empty or all-NaN.
        """
        if mode == "good" and is_good.any():
            xs = x_vals[is_good]
            ys = y_vals[is_good]
        else:
            xs = x_vals
            ys = y_vals

        # nan-safe; if everything is NaN, fall back to full data
        with np.errstate(all="ignore"):
            x_min, x_max = np.nanmin(xs), np.nanmax(xs)
            y_min, y_max = np.nanmin(ys), np.nanmax(ys)

        if not np.isfinite(x_min) or not np.isfinite(x_max):
            x_min, x_max = np.nanmin(x_vals), np.nanmax(x_vals)
        if not np.isfinite(y_min) or not np.isfinite(y_max):
            y_min, y_max = np.nanmin(y_vals), np.nanmax(y_vals)

        return (x_min, x_max), (y_min, y_max)

    def on_mode_changed(checked):
        # Checked -> hide excluded points (good only); unchecked -> show all
        new_mode = "good" if checked else "all"
        if new_mode == view_state["mode"]:
            return
        view_state["mode"] = new_mode

        # Redraw each subplot KEEPING the current zoom.
        for pdata_idx, pdata in enumerate(plot_data):
            ax = pdata["ax"]

            # Recompute the clamp range for the new mode
            (x_min, x_max), (y_min, y_max) = compute_bounds(
                pdata["x"], pdata["y"], pdata["is_good"], new_mode
            )
            pdata["x_orig"] = (x_min, x_max)
            pdata["y_orig"] = (y_min, y_max)

            # Redraw, preserving the current view by passing limits explicitly
            update_ax(ax, pdata["x"], pdata["y"], pdata["is_good"],
                      ax.get_title() if ax.get_title() else "",
                      y_col, show_mode=new_mode,
                      xlim=ax.get_xlim(), ylim=ax.get_ylim(),
                      is_first=pdata["is_first"], unit=pdata["unit"], y_unit=y_unit)
            # ax.clear() wiped the box selector for this subplot — rebuild.
            rebuild_selector(pdata_idx)

        canvas.draw_idle()

    def on_refresh():
        # Reset each subplot to a fully-zoomed-out view of the current mode's data extent
        for pdata_idx, pdata in enumerate(plot_data):
            ax = pdata["ax"]
            ox_min, ox_max = pdata["x_orig"]
            oy_min, oy_max = pdata["y_orig"]
            x_pad = (ox_max - ox_min) * 0.05 if ox_max > ox_min else 1.0
            y_pad = (oy_max - oy_min) * 0.05 if oy_max > oy_min else 1.0

            new_xlim = (ox_min - x_pad, ox_max + x_pad)
            # y is inverted (large, small); set as (max+pad, min-pad)
            new_ylim = (oy_max + y_pad, oy_min - y_pad)

            update_ax(ax, pdata["x"], pdata["y"], pdata["is_good"],
                      ax.get_title() if ax.get_title() else "",
                      y_col, show_mode=view_state["mode"],
                      xlim=new_xlim, ylim=new_ylim,
                      is_first=pdata["is_first"], unit=pdata["unit"], y_unit=y_unit)
            rebuild_selector(pdata_idx)

        canvas.draw_idle()

    def on_export():

        # Two parts: Channel Table: Min/Max, Actual Data
        # Part 1: Channel Table

        out_path = os.path.splitext(file_path)[0] + ".edt"

        if os.path.exists(out_path):
            reply = QtWidgets.QMessageBox.question(
                plot_window, "Overwrite?",
                f"{out_path}\nalready exists. Overwrite?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return

        export_comment, ok = QtWidgets.QInputDialog.getMultiLineText(
            plot_window, "Export Comment",
            "Enter a comment to record with this export (optional):",
            "",
        )
        if not ok:
            return
        export_comment = export_comment.strip()

        try:
            with open(file_path, "rb") as f:
                original_bytes = f.read()
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                plot_window, "Export failed",
                f"Could not read source file:\n{e}",
            )
            return

        try:
            text = original_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = original_bytes.decode("latin-1")     # fall back to latin-1.


        original_lines = text.splitlines(keepends=True)


        data_start_idx = None  # Find the data section start using '*END OF HEADER'.
        for i, line in enumerate(original_lines):
            if "*END OF HEADER" in line.upper():
                data_start_idx = i + 1
                break
        if data_start_idx is None:
            QtWidgets.QMessageBox.warning(plot_window, "Export failed","Could not locate '*END OF HEADER' in source file.",)
            return

        header_end_idx = data_start_idx - 1
        col_header_idx = None
        for i in range(header_end_idx):
            if re.match(r"^!-+1-+", original_lines[i].strip()):
                col_header_idx = i
                break
        comment_insert_idx = col_header_idx if col_header_idx is not None else header_end_idx

        col_order = list(df.columns)
        n_cols_expected = len(col_order)

        def _width_from_detail(detail):
            if detail.width:
                return detail.width
            # Width wasn't given in the header -- it's encoded in the Format field instead, e.g. "F9.4" -> 9, "I8" -> 8.
            m = re.search(r"\d+", detail.format)
            return int(m.group()) if m else 0

        def _decimals_from_detail(detail):
            if detail.decimal_places:
                return detail.decimal_places
            # Decimal_Places wasn't given in the header, ios_shell then defaults it to 0, but the precision is really encoded in the Format field instead, e.g. "F9.4" -> 4, "F10.5" -> 5.
            m = re.search(r"\.(\d+)", detail.format)
            return int(m.group(1)) if m else 0  #whole match as .4, group(1) explicit, from the one set of parentheses

        # Per-column width and decimal places from channel_details,
        col_widths = [_width_from_detail(channel_details[i]) if i < len(channel_details) else 0 for i in
                      range(n_cols_expected)]
        col_decimals = [_decimals_from_detail(channel_details[i]) if i < len(channel_details) else 0 for i in
                        range(n_cols_expected)]

        for i in range(n_cols_expected):
            if channel_details[i].type.strip().upper() == "T" and col_decimals[i] == 0:
                col_decimals[i] = 7

        spec_total_width = sum(col_widths)

        patched_lines = list(original_lines)

        def compute_new_minmax():
            """Return list of (new_min, new_max) per column index
            for a column that has zero good non-pad values, return none
            """
            results = []
            for ci in range(n_cols_expected):
                col_name = col_order[ci]  # column name
                col_type = channel_details[ci].type.strip().upper() if ci < len(channel_details) else ""

                if col_type == "D":
                    values = df.iloc[:, ci].values
                    mask = df_flags[col_name]
                    good = [d for d, ok in zip(values, mask) if ok and d is not None]
                    if not good:
                        results.append(None)
                    else:
                        doy = [d.timetuple().tm_yday for d in good]
                        results.append((float(min(doy)), float(max(doy))))
                    continue

                # Time columns hold datetime.time objects -- report min/max as the
                # fraction of a full day elapsed (e.g. 23:59:55 -> 0.9999421).
                if col_type == "T":
                    values = df.iloc[:, ci].values
                    mask = df_flags[col_name]
                    good = [t for t, ok in zip(values, mask) if ok and t is not None]
                    if not good:
                        results.append(None)
                    else:
                        frac = [
                            (t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1e6) / 86400
                            for t in good
                        ]
                        results.append((float(min(frac)), float(max(frac))))
                    continue

                if col_type == "DT":
                    results.append(None)
                    continue

                values = df.iloc[:, ci].values  # column value
                flags = df_flags[col_name]  # column flag

                with np.errstate(invalid="ignore"):  # invalid value is ignnored
                    finite = ~np.isnan(values.astype(float, copy=False))
                    not_pad = ~np.isclose(values, -99.0)

                mask = flags & finite & not_pad

                if not mask.any():
                    results.append(None)
                else:
                    good = values[mask]
                    results.append((float(np.min(good)), float(np.max(good))))
            return results



        def format_minmax(value, decimals):
            if value == 0:  # zero is always written bare, e.g. Time min "0" not "0.0000000"
                return "0"
            if decimals <= 0:  #if ios_shell cannot parse a decimal, the default is 0
                return str(int(round(value)))
            return f"{value:.{decimals}f}"


        def find_field_positions(underline):
            """Given an underline like '    !--- ----- ---' return a list
            of (start, end_exclusive) tuples for each run of '-'.
            """
            fields = []
            i = 0
            while i < len(underline):
                if underline[i] == '-':
                    s = i
                    while i < len(underline) and underline[i] == '-':
                        i += 1
                    fields.append((s, i))
                else:
                    i += 1
            return fields



        #Start Updating Channel Table Min/Max
        new_minmax = compute_new_minmax()

        table_start = None
        for i, line in enumerate(patched_lines):
            if "$TABLE: CHANNELS" in line and "$TABLE: CHANNEL DETAIL" not in line:
                table_start = i
                break

        if table_start is not None:
            underline_idx = None # Find header underline (line starting with !---)
            for i in range(table_start + 1, table_start + 5):
                if patched_lines[i].lstrip().startswith("!---"):
                    underline_idx = i
                    break

            fields = find_field_positions(patched_lines[underline_idx].rstrip("\r\n"))
            # Expected: No, Name, Units, Minimum, Maximum

            min_start, min_end = fields[3]
            max_start, max_end = fields[4]

            for i in range(underline_idx + 1, len(patched_lines)):
                raw = patched_lines[i]

                if raw.endswith("\r\n"):     # Separate the line content from its trailing newline (\r\n or \n).
                    content, ending = raw[:-2], "\r\n"
                elif raw.endswith("\n"):
                    content, ending = raw[:-1], "\n"
                else:
                    content, ending = raw, ""

                stripped = content.strip()
                if not stripped:
                    continue
                if stripped.startswith("$END"):
                    break
                no = int(stripped.split(None, 1)[0])       # Extract channel number from start of line, (first space split)


                ci = no - 1  # 1-based -> 0-based
                if ci < 0 or ci >= n_cols_expected:
                    continue

                mm = new_minmax[ci]
                dp = col_decimals[ci]
                if mm is None:
                    min_str = format_minmax(0, dp)
                    max_str = format_minmax(0, dp)
                else:
                    min_str = format_minmax(mm[0], dp)
                    max_str = format_minmax(mm[1], dp)


                min_field_width = min_end - min_start
                new_min_field = min_str.ljust(min_field_width) #no need to reformat max, cause left align and trailing space
                gap = patched_lines[underline_idx][min_end:max_start] # The gap between min and max fields (usually 1 space)

                new_line = (content[:min_start] + new_min_field + gap+ max_str)
                patched_lines[i] = new_line + ending



        # Export Part 2: Data Table

        def format_pad(width, decimals):
            """Format Pad Value using column width and decimal, right aligned.

            Examples:
              width=10, dp=3 -> "   -99.000"   (7 chars value, 3 leading spaces)
              width=11, dp=3 -> "    -99.000"
              width=10, dp=0 -> None (skip per user spec)
              width=2,  dp=3 -> None (won't fit -99.000 = 7 chars)
            """
            if decimals <= 0:
                return None
            value_str = "-99." + ("0" * decimals)
            if width < len(value_str):
                return None
            return value_str.rjust(width)



        def patch_via_spec_widths(line):
            """Strict fixed-width: each column occupies col_widths[i] chars.
            Returns patched line or None if widths don't add up.

            Line passed in is WITHOUT its line ending — caller re-attaches.
            """
            if len(line) != spec_total_width:
                return None
            out_parts = []
            pos = 0
            for col_i in range(n_cols_expected):
                w = col_widths[col_i]
                field = line[pos:pos + w]
                col_name = col_order[col_i]
                if not df_flags[col_name][row_idx]: # if current column row item is false, then it's pad, else untouched original number
                    pad = format_pad(w, col_decimals[col_i])
                    if pad is not None:
                        out_parts.append(pad)
                    else: #decimal<=0, too tight to append pad, append original number (ie. pump status)
                        out_parts.append(field)
                else:
                    out_parts.append(field)
                pos += w
            return "".join(out_parts)  #assembled new line with formatted pad



        row_idx = 0
        n_rows = len(df)

        for line_idx in range(data_start_idx, len(original_lines)):
            if row_idx >= n_rows:
                break

            raw_line = original_lines[line_idx]
            if raw_line.endswith("\r\n"):      # Separate the line content from its trailing newline (\r\n or \n).
                content, ending = raw_line[:-2], "\r\n"
            elif raw_line.endswith("\n"):
                content, ending = raw_line[:-1], "\n"
            else:
                content, ending = raw_line, ""

            if not content.strip():
                continue  # safeguard for empty line


            new_content = patch_via_spec_widths(content)
            if new_content is None:  # safeguard for original line length doesn't match sum of total column width
                print(f"Line {line_idx + 1}: length {len(content)} != spec {spec_total_width}, skipping")
                continue

            patched_lines[line_idx] = new_content + ending
            row_idx += 1

        if row_idx != n_rows:
            QtWidgets.QMessageBox.warning(
                plot_window, "Export warning",
                f"Expected {n_rows} data rows but only patched {row_idx}. "
                "The output file may be incomplete or misaligned.",)

        def build_comment_block(text, ending):

            timestamp = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            block = [f" Remarks from CTDEDIT ({timestamp}):{ending}"]
            for line in text.splitlines():
                block.append(f" {line}{ending}")
            return block

        if export_comment:
            # Determine line break
            insert_ref_raw = patched_lines[comment_insert_idx]
            if insert_ref_raw.endswith("\r\n"):
                header_ending = "\r\n"
            elif insert_ref_raw.endswith("\n"):
                header_ending = "\n"
            else:
                header_ending = ""

            comment_lines = build_comment_block(export_comment, header_ending)

            patched_lines = (
                    patched_lines[:comment_insert_idx]
                    + comment_lines
                    + patched_lines[comment_insert_idx:]
            )

        try:
            # Reassemble and write as bytes — preserves original encoding/EOLs.
            out_text = "".join(patched_lines)
            try:
                out_bytes = out_text.encode("utf-8")
            except UnicodeEncodeError:
                out_bytes = out_text.encode("latin-1")
            with open(out_path, "wb") as f:
                f.write(out_bytes)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                plot_window, "Export failed",
                f"Could not write output file:\n{e}", )
            return

        # Auto-save the flag sidecar so the file can be reopened and re-edited
        # without losing the current flag state. Silent unless write fails.
        sidecar_path = save_flags_sidecar()

        msg = f"Wrote {out_path}"
        if sidecar_path:
            msg += f"\nFlags saved to {sidecar_path}"
        QtWidgets.QMessageBox.information(
            plot_window, "Export complete", msg)


    def save_flags_sidecar():
        """Write df_flags to a .flag sidecar next to the source file. Preserves the
        complete per-column good/bad state so the file can be reopened later and re-edited
        without losing prior decisions.
        """
        out_path = os.path.splitext(file_path)[0] + ".flag"

        # Convert numpy bool arrays to plain Python lists for json serialization.
        flags_serializable = {
            col: [bool(v) for v in mask]
            for col, mask in df_flags.items()
        }

        payload = {
            "source_file": os.path.basename(file_path),
            "n_rows": len(df),
            "columns": list(df.columns),
            "flags": flags_serializable,
        }

        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                plot_window, "Flag sidecar write failed",
                f"Could not write flag file:\n{e}",
            )
            return None
        return out_path


    def on_load_flags():
        """Open a file picker for a .flag sidecar and apply it to df_flags.

        Mirrors the structure written by save_flags_sidecar. Validates row count
        before applying; columns missing from the sidecar keep their current
        flags (so partial sidecars still apply what they can). After loading,
        every currently-plotted subplot is redrawn and zoom-clamp ranges are
        recomputed so the new flags are visible immediately.
        """
        default_dir = os.path.dirname(file_path) or ""
        load_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            plot_window, "Load flag file", default_dir,
            "Flag files (*.flag);;JSON files (*.json);;All files (*)",
        )
        if not load_path:
            return  # user cancelled

        try:
            with open(load_path, "r", encoding="utf-8") as f:
                sidecar = json.load(f)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                plot_window, "Flag file load failed",
                f"Could not read flag file:\n{e}",
            )
            return

        sidecar_rows = sidecar.get("n_rows")
        sidecar_flags = sidecar.get("flags", {})
        nrows_local = len(df)

        if sidecar_rows != nrows_local:
            QtWidgets.QMessageBox.warning(
                plot_window, "Flag file mismatch",
                f"Flag file has {sidecar_rows} rows but data has {nrows_local}. "
                "Not loaded.",
            )
            return

        loaded_cols = 0
        skipped_cols = []
        for col_name, flag_list in sidecar_flags.items():
            if col_name in df_flags and len(flag_list) == nrows_local:
                df_flags[col_name][:] = np.array(flag_list, dtype=bool)
                loaded_cols += 1
            else:
                skipped_cols.append(col_name)

        # Refresh every currently-plotted subplot. Recompute zoom-clamp ranges
        # for "good only" mode and rebuild the box selectors (ax.clear wipes them).
        for pdata_idx, pdata in enumerate(plot_data):
            ax = pdata["ax"]
            if view_state["mode"] == "good":
                (gx_min, gx_max), (gy_min, gy_max) = compute_bounds(
                    pdata["x"], pdata["y"], pdata["is_good"], "good"
                )
                pdata["x_orig"] = (gx_min, gx_max)
                pdata["y_orig"] = (gy_min, gy_max)

            update_ax(ax, pdata["x"], pdata["y"], pdata["is_good"],
                      pdata["col"], y_col, show_mode=view_state["mode"],
                      xlim=ax.get_xlim(), ylim=ax.get_ylim(),
                      is_first=pdata["is_first"], unit=pdata["unit"], y_unit=y_unit)
            rebuild_selector(pdata_idx)

        # Loading is a fresh state, history from the prior session no longer
        # corresponds to what's on screen.
        undo_stack.clear()
        redo_stack.clear()

        canvas.draw_idle()

        refresh_ts_plot()

        msg = f"Loaded flags for {loaded_cols} columns from\n{load_path}"
        if skipped_cols:
            msg += f"\n\nSkipped {len(skipped_cols)} column(s) not in current data."
        QtWidgets.QMessageBox.information(plot_window, "Flags loaded", msg)

    def compute_ts_bounds(sal_col, temp_col):

        x_vals = df[sal_col].values
        y_vals = df[temp_col].values
        with np.errstate(all="ignore"):
            x_min, x_max = np.nanmin(x_vals), np.nanmax(x_vals)
            y_min, y_max = np.nanmin(y_vals), np.nanmax(y_vals)
        return (x_min, x_max), (y_min, y_max)

    def on_ts_scroll(event):
        ax = ts_plot_state["ax"]
        if ax is None or event.inaxes != ax:
            return

        base_scale = 1.15
        if event.button == 'up':
            scale = 1 / base_scale  # zoom in
        elif event.button == 'down':
            scale = base_scale  # zoom out
        else:
            return

        def clamp_window(new_a, new_b, lo, hi):
            w_min, w_max = (new_a, new_b) if new_a < new_b else (new_b, new_a)
            width = w_max - w_min
            allowed = hi - lo
            if width >= allowed:
                w_min, w_max = lo, hi
            elif w_min < lo:
                w_max += (lo - w_min)
                w_min = lo
            elif w_max > hi:
                w_min -= (w_max - hi)
                w_max = hi
            return w_min, w_max

        x_min, x_max = ax.get_xlim()
        y_min, y_max = ax.get_ylim()
        x_anchor, y_anchor = event.xdata, event.ydata

        new_x_min = x_anchor + (x_min - x_anchor) * scale
        new_x_max = x_anchor + (x_max - x_anchor) * scale
        new_y_min = y_anchor + (y_min - y_anchor) * scale
        new_y_max = y_anchor + (y_max - y_anchor) * scale

        ox_min, ox_max = ts_plot_state["x_orig"]
        oy_min, oy_max = ts_plot_state["y_orig"]
        x_pad = (ox_max - ox_min) * 0.05 if ox_max > ox_min else 1.0
        y_pad = (oy_max - oy_min) * 0.05 if oy_max > oy_min else 1.0

        new_x_min, new_x_max = clamp_window(new_x_min, new_x_max, ox_min - x_pad, ox_max + x_pad)
        new_y_min, new_y_max = clamp_window(new_y_min, new_y_max, oy_min - y_pad, oy_max + y_pad)

        ax.set_xlim(new_x_min, new_x_max)
        ax.set_ylim(new_y_min, new_y_max)
        ts_plot_state["canvas"].draw_idle()

    def on_ts_pan_press(event):
        ax = ts_plot_state["ax"]
        if event.button != 3 or event.inaxes is None or event.inaxes != ax:
            return
        ts_pan_state["active"] = True
        ts_pan_state["start_x"] = event.xdata
        ts_pan_state["start_y"] = event.ydata
        ts_pan_state["start_xlim"] = ax.get_xlim()
        ts_pan_state["start_ylim"] = ax.get_ylim()
        try:
            ts_plot_state["canvas"].setCursor(QtCore.Qt.ClosedHandCursor)
        except Exception:
            pass

    def on_ts_pan_motion(event):
        if not ts_pan_state["active"]:
            return
        if event.xdata is None or event.ydata is None:
            return  # cursor left the axes; keep drag alive but skip this frame

        ax = ts_plot_state["ax"]
        x_min0, x_max0 = ts_pan_state["start_xlim"]
        y_min0, y_max0 = ts_pan_state["start_ylim"]
        x_span = x_max0 - x_min0
        y_span = y_max0 - y_min0
        if x_span == 0 or y_span == 0:
            return

        shift_x = -(event.xdata - ts_pan_state["start_x"])
        shift_y = -(event.ydata - ts_pan_state["start_y"])

        ox_min, ox_max = ts_plot_state["x_orig"]
        oy_min, oy_max = ts_plot_state["y_orig"]
        x_pad = (ox_max - ox_min) * 0.05 if ox_max > ox_min else 1.0
        y_pad = (oy_max - oy_min) * 0.05 if oy_max > oy_min else 1.0
        x_lo, x_hi = ox_min - x_pad, ox_max + x_pad
        y_lo, y_hi = oy_min - y_pad, oy_max + y_pad

        # Clamp so the drag can't push the view past the data bounds + padding.
        if shift_x < x_lo - x_min0:
            shift_x = x_lo - x_min0
        if shift_x > x_hi - x_max0:
            shift_x = x_hi - x_max0
        if shift_y < y_lo - y_min0:
            shift_y = y_lo - y_min0
        if shift_y > y_hi - y_max0:
            shift_y = y_hi - y_max0

        ax.set_xlim(x_min0 + shift_x, x_max0 + shift_x)
        ax.set_ylim(y_min0 + shift_y, y_max0 + shift_y)
        ts_plot_state["canvas"].draw_idle()

    def on_ts_pan_release(event):
        if event.button != 3:
            return
        ts_pan_state["active"] = False
        try:
            ts_plot_state["canvas"].unsetCursor()
        except Exception:
            pass

    TS_PAN_STEP = 0.1  # fraction of current x/y range to shift per key press

    def ts_pan_view(dx_step=0.0, dy_step=0.0):
        ax = ts_plot_state["ax"]
        if ax is None:
            return
        x_min, x_max = ax.get_xlim()
        y_min, y_max = ax.get_ylim()
        x_shift = (x_max - x_min) * dx_step
        y_shift = (y_max - y_min) * dy_step
        ax.set_xlim(x_min + x_shift, x_max + x_shift)
        ax.set_ylim(y_min + y_shift, y_max + y_shift)
        ts_plot_state["canvas"].draw_idle()

    def on_ts_reset_view():
        """Zoom back out to the full data extent (plus padding)."""
        ax = ts_plot_state["ax"]
        if ax is None:
            return
        ox_min, ox_max = ts_plot_state["x_orig"]
        oy_min, oy_max = ts_plot_state["y_orig"]
        x_pad = (ox_max - ox_min) * 0.05 if ox_max > ox_min else 1.0
        y_pad = (oy_max - oy_min) * 0.05 if oy_max > oy_min else 1.0
        ax.set_xlim(ox_min - x_pad, ox_max + x_pad)
        ax.set_ylim(oy_min - y_pad, oy_max + y_pad)
        ts_plot_state["canvas"].draw_idle()

    def draw_ts_scatter(ax, sal_col, temp_col, keep_limits=False):

        xlim = ax.get_xlim() if keep_limits else None
        ylim = ax.get_ylim() if keep_limits else None

        ax.clear()

        x_vals = df[sal_col].values
        y_vals = df[temp_col].values
        is_good = df_flags[sal_col] & df_flags[temp_col]

        with np.errstate(all="ignore"):
            s_finite = x_vals[np.isfinite(x_vals)]
            t_finite = y_vals[np.isfinite(y_vals)]
        if s_finite.size and t_finite.size:
            s_pad = (s_finite.max() - s_finite.min()) * 0.05 or 0.5
            t_pad = (t_finite.max() - t_finite.min()) * 0.05 or 0.5
            s_grid = np.linspace(s_finite.min() - s_pad, s_finite.max() + s_pad, 150)
            t_grid = np.linspace(t_finite.min() - t_pad, t_finite.max() + t_pad, 150)
            S_grid, T_grid = np.meshgrid(s_grid, t_grid)
            sigma_t = sw.dens0(S_grid, T_grid) - 1000.0
            cs = ax.contour(S_grid, T_grid, sigma_t, colors='gray',
                            linewidths=0.7, linestyles='dashed', zorder=0)
            ax.clabel(cs, inline=True, fontsize=7, fmt="%.1f")

        ax.scatter(x_vals[is_good], y_vals[is_good], s=5, color='blue', label="Included")
        ax.scatter(x_vals[~is_good], y_vals[~is_good], s=5, color='red', label="Excluded")

        sal_unit = units_map.get(sal_col, "")
        temp_unit = units_map.get(temp_col, "")
        ax.set_xlabel(f"{sal_col} ({sal_unit})" if sal_unit else sal_col)
        ax.set_ylabel(f"{temp_col} ({temp_unit})" if temp_unit else temp_col)
        ax.set_title(f"T-S Plot - {file_name}")
        ax.grid(True)
        ax.legend(loc="best", fontsize=9, markerscale=2)

        if keep_limits and xlim is not None:
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)

    def refresh_ts_plot():
        """Redraw the T-S plot window (if one is open) to reflect the
        current df_flags, preserving the user's current zoom/pan."""
        if ts_plot_state["window"] is None:
            return
        draw_ts_scatter(ts_plot_state["ax"], ts_plot_state["sal_col"],
                         ts_plot_state["temp_col"], keep_limits=True)
        ts_plot_state["canvas"].draw_idle()

    def open_ts_plot_window(sal_col, temp_col):

        if ts_plot_state["window"] is not None:
            ts_plot_state["sal_col"] = sal_col
            ts_plot_state["temp_col"] = temp_col
            ts_plot_state["x_orig"], ts_plot_state["y_orig"] = compute_ts_bounds(sal_col, temp_col)
            draw_ts_scatter(ts_plot_state["ax"], sal_col, temp_col)
            ts_plot_state["ax"].figure.tight_layout()
            ts_plot_state["canvas"].draw_idle()
            ts_plot_state["window"].raise_()
            ts_plot_state["window"].activateWindow()
            return

        ts_window = QtWidgets.QMainWindow()
        ts_window.setWindowTitle(f"T-S Plot - {file_name}")
        ts_window.resize(600, 600)
        Main_Window.plot_windows.append(ts_window)

        central = QtWidgets.QWidget()
        ts_window.setCentralWidget(central)
        v_layout = QtWidgets.QVBoxLayout(central)

        ts_fig = Figure()
        ts_canvas = FigureCanvas(ts_fig)
        v_layout.addWidget(ts_canvas)

        reset_btn = QtWidgets.QPushButton("Reset View")
        v_layout.addWidget(reset_btn)

        ts_ax = ts_fig.add_subplot(1, 1, 1)

        ts_plot_state["window"] = ts_window
        ts_plot_state["canvas"] = ts_canvas
        ts_plot_state["ax"] = ts_ax
        ts_plot_state["sal_col"] = sal_col
        ts_plot_state["temp_col"] = temp_col
        ts_plot_state["x_orig"], ts_plot_state["y_orig"] = compute_ts_bounds(sal_col, temp_col)

        draw_ts_scatter(ts_ax, sal_col, temp_col)
        ts_fig.tight_layout()
        ts_canvas.draw()

        ts_canvas.mpl_connect("scroll_event", on_ts_scroll)
        ts_canvas.mpl_connect("button_press_event", on_ts_pan_press)
        ts_canvas.mpl_connect("motion_notify_event", on_ts_pan_motion)
        ts_canvas.mpl_connect("button_release_event", on_ts_pan_release)

        reset_btn.clicked.connect(on_ts_reset_view)

        ts_reset_shortcut = QtWidgets.QShortcut(QKeySequence("Ctrl+Space"), ts_window)
        ts_reset_shortcut.activated.connect(on_ts_reset_view)
        ts_pan_left_shortcut = QtWidgets.QShortcut(QKeySequence("Left"), ts_window)
        ts_pan_left_shortcut.activated.connect(lambda: ts_pan_view(dx_step=-TS_PAN_STEP))
        ts_pan_right_shortcut = QtWidgets.QShortcut(QKeySequence("Right"), ts_window)
        ts_pan_right_shortcut.activated.connect(lambda: ts_pan_view(dx_step=TS_PAN_STEP))
        ts_pan_up_shortcut = QtWidgets.QShortcut(QKeySequence("Up"), ts_window)
        ts_pan_up_shortcut.activated.connect(lambda: ts_pan_view(dy_step=TS_PAN_STEP))
        ts_pan_down_shortcut = QtWidgets.QShortcut(QKeySequence("Down"), ts_window)
        ts_pan_down_shortcut.activated.connect(lambda: ts_pan_view(dy_step=-TS_PAN_STEP))

        def on_ts_close(event):
            # Clear the tracked state so future edits stop trying to draw
            # onto a window that no longer exists, and so the menu action
            # opens a fresh window next time instead of reusing a dead one.
            ts_plot_state["window"] = None
            ts_plot_state["canvas"] = None
            ts_plot_state["ax"] = None
            ts_plot_state["sal_col"] = None
            ts_plot_state["temp_col"] = None
            ts_plot_state["x_orig"] = None
            ts_plot_state["y_orig"] = None
            event.accept()

        ts_window.closeEvent = on_ts_close

        ts_window.show()

    def on_show_TS_plot():

        temp_candidates = [c for c in df.columns if "temperature" in c.lower()]
        sal_candidates = [c for c in df.columns if "salinity" in c.lower()]

        if not temp_candidates or not sal_candidates:
            QtWidgets.QMessageBox.warning(
                plot_window, "T-S Plot",
                "Could not find both Temperature and Salinity columns in this file.",
            )
            return

        default_temp = temp_candidates[0]
        default_sal = sal_candidates[0]

        if len(temp_candidates) == 1 and len(sal_candidates) == 1:
            open_ts_plot_window(default_sal, default_temp)
            return

        # Ambiguous (e.g. Primary/Secondary sensors) -- let the user choose.
        dialog = QtWidgets.QDialog(plot_window)
        dialog.setWindowTitle("Select T-S Columns")
        dialog.resize(300, 160)
        layout = QtWidgets.QVBoxLayout(dialog)

        layout.addWidget(QtWidgets.QLabel("Temperature (Y axis):"))
        temp_combo = QtWidgets.QComboBox()
        temp_combo.addItems(temp_candidates)
        temp_combo.setCurrentText(default_temp)
        layout.addWidget(temp_combo)

        layout.addWidget(QtWidgets.QLabel("Salinity (X axis):"))
        sal_combo = QtWidgets.QComboBox()
        sal_combo.addItems(sal_candidates)
        sal_combo.setCurrentText(default_sal)
        layout.addWidget(sal_combo)

        btn_ok = QtWidgets.QPushButton("Plot")
        layout.addWidget(btn_ok)

        def on_ok():
            dialog.accept()
            open_ts_plot_window(sal_combo.currentText(), temp_combo.currentText())

        btn_ok.clicked.connect(on_ok)
        dialog.exec_()


    def on_show_shortcuts():
        shortcuts = [
            ("←", "Pan left"),
            ("→", "Pan right"),
            ("↑", "Pan up"),
            ("↓", "Pan down"),
            ("Ctrl+↑", "Zoom to first 5 units of y-range"),
            ("Ctrl+Space", "Refresh plot"),
            ("", ""),
            ("Ctrl+Z", "Undo last edit"),
            ("Ctrl+Shift+Z", "Redo"),
        ]

        rows = "".join(
            f"<tr><td>{key}</td><td style='padding-left:20px;'>{desc}</td></tr>"
            for key, desc in shortcuts
        )

        box = QtWidgets.QMainWindow()
        box.setWindowTitle("Keyboard Shortcuts")
        box.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        box.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        label = QtWidgets.QLabel(f"<table>{rows}</table>")
        label.setTextFormat(QtCore.Qt.RichText)
        label.setContentsMargins(12, 12, 12, 12)
        box.setCentralWidget(label)
        box.adjustSize()
        plot_window._shortcuts_box = box
        box.show()


    if not selected_columns:
        QtWidgets.QMessageBox.warning(Main_Window, "Warning", "No columns selected")
        return


    plot_window = QtWidgets.QMainWindow()
    uic.loadUi("plot.ui", plot_window)
    Main_Window.plot_windows.append(plot_window)
    plot_window.setWindowTitle(file_name)


    container = plot_window.findChild(QtWidgets.QWidget, "plotContainer")
    layout = QtWidgets.QGridLayout(container)

    # --- Top control row: hide-excluded checkbox + refresh button ---
    toggle_row = QtWidgets.QHBoxLayout()
    toggle_row.addStretch(1)

    hide_excluded_cb = QtWidgets.QCheckBox("Hide excluded points")
    hide_excluded_cb.setChecked(False)  # default = show all
    toggle_row.addWidget(hide_excluded_cb)

    refresh_btn = QtWidgets.QPushButton("Refresh Plot")
    toggle_row.addWidget(refresh_btn)
    toggle_row.addStretch(1)

    # Place the toggle row at the top, then the canvas below it
    layout.addLayout(toggle_row, 0, 0)

    fig = Figure()
    canvas = FigureCanvas(fig)
    layout.addWidget(canvas, 1, 0)

    # --- Bottom row: box-select mode + batch edit mode checkboxes ---
    bottom_row = QtWidgets.QHBoxLayout()
    bottom_row.addStretch(1)
    box_select_cb = QtWidgets.QCheckBox("Exclude multiple points (box select)")
    box_select_cb.setChecked(False)
    bottom_row.addWidget(box_select_cb)
    revive_cb = QtWidgets.QCheckBox("Revive")
    revive_cb.setChecked(False)
    bottom_row.addWidget(revive_cb)
    batch_edit_cb = QtWidgets.QCheckBox("Batch edit mode")
    batch_edit_cb.setChecked(False)

    bottom_row.addWidget(batch_edit_cb)
    bottom_row.addStretch(1)
    export_btn = QtWidgets.QPushButton("Export to .edt")

    bottom_row.addWidget(export_btn)
    load_flags_btn = QtWidgets.QPushButton("Load Flags")
    bottom_row.addWidget(load_flags_btn)
    layout.addLayout(bottom_row, 2, 0)

    # Make the canvas row expand and the toolbar rows stay compact
    layout.setRowStretch(0, 0)
    layout.setRowStretch(1, 1)
    layout.setRowStretch(2, 0)

    plot_data = []

    n = len(selected_columns)

    flag_col_name = next((c for c in df.columns if "prediction_flag" in c.lower()), None)    # Finds the column name that contains "prediction_flag"

    initial_flag_mask = None
    if flag_col_name is not None:  #if flag column found, check if it only contains 0 and 1
        flag_vals = df[flag_col_name]
        unique_vals = set(pd.unique(flag_vals.dropna()))
        has_nan = flag_vals.isna().any()
        if not has_nan and unique_vals.issubset({0, 1}):
            initial_flag_mask = (flag_vals.values == 0)  # returns a list the same length as flag_vals, set True where flag == 0, this works because this operation "df[col].values == 0" returns [True, Flase, True]
        else:
            QtWidgets.QMessageBox.warning(
                Main_Window, "Prediction flag column ignored because it contains values other than 0/1")

    nrows = len(df)
    if initial_flag_mask is not None: # df_flags is the same size as df, it holds a per-column good/bad mask for EVERY column, if initial_flag_mask is present, every column starts with a copy of the initial flag
        df_flags = {c: initial_flag_mask.copy() for c in df.columns}
    else:
        df_flags = {c: np.ones(nrows, dtype=bool) for c in df.columns}

    first_ax = None
    for i, col in enumerate(selected_columns):
        # Share y-axis across all subplots so they zoom/pan together vertically and use a common y-range. The first subplot defines the shared axis.
        if i == 0:
            ax = fig.add_subplot(1, n, i + 1)
            first_ax = ax
        else:
            ax = fig.add_subplot(1, n, i + 1, sharey=first_ax)

        x_vals = df[col].values
        y_vals = df[y_col].values

        is_good = df_flags[col] # Reference each column to df_flags, so subplot flagging mutates df_flags directly.


        plot_data.append({
            "ax": ax,
            "col": col,
            "x": x_vals,
            "y": y_vals,
            "is_good": is_good,
            "x_orig": (np.nanmin(x_vals), np.nanmax(x_vals)),
            "y_orig": (np.nanmin(y_vals), np.nanmax(y_vals)),
            "is_first": (i == 0),
            "unit": units_map.get(col, ""),
        })

        update_ax(ax, x_vals, y_vals, is_good, col, y_col,
                  show_mode=view_state["mode"], is_first=(i == 0),
                  unit=units_map.get(col, ""), y_unit=y_unit)



    col_to_pdata_idx = {}
    for pdata_idx, pdata in enumerate(plot_data):  #iterate through plot_data, look up pdata['col'] in the dict, append pdata_idx(subplot index) to the list value, if the key doesn't exist, create it
        col_to_pdata_idx.setdefault(pdata["col"], []).append(pdata_idx)
        """
        return: 
        col_to_pdata_idx = {
            "temperature": [0],
            "salinity":    [1],
            "pressure":    [2],}
        this dict is currently displayed columns for direct plot lookup, used in apply_changes
        which subplot are showing this column
        """

    fig.tight_layout()
    # Pull subplots together horizontally
    fig.subplots_adjust(wspace=0.05)

    canvas.mpl_connect("scroll_event", on_scroll)
    canvas.mpl_connect("button_press_event", on_click)
    canvas.mpl_connect("button_press_event", on_pan_press)
    canvas.mpl_connect("motion_notify_event", on_pan_motion)
    canvas.mpl_connect("button_release_event", on_pan_release)
    canvas.draw()

    hide_excluded_cb.toggled.connect(on_mode_changed)
    refresh_btn.clicked.connect(on_refresh)
    export_btn.clicked.connect(on_export)
    load_flags_btn.clicked.connect(on_load_flags)
    plot_window.actionShortcuts.triggered.connect(on_show_shortcuts)
    plot_window.actionShow_T_S_Plot.triggered.connect(on_show_TS_plot)



    setup_box_selectors()
    box_select_cb.toggled.connect(on_box_mode_changed)
    revive_cb.toggled.connect(
        lambda checked: revive_state.update({"enabled": bool(checked)})
    )
    batch_edit_cb.toggled.connect(
        lambda checked: batch_state.update({"enabled": bool(checked)})
    )

    undo_shortcut = QtWidgets.QShortcut(QKeySequence("Ctrl+Z"), plot_window)
    undo_shortcut.activated.connect(on_undo)
    redo_shortcut = QtWidgets.QShortcut(QKeySequence("Ctrl+Shift+Z"), plot_window)
    redo_shortcut.activated.connect(on_redo)
    refresh_shortcut = QtWidgets.QShortcut(QKeySequence("Ctrl+Space"), plot_window)
    refresh_shortcut.activated.connect(on_refresh)
    zoom_top5_shortcut = QtWidgets.QShortcut(QKeySequence("Ctrl+Up"), plot_window)
    zoom_top5_shortcut.activated.connect(on_zoom_top5)

    pan_left_shortcut = QtWidgets.QShortcut(QKeySequence("Left"), plot_window)
    pan_left_shortcut.activated.connect(on_pan_left)
    pan_right_shortcut = QtWidgets.QShortcut(QKeySequence("Right"), plot_window)
    pan_right_shortcut.activated.connect(on_pan_right)
    pan_up_shortcut = QtWidgets.QShortcut(QKeySequence("Up"), plot_window)
    pan_up_shortcut.activated.connect(on_pan_up)
    pan_down_shortcut = QtWidgets.QShortcut(QKeySequence("Down"), plot_window)
    pan_down_shortcut.activated.connect(on_pan_down)

    plot_window.show()

File_Picker_Button.clicked.connect(file_picker)
Select_Variable_Button.clicked.connect(show_column_selector)
app.exec_()