DCS HOTAS control map
=====================

Requires Python 3.9 or newer, Tkinter, and Pillow.
Python's standard Windows installer normally includes Tkinter.

Windows setup:
1. Extract every file in this zip into the same folder.
2. Open Command Prompt in that folder and run:
       py -m pip install -r requirements.txt
3. Run:
       py app.py

In DCS, use Options > Controls > Make HTML. In the app, select the
T.16000M joystick and TWCS throttle HTML files together or one at a time,
then click Save PNG. Other devices are skipped.

The diagram assumes TWCS Button 2 is the modifier M, including on the
joystick. The full command list below the diagram includes all parsed
bindings and axes; long diagram labels may be abbreviated. Axis curves
and other filters are not included in the DCS HTML exports.

The provided controller-template.png must remain alongside app.py.

The reference/ directory contains the separate throttle and joystick SVG
layouts supplied for future design work. The current program still uses
controller-template.png; it does not yet render or populate the SVGs.
