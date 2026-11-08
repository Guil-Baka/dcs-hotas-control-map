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
                button_name = parts[-1]
                # Combine button name with command (abbreviated)
                display_text = f"{button_name}: {command[:20]}" if command else button_name
                controls.append({
                    "key": button_name,
                    "modifiers": parts[:-1],
                    "command": command,
                    "category": category,
                    "display_text": display_text
                })
    
    return controls


class ControlBox:
    """Represents a draggable/resizable control box on the canvas."""
    
    def __init__(self, canvas, x, y, width=80, height=40, text="", subtitle="", control_key="", color="#81ff83"):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.text = text  # Title (button name)
        self.subtitle = subtitle  # Subtitle (function/command)
        self.control_key = control_key
        self.color = color
        self.selected = False
        self.line_id = None
        self.line_waypoints = []
        self.rect_id = None
        self.text_id = None
        self.subtitle_id = None
        
        self.draw()
    
    def draw(self):
        """Draw the box, title, and subtitle on canvas."""
        outline = "#ff0000" if self.selected else "#333333"
        width = 3 if self.selected else 1
        
        self.rect_id = self.canvas.create_rectangle(
            self.x, self.y, self.x + self.width, self.y + self.height,
            fill=self.color, outline=outline, width=width, tags=f"box_{id(self)}"
        )
        
        # Title text (larger, bold)
        self.text_id = self.canvas.create_text(
            self.x + self.width / 2, self.y + self.height / 3,
            text=self.text, fill="black", font=("Arial", 9, "bold"),
            tags=f"text_{id(self)}"
        )
        
        # Subtitle text (smaller, regular)
        if self.subtitle:
            self.subtitle_id = self.canvas.create_text(
                self.x + self.width / 2, self.y + 2 * self.height / 3,
                text=self.subtitle, fill="#333333", font=("Arial", 7),
                tags=f"subtitle_{id(self)}"
            )
    
    def redraw(self):
        """Redraw the box (used after changes)."""
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        if self.text_id:
            self.canvas.delete(self.text_id)
        if self.subtitle_id:
            self.canvas.delete(self.subtitle_id)
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
        self.root.geometry("1600x900")
        
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
        self.selected_box = None  # Current box being edited in sidebar
        self.dragging_box = None
        self.resizing_box = None
        self.resize_edge = None  # 'left', 'right', 'top', 'bottom', 'corner'
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.panning = False
        self.space_pressed = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup UI layout with canvas and sidebar."""
        # Top toolbar
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="Load Image", command=self.load_image).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Load HTML", command=self.load_html).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Insert Box", command=self.insert_custom_box).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Draw Line", command=self.start_line_mode).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Save Layout", command=self.save_layout).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Export PNG", command=self.export_png).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(toolbar, text="Zoom:").pack(side=tk.LEFT, padx=5)
        self.zoom_label = ttk.Label(toolbar, text="100%")
        self.zoom_label.pack(side=tk.LEFT, padx=2)
        
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Canvas
        self.canvas = tk.Canvas(main_container, bg="white", cursor="cross")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Sidebar
        sidebar = ttk.Frame(main_container, width=250)
        sidebar.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))
        sidebar.pack_propagate(False)
        
        ttk.Label(sidebar, text="Properties", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Properties frame with scrollbar
        properties_frame = ttk.Frame(sidebar)
        properties_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(properties_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.properties_canvas = tk.Canvas(properties_frame, bg="white", highlightthickness=0, yscrollcommand=scrollbar.set)
        self.properties_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.properties_canvas.yview)
        
        self.properties_inner = ttk.Frame(self.properties_canvas)
        self.properties_canvas.create_window((0, 0), window=self.properties_inner, anchor=tk.NW)
        
        # Bind events
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", self.on_mousewheel)
        self.canvas.bind("<Button-5>", self.on_mousewheel)
        self.canvas.bind("<Button-1>", self.on_canvas_left_click)
        self.canvas.bind("<Button-2>", self.on_canvas_middle_down)
        self.canvas.bind("<B2-Motion>", self.on_canvas_pan_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_canvas_middle_up)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
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
            
            # Extract button name and command
            button_name = control["key"].replace("JOY_BTN", "").replace("JOY_", "")
            command = control.get("command", "")
            # Abbreviate command if too long
            if len(command) > 25:
                command = command[:22] + "..."
            
            box = ControlBox(
                self.canvas, x, y, width=100, height=60,
                text=button_name, subtitle=command,
                control_key=control["key"]
            )
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
        """Handle left click - select or resize."""
        if self.drawing_line:
            self.handle_line_click(event, is_right=False)
            return
        
        # Check if clicking on a box
        for box in self.boxes:
            if box.contains(event.x, event.y):
                self.dragging_box = box
                self.last_mouse_x = event.x
                self.last_mouse_y = event.y
                
                # Detect which edge/corner is being dragged (10px tolerance)
                edge = self.get_resize_edge(box, event.x, event.y)
                if edge:
                    self.resizing_box = box
                    self.resize_edge = edge
                
                # Select box for sidebar
                self.selected_box = box
                self.update_sidebar()
                self.redraw_boxes()
                return
        
        # No box clicked - deselect
        self.selected_boxes = []
        self.selected_box = None
        self.update_sidebar()
        self.redraw_boxes()
    
    def get_resize_edge(self, box, x, y):
        """Detect which edge/corner the click is near. Returns 'top', 'bottom', 'left', 'right', or 'corner'."""
        tolerance = 8
        left = abs(x - box.x) < tolerance
        right = abs(x - (box.x + box.width)) < tolerance
        top = abs(y - box.y) < tolerance
        bottom = abs(y - (box.y + box.height)) < tolerance
        
        if (left or right) and (top or bottom):
            return "corner"
        elif top:
            return "top"
        elif bottom:
            return "bottom"
        elif left:
            return "left"
        elif right:
            return "right"
        return None
    
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
        """Handle drag - move or resize with edges."""
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
            
            if self.resizing_box and self.resize_edge:
                # Resize based on which edge(s) are being dragged
                edge = self.resize_edge
                box = self.resizing_box
                
                if edge == "corner":
                    # Bottom-right corner
                    box.width = max(40, box.width + dx)
                    box.height = max(20, box.height + dy)
                elif edge == "bottom":
                    box.height = max(20, box.height + dy)
                elif edge == "right":
                    box.width = max(40, box.width + dx)
                elif edge == "top":
                    box.y += dy
                    box.height = max(20, box.height - dy)
                elif edge == "left":
                    box.x += dx
                    box.width = max(40, box.width - dx)
                
                box.redraw()
                self.update_sidebar()
            else:
                # Drag selected boxes
                if self.dragging_box not in self.selected_boxes:
                    self.selected_boxes = [self.dragging_box]
                
                for box in self.selected_boxes:
                    box.move(dx, dy)
                
                self.update_sidebar()
            
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            self.redraw_canvas()
    
    def on_canvas_release(self, event):
        """Handle release."""
        self.dragging_box = None
        self.resizing_box = None
        self.resize_edge = None
    
    def redraw_boxes(self):
        """Redraw all boxes with selection states."""
        for box in self.boxes:
            box.set_select(box in self.selected_boxes)
    
    def show_color_picker(self, box, x, y):
        """Show color palette popup at mouse position."""
        colors = [
            "#81ff83", "#fff1a0", "#ff858b", "#83c8f2", "#baff85",
            "#ffb28a", "#ff6b73", "#4df500", "#83ffff", "#d585ee",
            "#ffffff", "#000000", "#cccccc", "#ff0000", "#00ff00"
        ]
        
        popup = tk.Toplevel(self.root)
        popup.geometry("200x200")
        popup.title("Color Palette")
        
        # Position popup at mouse location
        popup.geometry(f"200x200+{x}+{y}")
        
        def pick_color(c):
            box.set_color(c)
            popup.destroy()
        
        for i, color in enumerate(colors):
            row = i // 3
            col = i % 3
            btn = tk.Button(
                popup, bg=color, height=2, width=6,
                command=lambda c=color: pick_color(c)
            )
            btn.grid(row=row, column=col, padx=2, pady=2)
        
        # Focus popup so it gets destroyed when clicking outside
        popup.focus_set()
    
    def update_sidebar(self):
        """Update sidebar with selected box properties."""
        # Clear previous content
        for widget in self.properties_inner.winfo_children():
            widget.destroy()
        
        if not self.selected_box:
            ttk.Label(self.properties_inner, text="No box selected", foreground="gray").pack(pady=20)
            self.properties_canvas.configure(scrollregion=self.properties_canvas.bbox("all"))
            return
        
        box = self.selected_box
        
        # Title property
        ttk.Label(self.properties_inner, text="Title (Button)", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        text_var = tk.StringVar(value=box.text)
        text_entry = ttk.Entry(self.properties_inner, textvariable=text_var, width=25)
        text_entry.pack(padx=10, pady=5, fill=tk.X)
        
        def on_text_change(*args):
            box.text = text_var.get()
            box.redraw()
            self.redraw_canvas()
        
        text_var.trace("w", on_text_change)
        
        # Subtitle property
        ttk.Label(self.properties_inner, text="Subtitle (Function)", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        subtitle_var = tk.StringVar(value=box.subtitle)
        subtitle_entry = ttk.Entry(self.properties_inner, textvariable=subtitle_var, width=25)
        subtitle_entry.pack(padx=10, pady=5, fill=tk.X)
        
        def on_subtitle_change(*args):
            box.subtitle = subtitle_var.get()
            box.redraw()
            self.redraw_canvas()
        
        subtitle_var.trace("w", on_subtitle_change)
        
        # Control Key property
        ttk.Label(self.properties_inner, text="Control Key", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        key_var = tk.StringVar(value=box.control_key)
        key_entry = ttk.Entry(self.properties_inner, textvariable=key_var, width=25)
        key_entry.pack(padx=10, pady=5, fill=tk.X)
        
        def on_key_change(*args):
            box.control_key = key_var.get()
        
        key_var.trace("w", on_key_change)
        
        # Position section
        ttk.Label(self.properties_inner, text="Position", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(15, 5))
        
        # X position
        ttk.Label(self.properties_inner, text="X:").pack(anchor="w", padx=10)
        x_var = tk.StringVar(value=str(int(box.x)))
        x_entry = ttk.Entry(self.properties_inner, textvariable=x_var, width=25)
        x_entry.pack(padx=10, pady=2, fill=tk.X)
        
        def on_x_change(*args):
            try:
                box.x = float(x_var.get())
                box.redraw()
                self.redraw_canvas()
            except ValueError:
                pass
        
        x_var.trace("w", on_x_change)
        
        # Y position
        ttk.Label(self.properties_inner, text="Y:").pack(anchor="w", padx=10)
        y_var = tk.StringVar(value=str(int(box.y)))
        y_entry = ttk.Entry(self.properties_inner, textvariable=y_var, width=25)
        y_entry.pack(padx=10, pady=2, fill=tk.X)
        
        def on_y_change(*args):
            try:
                box.y = float(y_var.get())
                box.redraw()
                self.redraw_canvas()
            except ValueError:
                pass
        
        y_var.trace("w", on_y_change)
        
        # Size section
        ttk.Label(self.properties_inner, text="Size", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(15, 5))
        
        # Width
        ttk.Label(self.properties_inner, text="Width:").pack(anchor="w", padx=10)
        w_var = tk.StringVar(value=str(int(box.width)))
        w_entry = ttk.Entry(self.properties_inner, textvariable=w_var, width=25)
        w_entry.pack(padx=10, pady=2, fill=tk.X)
        
        def on_width_change(*args):
            try:
                box.width = max(40, float(w_var.get()))
                w_var.set(str(int(box.width)))
                box.redraw()
                self.redraw_canvas()
            except ValueError:
                pass
        
        w_var.trace("w", on_width_change)
        
        # Height
        ttk.Label(self.properties_inner, text="Height:").pack(anchor="w", padx=10)
        h_var = tk.StringVar(value=str(int(box.height)))
        h_entry = ttk.Entry(self.properties_inner, textvariable=h_var, width=25)
        h_entry.pack(padx=10, pady=2, fill=tk.X)
        
        def on_height_change(*args):
            try:
                box.height = max(20, float(h_var.get()))
                h_var.set(str(int(box.height)))
                box.redraw()
                self.redraw_canvas()
            except ValueError:
                pass
        
        h_var.trace("w", on_height_change)
        
        # Color section
        ttk.Label(self.properties_inner, text="Color", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(15, 5))
        
        def on_color_click():
            self.show_color_picker(box, 0, 0)
        
        color_btn = tk.Button(self.properties_inner, bg=box.color, text="Change Color", 
                               command=on_color_click, width=20, height=2)
        color_btn.pack(padx=10, pady=5)
        
        # Update scroll region
        self.properties_inner.update_idletasks()
        self.properties_canvas.configure(scrollregion=self.properties_canvas.bbox("all"))
    
    def insert_custom_box(self):
        """Insert a custom box."""
        # Create dialog for box properties
        dialog = tk.Toplevel(self.root)
        dialog.title("Insert Custom Box")
        dialog.geometry("300x350")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Title (Button):").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        text_var = tk.StringVar(value="Button")
        text_entry = tk.Entry(dialog, textvariable=text_var, width=20)
        text_entry.grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(dialog, text="Subtitle (Function):").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        subtitle_var = tk.StringVar(value="")
        subtitle_entry = tk.Entry(dialog, textvariable=subtitle_var, width=20)
        subtitle_entry.grid(row=1, column=1, padx=10, pady=5)
        
        tk.Label(dialog, text="Control Key:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        key_var = tk.StringVar(value="CUSTOM_1")
        key_entry = tk.Entry(dialog, textvariable=key_var, width=20)
        key_entry.grid(row=2, column=1, padx=10, pady=5)
        
        tk.Label(dialog, text="X Position:").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        x_var = tk.StringVar(value="100")
        x_entry = tk.Entry(dialog, textvariable=x_var, width=20)
        x_entry.grid(row=3, column=1, padx=10, pady=5)
        
        tk.Label(dialog, text="Y Position:").grid(row=4, column=0, padx=10, pady=5, sticky="w")
        y_var = tk.StringVar(value="100")
        y_entry = tk.Entry(dialog, textvariable=y_var, width=20)
        y_entry.grid(row=4, column=1, padx=10, pady=5)
        
        tk.Label(dialog, text="Width:").grid(row=5, column=0, padx=10, pady=5, sticky="w")
        w_var = tk.StringVar(value="100")
        w_entry = tk.Entry(dialog, textvariable=w_var, width=20)
        w_entry.grid(row=5, column=1, padx=10, pady=5)
        
        tk.Label(dialog, text="Height:").grid(row=6, column=0, padx=10, pady=5, sticky="w")
        h_var = tk.StringVar(value="60")
        h_entry = tk.Entry(dialog, textvariable=h_var, width=20)
        h_entry.grid(row=6, column=1, padx=10, pady=5)
        
        def create_box():
            try:
                box = ControlBox(
                    self.canvas, 
                    int(x_var.get()), 
                    int(y_var.get()),
                    width=int(w_var.get()),
                    height=int(h_var.get()),
                    text=text_var.get(),
                    subtitle=subtitle_var.get(),
                    control_key=key_var.get(),
                    color="#81ff83"
                )
                self.boxes.append(box)
                self.redraw_canvas()
                dialog.destroy()
                self.status.config(text="Custom box inserted")
            except ValueError:
                messagebox.showerror("Error", "Invalid numeric values")
        
        ttk.Button(dialog, text="Create", command=create_box).grid(row=7, column=0, columnspan=2, pady=20)
    
    def on_canvas_double_click(self, event):
        """Handle double-click to edit box."""
        for box in self.boxes:
            if box.contains(event.x, event.y):
                self.edit_box(box)
                return
    
    def edit_box(self, box):
        """Edit a box's properties."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Box")
        dialog.geometry("300x350")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Title (Button):").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        text_var = tk.StringVar(value=box.text)
        text_entry = tk.Entry(dialog, textvariable=text_var, width=20)
        text_entry.grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(dialog, text="Subtitle (Function):").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        subtitle_var = tk.StringVar(value=box.subtitle)
        subtitle_entry = tk.Entry(dialog, textvariable=subtitle_var, width=20)
        subtitle_entry.grid(row=1, column=1, padx=10, pady=5)
        
        tk.Label(dialog, text="Control Key:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        key_var = tk.StringVar(value=box.control_key)
        key_entry = tk.Entry(dialog, textvariable=key_var, width=20)
        key_entry.grid(row=2, column=1, padx=10, pady=5)
        
        tk.Label(dialog, text="X Position:").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        x_var = tk.StringVar(value=str(int(box.x)))
        x_entry = tk.Entry(dialog, textvariable=x_var, width=20)
        x_entry.grid(row=3, column=1, padx=10, pady=5)
        
        tk.Label(dialog, text="Y Position:").grid(row=4, column=0, padx=10, pady=5, sticky="w")
        y_var = tk.StringVar(value=str(int(box.y)))
        y_entry = tk.Entry(dialog, textvariable=y_var, width=20)
        y_entry.grid(row=4, column=1, padx=10, pady=5)
        
        tk.Label(dialog, text="Width:").grid(row=5, column=0, padx=10, pady=5, sticky="w")
        w_var = tk.StringVar(value=str(int(box.width)))
        w_entry = tk.Entry(dialog, textvariable=w_var, width=20)
        w_entry.grid(row=5, column=1, padx=10, pady=5)
        
        tk.Label(dialog, text="Height:").grid(row=6, column=0, padx=10, pady=5, sticky="w")
        h_var = tk.StringVar(value=str(int(box.height)))
        h_entry = tk.Entry(dialog, textvariable=h_var, width=20)
        h_entry.grid(row=6, column=1, padx=10, pady=5)
        
        def save_changes():
            try:
                box.text = text_var.get()
                box.subtitle = subtitle_var.get()
                box.control_key = key_var.get()
                box.x = int(x_var.get())
                box.y = int(y_var.get())
                box.width = int(w_var.get())
                box.height = int(h_var.get())
                box.redraw()
                self.redraw_canvas()
                dialog.destroy()
                self.status.config(text="Box edited")
            except ValueError:
                messagebox.showerror("Error", "Invalid numeric values")
        
        ttk.Button(dialog, text="Save", command=save_changes).grid(row=7, column=0, columnspan=2, pady=20)
    
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
                    "subtitle": box.subtitle,
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
            # Draw title
            title_y = box.y + box.height / 3
            draw.text(
                (box.x + box.width / 2, title_y),
                box.text,
                fill="black", anchor="mm", font=None
            )
            # Draw subtitle
            if box.subtitle:
                subtitle_y = box.y + 2 * box.height / 3
                draw.text(
                    (box.x + box.width / 2, subtitle_y),
                    box.subtitle,
                    fill="#333333", anchor="mm", font=None
                )
        
        device_dir = LAYOUTS_DIR / self.device_name
        export_path = device_dir / "layout.png"
        export_img.save(export_path)
        
        messagebox.showinfo("Success", f"Exported to {export_path}")


if __name__ == "__main__":
    root = tk.Tk()
    app = LayoutEditor(root)
    root.mainloop()
