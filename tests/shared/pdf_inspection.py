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


def _decode(stream: bytes) -> str | None:
    """Decode one PDF stream body, or return None when it is not text we can read.

    :param stream: Raw bytes between the ``stream`` and ``endstream`` keywords.
    :return: Decoded content stream, or None for images and other binary payloads.
    """
    body = stream.strip(b"\r\n")
    try:
        return zlib.decompress(base64.a85decode(body, adobe=True)).decode("latin-1")
    except (ValueError, zlib.error, UnicodeDecodeError):
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
