#!/usr/bin/env python3
"""Interactive HOTAS Layout Editor - Tkinter Canvas-based editor."""

import json
import re
import tkinter as tk
from html.parser import HTMLParser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk
import io

ROOT = Path(__file__).resolve().parent
LAYOUTS_DIR = ROOT / "layouts"
LAYOUTS_DIR.mkdir(exist_ok=True)


class TableParser(HTMLParser):
    """Parse DCS HTML control export."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.heading = ""
        self.in_heading = False
        self.in_cell = False
        self.cells = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == "h1":
            self.in_heading = True
        elif tag == "tr":
            self.cells = []
        elif tag == "td" and self.cells is not None:
            self.in_cell = True
            self.cells.append("")

    def handle_data(self, data):
        if self.in_heading:
            self.heading += data
        if self.in_cell:
            self.cells[-1] += data

    def handle_endtag(self, tag):
        if tag == "h1":
            self.in_heading = False
        elif tag == "td":
            self.in_cell = False
        elif tag == "tr" and self.cells is not None:
            if len(self.cells) >= 4 and self.cells[0].strip():
                self.rows.append([cell.strip() for cell in self.cells])
            self.cells = None


def parse_html(html_path):
    """Parse DCS HTML export and return list of controls."""
    data = Path(html_path).read_bytes()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252")
    
    parser = TableParser()
    parser.feed(text)
    
    controls = []
    for combo, command, category, *_ in parser.rows:
        for binding in combo.split(";"):
            parts = re.split(r"\s+-\s+", binding.strip())
            if parts and parts[-1]:
                controls.append({
                    "key": parts[-1],
                    "modifiers": parts[:-1],
                    "command": command,
                    "category": category
                })
    
    return controls


class ControlBox:
    """Represents a draggable/resizable control box on the canvas."""
    
    def __init__(self, canvas, x, y, width=80, height=40, text="", control_key="", color="#81ff83"):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.text = text
        self.control_key = control_key
        self.color = color
        self.selected = False
        self.line_id = None
        self.line_waypoints = []
        self.rect_id = None
        self.text_id = None
        
        self.draw()
    
    def draw(self):
        """Draw the box and text on canvas."""
        outline = "#ff0000" if self.selected else "#333333"
        width = 3 if self.selected else 1
        
        self.rect_id = self.canvas.create_rectangle(
            self.x, self.y, self.x + self.width, self.y + self.height,
            fill=self.color, outline=outline, width=width, tags=f"box_{id(self)}"
        )
        
        self.text_id = self.canvas.create_text(
            self.x + self.width / 2, self.y + self.height / 2,
            text=self.text, fill="black", font=("Arial", 10, "bold"),
            tags=f"text_{id(self)}"
        )
    
    def redraw(self):
        """Redraw the box (used after changes)."""
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        if self.text_id:
            self.canvas.delete(self.text_id)
        self.draw()
    
    def contains(self, x, y):
        """Check if point is inside this box."""
        return (self.x <= x <= self.x + self.width and 
                self.y <= y <= self.y + self.height)
    
    def move(self, dx, dy):
        """Move box by delta."""
        self.x += dx
        self.y += dy
        self.redraw()
    
    def resize(self, dx, dy):
        """Resize box by delta (bottom-right corner)."""
        self.width = max(40, self.width + dx)
        self.height = max(20, self.height + dy)
        self.redraw()
    
    def set_color(self, color):
        """Set box color."""
        self.color = color
        self.redraw()
    
    def toggle_select(self):
        """Toggle selection state."""
        self.selected = not self.selected
        self.redraw()
    
    def set_select(self, state):
        """Set selection state."""
        self.selected = state
        self.redraw()


class LayoutEditor:
    """Main editor window."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("HOTAS Layout Editor")
        self.root.geometry("1400x900")
        
        self.device_name = None
        self.image = None
        self.image_tk = None
        self.controls = []
        self.boxes = []
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.drawing_line = False
        self.line_start = None
        self.line_waypoints = []
        self.selected_boxes = []
        self.dragging_box = None
        self.resizing_box = None
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.panning = False
        self.space_pressed = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup UI layout."""
        # Top toolbar
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="Load Image", command=self.load_image).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Load HTML", command=self.load_html).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Draw Line", command=self.start_line_mode).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Save Layout", command=self.save_layout).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Export PNG", command=self.export_png).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(toolbar, text="Zoom:").pack(side=tk.LEFT, padx=5)
        self.zoom_label = ttk.Label(toolbar, text="100%")
        self.zoom_label.pack(side=tk.LEFT, padx=2)
        
        # Canvas
        self.canvas = tk.Canvas(self.root, bg="white", cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Bind events
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", self.on_mousewheel)  # Linux scroll up
        self.canvas.bind("<Button-5>", self.on_mousewheel)  # Linux scroll down
        self.canvas.bind("<Button-1>", self.on_canvas_left_click)
        self.canvas.bind("<Button-2>", self.on_canvas_middle_down)  # Middle mouse
        self.canvas.bind("<B2-Motion>", self.on_canvas_pan_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_canvas_middle_up)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Control-Button-1>", self.on_canvas_ctrl_click)
        self.canvas.bind("<KeyPress-space>", self.on_space_press)
        self.canvas.bind("<KeyRelease-space>", self.on_space_release)
        self.canvas.focus_set()
        
        # Status bar
        self.status = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)
    
    def load_image(self):
        """Load device image."""
        file_path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        
        device_name = simpledialog.askstring("Device Name", "Enter device name:")
        if not device_name:
            return
        
        self.device_name = device_name
        device_dir = LAYOUTS_DIR / device_name
        device_dir.mkdir(exist_ok=True)
        
        # Copy image
        import shutil
        image_path = device_dir / "image.png"
        shutil.copy(file_path, image_path)
        
        # Load image
        self.image = Image.open(image_path)
        self.redraw_canvas()
        self.status.config(text=f"Loaded: {device_name} ({self.image.size[0]}x{self.image.size[1]})")
    
    def load_html(self):
        """Load DCS HTML and create control boxes."""
        if not self.device_name:
            messagebox.showerror("Error", "Load image first")
            return
        
        file_path = filedialog.askopenfilename(filetypes=[("HTML Files", "*.html"), ("All Files", "*.*")])
        if not file_path:
            return
        
        try:
            self.controls = parse_html(file_path)
            self.create_boxes()
            self.status.config(text=f"Loaded {len(self.controls)} controls")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse HTML:\n{e}")
    
    def create_boxes(self):
        """Create control boxes from parsed controls."""
        self.canvas.delete("all")
        self.boxes = []
        
        # Grid layout for initial placement
        cols = 4
        for i, control in enumerate(self.controls):
            row = i // cols
            col = i % cols
            x = 100 + col * 150
            y = 200 + row * 80
            
            # Extract button number from key (e.g., JOY_BTN1 -> 1)
            text = control["key"].replace("JOY_BTN", "").replace("JOY_", "")
            box = ControlBox(self.canvas, x, y, text=text, control_key=control["key"])
            self.boxes.append(box)
        
        self.redraw_canvas()
    
    def redraw_canvas(self):
        """Redraw canvas with image and boxes."""
        self.canvas.delete("all")
        
        if self.image:
            # Draw image
            display_image = self.image.copy()
            display_image.thumbnail((int(self.image.width * self.zoom), int(self.image.height * self.zoom)))
            self.image_tk = ImageTk.PhotoImage(display_image)
            self.canvas.create_image(self.pan_x, self.pan_y, image=self.image_tk, anchor=tk.NW, tags="image")
        
        # Redraw all boxes
        for box in self.boxes:
            box.redraw()
    
    def on_mousewheel(self, event):
        """Handle zoom with mouse wheel."""
        delta = 1.1 if event.num == 4 or event.delta > 0 else 0.9
        self.zoom = max(0.1, min(3.0, self.zoom * delta))
        self.zoom_label.config(text=f"{int(self.zoom * 100)}%")
        self.redraw_canvas()
    
    def on_canvas_left_click(self, event):
        """Handle left click."""
        if self.drawing_line:
            self.handle_line_click(event, is_right=False)
            return
        
        # Check if clicking on a box
        for box in self.boxes:
            if box.contains(event.x, event.y):
                self.dragging_box = box
                self.last_mouse_x = event.x
                self.last_mouse_y = event.y
                
                # Check if near corner for resize
                if (abs(event.x - (box.x + box.width)) < 10 and
                    abs(event.y - (box.y + box.height)) < 10):
                    self.resizing_box = box
                
                return
        
        # No box clicked - start selection
        self.selected_boxes = []
        self.redraw_boxes()
    
    def on_canvas_middle_down(self, event):
        """Handle middle mouse button down - start panning."""
        self.panning = True
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.canvas.config(cursor="hand2")
    
    def on_canvas_middle_up(self, event):
        """Handle middle mouse button up - stop panning."""
        self.panning = False
        self.canvas.config(cursor="cross")
    
    def on_canvas_pan_drag(self, event):
        """Handle pan drag (middle mouse or space+drag)."""
        dx = event.x - self.last_mouse_x
        dy = event.y - self.last_mouse_y
        
        self.pan_x += dx
        self.pan_y += dy
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        
        self.redraw_canvas()
    
    def on_space_press(self, event):
        """Handle space key press."""
        self.space_pressed = True
        self.canvas.config(cursor="hand2")
    
    def on_space_release(self, event):
        """Handle space key release."""
        self.space_pressed = False
        self.canvas.config(cursor="cross")
    
    def on_canvas_right_click(self, event):
        """Handle right click - show color picker."""
        if self.drawing_line:
            self.handle_line_click(event, is_right=True)
            return
        
        for box in self.boxes:
            if box.contains(event.x, event.y):
                self.show_color_picker(box, event.x, event.y)
                return
    
    def on_canvas_ctrl_click(self, event):
        """Handle Ctrl+click - multi-select."""
        for box in self.boxes:
            if box.contains(event.x, event.y):
                if box not in self.selected_boxes:
                    self.selected_boxes.append(box)
                else:
                    self.selected_boxes.remove(box)
                self.redraw_boxes()
                return
    
    def on_canvas_drag(self, event):
        """Handle drag."""
        # If space is pressed, pan instead
        if self.space_pressed:
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y
            self.pan_x += dx
            self.pan_y += dy
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            self.redraw_canvas()
            return
        
        if self.dragging_box:
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y
            
            if self.resizing_box:
                self.resizing_box.resize(dx, dy)
            else:
                # Drag selected boxes
                if self.dragging_box not in self.selected_boxes:
                    self.selected_boxes = [self.dragging_box]
                
                for box in self.selected_boxes:
                    box.move(dx, dy)
            
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
    
    def on_canvas_release(self, event):
        """Handle release."""
        self.dragging_box = None
        self.resizing_box = None
    
    def redraw_boxes(self):
        """Redraw all boxes with selection states."""
        for box in self.boxes:
            box.set_select(box in self.selected_boxes)
    
    def show_color_picker(self, box, x, y):
        """Show color palette popup."""
        colors = [
            "#81ff83", "#fff1a0", "#ff858b", "#83c8f2", "#baff85",
            "#ffb28a", "#ff6b73", "#4df500", "#83ffff", "#d585ee",
            "#ffffff", "#000000", "#cccccc", "#ff0000", "#00ff00"
        ]
        
        popup = tk.Toplevel(self.root)
        popup.geometry("200x200")
        popup.title("Color Palette")
        
        for i, color in enumerate(colors):
            row = i // 3
            col = i % 3
            btn = tk.Button(
                popup, bg=color, height=2, width=6,
                command=lambda c=color: [box.set_color(c), popup.destroy()]
            )
            btn.grid(row=row, column=col, padx=2, pady=2)
    
    def start_line_mode(self):
        """Start line drawing mode."""
        self.drawing_line = True
        self.line_waypoints = []
        self.status.config(text="Line mode: Click to start, left-click to end, right-click for waypoint")
    
    def handle_line_click(self, event, is_right):
        """Handle clicks while drawing line."""
        if not self.line_start:
            self.line_start = (event.x, event.y)
            self.status.config(text="Line started. Right-click for waypoint, left-click to end")
            return
        
        if is_right:
            # Add waypoint
            self.line_waypoints.append((event.x, event.y))
            self.line_start = (event.x, event.y)
            self.status.config(text=f"Waypoint added. Right-click for more, left-click to end")
        else:
            # End line
            self.line_waypoints.append((event.x, event.y))
            # Draw the line on canvas
            for i in range(len(self.line_waypoints) - 1):
                self.canvas.create_line(
                    self.line_waypoints[i][0], self.line_waypoints[i][1],
                    self.line_waypoints[i + 1][0], self.line_waypoints[i + 1][1],
                    fill="red", width=2
                )
            
            self.drawing_line = False
            self.line_start = None
            self.line_waypoints = []
            self.status.config(text="Line drawn")
    
    def save_layout(self):
        """Save layout to JSON."""
        if not self.device_name:
            messagebox.showerror("Error", "Load image first")
            return
        
        device_dir = LAYOUTS_DIR / self.device_name
        layout_data = {
            "device_name": self.device_name,
            "image_width": self.image.width if self.image else 0,
            "image_height": self.image.height if self.image else 0,
            "boxes": [
                {
                    "x": box.x,
                    "y": box.y,
                    "width": box.width,
                    "height": box.height,
                    "text": box.text,
                    "control_key": box.control_key,
                    "color": box.color
                }
                for box in self.boxes
            ]
        }
        
        layout_path = device_dir / "layout.json"
        with open(layout_path, "w") as f:
            json.dump(layout_data, f, indent=2)
        
        messagebox.showinfo("Success", f"Layout saved to {layout_path}")
        self.status.config(text=f"Layout saved")
    
    def export_png(self):
        """Export layout as PNG."""
        if not self.device_name or not self.image:
            messagebox.showerror("Error", "Load image first")
            return
        
        # Create image with boxes
        export_img = self.image.copy()
        draw = ImageDraw.Draw(export_img)
        
        for box in self.boxes:
            # Draw box
            draw.rectangle(
                [box.x, box.y, box.x + box.width, box.y + box.height],
                fill=box.color, outline="#333333", width=2
            )
            # Draw text
            draw.text(
                (box.x + box.width / 2, box.y + box.height / 2),
                box.text,
                fill="black", anchor="mm"
            )
        
        device_dir = LAYOUTS_DIR / self.device_name
        export_path = device_dir / "layout.png"
        export_img.save(export_path)
        
        messagebox.showinfo("Success", f"Exported to {export_path}")


if __name__ == "__main__":
    root = tk.Tk()
    app = LayoutEditor(root)
    root.mainloop()
