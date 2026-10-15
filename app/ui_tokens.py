"""Design tokens for the hub: colour palettes, status, chart and banner colours, the
type scale and the spacing scale.

Every ttk style (ui_theme.apply_theme), chart colour and font in the hub takes its
value from here, so a colour or size is defined once. Pure data: no Tk.

Contrast (WCAG 2.1), checked by app/tests/test_design_tokens.py:
- text colours are at least 4.5:1 on the backgrounds they sit on;
- chart lines and candles are at least 3:1 on the plot, and the price tags' text
  (the line colour on the tag box) at least 4.5:1.
"""

from typing import Dict, Tuple

# --- palettes: the frames, buttons, tables and fields take one of these ---------------

DARK: Dict[str, str] = {
    "BG": "#070B10",
    "BG2": "#0B1220",
    "PANEL": "#0E1626",
    "PANEL2": "#121C2F",
    "BORDER": "#243044",
    "FRAME_BORDER": "#FFFFFF",  # LabelFrame outlines
    "FG": "#C7D1DB",
    "MUTED": "#8B949E",
    "ACCENT": "#00FF66",
    "ACCENT2": "#00E5FF",
    "SELECT_BG": "#17324A",
    "SELECT_FG": "#00FF66",
}

# Paper mode: the same keys in a blue family, with a warm gold accent so "PAPER
# TRADING" stands out.
PAPER: Dict[str, str] = {
    "BG": "#0A1B3A",
    "BG2": "#11264D",
    "PANEL": "#152E5C",
    "PANEL2": "#1B3870",
    "BORDER": "#2E4A82",
    "FRAME_BORDER": "#2E4A82",
    "FG": "#E6EEF8",
    "MUTED": "#9AB0CC",
    "ACCENT": "#FFC400",
    "ACCENT2": "#FFE082",
    "SELECT_BG": "#23488A",
    "SELECT_FG": "#FFC400",
}


def palette(paper_mode: bool) -> Dict[str, str]:
    return PAPER if paper_mode else DARK


# --- status colours (log lines, training age, signal counts) ---------------------------

STATUS: Dict[str, str] = {
    "good": "#4CAF50",
    "warn": "#FFA726",
    "bad": "#FF6B6B",
    "short": "#FF8A65",  # a short signal in the log
}

# --- charts -----------------------------------------------------------------------------

# The chart surfaces stay dark in both modes: the candle and line colours below are
# chosen for this plot colour, and a paper-blue plot would lower their contrast.
CHART: Dict[str, str] = {
    "figure": DARK["BG"],
    "plot": DARK["PANEL"],
    "text": DARK["FG"],
    "grid": DARK["BORDER"],
    "label_bg": DARK["BG2"],  # price tags, pattern labels, hover notes
}

# Level lines and the price tags beside them.
CHART_LINES: Dict[str, str] = {
    "neural_long": "#5C9DFF",
    "neural_short": "#FFA500",
    "ask": "#B388FF",
    "bid": "#26C6DA",
    "avg": "#FFFF00",
    "dca": "#FF0000",
    "trail": "#4CAF50",
}

# Trade markers on the coin and account charts.
TRADE_MARKERS: Dict[str, str] = {
    "buy": "#FF0000",
    "dca": CHART_LINES["ask"],
    "sell": CHART_LINES["trail"],
}

CHART_FONT_PT = 8  # chart labels, tags and notes (matplotlib points)

# --- the trading-mode banner ---------------------------------------------------------

BANNER: Dict[str, Tuple[str, str]] = {  # (background, text)
    "paper": ("#FFC400", "#0A1B3A"),
    "live": ("#B00020", "#FFFFFF"),
    "testnet": ("#E67E00", "#1A1A1A"),  # dark text: white on this orange is 2.9:1
}

# --- type scale ---------------------------------------------------------------------

FONT_SIZES: Dict[str, int] = {
    "micro": 7,
    "caption": 8,
    "small": 9,
    "body": 10,
    "subtitle": 11,
    "title": 12,
    "display": 14,
}
# The system UI family (Segoe UI on Windows). ui_theme.apply_theme reads it from Tk's
# own default font; until then a tuple naming "TkDefaultFont" falls back to Arial.
FAMILY = "TkDefaultFont"
MONO_FAMILY = "Consolas"


def font(role: str, *styles: str) -> Tuple:
    """A Tk font tuple for a role in the type scale, e.g. font("caption", "bold")."""
    return (FAMILY, FONT_SIZES[role], *styles)


def mono(role: str) -> Tuple:
    return (MONO_FAMILY, FONT_SIZES[role])


# --- spacing scale (pixels) ---------------------------------------------------------

SPACE: Dict[str, int] = {
    "hair": 2,
    "xs": 4,
    "edge": 5,  # the chart panel's outer margin (owner, 2026-10-14)
    "sm": 6,
    "md": 8,
    "lg": 10,
    "xl": 12,
    "xxl": 20,
}
