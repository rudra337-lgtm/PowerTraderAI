"""The hub's design tokens and theme (design-system audit, 2026-10-15).

Colours, fonts and the chart palette come from ui_tokens; ui_theme builds every ttk
style from one palette. These tests keep it that way: contrast meets WCAG 2.1, paper
mode re-themes every style, focus is visible, and the UI modules repeat no colour
or font literal.
"""

import os
import re
import sys

import pytest

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import ui_tokens  # noqa: E402

UI_MODULES = (
    "pt_hub.py",
    "pt_paper_mode.py",
    "trading_mode_ui.py",
    "pt_chart_patterns.py",
    "ui_theme.py",
)


def _luminance(colour):
    from matplotlib.colors import to_rgb

    def channel(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = to_rgb(colour)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# --- tokens ---------------------------------------------------------------------------


def test_both_palettes_define_the_same_tokens():
    assert set(ui_tokens.DARK) == set(ui_tokens.PAPER)
    assert ui_tokens.palette(False) is ui_tokens.DARK
    assert ui_tokens.palette(True) is ui_tokens.PAPER


@pytest.mark.parametrize("name", ["DARK", "PAPER"])
def test_text_meets_4_5_to_1_on_every_surface_it_sits_on(name):
    p = getattr(ui_tokens, name)
    for text in ("FG", "MUTED", "ACCENT", "ACCENT2"):
        for surface in ("BG", "BG2", "PANEL", "PANEL2"):
            assert contrast(p[text], p[surface]) >= 4.5, (name, text, surface)
    assert contrast(p["SELECT_FG"], p["SELECT_BG"]) >= 4.5
    for colour in ui_tokens.STATUS.values():  # log lines, training age
        assert contrast(colour, p["BG"]) >= 4.5, (name, colour)
        assert contrast(colour, p["PANEL"]) >= 4.5, (name, colour)


def test_chart_lines_and_tags_meet_their_contrast():
    """Lines and markers need 3:1 on the plot (WCAG 1.4.11); a price tag's text is
    its line colour on the tag box, so it needs 4.5:1 (WCAG 1.4.3)."""
    plot, tag_box = ui_tokens.CHART["plot"], ui_tokens.CHART["label_bg"]
    for key, colour in ui_tokens.CHART_LINES.items():
        assert contrast(colour, plot) >= 3.0, key
        assert contrast(colour, tag_box) >= 4.5, key
    for key, colour in ui_tokens.TRADE_MARKERS.items():
        assert contrast(colour, plot) >= 3.0, key
    assert contrast(ui_tokens.CHART["text"], plot) >= 4.5
    assert contrast(ui_tokens.CHART["text"], tag_box) >= 4.5


def test_the_audit_colours_were_replaced():
    """ASK was purple (1.9:1 on the plot), the neural long levels blue (2.1:1), BID
    teal and SELL green below 4.5:1 as tag text."""
    lines = ui_tokens.CHART_LINES
    assert (lines["ask"], lines["neural_long"], lines["bid"], lines["trail"]) == (
        "#B388FF",
        "#5C9DFF",
        "#26C6DA",
        "#4CAF50",
    )


def test_banner_text_is_readable():
    for bg, fg in ui_tokens.BANNER.values():
        assert contrast(fg, bg) >= 4.5, (bg, fg)


def test_the_type_scale_and_spacing_scale():
    assert ui_tokens.font("caption", "bold") == (ui_tokens.FAMILY, 8, "bold")
    assert ui_tokens.mono("small") == (ui_tokens.MONO_FAMILY, 9)
    sizes = list(ui_tokens.FONT_SIZES.values())
    assert sizes == sorted(sizes)
    space = list(ui_tokens.SPACE.values())
    assert space == sorted(space) and ui_tokens.SPACE["edge"] == 5


@pytest.mark.parametrize("module", UI_MODULES)
def test_ui_modules_repeat_no_colour_or_font_literal(module):
    """Colours and fonts come from ui_tokens; the candle palettes in chart_settings
    are user-selectable data and stay there."""
    with open(os.path.join(APP_DIR, module), encoding="utf-8") as f:
        source = f.read()
    assert not re.findall(r'"#[0-9A-Fa-f]{3,8}"', source)
    assert not re.findall(r'\bcolor="[a-z]+"', source)  # matplotlib colour names
    assert not re.findall(r'font=\("', source)


# --- the theme ------------------------------------------------------------------------


@pytest.fixture
def tk_root():
    import tkinter as tk

    root, error = None, None
    for _ in range(10):  # Tk sometimes fails to read init.tcl on the first try
        try:
            root = tk.Tk()
            break
        except tk.TclError as exc:
            error = exc
    if root is None:
        pytest.skip(f"Tk not available: {error}")
    root.withdraw()
    yield root
    import ui_theme

    ui_theme.apply_theme(
        root, __import__("tkinter.ttk").ttk.Style(root), ui_tokens.DARK
    )
    root.destroy()


EVERY_STYLE = (  # (style, option, palette key) across every style the hub uses
    (".", "background", "BG"),
    ("TFrame", "background", "BG"),
    ("TLabel", "foreground", "FG"),
    ("TLabelframe", "bordercolor", "FRAME_BORDER"),
    ("TLabelframe.Label", "foreground", "ACCENT"),
    ("TSeparator", "background", "BORDER"),
    ("TButton", "background", "BG2"),
    ("TEntry", "fieldbackground", "PANEL"),
    ("TCombobox", "fieldbackground", "PANEL"),
    ("TSpinbox", "fieldbackground", "PANEL"),
    ("TNotebook", "background", "BG"),
    ("TNotebook.Tab", "background", "BG2"),
    ("ChartTab.TButton", "background", "BG2"),
    ("ChartTabSelected.TButton", "background", "PANEL"),
    ("ChartTabSelected.TButton", "foreground", "ACCENT"),
    ("ChartCog.TButton", "background", "BG"),
    ("Treeview", "background", "PANEL"),
    ("Treeview.Heading", "background", "BG2"),
    ("TPanedwindow", "background", "BG"),
    ("Vertical.TScrollbar", "background", "BG2"),
    ("Horizontal.TScrollbar", "troughcolor", "BG"),
)


@pytest.mark.parametrize("name", ["PAPER", "DARK"])
def test_one_palette_styles_every_widget(tk_root, name):
    """Paper mode used to re-apply 10 of these styles, leaving tables, tabs, fields,
    scrollbars and the chart tabs dark on blue frames."""
    from tkinter import ttk

    import pt_paper_mode

    p = getattr(ui_tokens, name)
    style = ttk.Style(tk_root)
    pt_paper_mode.apply_palette_to_style(tk_root, style, p)  # paper mode's entry
    for widget_style, option, key in EVERY_STYLE:
        assert str(style.lookup(widget_style, option)).upper() == p[key].upper(), (
            widget_style,
            option,
        )
    assert str(tk_root.cget("bg")).upper() == p["BG"].upper()


def test_keyboard_focus_is_visible(tk_root):
    import ui_theme
    from tkinter import ttk

    p = ui_tokens.DARK
    style = ttk.Style(tk_root)
    ui_theme.apply_theme(tk_root, style, p)
    # the borderless cog lights up on focus, edges and all
    assert style.lookup("ChartCog.TButton", "background", ["focus"]) == p["PANEL2"]
    assert style.lookup("ChartCog.TButton", "background") == p["BG"]
    for edge in ("bordercolor", "lightcolor", "darkcolor", "focuscolor"):
        assert style.lookup("ChartCog.TButton", edge, ["focus"]) == p["PANEL2"]
    # the selected chart tab has its own states
    assert style.lookup("ChartTabSelected.TButton", "bordercolor", ["focus"]) == (
        p["ACCENT"]
    )
    assert style.lookup("ChartTabSelected.TButton", "background", ["active"]) == (
        p["PANEL2"]
    )
    # entries show focus too
    assert style.lookup("TEntry", "fieldbackground", ["focus"]) == p["PANEL2"]
    assert style.lookup("TEntry", "bordercolor", ["focus"]) == p["ACCENT2"]


def test_fonts_use_the_system_family_and_tooltips_the_theme(tk_root):
    import tkinter.font as tkfont
    from tkinter import ttk

    import pt_hub
    import ui_theme

    p = ui_tokens.PAPER
    ui_theme.apply_theme(tk_root, ttk.Style(tk_root), p)
    family = tkfont.nametofont("TkDefaultFont", root=tk_root).actual("family")
    assert ui_tokens.FAMILY == family  # not Arial, the fallback for "TkDefaultFont"
    widget = ttk.Label(tk_root, text="x")
    widget.pack()
    tip = pt_hub.ToolTip(widget, "explained")
    tip.on_enter()
    label = tip.tooltip_window.winfo_children()[0]
    assert str(label.cget("background")).upper() == p["PANEL2"].upper()
    assert str(label.cget("foreground")).upper() == p["FG"].upper()
    assert tkfont.Font(root=tk_root, font=label.cget("font")).actual("family") == (
        family
    )
    tip.on_leave()
