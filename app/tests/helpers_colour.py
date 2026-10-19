"""WCAG 2.x colour maths shared by the tests: relative luminance and contrast ratio.

Colours are "#RGB" / "#RRGGBB" strings or (r, g, b) tuples of 0..1 floats.
"""

from typing import Sequence, Tuple, Union

Colour = Union[str, Sequence[float]]


def rgb(colour: Colour) -> Tuple[float, float, float]:
    """(r, g, b) in 0..1."""
    if isinstance(colour, str):
        h = colour.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) != 6:
            raise ValueError(f"not a #RGB or #RRGGBB colour: {colour!r}")
        return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    r, g, b = colour
    return (r, g, b)


def linear(c: float) -> float:
    """An sRGB channel (0..1) in linear light (sRGB threshold 0.04045; WCAG 2.0's
    0.03928 sorts every 8-bit value the same way)."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(colour: Colour) -> float:
    r, g, b = (linear(c) for c in rgb(colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: Colour, b: Colour) -> float:
    """The WCAG contrast ratio, 1 to 21."""
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)
