# HOTAS Layout Editor

Interactive visual editor for designing custom HOTAS device control layouts for DCS (Digital Combat Simulator).

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python editor.py
```

## Features

✨ **Core Functionality**
- Load existing layouts from JSON (with auto-loaded images)
- **Auto-fit zoom** to show entire image on load (10-300% range)
- Drag & resize control boxes (200x200 default)
- Multi-select with Ctrl+Click
- Real-time color picker
- Connection lines with unlimited waypoints
- Zoom (10% to 300%) & pan controls
- Save layouts as JSON
- Export diagrams as PNG

✨ **Advanced Features**
- **Adjustable font sizes** with spinbox input (6-36pt per element)
- **Smart text wrapping** — Text stays within box boundaries at all zoom levels
- **Proportional font scaling** — Fonts scale with zoom for visual consistency
- **Unified text styling** — All text renders in black for maximum contrast
- Unlimited modifier support (1, 2, 3, 4+ modifiers)
- Line selection and deletion
- ESC key to cancel operations
- Real-time line preview while drawing

## Workflow

### Step 1: Load Device Image OR Open Existing Layout
**Option A: Start from scratch**
1. Click **"Load Image"** (🖼️ icon)
2. Select a PNG/JPG of your device
3. Enter device name (e.g., "T.16000M")
4. Canvas auto-fits zoom to show the entire image

**Option B: Load existing layout**
1. Click **"Open Layout"** (📂 icon)
2. Select a previously saved `layout.json` file
3. Image and all controls auto-load from that layout's folder
4. Canvas auto-fits zoom to show the entire image

### Step 2: Import Controls (Optional, if starting from scratch)
1. Click **"Load HTML"** (📄 icon)
2. Select DCS HTML export file
3. Control boxes are auto-placed in grid
4. Each box shows button + command from DCS

### Step 3: Customize Layout
| Task | How |
|------|-----|
| Move box | Click + Drag |
| Resize box | Drag bottom-right corner (red 50x50 box) |
| Edit box text | Double-click box or use sidebar |
| Change color | Right-click box (choose from 15 colors) |
| Multi-move boxes | Ctrl+Click multiple boxes, drag any one |
| Adjust font sizes | Select box, use spinboxes in sidebar (6-36pt each) |
| Delete box | Select box, press Delete |
| Undo import | Click "Regenerate Auto-Imported" button |

### Step 4: Draw Connection Lines (Optional)
1. Click **"Draw Line"** (📍 icon)
2. Click anywhere to start the line
3. Right-click to add waypoints (corners)
4. Left-click on a box to end the line
5. Line color matches the end box color
6. Press ESC to cancel

### Step 5: Select & Delete Lines
1. Click on any part of a line to select it
2. Selected line shows white outline
3. Press Delete to remove it

### Step 6: Save & Export
- Click **"Save Layout"** (💾 icon) → `layout.json`
- Click **"Export PNG"** (📸 icon) → `layout.png`

Layouts, copied device images, and exports are stored in
`layouts/{device_name}/` next to the executable, regardless of the current
working directory. When running from source, they are stored next to
`editor.py` instead. Opening a layout from another location does not move it;
saving it creates a local copy with its image.

## Text & Font System

### Font Sizing
- **Base sizes**: Title 14pt, Subtitle 11pt, Footer 9pt
- **Adjustable**: Select a box and use spinboxes in sidebar (6-36pt range)
- **Canvas behavior**: Fonts scale proportionally with zoom for visual consistency
- **Export behavior**: Fonts scale up to compensate for full-resolution image

### Text Wrapping
- **Automatic wrapping** when text exceeds box width
- **Word-aware** — Text breaks at word boundaries, never mid-word
- **Boundary safe** — Text always stays within box boundaries
- **Applies to**: Canvas editor AND PNG exports

### Color
- **All text**: Black (#000000) for maximum contrast on colored boxes
- **Title**: Bold black text at top of box
- **Subtitle**: Regular black text in middle of box
- **Footer**: Regular black text at bottom of box

## Controls Reference

### Mouse
| Action | Result |
|--------|--------|
| Click box | Select it |
| Click + Drag | Move selected box(es) |
| Drag corner | Resize single box |
| Ctrl + Click | Toggle multi-select |
| Ctrl + Drag | Move multiple boxes |
| Right-click box | Open color picker |
| Double-click box | Edit properties |
| Mouse Wheel Up | Zoom in (max 300%) |
| Mouse Wheel Down | Zoom out (min 10%) |
| Middle Mouse Drag | Pan canvas |
| Space + Drag | Pan canvas (Figma-style) |

### Line Drawing
| Action | Result |
|--------|--------|
| Left-click | Start line / End line on box |
| Right-click | Add waypoint |
| ESC | Cancel line drawing |
| Click line | Select line |
| Delete | Remove selected line |

### Keyboard
| Key | Action |
|-----|--------|
| Delete | Delete selected box(es) or line(s) |
| ESC | Cancel drawing or clear selection |
| Ctrl+Click | Multi-select boxes |
| Space | Hold for pan (Figma-style) |

## File Structure

```
editor.py                Main application (1585 lines)
requirements.txt        Python dependencies
build.ps1              PowerShell build script
build.bat              Batch build script
reference/             Example device layouts (T16000_REF.svg, TWCS_REF.svg)
layouts/               Saved user layouts
  └── {device_name}/
      ├── image.png       Device template
      ├── layout.json     Control positions, colors, text
      └── layout.png      Exported diagram
```

## Output Format

### layout.json
```json
{
  "device_name": "T.16000M",
  "image_width": 960,
  "image_height": 601,
  "boxes": [
    {
      "x": 100,
      "y": 150,
      "width": 200,
      "height": 200,
      "text": "Button 1",
      "subtitle": "Fire Trigger",
      "footer": "Mod: BTN2",
      "control_key": "JOY_BTN1",
      "color": "#81ff83",
      "title_font_size": 14,
      "subtitle_font_size": 11,
      "footer_font_size": 9
    }
  ],
  "lines": [
    {
      "start_point": [100, 100],
      "end_box_index": 0,
      "waypoints": [[150, 75], [200, 100]]
    }
  ]
}
```

You can edit JSON manually if needed! Font sizes use actual point sizes (6-36pt).

## Building to EXE

### Option 1: PowerShell (Recommended)
```powershell
.\build.ps1
```
- Automatically installs PyInstaller if needed
- Creates single `HOTAS Layout Editor.exe`
- Output: `.\bin\HOTAS Layout Editor.exe`

### Option 2: Batch (Double-click)
```
Double-click build.bat
```
Same as above but for Windows users who prefer batch.

### Option 3: Manual
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "HOTAS Layout Editor" --distpath ".\bin" editor.py
```

**No Python needed on target machine!** Users can run the EXE directly.
The directory containing the EXE must be writable. To move existing layouts to
another computer, copy the `layouts` folder alongside the EXE. The build
scripts preserve the `bin\layouts` folder when rebuilding.

## Troubleshooting

**"ModuleNotFoundError: No module named 'PIL'"**
```bash
pip install -r requirements.txt
```

**"Layouts not saving"**
- Check that the directory containing the EXE (or `editor.py` when running
  from source) and its `layouts/` folder are writable
- App creates folders automatically

**"Image won't load"**
- Use PNG or JPG format
- Check file permissions

**"Build fails with PyInstaller"**
- Make sure PyInstaller is installed: `pip install pyinstaller`
- Try clearing the `build/` folder and retrying

**"Lines disappear when I add waypoints"**
- This is fixed! Lines now preserve full path from start to end

**"Text is too big/small"**
- Select the box and adjust font sizes with spinboxes in the sidebar
- Range: 6pt to 36pt per element (actual point sizes)

## Tips & Tricks

💡 **Precise font control:** Use spinbox inputs to set exact font sizes (6-36pt per element)

💡 **Zoom without worrying:** Text size stays constant while boxes zoom - always readable!

💡 **Quick workflow:** Load HTML → Position boxes → Save. Next time, just click "Open Layout" (📂) to reload!

💡 **Precise positioning:** Zoom in (mouse wheel) for fine control

💡 **Color grouping:** Use same colors for related functions (e.g., all fire buttons = red)

💡 **Quick layout:** Load HTML first, then manually position boxes to match device

💡 **Export for printing:** Use "Export PNG" for print-friendly diagrams

💡 **Edit offline:** You can edit layout.json in any text editor

💡 **Font sizes:** Adjustable per box - make titles bigger, commands smaller

💡 **Unlimited modifiers:** Automatically handles DCS controls with 1, 2, 3, 4+ modifiers

## Quick Usage Examples

### Example 1: Create a new layout from scratch
```
1. File → Load Image (🖼️) → Select device PNG
2. File → Load HTML (📄) → Select DCS export
3. Drag boxes to match device layout
4. Right-click boxes to adjust colors
5. File → Save Layout (💾) → Done!
```

### Example 2: Edit an existing layout
```
1. File → Open Layout (📂)
2. Select a previously saved layout.json
3. Image and boxes auto-load
4. Make adjustments (move, resize, recolor)
5. File → Save Layout (💾) to update
```

### Example 3: Create connections between controls
```
1. File → Edit → Draw Line (📍)
2. Click anywhere to start
3. Right-click to add waypoints (corners/bends)
4. Left-click on end box to finish
5. Press Delete to remove a line
```

## Requirements

- **Python:** 3.9 or later
- **Tkinter:** Included with Python
- **Pillow:** `pip install -r requirements.txt`

## Command Reference

```bash
# Run the application
python editor.py

# Install dependencies
pip install -r requirements.txt

# Build to EXE (Windows)
.\build.ps1              # PowerShell
.\build.bat              # Batch
# or manually:
pyinstaller --onefile --windowed editor.py

# Run built EXE
.\bin\HOTAS Layout Editor.exe

# Optional: Clean build artifacts
python cleanup.py
```

## Project Status

✅ **Complete and fully functional**

Latest features:
- Line selection & deletion with visual feedback
- Font size adjustment controls
- Pixel-based text wrapping
- Unlimited modifier support
- Real-time line preview
- ESC key for canceling operations
- Centered toolbar icons with tooltips

All features tested and working smoothly.

---

**Ready to create custom HOTAS layouts!** 🎮
