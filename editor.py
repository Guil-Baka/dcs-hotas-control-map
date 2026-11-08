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
            binding_str = binding.strip()
            if not binding_str:
                continue

            # Split by " - " to separate modifier(s) from button
            # Format: "JOY_BTN2 - JOY_BTN4" means JOY_BTN4 with JOY_BTN2 held
            parts = binding_str.split(" - ")
            button_name = parts[-1]  # Last part is the actual button
            modifiers = parts[:-1]   # Everything before is modifiers

            # Create modifier text for footer (e.g., "Mod: BTN2")
            modifier_text = ""
            if modifiers:
                mod_names = []
                for mod in modifiers:
                    # Extract button number from "JOY_BTN2" -> "BTN2"
                    mod_clean = mod.replace("JOY_", "").replace("_", " ")
                    mod_names.append(mod_clean)
                modifier_text = f"Mod: {', '.join(mod_names)}"

            controls.append({
                "key": button_name,
                "modifiers": modifiers,
                "modifier_text": modifier_text,
                "command": command,
                "category": category,
            })

    return controls


class Tooltip:
    """Create tooltips that appear on hover."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        widget.bind("<Enter>", self.enter, add=True)
        widget.bind("<Leave>", self.leave, add=True)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hide()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.show)

    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)

    def show(self):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, background="#ffffe0",
                         relief=tk.SOLID, borderwidth=1, font=("Arial", 9))
        label.pack(ipadx=3)

    def hide(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


class ControlBox:
    """Represents a draggable/resizable control box on the canvas."""

    def __init__(self, canvas, x, y, width=200, height=200, text="", subtitle="", footer="", control_key="", color="#81ff83"):
        self.canvas = canvas
        self.x = x  # Model coordinates (unscaled)
        self.y = y
        self.width = width
        self.height = height
        self.text = text  # Title (button name) - top
        self.subtitle = subtitle  # Subtitle (function/command) - middle
        self.footer = footer  # Footer (optional) - bottom
        self.control_key = control_key
        self.color = color
        self.selected = False
        self.is_auto_imported = False  # Track if this box was auto-imported from HTML
        self.line_id = None
        self.line_waypoints = []
        self.rect_id = None
        self.text_id = None
        self.subtitle_id = None
        self.footer_id = None
        self.resize_handle_id = None  # Visual resize handle
        self.text_wrap_cache = {}  # Cache: (text, max_chars) -> wrapped_text

    def wrap_text(self, text, max_width_chars=15):
        """Wrap text to fit within reasonable bounds. Simple character-based wrapping with caching."""
        cache_key = (text, max_width_chars)
        if cache_key in self.text_wrap_cache:
            return self.text_wrap_cache[cache_key]

        if len(text) <= max_width_chars:
            wrapped = text
        else:
            # Break into multiple lines
            words = text.split()
            lines = []
            current_line = []
            for word in words:
                if len(" ".join(current_line + [word])) <= max_width_chars:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(" ".join(current_line))
            wrapped = "\n".join(lines)

        # Cache the result
        self.text_wrap_cache[cache_key] = wrapped
        return wrapped

    def draw(self, zoom=1.0, pan_x=0, pan_y=0, show_resize_handle=False):
        """Draw the box with zoom and pan transformations.

        Args:
            zoom: Zoom level
            pan_x: Pan offset in X
            pan_y: Pan offset in Y
            show_resize_handle: Whether to show the resize handle (only in resize mode)
        """
        # Apply transformations
        x_scaled = self.x * zoom + pan_x
        y_scaled = self.y * zoom + pan_y
        w_scaled = self.width * zoom
        h_scaled = self.height * zoom

        outline = "#ff0000" if self.selected else "#333333"
        width = max(1, int(3 * zoom)) if self.selected else 1

        self.rect_id = self.canvas.create_rectangle(
            x_scaled, y_scaled, x_scaled + w_scaled, y_scaled + h_scaled,
            fill=self.color, outline=outline, width=width, tags=f"box_{id(self)}"
        )

        # Font size scales with zoom
        font_size_title = max(7, int(9 * zoom))
        font_size_subtitle = max(5, int(7 * zoom))
        font_size_footer = max(4, int(6 * zoom))

        # Title text - at top (within 2% of box height from top)
        title_y = y_scaled + h_scaled * 0.08  # 2% + some padding
        self.text_id = self.canvas.create_text(
            x_scaled + w_scaled / 2, title_y,
            text=self.wrap_text(self.text, int(self.width / 5)),
            fill="black", font=("Arial", font_size_title, "bold"),
            tags=f"text_{id(self)}", justify=tk.CENTER, width=int(w_scaled * 0.9)
        )

        # Subtitle text - in middle
        subtitle_y = y_scaled + h_scaled * 0.5
        if self.subtitle:
            self.subtitle_id = self.canvas.create_text(
                x_scaled + w_scaled / 2, subtitle_y,
                text=self.wrap_text(self.subtitle, int(self.width / 5)),
                fill="#333333", font=("Arial", font_size_subtitle),
                tags=f"subtitle_{id(self)}", justify=tk.CENTER, width=int(w_scaled * 0.9)
            )

        # Footer text - at bottom (within 2% of box height from bottom)
        footer_y = y_scaled + h_scaled * 0.92  # 2% from bottom
        if self.footer:
            self.footer_id = self.canvas.create_text(
                x_scaled + w_scaled / 2, footer_y,
                text=self.wrap_text(self.footer, int(self.width / 5)),
                fill="#555555", font=("Arial", font_size_footer),
                tags=f"footer_{id(self)}", justify=tk.CENTER, width=int(w_scaled * 0.9)
            )

        # Draw resize handle at bottom-right only if in resize mode
        if show_resize_handle:
            # Handle is 50x50 in model coordinates (scales with zoom)
            handle_size_model = 50
            handle_size_screen = handle_size_model * zoom
            handle_x1 = x_scaled + w_scaled - handle_size_screen
            handle_y1 = y_scaled + h_scaled - handle_size_screen
            handle_x2 = x_scaled + w_scaled
            handle_y2 = y_scaled + h_scaled

            self.resize_handle_id = self.canvas.create_rectangle(
                handle_x1, handle_y1, handle_x2, handle_y2,
                fill="#ff6b73", outline="#ff0000", width=2, tags=f"resize_{id(self)}"
            )

    def redraw(self):
        """Redraw the box (used after changes). Note: box doesn't store zoom/pan; call via canvas redraw."""
        # This method is deprecated - use canvas.redraw_canvas() instead
        # Boxes cannot redraw themselves without access to current zoom/pan
        pass

    def set_select(self, selected):
        """Set selection state and store it."""
        self.selected = selected

    def contains(self, x, y):
        """Check if point is inside this box (model coordinates)."""
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.height)

    def is_on_resize_handle(self, x, y):
        """Check if point is on the resize handle (model coordinates). Returns True if on handle."""
        if not self.selected:
            return False
        # Handle is 50x50 at bottom-right corner
        handle_size = 50
        return (self.x + self.width - handle_size <= x <= self.x + self.width and
                self.y + self.height - handle_size <= y <= self.y + self.height)

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
        """Set box color and trigger redraw via canvas."""
        self.color = color
        # Note: redraw() is now a no-op; caller must call canvas.redraw_canvas()

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
        self.image_thumbnail_cache = {}  # Cache: (width, height) -> ImageTk
        self.controls = []
        self.boxes = []
        # List of connection lines: [{"start_box": box, "end_box": box, "waypoints": [...]}]
        self.lines = []
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.drawing_line = False
        self.line_start_box = None  # Box where line started
        self.line_original_start = None  # Original start point (never changes)
        self.line_start = None
        self.line_waypoints = []
        self.line_current_pos = None  # Current mouse position for preview
        self.selected_boxes = []
        self.selected_box = None  # Current box being edited in sidebar
        self.selected_line = None  # Currently selected line for deletion
        self.dragging_box = None
        self.resizing_box = None  # Box being resized via handle drag
        # Box in resize mode (activated by double-click)
        self.resize_mode_box = None
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.panning = False
        self.space_pressed = False
        self.canvas_need_redraw = True  # Track if canvas needs full redraw

        self.setup_ui()

    def setup_ui(self):
        """Setup UI layout with canvas and sidebar."""
        # Top toolbar with organized sections
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # File Operations
        file_frame = ttk.LabelFrame(toolbar, text="File")
        file_frame.pack(side=tk.LEFT, padx=2)

        btn_load_img = tk.Button(
            file_frame, text="     🖼️", command=self.load_image, width=4, height=2, font=("Arial", 14),
            anchor="center", padx=0, pady=0)
        btn_load_img.pack(side=tk.LEFT, padx=2)
        Tooltip(btn_load_img, "Load device image")

        btn_load_html = tk.Button(
            file_frame, text="📄", command=self.load_html, width=4, height=2, font=("Arial", 14),
            anchor="center", padx=0, pady=0)
        btn_load_html.pack(side=tk.LEFT, padx=2)
        Tooltip(btn_load_html, "Load DCS HTML controls")

        btn_save = tk.Button(
            file_frame, text="💾", command=self.save_layout, width=4, height=2, font=("Arial", 14),
            anchor="center", padx=0, pady=0)
        btn_save.pack(side=tk.LEFT, padx=2)
        Tooltip(btn_save, "Save layout to file")

        btn_export = tk.Button(
            file_frame, text="📸", command=self.export_png, width=4, height=2, font=("Arial", 14),
            anchor="center", padx=0, pady=0)
        btn_export.pack(side=tk.LEFT, padx=2)
        Tooltip(btn_export, "Export layout as PNG")

        # Editing
        edit_frame = ttk.LabelFrame(toolbar, text="Edit")
        edit_frame.pack(side=tk.LEFT, padx=2)

        btn_insert = tk.Button(
            edit_frame, text="➕", command=self.insert_custom_box, width=4, height=2, font=("Arial", 14),
            anchor="center", padx=0, pady=0)
        btn_insert.pack(side=tk.LEFT, padx=2)
        Tooltip(btn_insert, "Insert new box")

        btn_regen = tk.Button(
            edit_frame, text="🔄", command=self.regenerate_auto_imported, width=4, height=2, font=("Arial", 14),
            anchor="center", padx=0, pady=0)
        btn_regen.pack(side=tk.LEFT, padx=2)
        Tooltip(btn_regen, "Regenerate auto-imported controls")

        btn_line = tk.Button(
            edit_frame, text="📍", command=self.start_line_mode, width=4, height=2, font=("Arial", 14),
            anchor="center", padx=0, pady=0)
        btn_line.pack(side=tk.LEFT, padx=2)
        Tooltip(btn_line, "Draw connection lines")

        # View
        view_frame = ttk.LabelFrame(toolbar, text="View")
        view_frame.pack(side=tk.LEFT, padx=2)

        ttk.Label(view_frame, text="Zoom:").pack(side=tk.LEFT, padx=5)
        self.zoom_label = ttk.Label(view_frame, text="100%", width=5)
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

        ttk.Label(sidebar, text="Properties", font=(
            "Arial", 12, "bold")).pack(pady=10)

        # Properties frame with scrollbar
        properties_frame = ttk.Frame(sidebar)
        properties_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(properties_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.properties_canvas = tk.Canvas(
            properties_frame, bg="white", highlightthickness=0, yscrollcommand=scrollbar.set)
        self.properties_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.properties_canvas.yview)

        self.properties_inner = ttk.Frame(self.properties_canvas)
        self.canvas_window = self.properties_canvas.create_window(
            (0, 0), window=self.properties_inner, anchor=tk.NW)

        # Bind canvas resize to update inner frame width
        def on_canvas_configure(event):
            self.properties_canvas.itemconfig(
                self.canvas_window, width=event.width)

        self.properties_canvas.bind("<Configure>", on_canvas_configure)

        # Enable mousewheel scrolling on properties canvas
        def on_properties_mousewheel(event):
            delta = -1 if event.delta > 0 else 1
            self.properties_canvas.yview_scroll(delta, "units")

        self.properties_canvas.bind("<MouseWheel>", on_properties_mousewheel)
        self.properties_canvas.bind(
            "<Button-4>", lambda e: self.properties_canvas.yview_scroll(-1, "units"))
        self.properties_canvas.bind(
            "<Button-5>", lambda e: self.properties_canvas.yview_scroll(1, "units"))

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
        self.canvas.bind("<Motion>", self.on_canvas_motion)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Control-Button-1>", self.on_canvas_ctrl_click)
        self.canvas.bind("<KeyPress-space>", self.on_space_press)
        self.canvas.bind("<KeyRelease-space>", self.on_space_release)
        self.canvas.bind("<Delete>", self.on_delete_key)
        self.canvas.bind("<Escape>", self.on_escape_key)
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

        device_name = simpledialog.askstring(
            "Device Name", "Enter device name:")
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
        self.status.config(
            text=f"Loaded: {device_name} ({self.image.size[0]}x{self.image.size[1]})")

    def load_html(self):
        """Load DCS HTML and create control boxes."""
        if not self.device_name:
            messagebox.showerror("Error", "Load image first")
            return

        file_path = filedialog.askopenfilename(
            filetypes=[("HTML Files", "*.html"), ("All Files", "*.*")])
        if not file_path:
            return

        try:
            self.controls = parse_html(file_path)
            self.create_boxes()
            self.status.config(text=f"Loaded {len(self.controls)} controls")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse HTML:\n{e}")

    def regenerate_auto_imported(self):
        """Regenerate auto-imported controls from last loaded HTML without duplicates."""
        if not self.controls:
            messagebox.showwarning(
                "Warning", "No HTML controls loaded yet. Load HTML first.")
            return

        self.create_boxes()
        self.status.config(
            text=f"Regenerated {len([b for b in self.boxes if b.is_auto_imported])} auto-imported controls")

    def on_delete_key(self, event):
        """Delete selected boxes or lines when Delete key is pressed."""
        # Check if a line is selected
        if self.selected_line:
            if messagebox.askyesno("Confirm Delete", "Delete this line?"):
                if self.selected_line in self.lines:
                    self.lines.remove(self.selected_line)

                self.selected_line = None
                self.redraw_canvas()
                self.status.config(text="Line deleted")
            return

        # Otherwise check for selected boxes
        if not self.selected_boxes:
            return

        # Confirm deletion
        num_to_delete = len(self.selected_boxes)
        auto_imported_count = sum(
            1 for b in self.selected_boxes if b.is_auto_imported)

        msg = f"Delete {num_to_delete} box(es)?"
        if auto_imported_count > 0:
            msg += f"\n\n({auto_imported_count} auto-imported - use 'Regenerate Auto-Imported' to restore)"

        if messagebox.askyesno("Confirm Delete", msg):
            for box in self.selected_boxes:
                if box in self.boxes:
                    self.boxes.remove(box)

            self.selected_boxes = []
            self.selected_box = None
            self.update_sidebar()
            self.redraw_canvas()

            self.status.config(text=f"Deleted {num_to_delete} box(es)")

    def on_escape_key(self, event):
        """Cancel line drawing when ESC is pressed."""
        if self.drawing_line:
            # Cancel the line being drawn
            self.drawing_line = False
            self.line_start_box = None
            self.line_original_start = None
            self.line_start = None
            self.line_waypoints = []
            self.line_current_pos = None
            self.redraw_canvas()
            self.status.config(text="Line drawing cancelled")
        else:
            # If not drawing a line, deselect everything
            self.selected_boxes = []
            self.selected_box = None
            self.selected_line = None
            self.resize_mode_box = None
            self.update_sidebar()
            self.redraw_canvas()
            self.status.config(text="Selection cleared")

    def create_boxes(self):
        """Create control boxes from parsed controls, avoiding duplicates."""
        # Remove existing auto-imported boxes to regenerate them
        self.boxes = [box for box in self.boxes if not box.is_auto_imported]

        # Grid layout for initial placement
        cols = 3
        for i, control in enumerate(self.controls):
            row = i // cols
            col = i % cols
            x = 100 + col * 250
            y = 200 + row * 250

            # Extract button name and command
            button_name = control["key"].replace(
                "JOY_BTN", "").replace("JOY_", "")
            command = control.get("command", "")
            # Abbreviate command if too long
            if len(command) > 25:
                command = command[:22] + "..."

            # Determine color and footer based on modifiers
            color = "#81ff83"  # Default green
            footer = ""
            if control.get("modifiers"):
                color = "#ff4444"  # Red for modifier controls
                footer = control.get("modifier_text", "")

            box = ControlBox(
                self.canvas, x, y, width=200, height=200,
                text=button_name, subtitle=command, footer=footer,
                control_key=control["key"], color=color
            )
            box.is_auto_imported = True  # Mark as auto-imported
            self.boxes.append(box)

        self.redraw_canvas()

    def redraw_canvas(self):
        """Redraw canvas with image and boxes. Optimized with image caching."""
        self.canvas.delete("all")

        if self.image:
            # Use cached thumbnail if zoom level matches
            thumbnail_size = (int(self.image.width * self.zoom),
                              int(self.image.height * self.zoom))
            cache_key = thumbnail_size

            if cache_key not in self.image_thumbnail_cache:
                # Create and cache image at correct zoom level
                display_image = self.image.copy()
                # Use resize to handle both zoom in and zoom out
                display_image = display_image.resize(
                    (thumbnail_size[0], thumbnail_size[1]), Image.Resampling.LANCZOS)
                self.image_tk = ImageTk.PhotoImage(display_image)
                self.image_thumbnail_cache[cache_key] = self.image_tk
                # Limit cache to 5 entries to avoid memory bloat
                if len(self.image_thumbnail_cache) > 5:
                    oldest_key = next(iter(self.image_thumbnail_cache))
                    del self.image_thumbnail_cache[oldest_key]
            else:
                # Use cached image
                self.image_tk = self.image_thumbnail_cache[cache_key]

            self.canvas.create_image(
                self.pan_x, self.pan_y, image=self.image_tk, anchor=tk.NW, tags="image")

        # Draw lines first (so they appear behind boxes)
        for line in self.lines:
            self.draw_line(line)

        # Draw line preview while drawing
        if self.drawing_line and self.line_start and self.line_current_pos:
            self.draw_line_preview()

        # Redraw all boxes with zoom and pan
        for box in self.boxes:
            show_handle = (box == self.resize_mode_box)
            box.draw(self.zoom, self.pan_x, self.pan_y,
                     show_resize_handle=show_handle)

    def draw_line(self, line):
        """Draw a connection line with the color of the end box."""
        end_box = line["end_box"]
        waypoints = line["waypoints"]

        # Use the end box's color
        color = end_box.color
        # Make selected lines thicker and highlighted
        width = 4 if line == self.selected_line else 2

        # Build the complete path: start point/box -> waypoints -> end box center
        points = []

        # Start from start_point or start_box center (for backwards compatibility)
        if "start_point" in line:
            start_x, start_y = line["start_point"]
            start_screen_x = start_x * self.zoom + self.pan_x
            start_screen_y = start_y * self.zoom + self.pan_y
        else:
            # Backwards compatibility with old format using start_box
            start_box = line["start_box"]
            start_screen_x = (start_box.x + start_box.width /
                              2) * self.zoom + self.pan_x
            start_screen_y = (start_box.y + start_box.height /
                              2) * self.zoom + self.pan_y

        points.append(start_screen_x)
        points.append(start_screen_y)

        # Add waypoints (scaled and panned)
        for wp_x, wp_y in waypoints:
            points.append(wp_x * self.zoom + self.pan_x)
            points.append(wp_y * self.zoom + self.pan_y)

        # End at center of end box
        end_center_x = (end_box.x + end_box.width / 2) * self.zoom + self.pan_x
        end_center_y = (end_box.y + end_box.height / 2) * \
            self.zoom + self.pan_y
        points.append(end_center_x)
        points.append(end_center_y)

        # Draw the line (with highlight if selected)
        if len(points) >= 4:
            if line == self.selected_line:
                # Draw white/light outline for selected state
                self.canvas.create_line(
                    *points, fill="white", width=width + 2, tags="line_highlight")
            self.canvas.create_line(
                *points, fill=color, width=width, tags="line")

    def draw_line_preview(self):
        """Draw a preview line showing what the user is drawing in real-time."""
        if not self.line_start or not self.line_current_pos:
            return

        # Build the preview path: original start point -> waypoints -> current position
        points = []

        # Use original start point (not the moving line_start)
        start_x, start_y = self.line_original_start if self.line_original_start else self.line_start
        points.append(start_x * self.zoom + self.pan_x)
        points.append(start_y * self.zoom + self.pan_y)

        # Add waypoints (scaled and panned)
        for wp_x, wp_y in self.line_waypoints:
            points.append(wp_x * self.zoom + self.pan_x)
            points.append(wp_y * self.zoom + self.pan_y)

        # Current mouse position (scaled and panned)
        current_x, current_y = self.line_current_pos
        points.append(current_x * self.zoom + self.pan_x)
        points.append(current_y * self.zoom + self.pan_y)

        # Check if hovering over a box - if so, use its color, otherwise use gray
        preview_color = "#888888"  # Default gray
        for box in self.boxes:
            if box.contains(current_x, current_y):
                preview_color = box.color
                break

        # Draw the preview line
        if len(points) >= 4:
            self.canvas.create_line(
                *points, fill=preview_color, width=2, dash=(4, 4), tags="line_preview")

            # Draw circles at waypoints to show path
            for wp_x, wp_y in self.line_waypoints:
                wp_screen_x = wp_x * self.zoom + self.pan_x
                wp_screen_y = wp_y * self.zoom + self.pan_y
                self.canvas.create_oval(
                    wp_screen_x - 4, wp_screen_y - 4,
                    wp_screen_x + 4, wp_screen_y + 4,
                    fill=preview_color, outline=preview_color, tags="line_preview"
                )

    def on_mousewheel(self, event):
        """Handle zoom with mouse wheel."""
        delta = 1.1 if event.num == 4 or event.delta > 0 else 0.9
        self.zoom = max(0.1, min(3.0, self.zoom * delta))
        self.zoom_label.config(text=f"{int(self.zoom * 100)}%")
        self.redraw_canvas()

    def screen_to_model(self, screen_x, screen_y):
        """Convert screen coordinates to model coordinates (inverse of zoom/pan)."""
        model_x = (screen_x - self.pan_x) / self.zoom if self.zoom > 0 else 0
        model_y = (screen_y - self.pan_y) / self.zoom if self.zoom > 0 else 0
        return model_x, model_y

    def model_to_screen(self, model_x, model_y):
        """Convert model coordinates to screen coordinates (apply zoom/pan)."""
        screen_x = model_x * self.zoom + self.pan_x
        screen_y = model_y * self.zoom + self.pan_y
        return screen_x, screen_y

    def distance_to_line_segment(self, px, py, x1, y1, x2, y2):
        """Calculate perpendicular distance from point (px, py) to line segment (x1,y1)-(x2,y2)."""
        # Vector from start to end
        dx = x2 - x1
        dy = y2 - y1

        # If start and end are the same point
        if dx == 0 and dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5

        # Project point onto line (with clipping to segment bounds)
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))

        # Find closest point on segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy

        # Return distance
        return ((px - closest_x) ** 2 + (py - closest_y) ** 2) ** 0.5

    def find_line_at_point(self, model_x, model_y, tolerance=10):
        """Find a line near the given point (screen-space tolerance)."""
        # Convert tolerance to model space
        model_tolerance = tolerance / self.zoom if self.zoom > 0 else tolerance

        for line in self.lines:
            # Get line points in model space
            if "start_point" in line:
                start_x, start_y = line["start_point"]
            else:
                start_box = line["start_box"]
                start_x = start_box.x + start_box.width / 2
                start_y = start_box.y + start_box.height / 2

            # Check distance to each segment (start->waypoints->end)
            waypoints = line.get("waypoints", [])
            end_box = line["end_box"]
            end_x = end_box.x + end_box.width / 2
            end_y = end_box.y + end_box.height / 2

            # Build path: start -> waypoints -> end
            path_points = [(start_x, start_y)] + waypoints + [(end_x, end_y)]

            # Check distance to each segment
            for i in range(len(path_points) - 1):
                x1, y1 = path_points[i]
                x2, y2 = path_points[i + 1]

                dist = self.distance_to_line_segment(
                    model_x, model_y, x1, y1, x2, y2)
                if dist <= model_tolerance:
                    return line

        return None

    def on_canvas_left_click(self, event):
        """Handle left click - select box/line or start resize in resize mode."""
        if self.drawing_line:
            self.handle_line_click(event, is_right=False)
            return

        # Convert screen coords to model coords
        model_x, model_y = self.screen_to_model(event.x, event.y)

        # Check if clicking on a line first
        clicked_line = self.find_line_at_point(model_x, model_y)
        if clicked_line:
            self.selected_line = clicked_line
            self.selected_boxes = []
            self.selected_box = None
            self.resize_mode_box = None
            self.update_sidebar()
            self.redraw_canvas()
            self.status.config(
                text="Line selected. Press Delete to remove it.")
            return

        # Check if clicking on a box
        for box in self.boxes:
            if box.contains(model_x, model_y):
                self.dragging_box = box
                self.last_mouse_x = event.x
                self.last_mouse_y = event.y

                # Only allow resize handle drag if in resize mode for this box
                if self.resize_mode_box == box and box.is_on_resize_handle(model_x, model_y):
                    self.resizing_box = box

                # Select box for sidebar AND for visual highlighting (red outline)
                self.selected_box = box
                # Add to selected_boxes for red outline
                self.selected_boxes = [box]
                self.selected_line = None

                self.update_sidebar()
                self.redraw_boxes()
                return

        # Clicked outside boxes and lines - deselect and exit resize mode
        self.selected_boxes = []
        self.selected_box = None
        self.selected_line = None
        self.resize_mode_box = None
        self.update_sidebar()
        self.redraw_canvas()

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

        model_x, model_y = self.screen_to_model(event.x, event.y)
        for box in self.boxes:
            if box.contains(model_x, model_y):
                # Right-click now selects the box (like left-click)
                # Color picking moved to sidebar
                self.selected_box = box
                self.update_sidebar()
                self.redraw_boxes()
                return

    def on_canvas_ctrl_click(self, event):
        """Handle Ctrl+click - multi-select."""
        model_x, model_y = self.screen_to_model(event.x, event.y)
        for box in self.boxes:
            if box.contains(model_x, model_y):
                if box not in self.selected_boxes:
                    self.selected_boxes.append(box)
                else:
                    self.selected_boxes.remove(box)
                self.redraw_boxes()
                return

    def on_canvas_drag(self, event):
        """Handle drag - move boxes or resize in resize mode with real-time visual feedback."""
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

        # If in resize mode, only allow resizing via handle
        if self.resize_mode_box:
            if self.resizing_box:
                # Resize via handle drag in resize mode
                dx_model = (event.x - self.last_mouse_x) / self.zoom
                dy_model = (event.y - self.last_mouse_y) / self.zoom

                self.resizing_box.width = max(
                    40, self.resizing_box.width + dx_model)
                self.resizing_box.height = max(
                    20, self.resizing_box.height + dy_model)
                # Don't update sidebar during drag for performance

            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            self.redraw_canvas()
            return

        if self.dragging_box:
            # Convert deltas to model space (unzoom them)
            dx_model = (event.x - self.last_mouse_x) / self.zoom
            dy_model = (event.y - self.last_mouse_y) / self.zoom

            # Move the dragging box (and any multi-selected boxes with it)
            # Only move selected_boxes if there are any, otherwise just move the dragging box
            if self.selected_boxes:
                for box in self.selected_boxes:
                    box.x += dx_model
                    box.y += dy_model
            else:
                self.dragging_box.x += dx_model
                self.dragging_box.y += dy_model

            # Don't update sidebar during drag for performance
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            self.redraw_canvas()

    def on_canvas_release(self, event):
        """Handle release - update sidebar after dragging finishes."""
        # Update sidebar after drag/resize completes
        if self.dragging_box or self.resizing_box:
            self.update_sidebar()

        self.dragging_box = None
        self.resizing_box = None

    def redraw_boxes(self):
        """Redraw all boxes with selection states and update canvas."""
        for box in self.boxes:
            box.set_select(box in self.selected_boxes)
        self.redraw_canvas()

    def update_sidebar(self):
        """Update sidebar with selected box properties."""
        # Clear previous content
        for widget in self.properties_inner.winfo_children():
            widget.destroy()

        if not self.selected_box:
            ttk.Label(self.properties_inner, text="No box selected",
                      foreground="gray").pack(pady=20)
            self.properties_canvas.configure(
                scrollregion=self.properties_canvas.bbox("all"))
            return

        box = self.selected_box

        # Title property
        ttk.Label(self.properties_inner, text="Title (Button)", font=(
            "Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        text_var = tk.StringVar(value=box.text)
        text_entry = ttk.Entry(self.properties_inner,
                               textvariable=text_var, width=25)
        text_entry.pack(padx=10, pady=5, fill=tk.X)

        def on_text_change(*args):
            box.text = text_var.get()
            self.redraw_canvas()

        text_var.trace_add("write", on_text_change)

        # Subtitle property
        ttk.Label(self.properties_inner, text="Subtitle (Function)", font=(
            "Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        subtitle_var = tk.StringVar(value=box.subtitle)
        subtitle_entry = ttk.Entry(
            self.properties_inner, textvariable=subtitle_var, width=25)
        subtitle_entry.pack(padx=10, pady=5, fill=tk.X)

        def on_subtitle_change(*args):
            box.subtitle = subtitle_var.get()
            self.redraw_canvas()

        subtitle_var.trace_add("write", on_subtitle_change)

        # Footer property (optional)
        ttk.Label(self.properties_inner, text="Footer (Optional)", font=(
            "Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        footer_var = tk.StringVar(value=box.footer)
        footer_entry = ttk.Entry(
            self.properties_inner, textvariable=footer_var, width=25)
        footer_entry.pack(padx=10, pady=5, fill=tk.X)

        def on_footer_change(*args):
            box.footer = footer_var.get()
            self.redraw_canvas()

        footer_var.trace_add("write", on_footer_change)

        # Control Key property
        ttk.Label(self.properties_inner, text="Control Key", font=(
            "Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        key_var = tk.StringVar(value=box.control_key)
        key_entry = ttk.Entry(self.properties_inner,
                              textvariable=key_var, width=25)
        key_entry.pack(padx=10, pady=5, fill=tk.X)

        def on_key_change(*args):
            box.control_key = key_var.get()

        key_var.trace_add("write", on_key_change)

        # Position section
        ttk.Label(self.properties_inner, text="Position", font=(
            "Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(15, 5))

        # X position
        ttk.Label(self.properties_inner, text="X:").pack(anchor="w", padx=10)
        x_var = tk.StringVar(value=str(int(box.x)))
        x_entry = ttk.Entry(self.properties_inner,
                            textvariable=x_var, width=25)
        x_entry.pack(padx=10, pady=2, fill=tk.X)

        def on_x_change(*args):
            try:
                box.x = float(x_var.get())
                self.redraw_canvas()
            except ValueError:
                pass

        x_var.trace_add("write", on_x_change)

        # Y position
        ttk.Label(self.properties_inner, text="Y:").pack(anchor="w", padx=10)
        y_var = tk.StringVar(value=str(int(box.y)))
        y_entry = ttk.Entry(self.properties_inner,
                            textvariable=y_var, width=25)
        y_entry.pack(padx=10, pady=2, fill=tk.X)

        def on_y_change(*args):
            try:
                box.y = float(y_var.get())
                self.redraw_canvas()
            except ValueError:
                pass

        y_var.trace_add("write", on_y_change)

        # Size section
        ttk.Label(self.properties_inner, text="Size", font=(
            "Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(15, 5))

        # Width
        ttk.Label(self.properties_inner, text="Width:").pack(
            anchor="w", padx=10)
        w_var = tk.StringVar(value=str(int(box.width)))
        w_entry = ttk.Entry(self.properties_inner,
                            textvariable=w_var, width=25)
        w_entry.pack(padx=10, pady=2, fill=tk.X)

        def on_width_change(*args):
            try:
                box.width = max(40, float(w_var.get()))
                w_var.set(str(int(box.width)))
                self.redraw_canvas()
            except ValueError:
                pass

        w_var.trace_add("write", on_width_change)

        # Height
        ttk.Label(self.properties_inner, text="Height:").pack(
            anchor="w", padx=10)
        h_var = tk.StringVar(value=str(int(box.height)))
        h_entry = ttk.Entry(self.properties_inner,
                            textvariable=h_var, width=25)
        h_entry.pack(padx=10, pady=2, fill=tk.X)

        def on_height_change(*args):
            try:
                box.height = max(20, float(h_var.get()))
                h_var.set(str(int(box.height)))
                self.redraw_canvas()
            except ValueError:
                pass

        h_var.trace_add("write", on_height_change)

        # Color section - inline color picker
        ttk.Label(self.properties_inner, text="Color", font=(
            "Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(15, 5))

        colors = [
            "#81ff83", "#fff1a0", "#ff858b", "#83c8f2", "#baff85",
            "#ffb28a", "#ff6b73", "#4df500", "#83ffff", "#d585ee",
            "#ffffff", "#000000", "#cccccc", "#ff0000", "#00ff00"
        ]

        color_frame = tk.Frame(self.properties_inner)
        color_frame.pack(padx=10, pady=5)

        def on_color_change(new_color):
            box.set_color(new_color)
            self.redraw_canvas()

        for i, color in enumerate(colors):
            row = i // 3
            col = i % 3
            color_btn = tk.Button(
                color_frame, bg=color, width=5, height=2,
                relief=tk.RAISED if box.color != color else tk.SUNKEN,
                command=lambda c=color: on_color_change(c)
            )
            color_btn.grid(row=row, column=col, padx=2, pady=2)

        # Update scroll region
        self.properties_inner.update_idletasks()
        self.properties_canvas.configure(
            scrollregion=self.properties_canvas.bbox("all"))

    def insert_custom_box(self):
        """Insert a custom box."""
        # Create dialog for box properties
        dialog = tk.Toplevel(self.root)
        dialog.title("Insert Custom Box")
        dialog.geometry("300x420")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Title (Button):").grid(
            row=0, column=0, padx=10, pady=5, sticky="w")
        text_var = tk.StringVar(value="Button")
        text_entry = tk.Entry(dialog, textvariable=text_var, width=20)
        text_entry.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(dialog, text="Subtitle (Function):").grid(
            row=1, column=0, padx=10, pady=5, sticky="w")
        subtitle_var = tk.StringVar(value="")
        subtitle_entry = tk.Entry(dialog, textvariable=subtitle_var, width=20)
        subtitle_entry.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(dialog, text="Footer (Optional):").grid(
            row=2, column=0, padx=10, pady=5, sticky="w")
        footer_var = tk.StringVar(value="")
        footer_entry = tk.Entry(dialog, textvariable=footer_var, width=20)
        footer_entry.grid(row=2, column=1, padx=10, pady=5)

        tk.Label(dialog, text="Control Key:").grid(
            row=3, column=0, padx=10, pady=5, sticky="w")
        key_var = tk.StringVar(value="CUSTOM_1")
        key_entry = tk.Entry(dialog, textvariable=key_var, width=20)
        key_entry.grid(row=3, column=1, padx=10, pady=5)

        tk.Label(dialog, text="X Position:").grid(
            row=4, column=0, padx=10, pady=5, sticky="w")
        x_var = tk.StringVar(value="100")
        x_entry = tk.Entry(dialog, textvariable=x_var, width=20)
        x_entry.grid(row=4, column=1, padx=10, pady=5)

        tk.Label(dialog, text="Y Position:").grid(
            row=5, column=0, padx=10, pady=5, sticky="w")
        y_var = tk.StringVar(value="100")
        y_entry = tk.Entry(dialog, textvariable=y_var, width=20)
        y_entry.grid(row=5, column=1, padx=10, pady=5)

        tk.Label(dialog, text="Width:").grid(
            row=6, column=0, padx=10, pady=5, sticky="w")
        w_var = tk.StringVar(value="200")
        w_entry = tk.Entry(dialog, textvariable=w_var, width=20)
        w_entry.grid(row=6, column=1, padx=10, pady=5)

        tk.Label(dialog, text="Height:").grid(
            row=7, column=0, padx=10, pady=5, sticky="w")
        h_var = tk.StringVar(value="200")
        h_entry = tk.Entry(dialog, textvariable=h_var, width=20)
        h_entry.grid(row=7, column=1, padx=10, pady=5)

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
                    footer=footer_var.get(),
                    control_key=key_var.get(),
                    color="#81ff83"
                )
                self.boxes.append(box)
                self.redraw_canvas()
                dialog.destroy()
                self.status.config(text="Custom box inserted")
            except ValueError:
                messagebox.showerror("Error", "Invalid numeric values")

        ttk.Button(dialog, text="Create", command=create_box).grid(
            row=8, column=0, columnspan=2, pady=20)

    def on_canvas_double_click(self, event):
        """Handle double-click to enable/disable resize mode."""
        model_x, model_y = self.screen_to_model(event.x, event.y)

        # Check if double-clicking the same box that's in resize mode - toggle off
        if self.resize_mode_box:
            if self.resize_mode_box.contains(model_x, model_y):
                self.resize_mode_box = None
                self.redraw_boxes()
                return

        # Check if double-clicking a box to enter resize mode
        for box in self.boxes:
            if box.contains(model_x, model_y):
                self.resize_mode_box = box
                self.selected_box = box
                self.update_sidebar()
                self.redraw_boxes()
                return

    def start_line_mode(self):
        """Start line drawing mode."""
        self.drawing_line = True
        self.line_start_box = None
        self.line_original_start = None
        self.line_start = None
        self.line_waypoints = []
        self.status.config(
            text="Line mode: Click anywhere to start, right-click for waypoint, left-click on a box to end")

    def handle_line_click(self, event, is_right):
        """Handle clicks while drawing line."""
        # Store all waypoints in model coordinates
        model_x, model_y = self.screen_to_model(event.x, event.y)

        if not self.line_start:
            # Start line from any point on the canvas
            self.line_start = (model_x, model_y)
            # Remember original start point
            self.line_original_start = (model_x, model_y)
            self.status.config(
                text="Line started. Right-click for waypoint, left-click on a box to end")
            return

        if is_right:
            # Add waypoint
            self.line_waypoints.append((model_x, model_y))
            self.line_start = (model_x, model_y)
            self.status.config(
                text=f"Waypoint added. Right-click for more, left-click on a box to end")
        else:
            # End line - must click on a box
            end_box = None
            for box in self.boxes:
                if box.contains(model_x, model_y):
                    end_box = box
                    break

            if end_box:
                # Create line from original start point to end_box with waypoints
                line = {
                    "start_point": self.line_original_start,
                    "end_box": end_box,
                    "waypoints": self.line_waypoints.copy()
                }
                self.lines.append(line)
                self.redraw_canvas()
                self.status.config(text="Line drawn")
            else:
                self.status.config(text="Line cancelled - must end on a box")

            self.drawing_line = False
            self.line_start_box = None
            self.line_original_start = None
            self.line_start = None
            self.line_waypoints = []

    def on_canvas_motion(self, event):
        """Handle canvas mouse motion - update line preview during drawing."""
        if self.drawing_line and self.line_start:
            # Convert to model coordinates
            model_x, model_y = self.screen_to_model(event.x, event.y)
            self.line_current_pos = (model_x, model_y)
            self.redraw_canvas()

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
                    "footer": box.footer,
                    "control_key": box.control_key,
                    "color": box.color
                }
                for box in self.boxes
            ],
            "lines": [
                {
                    "start_point": line["start_point"] if "start_point" in line else None,
                    "end_box_index": self.boxes.index(line["end_box"]) if line["end_box"] in self.boxes else -1,
                    "waypoints": line["waypoints"]
                }
                for line in self.lines if line["end_box"] in self.boxes
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
            # Draw title (at top, within 2%)
            title_y = box.y + box.height * 0.08
            draw.text(
                (box.x + box.width / 2, title_y),
                box.text,
                fill="black", anchor="mm", font=None
            )
            # Draw subtitle (in middle)
            if box.subtitle:
                subtitle_y = box.y + box.height * 0.5
                draw.text(
                    (box.x + box.width / 2, subtitle_y),
                    box.subtitle,
                    fill="#333333", anchor="mm", font=None
                )
            # Draw footer (at bottom, within 2%)
            if box.footer:
                footer_y = box.y + box.height * 0.92
                draw.text(
                    (box.x + box.width / 2, footer_y),
                    box.footer,
                    fill="#555555", anchor="mm", font=None
                )

        device_dir = LAYOUTS_DIR / self.device_name
        export_path = device_dir / "layout.png"
        export_img.save(export_path)

        messagebox.showinfo("Success", f"Exported to {export_path}")


if __name__ == "__main__":
    root = tk.Tk()
    app = LayoutEditor(root)
    root.mainloop()
