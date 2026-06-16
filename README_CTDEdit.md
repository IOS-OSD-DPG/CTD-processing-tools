9**Description:**



A PyQt5-based GUI tool for visually inspecting and editing CTD oceanographic profile data. 







**Requirements**:



* PyQt5
* pandas
* numpy
* matplotlib
* PyYAML
* ios_shell (https://github.com/IOS-OSD-DPG/ios-shell)







**Workflow:**



1. **Pick a file** — click the file-picker button or paste a path into the text entry. (Accepts .del and .delpred files)

2. **Select variables** — click to select variables for x and y axis.

3. **Edit** — a new plot window opens with one subplot per selected channel

   * Click points to toggle their flag.
   * Use box-select for bulk exclusion.
   * Enable batch mode if a flag change should apply across all columns.

4. **Export** — click Export to .ctd. The output is written next to the source file with the .ctd extension. 









**Keyboard Shortcuts**:



* Ctrl+Z	   Undo last flag change
* Ctrl+Shift+Z	   Redo
* Ctrl+Space	   Refresh/zoom out to full data extent







**Mouse controls**:



* Click on point	   Toggle flag (good <-> bad)
* Right click + drag	   Flag all enclosed good points as bad
* Scroll wheel		   Zoom







**Notes for Future Maintainer**:

* df\_flags is the single source of truth for per-(column, row) good/bad state. Each plotted subplot's is\_good array is a reference into df\_flags, so flag mutations update the plot data in lockstep without copying.



* RectangleSelector uses props= on matplotlib ≥ 3.5 and rectprops= before that. This code tries both.



* Undo entries store (old\_val, new\_val) per cell rather than just toggling, so undo works correctly when batch mode propagates a "set bad" to columns that were already bad (those entries become no-ops on undo instead of incorrectly flipping back).







**Limitation/Potential Next Step:**



1. Adding an option to write df\_flags into a standalone output would help preserve the original data, so a file can be reopened and re-edited without losing information. Also no need to add additional column the original output file.



2\. Add a "make good" feature for pre-predicted flags. For .delpred files, points pre-marked bad by the prediction\_flag column start out excluded. A point can be flipped from bad → good via undo only if it was flipped in the current session. Adding make-good feature so falsely-predicted points can be recovered.



































