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
can actually draw the string, and otherwise the caller's fallback.

That fallback is Inter, and it is not universal. Measured against the DejaVu Sans it
replaced, character by character rather than by reputation:

- Kept: Czech, Cyrillic, Greek, Turkish, Polish, typographic punctuation.
- Lost: Armenian, Georgian, Hebrew and Arabic, which DejaVu covered completely and
  Inter does not cover at all; and emoji, where DejaVu had part of the range
  (U+1F600 yes, U+1F680 no).
- Unchanged: CJK, which neither font has.

Project names, descriptions and expert names are free text, so a name written in any
of those four scripts now draws as blank boxes where it used to render. That is a real
loss, taken knowingly: the report's two languages are English and Czech, and carrying
a fifth 738 KB face for scripts the interface itself cannot display was judged the
worse trade. If it is revisited, the shape of the fix is a third face passed as the
``fallback`` argument, not a change of default.
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


def font_for(text: str, preferred: str, fallback: str = FONT_SANS) -> str:
    """Return the face to set ``text`` in: the preferred one, or the fallback.

    Playfair Display cannot draw ``Γ``, and the report title is whatever a person
    typed. Asking the face whether it has every glyph is cheap and turns a silently
    blank character into a visible, correct one. Body text and table cells do not
    call this: they are already set in the fallback face itself.

    The fallback is a parameter because weight has to survive it: a bold heading
    falling back to regular body text would swap the typeface and the weight at
    once, which reads as a rendering bug rather than a substitution.

    :param text: The string about to be drawn.
    :param preferred: Face to use when it covers every character.
    :param fallback: Face to use when it does not. Not itself checked -- see the
        module docstring for what Inter does and does not cover.
    :return: ``preferred`` when it can draw the string, otherwise ``fallback``.
    """
    register_fonts()
    coverage = pdfmetrics.getFont(preferred).face.charToGlyph
    return preferred if all(ord(char) in coverage for char in text) else fallback
