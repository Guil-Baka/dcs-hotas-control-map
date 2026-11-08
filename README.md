# HOTAS Layout Editor

Interactive visual editor for designing custom HOTAS device control layouts.

## Quick Start

```bash
python editor.py
```

## Workflow

1. **Load Image** - Select device template (PNG/JPG)
2. **Load HTML** - Import DCS control export
3. **Position Boxes** - Drag & resize control boxes
4. **Customize Colors** - Right-click for color picker
5. **Draw Lines** (optional) - Connect related controls
6. **Save** - Saves JSON + PNG export

## Features

- Drag & resize control boxes
- Multi-select with Ctrl+click
- Color picker (right-click)
- Connection lines with waypoints
- Zoom/pan controls
- Save layouts as JSON
- Export diagrams as PNG

## Output

Layouts save to: `layouts/{device_name}/`
- `image.png` - Your device template
- `layout.json` - Box positions & colors
- `layout.png` - Exported diagram

## Documentation

- **QUICKSTART.md** - Step-by-step guide
- **EDITOR.md** - Full documentation

## Requirements

- Python 3.9+
- Tkinter (included)
- Pillow >= 9.2

```bash
pip install -r requirements.txt
```

## Controls

| Action | Control |
|--------|---------|
| Move box | Click + Drag |
| Resize box | Drag corner |
| Multi-select | Ctrl + Click boxes |
| Change color | Right-click box |
| Zoom | Mouse wheel |
| Draw line | Button in menu |

---

**Ready to create custom HOTAS layouts!** 🎮
