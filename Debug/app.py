import customtkinter as ctk
from tkinter import messagebox

from note_utils import BAUD, SWEEP_CHANNEL, CENTER, note_name
from serial_link import SerialLink
from joystick_pad import JoystickPad
from protocol import (
    Commands, parse_line,
    PosEvent, NoteOnEvent, NoteOffEvent, CCEvent,
    BaseAck, DeadzoneAck, SweepRateAck, SweepStateAck, ResetAck, DebugModeAck,
    RawLine, MidiBytes,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Joystick MIDI Debug")
        self.geometry("700x800")
        self.minsize(600, 500)

        self.link = SerialLink(BAUD)
        self.base_note = 60
        self.deadzone = 40
        self.last_zone = 0
        self.sweep_on = False

        self._build_ui()
        self.refresh_ports()
        self.after(50, self._poll)

    # ---------- UI construction ----------
    def _build_ui(self):
        # Log pinned to the bottom of the window first, so it always
        # reserves its space no matter how tall the scrollable content above grows.
        self.log = ctk.CTkTextbox(self, height=150)
        self.log.pack(side="bottom", padx=10, pady=10, fill="x")

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
            ctk.CTkButton(quick_frame, text=label, width=80,
                          command=lambda v=val: self.jump_base(v)).pack(side="left", padx=4)

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

        self.pad = JoystickPad(content)
        self.pad.pack(pady=(0, 4))

        self.current_note_label = ctk.CTkLabel(content, text="Target Note (buttons): -- (--)", font=("", 15, "bold"))
        self.current_note_label.pack(pady=(0, 2))
        self.sweep_note_label = ctk.CTkLabel(content, text="Sweep Note: -- (--)",
                                              font=("", 15, "bold"), text_color="#ffaa33")
        self.sweep_note_label.pack(pady=(0, 4))
        self.dz_status_label = ctk.CTkLabel(content, text="Ignored range: 512 ± 40 (472 - 552)", font=("", 12))
        self.dz_status_label.pack(pady=(0, 10))

    # ---------- serial plumbing ----------
    def refresh_ports(self):
        ports = SerialLink.list_ports()
        self.port_menu.configure(values=ports)
        if ports:
            self.port_menu.set(ports[0])

    def toggle_connect(self):
        if self.link.is_connected:
            self.link.disconnect()
            self.connect_btn.configure(text="Connect")
            return

        port = self.port_menu.get()
        if not port:
            return
        err = self.link.connect(port)
        if err:
            self.append_log(f"ERROR: {err}")
        else:
            self.connect_btn.configure(text="Disconnect")
            self.append_log("Connected. Click Debug Mode or MIDI Mode to sync display.")

    def set_mode(self, cmd: str):
        self.link.set_mode("DEBUG" if cmd == "D" else "MIDI")
        self.link.send(Commands.debug_mode() if cmd == "D" else Commands.midi_mode())

    def _poll(self):
        for raw in self.link.poll():
            try:
                self.handle_event(parse_line(raw))
            except Exception as e:
                self.append_log(f"PARSE ERROR: {e} (line={raw!r})")
        self.after(30, self._poll)

    # ---------- event dispatch ----------
    def handle_event(self, event):
        if isinstance(event, PosEvent):
            self.last_zone = event.zone
            self.apply_deadzone(event.deadzone)
            self.pad.update_position(event.x, event.y)
            self.update_current_note_label()

        elif isinstance(event, NoteOnEvent):
            if event.channel == SWEEP_CHANNEL:
                self.sweep_note_label.configure(text=f"Sweep Note: {note_name(event.note)} ({event.note})")
            self.append_log(f"ON:{event.note}:{event.velocity}:ch{event.channel}")

        elif isinstance(event, NoteOffEvent):
            if event.channel == SWEEP_CHANNEL:
                self.sweep_note_label.configure(text="Sweep Note: -- (--)")
            self.append_log(f"OFF:{event.note}:ch{event.channel}")

        elif isinstance(event, CCEvent):
            self.append_log(f"CC7:{event.value}:ch{event.channel}")

        elif isinstance(event, BaseAck):
            self.apply_base(event.base_note)
            self.append_log(f"BASE:{event.base_note}")

        elif isinstance(event, DeadzoneAck):
            self.apply_deadzone(event.deadzone)
            self.append_log(f"DEADZONE:{event.deadzone}")

        elif isinstance(event, SweepRateAck):
            self.rate_slider.set(event.rate_ms)
            self.rate_label.configure(text=str(event.rate_ms))
            self.append_log(f"SWEEPRATE:{event.rate_ms}")

        elif isinstance(event, SweepStateAck):
            self.apply_sweep_state(event.enabled)
            self.append_log(f"SWEEP:{1 if event.enabled else 0}")

        elif isinstance(event, ResetAck):
            self.apply_base(event.base_note)
            self.apply_deadzone(event.deadzone)
            self.apply_sweep_state(event.sweep_enabled)
            self.rate_slider.set(event.rate_ms)
            self.rate_label.configure(text=str(event.rate_ms))
            self.append_log(f"RESET:{event.base_note}:{event.deadzone}:{int(event.sweep_enabled)}:{event.rate_ms}")

        elif isinstance(event, DebugModeAck):
            self.append_log("DEBUG_MODE")

        elif isinstance(event, MidiBytes):
            self.append_log(f"MIDI: {event.hex_str}")

        elif isinstance(event, RawLine):
            self.append_log(event.text)

    def append_log(self, text: str):
        self.log.insert("end", text + "\n")
        self.log.see("end")

    # ---------- param controls ----------
    def on_base_change(self, val):
        note = int(val)
        self.link.send(Commands.set_base(note))
        self.apply_base(note)

    def jump_base(self, val):
        self.base_slider.set(val)
        self.on_base_change(val)

    def on_dz_change(self, val):
        dz = int(val)
        self.link.send(Commands.set_deadzone(dz))
        self.apply_deadzone(dz)

    def toggle_sweep(self):
        self.link.send(Commands.sweep_off() if self.sweep_on else Commands.sweep_on())

    def on_rate_change(self, val):
        ms = int(val)
        self.rate_label.configure(text=str(ms))
        self.link.send(Commands.set_rate(ms))

    def confirm_reset(self):
        if messagebox.askyesno("Reset to Defaults",
                                "This resets Base Note, Deadzone, and Sweep settings on "
                                "the Arduino back to defaults and saves it to EEPROM. Continue?"):
            self.link.send(Commands.reset())

    # ---------- state application helpers ----------
    def apply_base(self, note: int):
        self.base_note = note
        self.base_slider.set(note)
        self.base_label.configure(text=f"{note} ({note_name(note)})")
        self.pad.set_base_note(note)
        self.update_current_note_label()

    def apply_deadzone(self, dz: int):
        self.deadzone = dz
        self.dz_slider.set(dz)
        self.dz_label.configure(text=str(dz))
        self.pad.set_deadzone(dz)
        lo, hi = CENTER - dz, CENTER + dz
        self.dz_status_label.configure(text=f"Ignored range: 512 ± {dz}  ({lo} - {hi})")

    def apply_sweep_state(self, enabled: bool):
        self.sweep_on = enabled
        if enabled:
            self.sweep_btn.configure(text="Sweep: ON", fg_color="#2a8c4a")
        else:
            self.sweep_btn.configure(text="Sweep: OFF", fg_color="#555")
            self.sweep_note_label.configure(text="Sweep Note: -- (--)")

    def update_current_note_label(self):
        note = self.base_note + self.last_zone
        self.current_note_label.configure(text=f"Target Note (buttons): {note_name(note)} ({note})")
