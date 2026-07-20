import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import threading
import queue
import math

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BAUD = 115200
JOY_MAX = 1023
CENTER = 512
ZONES = 12
SWEEP_CHANNEL = 1  # must match firmware's SWEEP_CHANNEL
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def note_name(n):
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Joystick MIDI Debug")
        self.geometry("700x800")
        self.minsize(600, 500)

        self.ser = None
        self.running = False
        self.conn_id = 0
        self.rx_queue = queue.Queue()
        self.deadzone = 40
        self.base_note = 60
        self.last_zone = 0
        self.mode = "DEBUG"
        self.sweep_on = False

        # Log is pinned to the bottom of the actual window FIRST, so it
        # always reserves its space no matter how tall the scrollable
        # content above it grows.
        self.log = ctk.CTkTextbox(self, height=150)
        self.log.pack(side="bottom", padx=10, pady=10, fill="x")

        # Everything else lives in a scrollable frame that takes whatever
        # space remains -- if the window is too short, this scrolls instead
        # of pushing the log off-screen.
        content = ctk.CTkScrollableFrame(self, label_text="")
        content.pack(side="top", fill="both", expand=True, padx=10, pady=(10, 0))

        top = ctk.CTkFrame(content)
        top.pack(fill="x", pady=(0, 10))

        self.port_menu = ctk.CTkComboBox(top, values=[], width=180)
        self.port_menu.pack(side="left", padx=4)
        ctk.CTkButton(top, text="Refresh", width=80, command=self.refresh_ports).pack(side="left", padx=4)
        self.connect_btn = ctk.CTkButton(top, text="Connect", width=100, command=self.toggle_connect)
        self.connect_btn.pack(side="left", padx=4)

        mode_frame = ctk.CTkFrame(content)
        mode_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(mode_frame, text="Debug Mode", command=lambda: self.set_mode("D")).pack(side="left", padx=4)
        ctk.CTkButton(mode_frame, text="MIDI Mode", command=lambda: self.set_mode("M")).pack(side="left", padx=4)
        ctk.CTkButton(mode_frame, text="Reset to Defaults", fg_color="#8c2a2a",
                      hover_color="#a83232", command=self.confirm_reset).pack(side="right", padx=4)

        param_frame = ctk.CTkFrame(content)
        param_frame.pack(fill="x", pady=(0, 10))
        param_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(param_frame, text="Base Note").grid(row=0, column=0, padx=6, pady=6)
        self.base_slider = ctk.CTkSlider(param_frame, from_=0, to=127, number_of_steps=127, command=self.on_base_change)
        self.base_slider.set(60)
        self.base_slider.grid(row=0, column=1, padx=6, sticky="ew")
        self.base_label = ctk.CTkLabel(param_frame, text="60 (C4)", width=70)
        self.base_label.grid(row=0, column=2, padx=6)

        ctk.CTkLabel(param_frame, text="Deadzone").grid(row=1, column=0, padx=6, pady=6)
        self.dz_slider = ctk.CTkSlider(param_frame, from_=0, to=500, number_of_steps=500, command=self.on_dz_change)
        self.dz_slider.set(40)
        self.dz_slider.grid(row=1, column=1, padx=6, sticky="ew")
        self.dz_label = ctk.CTkLabel(param_frame, text="40", width=70)
        self.dz_label.grid(row=1, column=2, padx=6)

        quick_frame = ctk.CTkFrame(content)
        quick_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(quick_frame, text="Quick set:").pack(side="left", padx=6)
        for label, val in [("C2 (36)", 36), ("C3 (48)", 48), ("C4 (60)", 60), ("C5 (72)", 72), ("C6 (84)", 84)]:
            ctk.CTkButton(quick_frame, text=label, width=80, command=lambda v=val: self.jump_base(v)).pack(side="left", padx=4)

        sweep_frame = ctk.CTkFrame(content)
        sweep_frame.pack(fill="x", pady=(0, 10))
        sweep_frame.grid_columnconfigure(2, weight=1)

        self.sweep_btn = ctk.CTkButton(sweep_frame, text="Sweep: OFF", width=120,
                                        fg_color="#555", command=self.toggle_sweep)
        self.sweep_btn.grid(row=0, column=0, padx=6, pady=6)

        ctk.CTkLabel(sweep_frame, text="Speed (ms/step)").grid(row=0, column=1, padx=6)
        self.rate_slider = ctk.CTkSlider(sweep_frame, from_=30, to=600, number_of_steps=570, command=self.on_rate_change)
        self.rate_slider.set(150)
        self.rate_slider.grid(row=0, column=2, padx=6, sticky="ew")
        self.rate_label = ctk.CTkLabel(sweep_frame, text="150", width=50)
        self.rate_label.grid(row=0, column=3, padx=6)

        ctk.CTkLabel(sweep_frame, text="Sweep only sounds while a button is held",
                     font=("", 10), text_color="#888").grid(row=1, column=0, columnspan=4, pady=(0, 4))

        self.canvas = tk.Canvas(content, width=640, height=340, bg="#141414", highlightthickness=0)
        self.canvas.pack(pady=(0, 4))
        self.draw_static()

        self.current_note_label = ctk.CTkLabel(content, text="Target Note (buttons): -- (--)", font=("", 15, "bold"))
        self.current_note_label.pack(pady=(0, 2))
        self.sweep_note_label = ctk.CTkLabel(content, text="Sweep Note: -- (--)", font=("", 15, "bold"), text_color="#ffaa33")
        self.sweep_note_label.pack(pady=(0, 4))
        self.dz_status_label = ctk.CTkLabel(content, text="Ignored range: 512 ± 40 (472 - 552)", font=("", 12))
        self.dz_status_label.pack(pady=(0, 10))

        self.refresh_ports()
        self.update_zone_labels()
        self.update_dz_status()
        self.after(50, self.poll_queue)

    # ---------- serial plumbing ----------
    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_menu.configure(values=ports)
        if ports:
            self.port_menu.set(ports[0])

    def toggle_connect(self):
        if self.ser and self.ser.is_open:
            self.running = False
            self.conn_id += 1
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
            self.connect_btn.configure(text="Connect")
            return

        port = self.port_menu.get()
        if not port:
            return
        try:
            self.ser = serial.Serial(port, BAUD, timeout=0.1)
            try:
                self.ser.reset_input_buffer()
            except Exception:
                pass
            self.running = True
            self.conn_id += 1
            my_id = self.conn_id
            self.connect_btn.configure(text="Disconnect")
            threading.Thread(target=self.read_loop, args=(my_id,), daemon=True).start()
            self.append_log("Connected. Click Debug Mode or MIDI Mode to sync display.")
        except serial.SerialException as e:
            self.append_log(f"ERROR: {e}")

    def set_mode(self, cmd):
        self.mode = "DEBUG" if cmd == "D" else "MIDI"
        self.send(cmd)

    def read_loop(self, my_id):
        while self.running and my_id == self.conn_id and self.ser and self.ser.is_open:
            try:
                if self.mode == "MIDI":
                    n = self.ser.in_waiting or 1
                    data = self.ser.read(n)
                    if data:
                        hex_str = " ".join(f"{b:02X}" for b in data)
                        self.rx_queue.put(f"MIDI: {hex_str}")
                else:
                    line = self.ser.readline().decode(errors="ignore").strip()
                    if line:
                        self.rx_queue.put(line)
            except Exception as e:
                self.rx_queue.put(f"READ ERROR: {e}")
                break

    def poll_queue(self):
        while not self.rx_queue.empty():
            line = self.rx_queue.get()
            try:
                self.handle_line(line)
            except Exception as e:
                self.append_log(f"PARSE ERROR: {e} (line={line!r})")
        self.after(30, self.poll_queue)

    def send(self, line):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write((line + "\n").encode())
            except Exception as e:
                self.append_log(f"WRITE ERROR: {e}")

    # ---------- incoming line handling ----------
    def handle_line(self, line):
        if line.startswith("POS:"):
            _, x, y, zone, dz = line.split(":")
            self.update_pad(int(x), int(y), int(zone), int(dz))

        elif line.startswith("ON:"):
            parts = line.split(":")  # ON:<note>:<vel>:ch<channel>
            if len(parts) == 4 and parts[3].startswith("ch"):
                note = int(parts[1])
                ch = int(parts[3][2:])
                if ch == SWEEP_CHANNEL:
                    self.sweep_note_label.configure(text=f"Sweep Note: {note_name(note)} ({note})")
            self.append_log(line)

        elif line.startswith("OFF:"):
            parts = line.split(":")  # OFF:<note>:ch<channel>
            if len(parts) == 3 and parts[2].startswith("ch"):
                ch = int(parts[2][2:])
                if ch == SWEEP_CHANNEL:
                    self.sweep_note_label.configure(text="Sweep Note: -- (--)")
            self.append_log(line)

        elif line.startswith("BASE:"):
            self.base_note = int(line.split(":")[1])
            self.base_slider.set(self.base_note)
            self.base_label.configure(text=f"{self.base_note} ({note_name(self.base_note)})")
            self.update_zone_labels()
            self.update_current_note_label()
            self.append_log(line)

        elif line.startswith("DEADZONE:"):
            self.deadzone = int(line.split(":")[1])
            self.dz_slider.set(self.deadzone)
            self.dz_label.configure(text=str(self.deadzone))
            self.redraw_deadzone_circle()
            self.update_dz_status()
            self.append_log(line)

        elif line.startswith("SWEEPRATE:"):
            ms = int(line.split(":")[1])
            self.rate_slider.set(ms)
            self.rate_label.configure(text=str(ms))
            self.append_log(line)

        elif line == "SWEEP:1":
            self.sweep_on = True
            self.sweep_btn.configure(text="Sweep: ON", fg_color="#2a8c4a")
            self.append_log(line)

        elif line == "SWEEP:0":
            self.sweep_on = False
            self.sweep_btn.configure(text="Sweep: OFF", fg_color="#555")
            self.sweep_note_label.configure(text="Sweep Note: -- (--)")
            self.append_log(line)

        elif line.startswith("RESET:"):
            _, base, dz, sweep, rate = line.split(":")
            self.apply_reset(int(base), int(dz), sweep == "1", int(rate))
            self.append_log(line)

        else:
            self.append_log(line)

    def append_log(self, text):
        self.log.insert("end", text + "\n")
        self.log.see("end")

    # ---------- param controls ----------
    def on_base_change(self, val):
        self.base_note = int(val)
        self.base_label.configure(text=f"{self.base_note} ({note_name(self.base_note)})")
        self.send(f"B:{self.base_note}")
        self.update_zone_labels()
        self.update_current_note_label()

    def jump_base(self, val):
        self.base_slider.set(val)
        self.on_base_change(val)

    def on_dz_change(self, val):
        self.deadzone = int(val)
        self.dz_label.configure(text=str(self.deadzone))
        self.send(f"Z:{self.deadzone}")
        self.redraw_deadzone_circle()
        self.update_dz_status()

    def toggle_sweep(self):
        target = not self.sweep_on
        self.send("S:1" if target else "S:0")

    def on_rate_change(self, val):
        ms = int(val)
        self.rate_label.configure(text=str(ms))
        self.send(f"R:{ms}")

    def confirm_reset(self):
        if messagebox.askyesno("Reset to Defaults",
                                "This resets Base Note, Deadzone, and Sweep settings on "
                                "the Arduino back to defaults and saves it to EEPROM. Continue?"):
            self.send("X")

    def apply_reset(self, base, dz, sweep, rate):
        self.base_note = base
        self.base_slider.set(base)
        self.base_label.configure(text=f"{base} ({note_name(base)})")

        self.deadzone = dz
        self.dz_slider.set(dz)
        self.dz_label.configure(text=str(dz))
        self.redraw_deadzone_circle()
        self.update_dz_status()

        self.sweep_on = sweep
        if sweep:
            self.sweep_btn.configure(text="Sweep: ON", fg_color="#2a8c4a")
        else:
            self.sweep_btn.configure(text="Sweep: OFF", fg_color="#555")
            self.sweep_note_label.configure(text="Sweep Note: -- (--)")

        self.rate_slider.set(rate)
        self.rate_label.configure(text=str(rate))

        self.update_zone_labels()
        self.update_current_note_label()

    # ---------- visualization ----------
    def draw_static(self):
        pad_size = 320
        self.pad_x0 = (640 - pad_size) / 2
        self.pad_y0 = 10
        self.pad_x1 = self.pad_x0 + pad_size
        self.pad_y1 = self.pad_y0 + pad_size
        self.cx = (self.pad_x0 + self.pad_x1) / 2
        self.cy = (self.pad_y0 + self.pad_y1) / 2
        self.scale = pad_size / JOY_MAX

        self.canvas.create_rectangle(self.pad_x0, self.pad_y0, self.pad_x1, self.pad_y1, outline="#666", width=2)

        zone_w = pad_size / ZONES
        for i in range(1, ZONES):
            x = self.pad_x0 + i * zone_w
            self.canvas.create_line(x, self.pad_y0, x, self.pad_y1, fill="#2a2a2a")

        self.zone_labels = []
        for i in range(ZONES):
            x = self.pad_x0 + i * zone_w + zone_w / 2
            t = self.canvas.create_text(x, self.pad_y0 - 10, text="", fill="#999", font=("", 8))
            self.zone_labels.append(t)

        self.canvas.create_line(self.pad_x0, self.cy, self.pad_x1, self.cy, fill="#a33", dash=(4, 3))
        self.canvas.create_line(self.cx, self.pad_y0, self.cx, self.pad_y1, fill="#a33", dash=(4, 3))

        self.deadzone_circle = self.canvas.create_oval(0, 0, 0, 0, fill="#5a3a1a", outline="#ffaa33", stipple="gray50")

        r = 10
        self.dot = self.canvas.create_oval(self.cx - r, self.cy - r, self.cx + r, self.cy + r,
                                            fill="#ff5a5a", outline="")

        self.canvas.create_text(self.cx, self.pad_y1 + 16, text="Center = 512, 512", fill="#777", font=("", 10))

    def update_zone_labels(self):
        for i, t in enumerate(self.zone_labels):
            self.canvas.itemconfigure(t, text=note_name(self.base_note + i))

    def redraw_deadzone_circle(self):
        r_px = self.deadzone * self.scale
        self.canvas.coords(self.deadzone_circle, self.cx - r_px, self.cy - r_px, self.cx + r_px, self.cy + r_px)

    def update_pad(self, x, y, zone, dz):
        self.last_zone = zone
        self.deadzone = dz
        self.dz_slider.set(dz)
        self.dz_label.configure(text=str(dz))
        self.redraw_deadzone_circle()
        self.update_dz_status()

        px = self.pad_x0 + x * self.scale
        py = self.pad_y1 - y * self.scale
        r = 10
        self.canvas.coords(self.dot, px - r, py - r, px + r, py + r)

        dist = math.hypot(x - CENTER, y - CENTER)
        color = "#888888" if dist < dz else "#ff5a5a"
        self.canvas.itemconfigure(self.dot, fill=color)

        self.update_current_note_label()

    def update_dz_status(self):
        lo = CENTER - self.deadzone
        hi = CENTER + self.deadzone
        self.dz_status_label.configure(text=f"Ignored range: 512 ± {self.deadzone}  ({lo} - {hi})")

    def update_current_note_label(self):
        note = self.base_note + self.last_zone
        self.current_note_label.configure(text=f"Target Note (buttons): {note_name(note)} ({note})")


if __name__ == "__main__":
    App().mainloop()