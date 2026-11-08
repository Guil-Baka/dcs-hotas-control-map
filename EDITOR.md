# Interactive HOTAS Layout Editor

A fully interactive editor for creating custom HOTAS device layouts with visual editor, drag-and-drop boxes, and connection lines.

## Features

✅ **Image Upload** - Load device photos/templates  
✅ **DCS HTML Import** - Parse DCS control exports  
✅ **Draggable Boxes** - Position each control on the layout  
✅ **Resizable Boxes** - Adjust box sizes to fit  
✅ **Multi-Select** - Drag multiple boxes together with Ctrl+click  
✅ **Color Customization** - Right-click boxes for color picker  
✅ **Connection Lines** - Draw lines with waypoints to show relationships  
✅ **Zoom/Pan** - Mouse wheel to zoom, drag to pan  
✅ **JSON Save** - Save layout configuration  
✅ **PNG Export** - Export final layout as image

## Quick Start

```bash
python editor.py
```

## Workflow

### 1. Load Device Image

1. Click **"Load Image"**
2. Select your device photo/template (PNG/JPG)
3. Enter device name (e.g., "T.16000M", "TWCS Throttle")
4. Image is saved to `layouts/{device_name}/image.png`

### 2. Load DCS HTML

1. In DCS: **Options → Controls → Make HTML** to export your profile
2. Click **"Load HTML"**
3. Select the exported HTML file
4. Control boxes automatically appear in a grid layout

### 3. Position Controls

**Drag Boxes:**
- Click and drag any box to move it
- Boxes show button/control name inside

**Resize Boxes:**
- Click and drag the **bottom-right corner** of a box to resize

**Multi-Select:**
- Hold **Ctrl** and click boxes to select multiple
- Drag one selected box to move all selected boxes together

### 4. Customize Colors

1. **Right-click** a box
2. Click a color in the popup palette
3. Box color updates instantly

**Available Colors:**
- Greens, Yellows, Reds, Blues
- Plus whites, blacks, grays

### 5. Draw Connection Lines (Optional)

1. Click **"Draw Line"**
2. **Left-click** on the image where line should start
3. **Right-click** to add waypoints (line corners)
4. **Left-click** to end the line
5. Line is drawn with red segments connecting all waypoints

### 6. Save & Export

**Save Layout (JSON):**
- Click **"Save Layout"**
- Creates `layouts/{device_name}/layout.json` with:
  - All box positions and sizes
  - Color assignments
  - Button names/keys

**Export as PNG:**
- Click **"Export PNG"**
- Creates `layouts/{device_name}/layout.png` with all boxes rendered

## Layout File Structure

```
layouts/
├── T.16000M/
│   ├── image.png          # Original template image
│   ├── layout.json        # Saved box positions and colors
│   └── layout.png         # Exported final diagram
└── TWCS_Throttle/
    ├── image.png
    ├── layout.json
    └── layout.png
```

## JSON Layout Format

```json
{
  "device_name": "T.16000M",
  "image_width": 960,
  "image_height": 601,
  "boxes": [
    {
      "x": 100,
      "y": 150,
      "width": 80,
      "height": 40,
      "text": "1",
      "control_key": "JOY_BTN1",
      "color": "#81ff83"
    }
  ]
}
```

## Keyboard/Mouse Controls

| Action | Control |
|--------|---------|
| **Zoom In** | Mouse Wheel Up / Scroll Up |
| **Zoom Out** | Mouse Wheel Down / Scroll Down |
| **Drag Box** | Click + Drag |
| **Resize Box** | Click corner + Drag |
| **Select Multiple** | Ctrl + Click boxes |
| **Change Color** | Right-click box |
| **Draw Line** | Click "Draw Line" button |

## Line Drawing Mode

Once in line drawing mode:

1. **Start Line:** Left-click on image
2. **Add Waypoint:** Right-click to create corner
3. **End Line:** Left-click to finalize
4. Each segment draws automatically

Lines are drawn in red and persist on canvas.

## Tips

- **Start with a clean template** - Use a photo or screenshot of your actual device
- **Group related buttons** - Use colors to visually group buttons by function
- **Use waypoints sparingly** - Connection lines are optional and mainly for reference
- **Export frequently** - PNG exports make it easy to share your layout
- **Test your layout** - Make sure box positions match where you actually press buttons

## Troubleshooting

**Image won't load:**
- Check file format (PNG, JPG supported)
- Ensure file is readable

**HTML import failed:**
- Verify it's a valid DCS HTML export
- Should contain `<h1>` heading with device name
- Should contain `<table>` with control data

**Boxes appear off-screen:**
- Use mouse wheel to zoom out
- Drag boxes back into view

**Can't save:**
- Ensure `layouts/` folder exists and is writable
- Check file permissions

## Architecture

- **editor.py** - Main application (Tkinter Canvas-based)
  - `TableParser` - HTML parser (from original app.py)
  - `ControlBox` - Draggable box class
  - `LayoutEditor` - Main editor window

## Next Steps

After creating your layout:
1. **Refine positions** - Fine-tune box placement on template
2. **Save JSON** - Commit layout configuration
3. **Export PNG** - Use for printing/documentation
4. **Create multiple devices** - Add more device layouts as needed

Enjoy designing your custom HOTAS layouts!
