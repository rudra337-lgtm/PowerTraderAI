"""The hub's one ttk theme, built from a palette in ui_tokens.

apply_theme() styles every widget the hub uses from a single palette, so the dark
theme and paper mode's blue one cover the same styles. (Paper mode used to re-apply
only some of them, leaving tables, tabs, fields and scrollbars dark on blue frames.)
"""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from typing import Dict

import ui_tokens

_active: Dict[str, str] = ui_tokens.DARK


def active_palette() -> Dict[str, str]:
    """The palette the theme was last built from (for widgets drawn later, such as
    tooltips)."""
    return _active


def _use_system_family(root: tk.Misc) -> None:
    """Point the type scale at the system UI family (Segoe UI on Windows), the one
    widgets without an explicit font already use. A tuple naming "TkDefaultFont"
    is not a family, and Tk falls back to Arial for it."""
    try:
        ui_tokens.FAMILY = tkfont.nametofont("TkDefaultFont", root=root).actual(
            "family"
        )
    except Exception:
        pass


def install_classic_defaults(root: tk.Misc, p: Dict[str, str]) -> None:
    """Classic Tk widgets read their colours at creation time from the option
    database, so this runs before the layout is built."""
    try:
        root.option_add("*Text.background", p["PANEL"])
        root.option_add("*Text.foreground", p["FG"])
        root.option_add("*Text.insertBackground", p["FG"])
        root.option_add("*Text.selectBackground", p["SELECT_BG"])
        root.option_add("*Text.selectForeground", p["SELECT_FG"])

        root.option_add("*Listbox.background", p["PANEL"])
        root.option_add("*Listbox.foreground", p["FG"])
        root.option_add("*Listbox.selectBackground", p["SELECT_BG"])
        root.option_add("*Listbox.selectForeground", p["SELECT_FG"])

        root.option_add("*Menu.background", p["BG2"])
        root.option_add("*Menu.foreground", p["FG"])
        root.option_add("*Menu.activeBackground", p["SELECT_BG"])
        root.option_add("*Menu.activeForeground", p["SELECT_FG"])
    except tk.TclError:
        pass


def apply_theme(root: tk.Misc, style: ttk.Style, p: Dict[str, str]) -> None:
    """Style every widget the hub uses from palette ``p``."""
    global _active
    _active = p
    _use_system_family(root)
    try:
        root.configure(bg=p["BG"])
    except tk.TclError:
        pass
    install_classic_defaults(root, p)

    # 'clam' honours colour settings; Windows' 'vista' theme ignores many of them
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=p["BG"], foreground=p["FG"])
    for name in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton"):
        style.configure(name, background=p["BG"], foreground=p["FG"])
    style.configure(
        "TLabelframe",
        background=p["BG"],
        foreground=p["FG"],
        bordercolor=p["FRAME_BORDER"],
    )
    style.configure("TLabelframe.Label", background=p["BG"], foreground=p["ACCENT"])
    style.configure("TSeparator", background=p["BORDER"])

    # Buttons
    style.configure(
        "TButton",
        background=p["BG2"],
        foreground=p["FG"],
        bordercolor=p["BORDER"],
        focusthickness=1,
        focuscolor=p["ACCENT"],
        padding=(3, 2),
    )
    style.map(
        "TButton",
        background=[
            ("active", p["PANEL2"]),
            ("pressed", p["PANEL"]),
            ("disabled", p["BG2"]),
        ],
        foreground=[("active", p["ACCENT"]), ("disabled", p["MUTED"])],
        bordercolor=[("active", p["ACCENT2"]), ("focus", p["ACCENT"])],
    )

    # Entries, combos, spinboxes
    style.configure(
        "TEntry",
        fieldbackground=p["PANEL"],
        foreground=p["FG"],
        bordercolor=p["BORDER"],
        insertcolor=p["FG"],
    )
    style.map(
        "TEntry",
        fieldbackground=[("focus", p["PANEL2"])],
        bordercolor=[("focus", p["ACCENT2"])],
        foreground=[("disabled", p["MUTED"])],
    )
    for name in ("TCombobox", "TSpinbox"):
        style.configure(
            name,
            fieldbackground=p["PANEL"],
            background=p["PANEL"],
            foreground=p["FG"],
            bordercolor=p["BORDER"],
            arrowcolor=p["ACCENT"],
            insertcolor=p["FG"],
        )
        style.map(
            name,
            fieldbackground=[("readonly", p["PANEL"]), ("focus", p["PANEL2"])],
            foreground=[("readonly", p["FG"])],
            background=[("readonly", p["PANEL"])],
        )

    # Notebooks
    style.configure("TNotebook", background=p["BG"], bordercolor=p["BORDER"])
    style.configure(
        "TNotebook.Tab", background=p["BG2"], foreground=p["FG"], padding=(10, 6)
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", p["PANEL"]), ("active", p["PANEL2"])],
        foreground=[("selected", p["ACCENT"]), ("active", p["ACCENT2"])],
    )
    # A notebook with no tab strip (the chart pages draw their own tab row)
    style.configure("HiddenTabs.TNotebook", tabmargins=0)
    style.layout(
        "HiddenTabs.TNotebook",
        [
            (
                "Notebook.padding",
                {
                    "sticky": "nswe",
                    "children": [("Notebook.client", {"sticky": "nswe"})],
                },
            )
        ],
    )

    # Chart tab buttons, sized to their text: 10 px from the text to each edge
    # (owner, 2026-10-14) is 7 px of padding plus the theme's 3 px of border and
    # focus ring. Width 0 drops the theme's 11-character minimum.
    style.configure(
        "ChartTab.TButton",
        background=p["BG2"],
        foreground=p["FG"],
        bordercolor=p["BORDER"],
        padding=(7, 7),
        width=0,
    )
    style.map(
        "ChartTab.TButton",
        background=[("active", p["PANEL2"]), ("pressed", p["PANEL"])],
        foreground=[("active", p["ACCENT2"])],
        bordercolor=[("active", p["ACCENT2"]), ("focus", p["ACCENT"])],
    )
    style.configure(
        "ChartTabSelected.TButton",
        background=p["PANEL"],
        foreground=p["ACCENT"],
        bordercolor=p["ACCENT2"],
        padding=(7, 7),
        width=0,
    )
    style.map(  # its own states: hover lights it, focus shows on its border
        "ChartTabSelected.TButton",
        background=[("pressed", p["PANEL"]), ("active", p["PANEL2"])],
        foreground=[("active", p["ACCENT"])],
        bordercolor=[("focus", p["ACCENT"]), ("active", p["ACCENT2"])],
    )

    # The Chart settings cog shows no border (owner, 2026-10-14): its edges take its
    # background, the frame colour. Hover and keyboard focus light the whole button.
    edges = ("background", "bordercolor", "lightcolor", "darkcolor", "focuscolor")
    style.configure(
        "ChartCog.TButton",
        foreground=p["FG"],
        padding=(7, 7),
        width=0,
        **{edge: p["BG"] for edge in edges},
    )
    lit = [("pressed", p["PANEL"]), ("active", p["PANEL2"]), ("focus", p["PANEL2"])]
    style.map(
        "ChartCog.TButton",
        foreground=[("active", p["ACCENT2"]), ("focus", p["ACCENT2"])],
        **{edge: lit for edge in edges},
    )

    # Tables
    style.configure(
        "Treeview",
        background=p["PANEL"],
        fieldbackground=p["PANEL"],
        foreground=p["FG"],
        bordercolor=p["BORDER"],
        lightcolor=p["BORDER"],
        darkcolor=p["BORDER"],
    )
    style.map(
        "Treeview",
        background=[("selected", p["SELECT_BG"])],
        foreground=[("selected", p["SELECT_FG"])],
    )
    style.configure(
        "Treeview.Heading", background=p["BG2"], foreground=p["ACCENT"], relief="flat"
    )
    style.map(
        "Treeview.Heading",
        background=[("active", p["PANEL2"])],
        foreground=[("active", p["ACCENT2"])],
    )

    # Panes and scrollbars
    style.configure("TPanedwindow", background=p["BG"])
    for name in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(
            name,
            background=p["BG2"],
            troughcolor=p["BG"],
            bordercolor=p["BORDER"],
            arrowcolor=p["ACCENT"],
        )
