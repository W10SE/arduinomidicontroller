import customtkinter as ctk
import tkinter as tk
import serial
import serial.tools.list_ports
import threading
import queue

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BAUD = 115200
JOY_MAX = 1023
ZONES = 12

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Joystick MIDI Debug")
        self.geometry("700x680")

        self.ser = None
        self.rx_queue = queue.Queue()
        self.deadzone = 15
        self.last_zone = 0

        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=10, pady=10)

        self.port_menu = ctk.CTkComboBox(top, values=[], width=180)
        self.port_menu.pack(side="left", padx=4)
        ctk.CTkButton(top, text="Refresh", width=80, command=self.refresh_ports).pack(side="left", padx=4)
        self.connect_btn = ctk.CTkButton(top, text="Connect", width=100, command=self.toggle_connect)
        self.connect_btn.pack(side="left", padx=4)

        mode_frame = ctk.CTkFrame(self)
        mode_frame.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(mode_frame, text="Debug Mode", command=lambda: self.send("D")).pack(side="left", padx=4)
        ctk.CTkButton(mode_frame, text="MIDI Mode", command=lambda: self.send("M")).pack(side="left", padx=4)

        param_frame = ctk.CTkFrame(self)
        param_frame.pack(fill="x", padx=10, pady=(0, 10))
        param_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(param_frame, text="Base Note").grid(row=0, column=0, padx=6, pady=6)
        self.base_slider = ctk.CTkSlider(param_frame, from_=0, to=127, number_of_steps=127, command=self.on_base_change)
        self.base_slider.set(60)
        self.base_slider.grid(row=0, column=1, padx=6, sticky="ew")
        self.base_label = ctk.CTkLabel(param_frame, text="60")
        self.base_label.grid(row=0, column=2, padx=6)

        ctk.CTkLabel(param_frame, text="Deadzone").grid(row=1, column=0, padx=6, pady=6)
        self.dz_slider = ctk.CTkSlider(param_frame, from_=0, to=100, number_of_steps=100, command=self.on_dz_change)
        self.dz_slider.set(15)
        self.dz_slider.grid(row=1, column=1, padx=6, sticky="ew")
        self.dz_label = ctk.CTkLabel(param_frame, text="15")
        self.dz_label.grid(row=1, column=2, padx=6)

        self.canvas = tk.Canvas(self, width=660, height=260, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(padx=10, pady=(0, 10))
        self.draw_static()

        self.log = ctk.CTkTextbox(self, width=660, height=160)
        self.log.pack(padx=10, pady=(0, 10), fill="both", expand=True)

        self.refresh_ports()
        self.after(50, self.poll_queue)

    # ---------- serial plumbing ----------
    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_menu.configure(values=ports)
        if ports:
            self.port_menu.set(ports[0])

    def toggle_connect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None
            self.connect_btn.configure(text="Connect")
            return
        port = self.port_menu.get()
        if not port:
            return
        try:
            self.ser = serial.Serial(port, BAUD, timeout=0.1)
            self.connect_btn.configure(text="Disconnect")
            threading.Thread(target=self.read_loop, daemon=True).start()
        except serial.SerialException as e:
            self.append_log(f"ERROR: {e}")

    def read_loop(self):
        while self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
                if line:
                    self.rx_queue.put(line)
            except serial.SerialException:
                break

    def poll_queue(self):
        while not self.rx_queue.empty():
            self.handle_line(self.rx_queue.get())
        self.after(30, self.poll_queue)

    def send(self, line):
        if self.ser and self.ser.is_open:
            self.ser.write((line + "\n").encode())

    # ---------- incoming line handling ----------
    def handle_line(self, line):
        if line.startswith("POS:"):
            _, x, y, zone, dz = line.split(":")
            self.update_pad(int(x), int(y), int(zone), int(dz))
        else:
            self.append_log(line)

    def append_log(self, text):
        self.log.insert("end", text + "\n")
        self.log.see("end")

    # ---------- param controls ----------
    def on_base_change(self, val):
        note = int(val)
        self.base_label.configure(text=str(note))
        self.send(f"B:{note}")

    def on_dz_change(self, val):
        self.deadzone = int(val)
        self.dz_label.configure(text=str(self.deadzone))
        self.send(f"Z:{self.deadzone}")
        self.redraw_deadzone(self.last_zone)

    # ---------- visualization ----------
    def draw_static(self):
        self.pad_x0, self.pad_y0 = 20, 20
        self.pad_x1, self.pad_y1 = 640, 240
        self.canvas.create_rectangle(self.pad_x0, self.pad_y0, self.pad_x1, self.pad_y1, outline="#555", width=2)

        zone_w = (self.pad_x1 - self.pad_x0) / ZONES
        for i in range(1, ZONES):
            x = self.pad_x0 + i * zone_w
            self.canvas.create_line(x, self.pad_y0, x, self.pad_y1, fill="#333")

        self.deadzone_rect = self.canvas.create_rectangle(0, 0, 0, 0, fill="#5a5a1a", outline="", stipple="gray50")
        self.zone_highlight = self.canvas.create_rectangle(0, 0, 0, 0, outline="#5aa9ff", width=2)
        self.dot = self.canvas.create_oval(0, 0, 0, 0, fill="#ff5a5a", outline="")

    def update_pad(self, x, y, zone, dz):
        self.last_zone = zone
        self.deadzone = dz
        self.dz_slider.set(dz)
        self.dz_label.configure(text=str(dz))

        px = self.pad_x0 + (x / JOY_MAX) * (self.pad_x1 - self.pad_x0)
        py = self.pad_y1 - (y / JOY_MAX) * (self.pad_y1 - self.pad_y0)
        r = 8
        self.canvas.coords(self.dot, px - r, py - r, px + r, py + r)
        self.redraw_deadzone(zone)

    def redraw_deadzone(self, zone):
        if zone < 0:
            return
        zone_w = (self.pad_x1 - self.pad_x0) / ZONES
        zx0 = self.pad_x0 + zone * zone_w
        zx1 = zx0 + zone_w
        self.canvas.coords(self.zone_highlight, zx0, self.pad_y0, zx1, self.pad_y1)

        dz_px = (self.deadzone / JOY_MAX) * (self.pad_x1 - self.pad_x0)
        self.canvas.coords(self.deadzone_rect, zx0 - dz_px, self.pad_y0, zx1 + dz_px, self.pad_y1)


if __name__ == "__main__":
    App().mainloop()