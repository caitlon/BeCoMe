"""Register the bundled DejaVu Sans font with reportlab for Czech glyphs.

reportlab's built-in PDF fonts only cover Latin-1, which misses Czech letters
such as ``č`` or ``ů``. DejaVu Sans carries the full set (plus the Greek method
symbols Γ/Ω/Δ), so reports render correctly in both languages.
"""

from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_NAME = "DejaVuSans"
FONT_NAME_BOLD = "DejaVuSans-Bold"

# api/services/export/fonts.py -> parents[2] is the api/ package root.
_FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"


def register_fonts() -> None:
    """Register DejaVu Sans (regular + bold) with reportlab, once.

    Registration is idempotent: repeated report builds reuse the already
    registered family instead of re-reading the TTF files from disk.
    """
    if FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return
    pdfmetrics.registerFont(TTFont(FONT_NAME, str(_FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_NAME_BOLD, str(_FONT_DIR / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily(FONT_NAME, normal=FONT_NAME, bold=FONT_NAME_BOLD)
