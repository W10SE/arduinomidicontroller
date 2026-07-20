import math
import tkinter as tk
from note_utils import JOY_MAX, CENTER, ZONES, note_name


class JoystickPad:
    """Owns the canvas drawing for the joystick position + deadzone visual.

    Doesn't know about serial or the rest of the app -- just renders
    whatever state it's told via set_base_note / set_deadzone / update_position.
    """

    def __init__(self, parent, width=640, pad_size=320):
        self.canvas = tk.Canvas(parent, width=width, height=pad_size + 40,
                                 bg="#141414", highlightthickness=0)
        self.pad_x0 = (width - pad_size) / 2
        self.pad_y0 = 10
        self.pad_x1 = self.pad_x0 + pad_size
        self.pad_y1 = self.pad_y0 + pad_size
        self.cx = (self.pad_x0 + self.pad_x1) / 2
        self.cy = (self.pad_y0 + self.pad_y1) / 2
        self.scale = pad_size / JOY_MAX

        self.base_note = 60
        self.deadzone = 40

        self._draw_static()

    def pack(self, **kwargs):
        self.canvas.pack(**kwargs)

    def _draw_static(self):
        c = self.canvas
        c.create_rectangle(self.pad_x0, self.pad_y0, self.pad_x1, self.pad_y1, outline="#666", width=2)

        zone_w = (self.pad_x1 - self.pad_x0) / ZONES
        for i in range(1, ZONES):
            x = self.pad_x0 + i * zone_w
            c.create_line(x, self.pad_y0, x, self.pad_y1, fill="#2a2a2a")

        self.zone_labels = []
        for i in range(ZONES):
            x = self.pad_x0 + i * zone_w + zone_w / 2
            t = c.create_text(x, self.pad_y0 - 10, text="", fill="#999", font=("", 8))
            self.zone_labels.append(t)

        c.create_line(self.pad_x0, self.cy, self.pad_x1, self.cy, fill="#a33", dash=(4, 3))
        c.create_line(self.cx, self.pad_y0, self.cx, self.pad_y1, fill="#a33", dash=(4, 3))

        self.deadzone_circle = c.create_oval(0, 0, 0, 0, fill="#5a3a1a", outline="#ffaa33", stipple="gray50")

        r = 10
        self.dot = c.create_oval(self.cx - r, self.cy - r, self.cx + r, self.cy + r, fill="#ff5a5a", outline="")

        c.create_text(self.cx, self.pad_y1 + 16, text="Center = 512, 512", fill="#777", font=("", 10))

        self.update_zone_labels()
        self.redraw_deadzone()

    def set_base_note(self, base_note: int):
        self.base_note = base_note
        self.update_zone_labels()

    def update_zone_labels(self):
        for i, t in enumerate(self.zone_labels):
            self.canvas.itemconfigure(t, text=note_name(self.base_note + i))

    def set_deadzone(self, deadzone: int):
        self.deadzone = deadzone
        self.redraw_deadzone()

    def redraw_deadzone(self):
        r_px = self.deadzone * self.scale
        self.canvas.coords(self.deadzone_circle, self.cx - r_px, self.cy - r_px, self.cx + r_px, self.cy + r_px)

    def update_position(self, x: int, y: int):
        px = self.pad_x0 + x * self.scale
        py = self.pad_y1 - y * self.scale
        r = 10
        self.canvas.coords(self.dot, px - r, py - r, px + r, py + r)

        dist = math.hypot(x - CENTER, y - CENTER)
        color = "#888888" if dist < self.deadzone else "#ff5a5a"
        self.canvas.itemconfigure(self.dot, fill=color)
