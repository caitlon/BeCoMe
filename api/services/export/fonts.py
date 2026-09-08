"""Register the interface's typefaces with reportlab, so the report reads as ours.

The web page is set in three faces: Playfair Display for headings, Inter for text,
JetBrains Mono for every number. The report used to be set in DejaVu Sans alone --
chosen for coverage, not for looks -- which is a large part of why an exported PDF
looked like it came from a different product than the page that produced it.

All three are bundled as static TrueType, because reportlab reads only TrueType
with glyf outlines: the ``@fontsource`` packages the frontend installs carry woff
and woff2, which it cannot open. Licences (OFL 1.1) sit beside the files.

One gap decides how they are used. Playfair Display has no ``Γ`` -- it carries Ω
and Δ, but not Gamma -- and the method names its measures ΓΩMean and Γ. reportlab
does not fall back per glyph the way a browser does: a missing character is drawn
as ``.notdef``, silently. So :func:`font_for` picks the preferred face only when it
can actually draw the string, and otherwise returns Inter, which covers everything
the report can contain.
"""

from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_SANS = "Inter-Regular"
FONT_SANS_BOLD = "Inter-SemiBold"
FONT_MONO = "JetBrainsMono-Regular"
FONT_DISPLAY = "PlayfairDisplay"

# api/services/export/fonts.py -> parents[2] is the api/ package root.
_FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"

_FILES = {
    FONT_SANS: "Inter-Regular.ttf",
    FONT_SANS_BOLD: "Inter-SemiBold.ttf",
    FONT_MONO: "JetBrainsMono-Regular.ttf",
    FONT_DISPLAY: "PlayfairDisplay.ttf",
}


def register_fonts() -> None:
    """Register the report's typefaces with reportlab, once.

    Registration is idempotent: repeated report builds reuse the already
    registered faces instead of re-reading the TTF files from disk.
    """
    if FONT_SANS in pdfmetrics.getRegisteredFontNames():
        return
    for name, filename in _FILES.items():
        pdfmetrics.registerFont(TTFont(name, str(_FONT_DIR / filename)))
    pdfmetrics.registerFontFamily(FONT_SANS, normal=FONT_SANS, bold=FONT_SANS_BOLD)


def font_for(text: str, preferred: str) -> str:
    """Return the face to set ``text`` in: the preferred one, or Inter.

    Playfair Display cannot draw ``Γ``, and project names and expert names are
    whatever a person typed. Asking the face whether it has every glyph is cheap
    and turns a silently blank character into a visible, correct one.

    :param text: The string about to be drawn.
    :param preferred: Face to use when it covers every character.
    :return: ``preferred`` when it can draw the string, otherwise :data:`FONT_SANS`.
    """
    register_fonts()
    coverage = pdfmetrics.getFont(preferred).face.charToGlyph
    return preferred if all(ord(char) in coverage for char in text) else FONT_SANS
