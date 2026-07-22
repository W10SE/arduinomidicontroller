# Restyling the app (no code required)

All colors, fonts, and sizes now in **`theme.json`**. Edit that file, save
it, and restart the app.This was made so that you never to have to ope `app.py` 
or `joystick_pad.py` to change how it looks.

If `theme.json` is missing, has a typo, or is missing some keys, the app
falls back to its built-in defaults for whatever is missing/broken and still
starts up normally (it prints a warning in the console if the file itself
couldn't be parsed).

## How to change something

1. Open `theme.json` in any text editor.
2. Change a value — e.g. change `"danger": "#8c2a2a"` to `"danger": "#c0392b"`.
3. Save the file.
4. Restart the app (`python main.py`). Themes are loaded once at startup.

You only need to include the keys you want to change — any key you leave out
keeps its default value. For example, this is a perfectly valid `theme.json`
that only recolors the joystick pad background and leaves everything else as
default:

```json
{
  "colors": {
    "pad_background": "#001a33"
  }
}
```

## Reference: all keys in theme.json

### `appearance_mode`
`"dark"`, `"light"`, or `"system"` — controls customtkinter's overall
dark/light widget rendering.

### `color_theme`
`"blue"`, `"green"`, or `"dark-blue"` — one of customtkinter's built-in
accent-color palettes (affects default button/slider colors that aren't
otherwise overridden below). You can also point this at the path of a custom
[CustomTkinter theme JSON file](https://customtkinter.tomschimansky.com/documentation/color)
for deeper control over every built-in widget.

### `window`
| Key | Meaning |
|---|---|
| `title` | Window title bar text |
| `geometry` | Initial window size, `"WIDTHxHEIGHT"` |
| `min_width` / `min_height` | Minimum resizable window size |

### `fonts`
| Key | Meaning |
|---|---|
| `family` | Font family name, e.g. `"Helvetica"`. Leave as `""` to use the system default. |
| `sizes.small` | Used for hint text, joystick zone labels |
| `sizes.normal` | Used for the deadzone status line |
| `sizes.large` | Used for the big "Target Note" / "Sweep Note" labels (bold) |

### `colors`
| Key | Where it's used |
|---|---|
| `danger` / `danger_hover` | "Reset to Defaults" button (normal / hover) |
| `toggle_off` | Sweep button when sweep is OFF |
| `toggle_on` | Sweep button when sweep is ON |
| `accent_text` | "Sweep Note" label text |
| `hint_text` | Small gray hint text under the sweep controls |
| `pad_background` | Joystick pad canvas background |
| `pad_border` | Joystick pad outer border |
| `pad_zone_lines` | Vertical zone divider lines on the pad |
| `pad_zone_labels` | Note-name labels above each zone |
| `pad_crosshair` | Center crosshair lines |
| `pad_deadzone_fill` / `pad_deadzone_outline` | The shaded deadzone circle |
| `pad_dot_idle` | Position dot color while inside the deadzone |
| `pad_dot_active` | Position dot color while outside the deadzone |
| `pad_center_label` | "Center = 512, 512" caption text |

### `dimensions`
| Key | Meaning |
|---|---|
| `pad_width` / `pad_size` | Joystick canvas width and square pad size (px) |
| `pad_dot_radius` | Radius of the position dot (px) |
| `log_height` | Height of the log textbox at the bottom (px) |
| `port_menu_width` | Width of the serial port dropdown (px) |
| `button_width` | Width of Refresh / quick-set note buttons (px) |
| `connect_button_width` | Width of the Connect/Disconnect button (px) |
| `sweep_button_width` | Width of the Sweep on/off button (px) |

## Example: a light "midnight purple" alternate theme

Save this as `theme.json` (replacing the existing one, or back it up first)
to try a very different look with no code changes:

```json
{
  "appearance_mode": "dark",
  "color_theme": "dark-blue",
  "colors": {
    "danger": "#7a2048",
    "danger_hover": "#9c2c5e",
    "toggle_off": "#3a3a5c",
    "toggle_on": "#6a3fa0",
    "accent_text": "#c78bff",
    "hint_text": "#9a90b8",
    "pad_background": "#12081f",
    "pad_border": "#4a3a6a",
    "pad_zone_lines": "#241a38",
    "pad_zone_labels": "#8a7ab0",
    "pad_crosshair": "#8a3fd0",
    "pad_deadzone_fill": "#301a4a",
    "pad_deadzone_outline": "#c78bff",
    "pad_dot_idle": "#7a6a9a",
    "pad_dot_active": "#e05fff",
    "pad_center_label": "#8a7ab0"
  }
}
```

## Want a totally different layout, not just colors?

This system covers colors, fonts, and sizes — the things you'd normally want
to tweak repeatedly. Structural changes (adding new buttons, rearranging
sections) still require editing `app.py`.
