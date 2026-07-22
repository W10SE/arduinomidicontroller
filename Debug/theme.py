"""
Loads visual settings (colors, fonts, sizes, window options) from theme.json
so the GUI's *look* can be changed by editing that file -- no Python required.

If theme.json is missing, unreadable, or missing individual keys, sensible
built-in defaults are used instead (these match the original hardcoded look),
so the app always starts even with a broken or partial theme file.

See THEME_GUIDE.md for the list of keys and how to edit them.
"""

import json
import os

_THEME_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "theme.json")

# Built-in fallback values. Anything missing from theme.json falls back to these.
DEFAULTS = {
    "appearance_mode": "dark",   # "dark", "light", or "system"
    "color_theme": "blue",       # "blue", "green", "dark-blue", or a path to a ctk theme json

    "window": {
        "title": "Joystick MIDI Debug",
        "geometry": "700x800",
        "min_width": 600,
        "min_height": 500,
    },

    "fonts": {
        "family": "",   # "" = tkinter default system font
        "sizes": {
            "small": 10,
            "normal": 12,
            "large": 15,
        },
    },

    "colors": {
        "danger": "#8c2a2a",
        "danger_hover": "#a83232",
        "toggle_off": "#555555",
        "toggle_on": "#2a8c4a",
        "accent_text": "#ffaa33",
        "hint_text": "#888888",

        "pad_background": "#141414",
        "pad_border": "#666666",
        "pad_zone_lines": "#2a2a2a",
        "pad_zone_labels": "#999999",
        "pad_crosshair": "#aa3333",
        "pad_deadzone_fill": "#5a3a1a",
        "pad_deadzone_outline": "#ffaa33",
        "pad_dot_idle": "#888888",
        "pad_dot_active": "#ff5a5a",
        "pad_center_label": "#777777",
    },

    "dimensions": {
        "pad_width": 640,
        "pad_size": 320,
        "pad_dot_radius": 10,
        "log_height": 150,
        "port_menu_width": 180,
        "button_width": 80,
        "connect_button_width": 100,
        "sweep_button_width": 120,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into a copy of base. override wins on conflicts."""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Theme:
    def __init__(self, path: str = _THEME_PATH):
        self.path = path
        self.data = DEFAULTS
        self.load_error = None
        self.reload()

    def reload(self):
        """(Re)load theme.json from disk, merging over the built-in defaults."""
        merged = DEFAULTS
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    user_theme = json.load(f)
                merged = _deep_merge(DEFAULTS, user_theme)
                self.load_error = None
            except (json.JSONDecodeError, OSError) as e:
                self.load_error = str(e)
                print(f"[theme] Warning: couldn't load {self.path} ({e}); using built-in defaults.")
        self.data = merged

    # ---------- accessors ----------
    def color(self, name: str, fallback: str = "#ffffff") -> str:
        return self.data.get("colors", {}).get(name, fallback)

    def dim(self, name: str, fallback: int = 0):
        return self.data.get("dimensions", {}).get(name, fallback)

    def window(self, name: str, fallback=None):
        return self.data.get("window", {}).get(name, fallback)

    def font(self, size: str = "normal", bold: bool = False):
        """Returns a tkinter font tuple, e.g. ("", 15, "bold") or ("", 12)."""
        family = self.data.get("fonts", {}).get("family", "")
        px = self.data.get("fonts", {}).get("sizes", {}).get(size, 12)
        return (family, px, "bold") if bold else (family, px)

    @property
    def appearance_mode(self) -> str:
        return self.data.get("appearance_mode", "dark")

    @property
    def color_theme(self) -> str:
        return self.data.get("color_theme", "blue")


# Single shared instance -- import `theme` from this module elsewhere.
theme = Theme()
