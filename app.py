"""Create a printable DCS HOTAS control map from Make HTML exports."""

import re
import sys
import tkinter as tk
from html.parser import HTMLParser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk


ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "controller-template.png"
SCALE = 2
BOXES = {
    "stick": {
        "JOY_BTN1": (63, 20), "JOY_BTN2": (63, 135),
        "JOY_BTN3": (7, 78), "JOY_BTN4": (119, 78),
        "JOY_BTN5": (2, 298), "JOY_BTN6": (58, 298),
        "JOY_BTN7": (114, 298), "JOY_BTN8": (114, 356),
        "JOY_BTN9": (58, 356), "JOY_BTN10": (2, 356),
        "JOY_BTN11": (339, 298), "JOY_BTN12": (283, 298),
        "JOY_BTN13": (227, 298), "JOY_BTN14": (227, 356),
        "JOY_BTN15": (283, 356), "JOY_BTN16": (339, 356),
        "JOY_BTN_POV1_U": (279, 20), "JOY_BTN_POV1_D": (279, 135),
        "JOY_BTN_POV1_L": (223, 78), "JOY_BTN_POV1_R": (335, 78),
    },
    "throttle": {
        "JOY_BTN1": (553, 512), "JOY_BTN2": (670, 42),
        "JOY_BTN3": (609, 4), "JOY_BTN4": (469, 69),
        "JOY_BTN5": (469, 127), "JOY_BTN7": (835, 424),
        "JOY_BTN8": (891, 482), "JOY_BTN9": (835, 540),
        "JOY_BTN10": (779, 482), "JOY_BTN11": (356, 424),
        "JOY_BTN12": (412, 482), "JOY_BTN13": (356, 540),
        "JOY_BTN14": (300, 482), "JOY_BTN_POV1_UL": (654, 276),
        "JOY_BTN_POV1_U": (710, 276), "JOY_BTN_POV1_UR": (766, 276),
        "JOY_BTN_POV1_L": (654, 334), "JOY_BTN_POV1_R": (766, 334),
        "JOY_BTN_POV1_DL": (654, 392), "JOY_BTN_POV1_D": (710, 392),
        "JOY_BTN_POV1_DR": (766, 392),
    },
}


class TableParser(HTMLParser):
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


def parse_profile(path):
    """Return a device and its assignments, or None for another device."""
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252")
    parser = TableParser()
    parser.feed(text)
    name = parser.heading.strip()
    identity = (name + " " + path.name).lower()
    if "twcs" in identity:
        device = "throttle"
    elif "t.16000m" in identity or "t16000m" in identity:
        device = "stick"
    else:
        return None
    entries = []
    for combo, command, category, *_ in parser.rows:
        for binding in combo.split(";"):
            parts = re.split(r"\s+-\s+", binding.strip())
            if parts and parts[-1]:
                entries.append({"key": parts[-1], "modifiers": parts[:-1],
                                "command": command, "category": category})
    if not entries:
        raise ValueError(f"{path.name}: no assigned controls found in the DCS HTML table.")
    return device, {"name": name or path.name, "filename": path.name, "entries": entries}


def font(size, bold=False):
    names = (["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold
             else ["arial.ttf", "DejaVuSans.ttf"])
    for name in names:
        try:
            return ImageFont.truetype(name, size * SCALE)
        except OSError:
            continue
    return ImageFont.load_default()


def key_name(key):
    return (key.replace("JOY_BTN_POV1_", "POV ").replace("JOY_BTN", "Button ")
            .replace("JOY_SLIDER", "Slider ").replace("JOY_", ""))


def modifier_name(key):
    return "M" if key == "JOY_BTN2" else key_name(key)


def short_name(command):
    replacements = [
        ("Weapons Trigger Switch - ", "Trigger: "),
        ("Weapons Action Switch - ", "Weapon: "),
        ("Force Trim/Hold Mode Switch - ", "Trim: "),
        ("FCR Scan Size Switch - ", "Scan size: "),
        ("FCR Mode Switch - ", "FCR: "),
        ("FCR Scan Switch - ", "Scan: "),
        ("Sight Select Switch - ", "Sight: "),
        ("PTT/RTS Switch - ", "PTT: "),
        ("Symbology Select Switch - ", "Symbology: "),
        ("NVS Select Switch - ", "NVS: "),
        ("Boresight/Polarity Switch - ", "Polarity: "),
        ("TAIL WHEEL Pushbutton - ", "Tail wheel: "),
        ("George AI - Multifunctional Input (Center)", "George: center"),
        ("Flare Dispense Button - Depress", "Flare"),
        ("Trim - RESET to default", "Trim reset"),
        ("Missile Advance Switch - Depress", "Missile advance"),
        ("CUED Search Switch - Depress", "Cued search"),
        ("Wheel Brake - ON/OFF", "Wheel brake"),
        ("HOCAS Cursor Controller - ", "Cursor "),
        ("Zoom View", "Zoom"),
        (" (call radio menu)", ""),
        (" (Continuous)", " cont."),
        (" (Single)", " single"),
    ]
    for old, new in replacements:
        command = command.replace(old, new)
    return re.sub(r"/(Up|Down|Left|Right|Center|Depress)\b", "", command)


def wrap(draw, text, font_obj, width):
    lines, line = [], ""
    for word in text.split():
        candidate = (line + " " + word).strip()
        if draw.textlength(candidate, font=font_obj) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
        line = word
        while draw.textlength(line, font=font_obj) > width and len(line) > 1:
            cut = len(line)
            while cut > 1 and draw.textlength(line[:cut] + "-", font=font_obj) > width:
                cut -= 1
            lines.append(line[:cut] + "-")
            line = line[cut:]
    if line:
        lines.append(line)
    return lines


def tile_color(device, key):
    if "POV" in key:
        return "#baff85" if device == "stick" else "#d585ee"
    number = int(key.removeprefix("JOY_BTN"))
    if device == "stick":
        if number <= 4:
            return "#fff1a0"
        return "#ff858b" if number <= 7 or 11 <= number <= 13 else "#83c8f2"
    return {1: "#ffb28a", 2: "#ff6b73", 3: "#4df500",
            4: "#83c8f2", 5: "#83c8f2"}.get(number, "#81ff83" if number >= 11 else "#83ffff")


def draw_tile(draw, pos, title, labels, color):
    x, y = (v * SCALE for v in pos)
    width, height = 56 * SCALE, 57 * SCALE
    draw.rectangle((x, y, x + width - 1, y + height - 1), fill=color, outline="#333333", width=SCALE)
    title_font, body_font = font(8, True), font(6)
    draw.text((x + width / 2, y + 3 * SCALE), title, fill="black", font=title_font, anchor="mt")
    lines = []
    for label in labels:
        lines.extend(wrap(draw, label, body_font, width - 5 * SCALE))
    if len(lines) > 7:
        lines = lines[:6] + ["..."]
    for i, line in enumerate(lines):
        draw.text((x + width / 2, y + (14 + i * 6) * SCALE), line,
                  fill="black", font=body_font, anchor="mt")


def legend(profile):
    if not profile:
        return ["No profile loaded."]
    lines = []
    for entry in sorted(profile["entries"], key=lambda e: (e["key"], len(e["modifiers"]))):
        parts = [modifier_name(m) for m in entry["modifiers"]] + [key_name(entry["key"])]
        lines.append(" + ".join(parts) + ": " + entry["command"])
    return lines


def render(profiles, template=TEMPLATE):
    with Image.open(template) as img:
        if img.size != (960, 601):
            raise ValueError("The controller template must be 960 × 601 pixels.")
        base = img.convert("RGB").resize((960 * SCALE, 601 * SCALE), Image.Resampling.LANCZOS)
    measure = ImageDraw.Draw(base)
    legend_font = font(11)
    columns = []
    for device in ("stick", "throttle"):
        column = []
        for line in legend(profiles.get(device)):
            column.extend(wrap(measure, line, legend_font, 445 * SCALE))
        columns.append(column)
    height = 655 + max(map(len, columns)) * 16 + 24
    result = Image.new("RGB", (960 * SCALE, height * SCALE), "white")
    result.paste(base, (0, 0))
    draw = ImageDraw.Draw(result)
    draw.rectangle((351*SCALE, 248*SCALE, 643*SCALE, 353*SCALE), fill="#c0c0c0")
    draw.rectangle((0, 20*SCALE, 62*SCALE, 75*SCALE), fill="#c0c0c0")
    draw.text((497*SCALE, 266*SCALE), "DCS CONTROL MAP", fill="black", font=font(18, True), anchor="mt")
    draw.text((497*SCALE, 291*SCALE), "M = TWCS Button 2", fill="black", font=font(11), anchor="mt")
    for device, mapping in BOXES.items():
        entries = profiles.get(device, {}).get("entries", [])
        for key, pos in mapping.items():
            labels = []
            if device == "throttle" and key == "JOY_BTN2":
                labels.append("Modifier (M)")
            for entry in entries:
                if entry["key"] == key:
                    prefix = "+".join(map(modifier_name, entry["modifiers"]))
                    labels.append((prefix + ": " if prefix else "") + short_name(entry["command"]))
            title = "POV " + key.rsplit("_", 1)[-1] if "POV" in key else key_name(key)
            draw_tile(draw, pos, title, labels, tile_color(device, key))
    entries = profiles.get("throttle", {}).get("entries", [])
    for pos, title, keys in [
        ((502, 4), "MINISTICK", {"JOY_X", "JOY_Y"}),
        ((558, 168), "ROCKER RZ", {"JOY_RZ"}),
        ((682, 110), "ANTENNA", {"JOY_SLIDER1"}),
    ]:
        labels = [key_name(e["key"]) + ": " + short_name(e["command"])
                  for e in entries if e["key"] in keys]
        draw_tile(draw, pos, title, labels, "#ffb28a")
    for x, title, lines in [(15, "T.16000M — all assigned controls", columns[0]),
                            (490, "TWCS — all assigned controls", columns[1])]:
        draw.text((x*SCALE, 615*SCALE), title, fill="black", font=font(15, True))
        for i, line in enumerate(lines):
            draw.text((x*SCALE, (643+i*16)*SCALE), line, fill="black", font=legend_font)
    return result


class App:
    def __init__(self, root):
        self.root = root
        self.profiles = {}
        self.result = None
        root.title("DCS HOTAS control map")
        root.geometry("1000x800")
        bar = ttk.Frame(root, padding=8)
        bar.pack(fill="x")
        ttk.Button(bar, text="Open DCS HTML files", command=self.open_files).pack(side="left")
        self.save_button = ttk.Button(bar, text="Save PNG", command=self.save, state="disabled")
        self.save_button.pack(side="left", padx=8)
        ttk.Button(bar, text="Clear", command=self.clear).pack(side="left")
        self.status = tk.StringVar(value="Select T.16000M and TWCS Make HTML exports.")
        ttk.Label(root, textvariable=self.status, wraplength=950, padding=(8, 0)).pack(fill="x")
        ttk.Label(root, text="M = TWCS Button 2. Full commands and axes are listed beneath the diagram.",
                  padding=(8, 4)).pack(fill="x")
        frame = ttk.Frame(root)
        frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(frame, background="#555555", highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.update_image()

    def update_image(self):
        self.result = render(self.profiles)
        preview = self.result.resize((960, self.result.height // SCALE), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(preview)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.canvas.configure(scrollregion=(0, 0, preview.width, preview.height))
        self.save_button.configure(state="normal" if self.profiles else "disabled")

    def open_files(self):
        paths = filedialog.askopenfilenames(title="Select DCS Make HTML exports",
                                            filetypes=[("HTML files", "*.html *.htm"), ("All files", "*.*")])
        errors, skipped, loaded = [], [], []
        for filename in paths:
            try:
                profile = parse_profile(Path(filename))
                if profile is None:
                    skipped.append(Path(filename).name)
                    continue
                device, data = profile
                self.profiles[device] = data
                loaded.append(f"{data['name']}: {len(data['entries'])} bindings")
            except (OSError, UnicodeError, ValueError) as exc:
                errors.append(str(exc))
        if not paths:
            return
        status = loaded or ["No supported profiles loaded in this selection."]
        if skipped:
            status.append("Skipped other devices: " + ", ".join(skipped))
        self.status.set("\n".join(status))
        self.update_image()
        if errors:
            messagebox.showerror("Could not read profile", "\n".join(errors))

    def clear(self):
        self.profiles.clear()
        self.status.set("Select T.16000M and TWCS Make HTML exports.")
        self.update_image()

    def save(self):
        filename = filedialog.asksaveasfilename(title="Save control map", defaultextension=".png",
                                                initialfile="dcs-hotas-controls.png",
                                                filetypes=[("PNG image", "*.png")])
        if filename:
            try:
                self.result.save(filename, format="PNG")
                self.status.set("Saved: " + filename)
            except OSError as exc:
                messagebox.showerror("Could not save image", str(exc))


def main():
    root = tk.Tk()
    try:
        App(root)
    except (OSError, ValueError) as exc:
        messagebox.showerror("Could not load controller template", str(exc))
        root.destroy()
        return 1
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
