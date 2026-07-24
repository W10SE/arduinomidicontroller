# Arduino Joystick MIDI Controller

A joystick-and-buttons MIDI controller built on an Arduino, paired with a desktop debug/config app written in Python. The joystick picks a note zone and controls velocity/volume, four buttons trigger notes, and an optional "sweep" mode auto-arpeggiates across the octave while a button is held.

## How it works

**Note selection.** The octave from `BASE_NOTE` to `BASE_NOTE + 11` is split into 12 zones across the joystick's X axis. Moving the stick left/right selects a zone; each of the 4 buttons maps to a fixed offset (0, 1, 2, 3 semitones) from that zone, so a button's note shifts as you move the stick. The Y axis controls velocity/volume, sent as MIDI CC7 while a button is held.

**Deadzone.** A radial deadzone around the joystick's center (512, 512) is ignored, so small physical drift doesn't shift the note zone or emit unwanted CC messages. Its radius is adjustable and persisted.

**Sweep.** A second, independent voice on its own MIDI channel. When armed, it only sounds while at least one button is held, stepping up and down through the octave at a configurable interval (ping-pong pattern). Releasing all buttons stops it immediately; pressing one again restarts the sweep from the bottom.

**Modes.** The firmware boots into MIDI mode, where note on/off/CC events go out as raw MIDI bytes over serial (for use with a MIDI-over-serial bridge like Hairless MIDI). Debug mode instead sends human-readable text lines, which the desktop app parses to drive the on-screen joystick visualization and log. Mode is not persisted or touched by a reset.

**Persistence.** Base note, deadzone radius, sweep on/off, and sweep rate are stored in EEPROM behind a magic-byte check, so settings survive power cycles. A reset command restores factory defaults and re-saves them.

## Serial protocol

Single-line text commands sent to the Arduino at 115200 baud:

| Command | Effect |
|---|---|
| `M` | switch to MIDI mode |
| `D` | switch to debug mode |
| `B:<note>` | set base note (0-127) |
| `Z:<radius>` | set deadzone radius |
| `S:1` / `S:0` | arm / disarm sweep |
| `R:<ms>` | set sweep step interval |
| `X` | reset everything to defaults |

Outgoing lines in debug mode: `POS:x:y:zone:deadzone`, `ON:note:vel:ch<n>`, `OFF:note:ch<n>`, `CC7:val:ch<n>`, plus acks for each of the commands above (`BASE:`, `DEADZONE:`, `SWEEPRATE:`, `SWEEP:`, `RESET:...`, `DEBUG_MODE`). In MIDI mode, note/CC events go out as raw 3-byte MIDI messages instead of text.

## Repo layout

```
Arduino/Controller/Controller.ino   firmware
Debug/
  main.py           entry point
  app.py            main window, wires UI to serial events
  serial_link.py     background-thread serial reader/writer
  protocol.py         line parsing + outgoing command builders
  joystick_pad.py    canvas widget showing stick position, zones, deadzone
  note_utils.py        shared constants, MIDI note number to name
  theme.py / theme.json / THEME_GUIDE.md   GUI look and feel, editable without touching code
```

## Hardware

- Analog joystick: X on A0, Y on A1
- 4 momentary buttons on pins 2-5, wired to ground (internal pull-ups, active low)
- Debounced in software, 15ms

## Desktop app

Built with `customtkinter`. Lets you pick a serial port and connect, switch the Arduino between debug/MIDI mode, drag sliders for base note and deadzone, jump to common octave presets, arm/tune the sweep, and watch joystick position plus zone boundaries live on a canvas. A reset button wipes the Arduino's saved settings back to defaults after a confirmation prompt. A scrolling log at the bottom shows every parsed event, or raw hex bytes while in MIDI mode.

Run with:

```
cd Debug
pip install customtkinter pyserial
python main.py
```

Appearance (colors, fonts, window size, widget dimensions) is pulled from `theme.json` at startup, with built-in fallbacks for anything missing, so restyling doesn't require touching Python. See `THEME_GUIDE.md` for the full key reference.

## Getting MIDI out of it

The Arduino itself only speaks serial. To turn that into a system MIDI device, route the serial port through something like Hairless MIDI + a virtual MIDI port (loopMIDI on Windows, IAC on macOS), with the Arduino in MIDI mode. Debug mode's text protocol is only for the desktop app and won't produce usable MIDI.
