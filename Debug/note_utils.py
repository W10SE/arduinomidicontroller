BAUD = 115200
JOY_MAX = 1023
CENTER = 512
ZONES = 12
SWEEP_CHANNEL = 1  # must match firmware's SWEEP_CHANNEL

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_name(n: int) -> str:
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"
