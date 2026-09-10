"""Read colours back out of a rendered PDF, without rasterizing it.

Comparing rendered pages as images was rejected: this repository's visual
baselines are already pinned to amd64 and cannot be regenerated on an arm64 Mac,
and PDF rasterization varies with the renderer more than browser painting does.
Reading the content stream needs no extra dependency and no platform baseline.
"""

import base64
import re
import zlib

from reportlab.lib import colors

_STREAM = re.compile(rb"stream(.*?)endstream", re.S)
_FILL_COLOR = re.compile(r"([\d.]+) ([\d.]+) ([\d.]+) rg")
_BASE_FONT = re.compile(rb"/BaseFont\s*/([A-Za-z0-9+\-]+)")
_BF_CHAR = re.compile(r"<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]{4,})>")


def _decode(stream: bytes) -> str | None:
    """Decode one PDF stream body, or return None when it is not text we can read.

    :param stream: Raw bytes between the ``stream`` and ``endstream`` keywords.
    :return: Decoded content stream, or None for images and other binary payloads.
    """
    body = stream.strip(b"\r\n")
    # Page content arrives as ASCII85 over Flate; the ToUnicode maps are Flate
    # alone. Trying only the first combination returned nothing for the maps, which
    # read as the Greek and Czech characters being missing from the document.
    # The second branch also "succeeds" on the embedded TrueType binaries, since
    # latin-1 decoding never raises. Harmless for both callers -- one gates on
    # "beginbfchar", the other on fill-colour operators, and neither appears in a
    # font file -- but that is a property of these bytes, not of this code.
    for decode in (
        lambda raw: zlib.decompress(base64.a85decode(raw, adobe=True)),
        zlib.decompress,
    ):
        try:
            return decode(body).decode("latin-1")
        except (ValueError, zlib.error, UnicodeDecodeError):
            continue
    return None


def fill_colours(pdf: bytes) -> set[tuple[float, float, float]]:
    """Return every fill colour the document sets, as rounded RGB fractions.

    :param pdf: Rendered PDF bytes.
    :return: Set of ``(red, green, blue)`` triples, each rounded to six decimals.
    :raises AssertionError: If not one stream could be decoded. Negative assertions
        ("this colour is absent") would otherwise pass on an empty set, which is the
        failure this whole helper exists to avoid.
    """
    found: set[tuple[float, float, float]] = set()
    decoded_any = False
    for stream in _STREAM.findall(pdf):
        content = _decode(stream)
        if content is None:
            continue
        decoded_any = True
        for match in _FILL_COLOR.finditer(content):
            found.add(tuple(round(float(channel), 6) for channel in match.groups()))
    if not decoded_any:
        raise AssertionError(
            "no PDF content stream could be decoded, so no colour was read. "
            "Callers assert that a colour is absent, and an empty result would "
            "satisfy them without proving anything."
        )
    return found


def text_characters(pdf: bytes) -> set[str]:
    """Return every character the document's text layer can be read back as.

    This is what distinguishes a glyph that was drawn from one that silently became
    ``.notdef``: reportlab writes a ToUnicode CMap for each embedded subset, and a
    character that never made it into a subset has no entry to be found here.

    One trap, met while writing this: each subset numbers its glyphs from zero, so
    the codes collide across fonts. Merging the CMaps into one code-keyed mapping
    loses everything the later fonts contribute -- which looked exactly like the
    Greek and Czech letters being absent. Only the characters are collected.

    :param pdf: Rendered PDF bytes.
    :return: Set of characters present in the document's ToUnicode maps.
    """
    found: set[str] = set()
    for stream in _STREAM.findall(pdf):
        content = _decode(stream)
        if content is None or "beginbfchar" not in content:
            continue
        for _, target in _BF_CHAR.findall(content):
            # The whole value, not its first four digits. reportlab writes each
            # target as a single scalar ("%04X"), so above U+FFFF it is five or six
            # digits and truncating produced a different, perfectly valid-looking
            # character: <1F12F> came back as U+1F12. Both bundled sans faces carry
            # astral codepoints (31 in Inter, 46 in JetBrains Mono), so a future
            # test on emoji coverage would have got a confident wrong answer rather
            # than an honest failure.
            char = chr(int(target, 16))
            if char != "\x00":
                found.add(char)
    return found


def embedded_fonts(pdf: bytes) -> set[str]:
    """Return the family names of every font embedded in the document.

    Subset names carry a six-letter prefix (``ABCDEF+Inter``); it is stripped here,
    because it changes between renders and says nothing about which face was used.

    :param pdf: Rendered PDF bytes.
    :return: Set of base font names, without subset prefixes.
    """
    found = {match.decode("latin-1") for match in _BASE_FONT.findall(pdf)}
    return {name.split("+", 1)[-1] for name in found}


def as_fractions(colour: colors.Color) -> tuple[float, float, float]:
    """Express a reportlab colour the way it appears in a content stream.

    :param colour: Colour taken from a report palette.
    :return: ``(red, green, blue)`` triple rounded to six decimals.
    """
    return (round(colour.red, 6), round(colour.green, 6), round(colour.blue, 6))
