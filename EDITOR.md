# Interactive HOTAS Layout Editor

A fully interactive, Figma-inspired editor for creating custom HOTAS device layouts with visual canvas editing and real-time property sidebar.

## Features

✅ **Image Upload** - Load device photos/templates  
✅ **DCS HTML Import** - Parse DCS control exports (shows button + command)  
✅ **Custom Boxes** - Insert boxes with any text/properties  
✅ **Figma-Style Editing** - Click box to select, sidebar shows/updates properties in real-time  
✅ **Sidebar Resizing** - Edit width/height directly in properties sidebar  
✅ **Draggable Boxes** - Position each control on the layout  
✅ **Multi-Select** - Ctrl+click to select multiple boxes, drag together  
✅ **Color Customization** - Inline color palette in sidebar  
✅ **Connection Lines** - Draw lines with waypoints to show relationships  
✅ **Zoom/Pan** - Mouse wheel to zoom, Figma-style middle-mouse/space pan  
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
5. Each box shows: **Button name: Command description** (e.g., "BTN1: Trigger Down")

### 3. Edit/Position with Sidebar

**Click a box to select:**
- Properties panel appears on the right showing all box properties
- Edit text (title), subtitle, position (X, Y), size (Width, Height), and color
- All changes apply instantly to the canvas

**Move Boxes:**
- Click and drag any box to move it
- Use Ctrl+click to select multiple boxes
- Drag any selected box to move all together

**Resize Boxes:**
- Edit **Width** and **Height** fields in the sidebar
- Click the "+" and "-" buttons to adjust, or type values directly
- Minimum width: 40px, minimum height: 20px

**Customize Colors:**
- Click a box to select it
- Scroll to the "Color" section in the sidebar
- Click any color in the inline 3×5 color grid
- Selected color shows with sunken button appearance
- Color updates instantly on canvas

**Insert Custom Boxes:**
- Click **"Insert Box"** button
- Enter properties in dialog (text, subtitle, position, size, color)
- Custom box appears and is ready to move/edit

### 6. Draw Connection Lines (Optional)

1. Click **"Draw Line"**
2. **Left-click** on the image where line should start
3. **Right-click** to add waypoints (line corners)
4. **Left-click** to end the line
5. Line is drawn with red segments connecting all waypoints

### 7. Save & Export

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
│   ├── layout.json        # Saved box positions, colors, text, subtitle
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
      "text": "Button 1",
      "subtitle": "Fire Trigger",
      "control_key": "JOY_BTN1",
      "color": "#81ff83"
    }
  ]
}
```

## Properties Sidebar

The right sidebar shows the **selected box's properties** and updates in real-time:

### Title (Button)
- Main button/control name (displayed larger, bold)
- Updates instantly as you type

### Subtitle (Function)
- What the button does (displayed smaller, dimmed)
- Updates instantly as you type

### Control Key
- Identifier for this control in JSON
- Used for tracking button bindings

### Position (X, Y)
- Exact coordinates of top-left corner
- Edit to move box to precise location
- Updates as you drag

### Size (Width, Height)
- Box dimensions
- Edit to resize to exact size
- Updates as you drag edges

## Keyboard/Mouse Controls

| Action | Control |
|--------|---------|
| **Select Box** | Click on box (properties appear in sidebar) |
| **Move Box** | Click + Drag (anywhere inside box) |
| **Resize Box** | Edit Width/Height in sidebar (easier than dragging) |
| **Multi-Select** | Ctrl + Click boxes (toggles selection) |
| **Move Multiple** | Drag any selected box (all move together) |
| **Change Color** | Select box → Click color in sidebar (3×5 palette grid) |
| **Edit Text** | Select box → Edit "Title" field in sidebar |
| **Edit Function** | Select box → Edit "Subtitle" field in sidebar |
| **Edit Position** | Select box → Edit X/Y in sidebar |
| **Zoom In** | Mouse Wheel Up (max 300%) |
| **Zoom Out** | Mouse Wheel Down (min 10%) |
| **Pan Canvas** | Middle Mouse Drag |
| **Pan Canvas** | Space + Click + Drag (Figma-style) |
| **Draw Line** | Click "Draw Line" button, then left/right click on canvas |
| **Double-Click** | Open legacy edit dialog (text/subtitle/key/position/size/color all in one dialog) |

## Editing Boxes

### Select a Box for Editing

1. **Click any box on the canvas**
2. Box highlights with red border
3. Properties panel loads on the right sidebar
4. All properties update in real-time as you edit or drag

### Edit Properties in Sidebar

- **Text** - Change what displays in the box
- **Control Key** - Identifier for JSON storage
- **Position (X, Y)** - Pixel coordinates
- **Size (W, H)** - Box dimensions
- **Color** - Click button to pick color

Changes apply **instantly** as you type/drag!

### Resize Like Figma

Drag from any edge to resize:

```
        ↑ top
    ┌───────┐
  ← │       │ →
    └───────┘
      ↓ bottom

↙ corner = resize both width & height
```

- **Edge drag** = resize that dimension only
- **Corner drag** = resize width & height together
- Opposite corner stays fixed

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
