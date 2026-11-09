# HOTAS Layout Editor

A desktop editor for creating visual control layouts for DCS (Digital Combat Simulator). Arrange controls over a device image, draw connections, and save layouts as JSON or export them as PNG.

## Requirements

- Python 3.9 or later
- Tkinter (included with the standard Python installer)
- Pillow

## Run from source

```bash
python -m pip install -r requirements.txt
python editor.py
```

## Create and edit a layout

1. Select **Load device image** and choose a PNG or JPEG. Enter a device name when prompted.
2. Optionally select **Load DCS HTML controls** and choose an HTML export from DCS. The controls are added in a grid; use **Regenerate auto-imported controls** to restore them after editing or deleting them.
3. Arrange the boxes on the canvas:
   - Drag a box to move it. Use **Ctrl+click** to select multiple boxes.
   - Double-click a box to edit its properties. Adjust its color and title, subtitle, and footer font sizes (6–36 pt) in the sidebar.
   - Drag the bottom-right resize handle to resize a box.
   - Use **Insert new box** to add a custom control.
4. To draw a connection, select **Draw connection lines**, click to start, right-click to add waypoints, then left-click a box to finish. Press **Esc** to cancel.
5. Select **Save layout** to save the JSON and device image, or **Export layout as PNG** to create an image.

Text wraps to fit inside boxes. Canvas text scales with zoom; exported text is scaled for the image.

### Export controls from DCS

1. In DCS, open **Options → Controls**.
2. Select the aircraft or module whose bindings you want, then select the controller/device column to export.
3. Click **Make HTML** at the bottom of the Controls screen and save the generated `.html` file somewhere you can find it.
4. In the editor, click **Load DCS HTML controls** and select that file.

## Controls

| Action | Control |
|---|---|
| Select a box | Click |
| Move selected boxes | Drag |
| Select multiple boxes | Ctrl+click |
| Resize a box | Double-click it, then drag its bottom-right handle |
| Change a box color | Right-click it |
| Zoom | Mouse wheel (10–300%) |
| Pan | Middle-mouse drag or hold Space and drag |
| Delete selected boxes or line | Delete |
| Cancel line drawing or clear selection | Esc |
| Select a line | Click it |

## Saved files

Layouts are stored beside the application:

- When running from source: `layouts/<device_name>/`
- When running the executable: `layouts/<device_name>/` next to the executable

Each device folder contains `image.png` and `layout.json`; `layout.png` is created when you export. Opening a layout loads its image from the same folder as the JSON file. When you save, the layout is written to the application's `layouts` folder.

The JSON stores box positions, text, colors, font sizes, and connection lines, and can be edited manually.

## Build a Windows executable

Run either build script from the repository folder:

```powershell
.\build.ps1
```

Or double-click `build.bat`. The scripts install PyInstaller if needed and create `bin\HOTAS Layout Editor.exe`. Python is not required on the target computer. Keep the executable's `layouts` folder writable, and copy it alongside the executable to transfer saved layouts.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'PIL'`**: Run `python -m pip install -r requirements.txt`.
- **Layouts do not save**: Check that the application folder and its `layouts` folder are writable.
- **The layout opens without a device image**: Keep `image.png` (or another supported PNG/JPEG) in the same folder as `layout.json`.
