from dataclasses import dataclass


@dataclass
class PosEvent:
    x: int
    y: int
    zone: int
    deadzone: int


@dataclass
class NoteOnEvent:
    note: int
    velocity: int
    channel: int


@dataclass
class NoteOffEvent:
    note: int
    channel: int


@dataclass
class CCEvent:
    value: int
    channel: int


@dataclass
class BaseAck:
    base_note: int


@dataclass
class DeadzoneAck:
    deadzone: int


@dataclass
class SweepRateAck:
    rate_ms: int


@dataclass
class SweepStateAck:
    enabled: bool


@dataclass
class ResetAck:
    base_note: int
    deadzone: int
    sweep_enabled: bool
    rate_ms: int


@dataclass
class DebugModeAck:
    pass


@dataclass
class MidiBytes:
    hex_str: str


@dataclass
class RawLine:
    text: str


def parse_line(line: str):
    """Turn one raw line from SerialLink into a typed event object."""
    if line.startswith("MIDI: "):
        return MidiBytes(line[6:])

    if line.startswith("POS:"):
        _, x, y, zone, dz = line.split(":")
        return PosEvent(int(x), int(y), int(zone), int(dz))

    if line.startswith("ON:"):
        parts = line.split(":")  # ON:<note>:<vel>:ch<channel>
        if len(parts) == 4 and parts[3].startswith("ch"):
            return NoteOnEvent(int(parts[1]), int(parts[2]), int(parts[3][2:]))
        return RawLine(line)

    if line.startswith("OFF:"):
        parts = line.split(":")  # OFF:<note>:ch<channel>
        if len(parts) == 3 and parts[2].startswith("ch"):
            return NoteOffEvent(int(parts[1]), int(parts[2][2:]))
        return RawLine(line)

    if line.startswith("CC7:"):
        parts = line.split(":")  # CC7:<value>:ch<channel>
        if len(parts) == 3 and parts[2].startswith("ch"):
            return CCEvent(int(parts[1]), int(parts[2][2:]))
        return RawLine(line)

    if line.startswith("BASE:"):
        return BaseAck(int(line.split(":")[1]))

    if line.startswith("DEADZONE:"):
        return DeadzoneAck(int(line.split(":")[1]))

    if line.startswith("SWEEPRATE:"):
        return SweepRateAck(int(line.split(":")[1]))

    if line == "SWEEP:1":
        return SweepStateAck(True)

    if line == "SWEEP:0":
        return SweepStateAck(False)

    if line.startswith("RESET:"):
        _, base, dz, sweep, rate = line.split(":")
        return ResetAck(int(base), int(dz), sweep == "1", int(rate))

    if line == "DEBUG_MODE":
        return DebugModeAck()

    return RawLine(line)


class Commands:
    """Builders for outgoing text commands sent to the Arduino."""

    @staticmethod
    def debug_mode():
        return "D"

    @staticmethod
    def midi_mode():
        return "M"

    @staticmethod
    def set_base(note: int):
        return f"B:{note}"

    @staticmethod
    def set_deadzone(radius: int):
        return f"Z:{radius}"

    @staticmethod
    def sweep_on():
        return "S:1"

    @staticmethod
    def sweep_off():
        return "S:0"

    @staticmethod
    def set_rate(ms: int):
        return f"R:{ms}"

    @staticmethod
    def reset():
        return "X"
