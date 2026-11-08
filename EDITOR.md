# Interactive HOTAS Layout Editor

A fully interactive, Figma-inspired editor for creating custom HOTAS device layouts with visual canvas editing and real-time property sidebar.

## Features

✅ **Image Upload** - Load device photos/templates  
✅ **DCS HTML Import** - Parse DCS control exports (shows button + command)  
✅ **Custom Boxes** - Insert boxes with any text/properties  
✅ **Figma-Style Editing** - Click box to select, sidebar shows/updates properties in real-time  
✅ **Advanced Resizing** - Drag from any edge (top, bottom, left, right, corner)  
✅ **Draggable Boxes** - Position each control on the layout  
✅ **Multi-Select** - Drag multiple boxes together with Ctrl+click  
✅ **Color Customization** - Right-click for instant color picker at mouse  
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

**Click a box:**
- Properties panel appears on the right
- Edit text, position, size, color in real-time
- Changes apply instantly

**Resize like Figma:**
- Drag from **any edge**: top, bottom, left, right, or corner
- Drag from **corners** to resize both dimensions
- Drag from **edges** to resize one dimension while keeping opposite edge fixed

**Insert Custom Boxes:**
- Click **"Insert Box"** button
- Enter properties in dialog
- Custom box appears at specified location

### 4. Position Controls

**Drag Boxes:**
- Click and drag any box to move it
- Boxes show button/control name and command inside

**Multi-Select:**
- Hold **Ctrl** and click boxes to select multiple
- Drag one selected box to move all selected boxes together

### 5. Customize Colors

1. **Right-click** a box → color picker opens at mouse position
2. Click a color in the popup palette
3. Box color updates instantly and picker closes

**Or use sidebar:**
- Click box to select
- Click "Change Color" button in sidebar

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

### Color
- Shows current color
- Click "Change Color" to pick new color
- Also accessible via right-click on canvas

## Keyboard/Mouse Controls

| Action | Control |
|--------|---------|
| **Select Box** | Click on box (properties appear in sidebar) |
| **Move Box** | Click + Drag (anywhere inside box) |
| **Resize Box** | Drag from edge or corner |
| **- Top edge** | Drag top, keeps bottom fixed |
| **- Bottom edge** | Drag bottom, keeps top fixed |
| **- Left edge** | Drag left, keeps right fixed |
| **- Right edge** | Drag right, keeps left fixed |
| **- Corner** | Drag corner, keeps opposite corner fixed |
| **Multi-Select** | Ctrl + Click boxes |
| **Move Multiple** | Drag any selected box |
| **Change Color** | Right-click box (opens at mouse) |
| **Zoom In** | Mouse Wheel Up / Scroll Up |
| **Zoom Out** | Mouse Wheel Down / Scroll Down (min 10%) |
| **Pan Canvas** | Middle Mouse Drag |
| **Pan Canvas** | Space + Click + Drag (Figma-style) |
| **Draw Line** | Click "Draw Line" button |

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
