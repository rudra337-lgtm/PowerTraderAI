"""The hub's one ttk theme, built from a palette in ui_tokens.

apply_theme() styles every widget the hub uses from a single palette, so the dark
theme and paper mode's blue one cover the same styles. (Paper mode used to re-apply
only some of them, leaving tables, tabs, fields and scrollbars dark on blue frames.)
The palette is chosen at start-up; a change of trading mode repaints on restart.

ttk styles are shared by every window in the process, so only this module
configures them. A window or tab that wants its own look uses one of the styles
below, and takes any other colour from active_palette() or ui_tokens.

Styles, beyond the plain ttk class names:

    ChartTab.TButton          an unselected chart tab button
    ChartTabSelected.TButton  the selected chart tab button
    ChartCog.TButton          the borderless Chart settings button
    Accent.TButton            the one main action in a panel (Run, Save)
    HiddenTabs.TNotebook      a notebook with no tab strip
    Title.TLabel              a panel title
    Header.TLabel             a field name or a column heading made of labels
    Muted.TLabel              secondary text: hints, units, "not available"
    Good.TLabel               a good status: connected, profit, filled
    Warn.TLabel               a warning: pending, stale, partly available
    Bad.TLabel                a bad status: error, disconnected, loss

Classic Tk widgets (tk.Frame, tk.Label, tk.Entry ...) read their colours from
the option database when created; install_classic_defaults() fills it, so they
match the ttk widgets without colours of their own. theme_figure() gives a
matplotlib figure the chart surfaces from ui_tokens.CHART.

A feature window run on its own builds its root with themed_root(), so it looks
as it does inside the hub.
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
    database, so this runs before the layout is built. A colour passed to the
    widget itself still wins."""
    try:
        root.option_add("*Toplevel.background", p["BG"])
        root.option_add("*Frame.background", p["BG"])
        # matplotlib's canvas sets its own colours; this covers scrolling canvases
        root.option_add("*Canvas.background", p["BG"])
        root.option_add("*Canvas.highlightBackground", p["BG"])

        root.option_add("*Label.background", p["BG"])
        root.option_add("*Label.foreground", p["FG"])

        root.option_add("*Labelframe.background", p["BG"])
        root.option_add("*Labelframe.foreground", p["ACCENT"])

        root.option_add("*Button.background", p["BG2"])
        root.option_add("*Button.foreground", p["FG"])
        root.option_add("*Button.activeBackground", p["PANEL2"])
        root.option_add("*Button.activeForeground", p["ACCENT"])
        root.option_add("*Button.disabledForeground", p["MUTED"])
        root.option_add("*Button.highlightBackground", p["BG"])

        # Flat with a one-pixel outline, like the ttk entries
        root.option_add("*Entry.background", p["PANEL"])
        root.option_add("*Entry.foreground", p["FG"])
        root.option_add("*Entry.insertBackground", p["FG"])
        root.option_add("*Entry.selectBackground", p["SELECT_BG"])
        root.option_add("*Entry.selectForeground", p["SELECT_FG"])
        root.option_add("*Entry.disabledBackground", p["BG2"])
        root.option_add("*Entry.disabledForeground", p["MUTED"])
        root.option_add("*Entry.readonlyBackground", p["PANEL"])
        root.option_add("*Entry.relief", "flat")
        root.option_add("*Entry.highlightThickness", 1)
        root.option_add("*Entry.highlightBackground", p["BORDER"])
        root.option_add("*Entry.highlightColor", p["ACCENT2"])

        for name in ("Checkbutton", "Radiobutton"):
            root.option_add(f"*{name}.background", p["BG"])
            root.option_add(f"*{name}.foreground", p["FG"])
            root.option_add(f"*{name}.selectColor", p["PANEL"])
            root.option_add(f"*{name}.activeBackground", p["PANEL2"])
            root.option_add(f"*{name}.activeForeground", p["FG"])
            root.option_add(f"*{name}.disabledForeground", p["MUTED"])

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


def themed_root() -> tk.Tk:
    """The root window for a feature window run on its own (python x_gui.py),
    themed like the hub's dark mode. A bare tk.Tk() has no option database, so
    classic widgets keep Tk's white and black, and the named label styles fall
    back to plain labels."""
    root = tk.Tk()
    apply_theme(root, ttk.Style(root), ui_tokens.DARK)
    return root


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

    style.configure(
        ".",
        background=p["BG"],
        foreground=p["FG"],
        bordercolor=p["MUTED"],  # tab and heading outlines; near clam's #9E9A91
        troughcolor=p["BG"],
        selectbackground=p["SELECT_BG"],
        selectforeground=p["SELECT_FG"],
    )
    # clam's own state colours are light greys (#EEEBE7 on hover, #DCDAD5 when
    # disabled); every style without a map of its own inherits these instead.
    style.map(
        ".",
        background=[("disabled", p["BG"]), ("active", p["PANEL2"])],
        foreground=[("disabled", p["MUTED"])],
        selectbackground=[("!focus", p["SELECT_BG"])],
        selectforeground=[("!focus", p["SELECT_FG"])],
    )
    for name in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton"):
        style.configure(name, background=p["BG"], foreground=p["FG"])

    # Check and radio boxes: a dark box with an accent mark (clam's is white)
    for name in ("TCheckbutton", "TRadiobutton"):
        style.configure(
            name,
            indicatorbackground=p["PANEL"],
            indicatorforeground=p["ACCENT"],
            upperbordercolor=p["BORDER"],
            lowerbordercolor=p["BORDER"],
        )
        style.map(
            name,
            indicatorbackground=[
                ("disabled", p["BG"]),
                ("pressed", p["PANEL2"]),
                ("active", p["PANEL2"]),
            ],
            indicatorforeground=[("disabled", p["MUTED"])],
        )

    # Label variants (see the module docstring)
    style.configure("Title.TLabel", font=ui_tokens.font("title", "bold"))
    style.configure("Header.TLabel", font=ui_tokens.font("body", "bold"))
    style.configure("Muted.TLabel", foreground=p["MUTED"])
    for name, key in (("Good", "good"), ("Warn", "warn"), ("Bad", "bad")):
        style.configure(f"{name}.TLabel", foreground=ui_tokens.STATUS[key])
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
    # The one main action in a panel: filled with the accent
    style.configure(
        "Accent.TButton",
        background=p["ACCENT"],
        foreground=p["BG"],
        bordercolor=p["ACCENT"],
    )
    style.map(
        "Accent.TButton",
        background=[
            ("disabled", p["BG2"]),
            ("pressed", p["ACCENT2"]),
            ("active", p["ACCENT2"]),
        ],
        foreground=[("disabled", p["MUTED"]), ("!disabled", p["BG"])],
        bordercolor=[("focus", p["FG"]), ("active", p["ACCENT2"])],
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
        fieldbackground=[("disabled", p["BG2"]), ("focus", p["PANEL2"])],
        background=[("disabled", p["BG2"]), ("readonly", p["PANEL"])],
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
        style.map(  # disabled first: a disabled readonly combo must look disabled
            name,
            fieldbackground=[
                ("disabled", p["BG2"]),
                ("readonly", p["PANEL"]),
                ("focus", p["PANEL2"]),
            ],
            foreground=[("disabled", p["MUTED"]), ("readonly", p["FG"])],
            background=[("disabled", p["BG2"]), ("readonly", p["PANEL"])],
            bordercolor=[("focus", p["ACCENT2"])],
            arrowcolor=[("disabled", p["MUTED"])],
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
        bordercolor=[("focus", p["ACCENT2"])],
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


def theme_figure(fig) -> None:
    """Give a matplotlib figure the chart surfaces from ui_tokens.CHART: the same
    dark plot in both modes, light text, quiet spines. Call it after the axes are
    drawn and before canvas.draw(). Text given its own colour keeps it."""
    from matplotlib.colors import to_hex
    from matplotlib import rcParams

    c = ui_tokens.CHART
    default_text = to_hex(rcParams["text.color"])
    fig.patch.set_facecolor(c["figure"])
    for ax in fig.axes:
        ax.set_facecolor(c["plot"])
        ax.tick_params(colors=c["text"])
        for label in (ax.title, ax.xaxis.label, ax.yaxis.label):
            label.set_color(c["text"])
        for text in ax.texts:  # annotations and pie labels
            if to_hex(text.get_color()) == default_text:
                text.set_color(c["text"])
        for spine in ax.spines.values():
            spine.set_color(c["grid"])
        legend = ax.get_legend()
        if legend is not None:
            legend.get_frame().set_facecolor(c["label_bg"])
            legend.get_frame().set_edgecolor(c["grid"])
            for text in legend.get_texts():
                text.set_color(c["text"])
