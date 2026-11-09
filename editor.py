#!/usr/bin/env python3
"""Interactive HOTAS Layout Editor - Tkinter Canvas-based editor."""

import json
import re
import sys
import tkinter as tk
from html.parser import HTMLParser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
from tkinter import ttk
from PIL import Image, ImageDraw, ImageFont, ImageTk
import io

ROOT = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
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
    """Parse DCS HTML export and return list of controls with support for unlimited modifiers.
    
    Handles control bindings with any number of modifiers:
    - "JOY_BTN1" - single button, no modifiers
    - "JOY_BTN2 - JOY_BTN4" - BTN4 with BTN2 modifier
    - "JOY_BTN1 - JOY_BTN2 - JOY_BTN4" - BTN4 with BTN1 and BTN2 modifiers (triple combo)
    - "JOY_BTN1 - JOY_BTN2 - JOY_BTN3 - JOY_BTN4" - BTN4 with 3 modifiers (quad combo)
    - And so on for any number of modifiers...
    """
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

            # Split by " - " to separate all modifiers from the main button
            # The LAST part is the main button, everything before are modifiers
            # This supports unlimited modifiers (1, 2, 3, 4+ modifiers)
            parts = binding_str.split(" - ")
            button_name = parts[-1].strip()  # Last part is the main button
            modifiers = [p.strip() for p in parts[:-1]] if len(parts) > 1 else []  # All others are modifiers

            # Create modifier text for footer (e.g., "Mod: BTN1, BTN2, BTN3")
            modifier_text = ""
            if modifiers:
                mod_names = []
                for mod in modifiers:
                    # Extract button/axis name from "JOY_BTN2" -> "BTN2" or "JOY_Y_AXIS" -> "Y AXIS"
                    mod_clean = mod.replace("JOY_", "").replace("_", " ")
                    mod_names.append(mod_clean)
                
                # Format: "Mod: BTN1, BTN2" or "Mod: BTN1, BTN2, BTN3" etc.
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
        # Font sizes (actual point sizes, not multipliers)
        self.title_font_size = 14  # Title font size (default 14pt)
        self.subtitle_font_size = 11  # Subtitle font size (default 11pt)
        self.footer_font_size = 9  # Footer font size (default 9pt)
        self.line_id = None
        self.line_waypoints = []
        self.rect_id = None
        self.text_id = None
        self.subtitle_id = None
        self.footer_id = None
        self.resize_handle_id = None  # Visual resize handle
        self.text_wrap_cache = {}  # Cache: (text, max_chars) -> wrapped_text

    def wrap_text(self, text, box_width, font_size):
        """Wrap text to fit within box width (pixel-based, not character-based).
        
        Only breaks lines when text actually exceeds the available width.
        Uses approximate character width calculation based on font size.
        """
        if not text:
            return text
        
        # Average character width is roughly 0.5 * font_size
        # This is an approximation that works reasonably for most fonts
        avg_char_width = font_size * 0.5
        
        # Available width is 90% of box width
        available_width = box_width * 0.9
        
        # Maximum characters that can fit in one line
        max_chars_per_line = int(available_width / avg_char_width)
        
        # If text fits on one line, return as-is
        if len(text) <= max_chars_per_line:
            return text
        
        # Split text into words and build lines
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_length = len(word)
            # Account for spaces between words
            space_needed = 1 if current_line else 0
            
            if current_length + space_needed + word_length <= max_chars_per_line:
                current_line.append(word)
                current_length += space_needed + word_length
            else:
                # Start a new line
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length
        
        # Add remaining words
        if current_line:
            lines.append(" ".join(current_line))
        
        return "\n".join(lines)

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

        # Font size SCALES with zoom on canvas for visual proportion
        # At high zoom (200%+), text is larger; at low zoom (44%), text is smaller
        # But always clamped to readable minimum (6pt) and reasonable maximum (72pt)
        font_size_title = max(6, min(72, int(self.title_font_size * zoom)))
        font_size_subtitle = max(6, min(72, int(self.subtitle_font_size * zoom)))
        font_size_footer = max(6, min(72, int(self.footer_font_size * zoom)))

        # Title text - at top (within 2% of box height from top)
        title_y = y_scaled + h_scaled * 0.08  # 2% + some padding
        # Width in pixels: 90% of scaled box width
        text_width_pixels = int(w_scaled * 0.9)
        self.text_id = self.canvas.create_text(
            x_scaled + w_scaled / 2, title_y,
            text=self.wrap_text(self.text, self.width, font_size_title),
            fill="black", font=("Arial", font_size_title, "bold"),
            width=text_width_pixels,
            tags=f"text_{id(self)}", justify=tk.CENTER
        )

        # Subtitle text - in middle
        subtitle_y = y_scaled + h_scaled * 0.5
        if self.subtitle:
            self.subtitle_id = self.canvas.create_text(
                x_scaled + w_scaled / 2, subtitle_y,
                text=self.wrap_text(self.subtitle, self.width, font_size_subtitle),
                fill="black", font=("Arial", font_size_subtitle),
                width=text_width_pixels,
                tags=f"subtitle_{id(self)}", justify=tk.CENTER
            )

        # Footer text - at bottom (within 2% of box height from bottom)
        footer_y = y_scaled + h_scaled * 0.92  # 2% from bottom
        if self.footer:
            self.footer_id = self.canvas.create_text(
                x_scaled + w_scaled / 2, footer_y,
                text=self.wrap_text(self.footer, self.width, font_size_footer),
                fill="black", font=("Arial", font_size_footer),
                width=text_width_pixels,
                tags=f"footer_{id(self)}", justify=tk.CENTER
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

        btn_open = tk.Button(
            file_frame, text="📂", command=self.open_layout, width=4, height=2, font=("Arial", 14),
            anchor="center", padx=0, pady=0)
        btn_open.pack(side=tk.LEFT, padx=2)
        Tooltip(btn_open, "Open existing layout")

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
        # Auto-fit zoom to show entire image
        self.zoom = self.calculate_autofit_zoom()
        self.pan_x = 0
        self.pan_y = 0
        self.zoom_label.config(text=f"{int(self.zoom * 100)}%")
        self.redraw_canvas()
        self.status.config(
            text=f"Loaded: {device_name} ({self.image.size[0]}x{self.image.size[1]}) at {int(self.zoom * 100)}%")

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
            # No truncation - let the text wrapping handle it naturally

            # Determine color and footer based on modifiers
            # Support any number of modifiers (1, 2, 3, or more)
            modifiers = control.get("modifiers", [])
            color = "#81ff83"  # Default green
            footer = ""
            
            if modifiers:
                # Multi-modifier support: any number of modifiers are marked as red
                color = "#ff4444"  # Red for modifier controls
                # Use the modifier text generated during parsing
                # which already handles multiple modifiers: "Mod: BTN1, BTN2, BTN3"
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

        # Font Size section
        ttk.Label(self.properties_inner, text="Font Sizes (points)", font=(
            "Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(15, 5))

        # Title font size (spinbox for actual point size)
        ttk.Label(self.properties_inner, text="Title:").pack(
            anchor="w", padx=10)
        title_size_var = tk.StringVar(value=str(box.title_font_size))
        title_size_spinbox = ttk.Spinbox(self.properties_inner,
                                         from_=6, to=36, textvariable=title_size_var,
                                         width=25)
        title_size_spinbox.pack(padx=10, pady=2, fill=tk.X)

        def on_title_size_change(*args):
            try:
                box.title_font_size = max(6, min(36, int(title_size_var.get())))
                title_size_var.set(str(box.title_font_size))
                self.redraw_canvas()
            except ValueError:
                pass

        title_size_var.trace_add("write", on_title_size_change)

        # Subtitle font size (spinbox for actual point size)
        ttk.Label(self.properties_inner, text="Subtitle:").pack(
            anchor="w", padx=10)
        subtitle_size_var = tk.StringVar(value=str(box.subtitle_font_size))
        subtitle_size_spinbox = ttk.Spinbox(self.properties_inner,
                                            from_=6, to=36, textvariable=subtitle_size_var,
                                            width=25)
        subtitle_size_spinbox.pack(padx=10, pady=2, fill=tk.X)

        def on_subtitle_size_change(*args):
            try:
                box.subtitle_font_size = max(6, min(36, int(subtitle_size_var.get())))
                subtitle_size_var.set(str(box.subtitle_font_size))
                self.redraw_canvas()
            except ValueError:
                pass

        subtitle_size_var.trace_add("write", on_subtitle_size_change)

        # Footer font size (spinbox for actual point size)
        ttk.Label(self.properties_inner, text="Footer:").pack(
            anchor="w", padx=10)
        footer_size_var = tk.StringVar(value=str(box.footer_font_size))
        footer_size_spinbox = ttk.Spinbox(self.properties_inner,
                                          from_=6, to=36, textvariable=footer_size_var,
                                          width=25)
        footer_size_spinbox.pack(padx=10, pady=2, fill=tk.X)

        def on_footer_size_change(*args):
            try:
                box.footer_font_size = max(6, min(36, int(footer_size_var.get())))
                footer_size_var.set(str(box.footer_font_size))
                self.redraw_canvas()
            except ValueError:
                pass

        footer_size_var.trace_add("write", on_footer_size_change)

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
                    "color": box.color,
                    "title_font_size": box.title_font_size,
                    "subtitle_font_size": box.subtitle_font_size,
                    "footer_font_size": box.footer_font_size
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
        try:
            device_dir.mkdir(parents=True, exist_ok=True)
            image_path = device_dir / "image.png"
            if self.image:
                source_path = getattr(self.image, "filename", None)
                if not source_path or Path(source_path).resolve() != image_path.resolve():
                    self.image.save(image_path, format="PNG")
            with open(layout_path, "w") as f:
                json.dump(layout_data, f, indent=2)
        except OSError as e:
            messagebox.showerror("Error", f"Failed to save layout:\n{e}")
            return

        messagebox.showinfo("Success", f"Layout saved to {layout_path}")
        self.status.config(text=f"Layout saved")

    def calculate_autofit_zoom(self):
        """Calculate zoom level to fit entire image in canvas with padding."""
        if not self.image:
            return 1.0
        
        # Get canvas dimensions
        self.root.update_idletasks()  # Ensure canvas is fully rendered
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # If canvas not yet sized, return default
        if canvas_width <= 1 or canvas_height <= 1:
            return 1.0
        
        # Calculate zoom to fit image with 5% padding
        padding = 0.95
        zoom_x = (canvas_width / self.image.width) * padding
        zoom_y = (canvas_height / self.image.height) * padding
        
        # Use the smaller zoom to fit both dimensions
        zoom = min(zoom_x, zoom_y)
        
        # Clamp to reasonable range
        return max(0.1, min(3.0, zoom))

    def open_layout(self):
        """Open existing layout from JSON."""
        layout_path = filedialog.askopenfilename(
            initialdir=LAYOUTS_DIR,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Open Layout"
        )
        
        if not layout_path:
            return
        
        try:
            with open(layout_path, "r") as f:
                layout_data = json.load(f)
            
            # Set device name
            self.device_name = layout_data.get("device_name", "Untitled")
            
            # Load image from the same directory as the JSON
            layout_dir = Path(layout_path).parent
            image_path = None
            for img_ext in ["*.png", "*.jpg", "*.jpeg"]:
                matches = list(layout_dir.glob(img_ext))
                if matches:
                    image_path = matches[0]
                    break
            
            if image_path and image_path.exists():
                self.image = Image.open(image_path)
                self.image_thumbnail_cache.clear()
                # Auto-fit zoom to show entire image
                self.zoom = self.calculate_autofit_zoom()
                self.pan_x = 0
                self.pan_y = 0
                self.zoom_label.config(text=f"{int(self.zoom * 100)}%")
                self.status.config(text=f"Loaded image: {image_path.name} (auto-fit: {int(self.zoom * 100)}%)")
            else:
                self.image = None
                messagebox.showwarning("Warning", 
                    f"Device image not found in {layout_dir}\n"
                    f"You can still edit boxes, but image won't display")
            
            # Clear existing boxes and lines
            self.boxes = []
            self.lines = []
            self.selected_boxes = []
            self.selected_box = None
            self.selected_line = None
            
            # Load boxes
            for box_data in layout_data.get("boxes", []):
                box = ControlBox(
                    self.canvas,
                    box_data["x"],
                    box_data["y"],
                    width=box_data.get("width", 200),
                    height=box_data.get("height", 200),
                    text=box_data.get("text", ""),
                    subtitle=box_data.get("subtitle", ""),
                    footer=box_data.get("footer", ""),
                    control_key=box_data.get("control_key", ""),
                    color=box_data.get("color", "#81ff83")
                )
                box.is_auto_imported = False  # User loaded layout, not auto-imported
                # Load font sizes (with defaults if not present)
                box.title_font_size = box_data.get("title_font_size", 14)
                box.subtitle_font_size = box_data.get("subtitle_font_size", 11)
                box.footer_font_size = box_data.get("footer_font_size", 9)
                self.boxes.append(box)
            
            # Load lines
            for line_data in layout_data.get("lines", []):
                end_box_index = line_data.get("end_box_index", -1)
                if 0 <= end_box_index < len(self.boxes):
                    line = {
                        "start_point": tuple(line_data["start_point"]) if line_data.get("start_point") else (0, 0),
                        "end_box": self.boxes[end_box_index],
                        "waypoints": [tuple(wp) for wp in line_data.get("waypoints", [])]
                    }
                    self.lines.append(line)
            
            self.redraw_canvas()
            messagebox.showinfo("Success", 
                f"Loaded layout: {self.device_name}\n"
                f"Boxes: {len(self.boxes)}\n"
                f"Lines: {len(self.lines)}")
            self.status.config(text=f"Loaded layout: {self.device_name}")
        
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON file")
        except KeyError as e:
            messagebox.showerror("Error", f"Missing required field: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load layout: {e}")

    def export_png(self):
        """Export layout as PNG with text wrapping and automatic sizing."""
        if not self.device_name or not self.image:
            messagebox.showerror("Error", "Load image first")
            return

        # Create image with boxes
        export_img = self.image.copy()
        draw = ImageDraw.Draw(export_img)
        
        # Calculate scale factor: how much larger is the export image compared to canvas view
        if self.zoom > 0:
            scale_factor = 1.0 / self.zoom
        else:
            scale_factor = 1.0
        
        # Try to load Arial font from Windows
        font_path = None
        try:
            import os
            win_fonts = Path("C:/Windows/Fonts")
            if win_fonts.exists():
                arial_files = list(win_fonts.glob("arial.ttf"))
                if arial_files:
                    font_path = str(arial_files[0])
        except:
            pass

        def get_font(size):
            """Get a font at the specified size."""
            if font_path:
                try:
                    return ImageFont.truetype(font_path, size)
                except:
                    return ImageFont.load_default()
            return ImageFont.load_default()

        def wrap_text_export(text, box_width, font_size):
            """Wrap text to fit within box width."""
            if not text:
                return text
            
            avg_char_width = font_size * 0.5
            available_width = box_width * 0.9
            max_chars_per_line = max(1, int(available_width / avg_char_width))
            
            if len(text) <= max_chars_per_line:
                return text
            
            words = text.split()
            lines = []
            current_line = []
            current_length = 0
            
            for word in words:
                word_length = len(word)
                space_needed = 1 if current_line else 0
                
                if current_length + space_needed + word_length <= max_chars_per_line:
                    current_line.append(word)
                    current_length += space_needed + word_length
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [word]
                    current_length = word_length
            
            if current_line:
                lines.append(" ".join(current_line))
            
            return "\n".join(lines)

        for box in self.boxes:
            # Draw box
            draw.rectangle(
                [box.x, box.y, box.x + box.width, box.y + box.height],
                fill=box.color, outline="#333333", width=2
            )
            
            # Scale font sizes from canvas to export resolution
            title_font_size = max(8, int(box.title_font_size * scale_factor))
            subtitle_font_size = max(8, int(box.subtitle_font_size * scale_factor))
            footer_font_size = max(8, int(box.footer_font_size * scale_factor))
            
            # Apply text wrapping
            wrapped_title = wrap_text_export(box.text, box.width, title_font_size)
            wrapped_subtitle = wrap_text_export(box.subtitle, box.width, subtitle_font_size) if box.subtitle else ""
            wrapped_footer = wrap_text_export(box.footer, box.width, footer_font_size) if box.footer else ""
            
            # Draw title at top
            if wrapped_title:
                title_font = get_font(title_font_size)
                title_x = box.x + box.width / 2
                title_y = box.y + box.height * 0.08
                
                # Clamp to box bounds (with small margin)
                title_x = max(box.x + 5, min(box.x + box.width - 5, title_x))
                title_y = max(box.y + 5, min(box.y + box.height - 5, title_y))
                
                try:
                    draw.text(
                        (title_x, title_y),
                        wrapped_title,
                        fill="black", anchor="mm", font=title_font
                    )
                except Exception:
                    pass
            
            # Draw subtitle in middle
            if wrapped_subtitle:
                subtitle_font = get_font(subtitle_font_size)
                subtitle_x = box.x + box.width / 2
                subtitle_y = box.y + box.height * 0.5
                
                # Clamp to box bounds
                subtitle_x = max(box.x + 5, min(box.x + box.width - 5, subtitle_x))
                subtitle_y = max(box.y + 5, min(box.y + box.height - 5, subtitle_y))
                
                try:
                    draw.text(
                        (subtitle_x, subtitle_y),
                        wrapped_subtitle,
                        fill="black", anchor="mm", font=subtitle_font
                    )
                except Exception:
                    pass
            
            # Draw footer at bottom
            if wrapped_footer:
                footer_font = get_font(footer_font_size)
                footer_x = box.x + box.width / 2
                footer_y = box.y + box.height * 0.92
                
                # Clamp to box bounds
                footer_x = max(box.x + 5, min(box.x + box.width - 5, footer_x))
                footer_y = max(box.y + 5, min(box.y + box.height - 5, footer_y))
                
                try:
                    draw.text(
                        (footer_x, footer_y),
                        wrapped_footer,
                        fill="black", anchor="mm", font=footer_font
                    )
                except Exception:
                    pass

        device_dir = LAYOUTS_DIR / self.device_name
        export_path = device_dir / "layout.png"
        try:
            device_dir.mkdir(parents=True, exist_ok=True)
            export_img.save(export_path)
        except OSError as e:
            messagebox.showerror("Error", f"Failed to export layout:\n{e}")
            return

        messagebox.showinfo("Success", f"Exported to {export_path}")



if __name__ == "__main__":
    root = tk.Tk()
    app = LayoutEditor(root)
    root.mainloop()
