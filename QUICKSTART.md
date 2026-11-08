# Quick Reference - HOTAS Layout Editor

## Launch

```bash
python editor.py
```

## Menu Buttons

| Button | Action |
|--------|--------|
| **Load Image** | Select device template image (PNG/JPG) + enter device name |
| **Load HTML** | Import DCS control export (creates control boxes) |
| **Draw Line** | Enter line-drawing mode |
| **Save Layout** | Save positions + colors as `layout.json` |
| **Export PNG** | Export diagram as `layout.png` |

## Mouse Controls

### Box Selection & Movement
| Action | Result |
|--------|--------|
| Click + Drag | Move single box |
| Ctrl + Click + Drag | Move multiple selected boxes |
| Click corner + Drag | Resize box (corner = bottom-right) |
| Right-Click | Show color picker |

### Zoom & Pan
| Action | Result |
|--------|--------|
| Mouse Wheel Up | Zoom in |
| Mouse Wheel Down | Zoom out |

### Line Drawing (When in Draw Mode)
| Action | Result |
|--------|--------|
| Left-Click | Start line / End line |
| Right-Click | Add waypoint (line corner) |

## Workflow (Step by Step)

```
1. Load Image
   ├─ Click "Load Image"
   ├─ Select device photo
   └─ Enter name (e.g., "T.16000M")

2. Import Controls
   ├─ Click "Load HTML"
   ├─ Select DCS export HTML
   └─ Control boxes appear in grid

3. Position Boxes
   ├─ Drag boxes to match button positions
   ├─ Resize to match button sizes
   └─ Use Ctrl+Click to move multiple boxes

4. Customize Colors
   ├─ Right-Click a box
   ├─ Click color in popup
   └─ Repeat for all boxes

5. Draw Lines (Optional)
   ├─ Click "Draw Line"
   ├─ Left-Click to start
   ├─ Right-Click for waypoints
   └─ Left-Click to end

6. Save & Export
   ├─ Click "Save Layout" → layout.json
   └─ Click "Export PNG" → layout.png
```

## Keyboard Shortcuts

Currently: None (can be added)

## Tips & Tricks

**Multi-Select Dragging:**
```
1. Ctrl + Click box 1
2. Ctrl + Click box 2
3. Ctrl + Click box 3
4. Click + Drag any selected box → all move together
```

**Resizing Multiple Boxes:**
- Select multiple boxes → drag ONE corner → only that box resizes
- Must resize one at a time

**Precise Positioning:**
- Zoom in (wheel up) for finer control
- Use grid as reference

**Color Grouping:**
- Similar functions = same color
- E.g., all fire buttons = red, all views = green

## Output Files

After saving:

```
layouts/{device_name}/
├── image.png       # Original template
├── layout.json     # Positions + colors (editable)
└── layout.png      # Exported diagram (for printing)
```

## Troubleshooting

**Image won't load:**
- Check file format (PNG/JPG)
- Check file permissions

**HTML parse error:**
- Verify it's a real DCS export
- Should have `<h1>` heading + `<table>`

**Boxes off-screen:**
- Zoom out (wheel down)
- Drag canvas to find boxes

**PNG export blank:**
- Ensure image was loaded first
- Check `layouts/{device_name}/` folder

## File Locations

```
Current directory: dcs-hotas-control-map/
├── editor.py              ← Run this
└── layouts/               ← Your layouts save here
    └── {device_name}/
        ├── image.png
        ├── layout.json
        └── layout.png
```

## Advanced: Edit JSON Manually

Layout JSON structure:

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

- `x, y` = top-left position
- `width, height` = box size
- `text` = label inside box
- `color` = hex color code

You can edit these values manually if needed.

## Common Colors

| Color | Hex |
|-------|-----|
| Green | #81ff83 |
| Yellow | #fff1a0 |
| Red | #ff858b |
| Blue | #83c8f2 |
| Light Green | #baff85 |
| Orange | #ffb28a |
| Pink | #ff6b73 |
| Lime | #4df500 |
| Cyan | #83ffff |
| Purple | #d585ee |
| White | #ffffff |
| Black | #000000 |

---

**That's it!** You're ready to create custom HOTAS layouts. 🎮
