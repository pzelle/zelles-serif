#!/usr/bin/env python3
"""Build the site's custom heading serif.

The face is a display cut of Gentium Book Plus (SIL International, OFL 1.1):
a flared serif with calligraphic and inscriptional roots, warm and open. The
cut widens the source by a few percent, which opens the counters and gives the
capitals the generous inscriptional proportion the design wants at heading
sizes, closes the bowls the source leaves hanging, then normalizes the
vertical metrics so every browser draws the same line box.

Gentium reserves the names "Gentium" and "SIL", so the OFL requires the
modified font to carry a different name. FAMILY below is that name; change it
and rebuild to rename the whole family.

Two sets of files come out of a build:

  ./            the web cut, Latin and symbols, as WOFF2 (plus bold TTF for OG renderers)
  ./full/       every glyph in the source, as TTF, for desktop use

Usage:
    pip install "fonttools[woff]"
    python3 scripts/build-font.py
"""

from __future__ import annotations

import shutil
import sys
import urllib.request
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

# --- What the family is called -------------------------------------------- #

FAMILY = "Zelles Serif"
VERSION = "1.000"
DESIGNER = "Pete Zelles"
DESIGNER_URL = "https://petezelles.com"
SLUG = "zelles-serif"

# How much wider than the source, as a ratio. 1.0 leaves the source untouched;
# 1.03 is the display cut. Past about 1.08 the verticals grow heavy enough to
# flatten the stroke contrast.
WIDTH = 1.03

# --- Where the source comes from ------------------------------------------ #

UPSTREAM = "https://raw.githubusercontent.com/google/fonts/main/ofl/gentiumbookplus"
SOURCE_COPYRIGHT = (
    "Copyright (c) 2003-2022 SIL International (http://www.sil.org/), "
    'with Reserved Font Names "Gentium" and "SIL".'
)

# style key -> (source file, subfamily, weight class, is bold, is italic)
STYLES = {
    "regular": ("GentiumBookPlus-Regular.ttf", "Regular", 400, False, False),
    "italic": ("GentiumBookPlus-Italic.ttf", "Italic", 400, False, True),
    "bold": ("GentiumBookPlus-Bold.ttf", "Bold", 700, True, False),
    "bolditalic": ("GentiumBookPlus-BoldItalic.ttf", "Bold Italic", 700, True, True),
}

# Everything the site can put on a page: the Latin alphabets with their
# diacritics, plus punctuation, currency, fractions, arrows, math and the
# ligatures. Greek, Cyrillic and the phonetic alphabet stay in the full build,
# which keeps the web files roughly a third of the size.
WEB_RANGES = [
    (0x0000, 0x024F),  # Basic Latin, Latin-1, Latin Extended-A and -B
    (0x02B0, 0x02FF),  # spacing modifiers
    (0x0300, 0x036F),  # combining diacritics
    (0x0370, 0x03FF),  # Greek, which carries pi, ohm and the rest of math
    (0x1E00, 0x1EFF),  # Latin Extended Additional
    (0x2000, 0x206F),  # general punctuation
    (0x2070, 0x209F),  # superscripts and subscripts
    (0x20A0, 0x20BF),  # currency
    (0x2100, 0x214F),  # letterlike symbols
    (0x2150, 0x218F),  # number forms and fractions
    (0x2190, 0x21FF),  # arrows
    (0x2200, 0x22FF),  # mathematical operators
    (0x2300, 0x23FF),  # miscellaneous technical
    (0x25A0, 0x25FF),  # geometric shapes
    (0x2600, 0x26FF),  # miscellaneous symbols
    (0x2700, 0x27BF),  # dingbats
    (0xFB00, 0xFB4F),  # alphabetic presentation forms (fi, fl, ffi ...)
    (0xFEFF, 0xFEFF),
    (0xFFFD, 0xFFFD),
]

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".font-cache"
WEB_OUT = ROOT
FULL_OUT = WEB_OUT / "full"


def fetch_sources() -> None:
    """Download the upstream font files once and keep them in .font-cache."""
    CACHE.mkdir(exist_ok=True)
    wanted = [src for src, *_ in STYLES.values()] + ["OFL.txt"]
    for name in wanted:
        target = CACHE / name
        if target.exists():
            continue
        print(f"  fetching {name}")
        with urllib.request.urlopen(f"{UPSTREAM}/{name}") as response:
            target.write_bytes(response.read())


def widen(font: TTFont, ratio: float) -> None:
    """Scale the design horizontally, leaving the vertical proportions alone.

    Outlines, advance widths, composite offsets and every horizontal value in
    the kerning and mark-attachment tables all move together, so the spacing
    stays true to the source. TrueType hinting is dropped, since the
    instructions describe stem positions that no longer hold; browsers hint
    these sizes themselves.
    """
    glyf, hmtx = font["glyf"], font["hmtx"]
    for name in font.getGlyphOrder():
        glyph = glyf[name]
        glyph.expand(glyf)
        if glyph.isComposite():
            for component in glyph.components:
                if hasattr(component, "x"):
                    component.x = round(component.x * ratio)
        elif getattr(glyph, "numberOfContours", 0) > 0:
            glyph.coordinates = type(glyph.coordinates)(
                [(round(x * ratio), y) for x, y in glyph.coordinates]
            )
            glyph.program.fromBytecode(b"")
        advance, lsb = hmtx[name]
        hmtx[name] = (round(advance * ratio), round(lsb * ratio))

    if "GPOS" in font:
        _scale_gpos_x(font["GPOS"].table, ratio)

    for table in ("prep", "fpgm", "cvt ", "hdmx", "LTSH", "VDMX"):
        if table in font:
            del font[table]


def _scale_gpos_x(table, ratio: float) -> None:
    """Walk GPOS and scale every horizontal placement, advance and anchor."""
    seen: set[int] = set()

    def walk(node) -> None:
        if node is None or id(node) in seen:
            return
        seen.add(id(node))
        if node.__class__.__name__ == "Anchor":
            if getattr(node, "XCoordinate", None):
                node.XCoordinate = round(node.XCoordinate * ratio)
            return
        for attr in ("XAdvance", "XPlacement"):
            value = getattr(node, attr, None)
            if value:
                setattr(node, attr, round(value * ratio))
        for value in getattr(node, "__dict__", {}).values():
            if hasattr(value, "__dict__"):
                walk(value)
            elif isinstance(value, list):
                for item in value:
                    if hasattr(item, "__dict__"):
                        walk(item)

    walk(table)


def _contours(glyph, glyf):
    """Split a glyph's points into one list per contour."""
    coords, ends, flags = glyph.getCoordinates(glyf)
    out, start = [], 0
    for end in ends:
        out.append(
            [(coords[i][0], coords[i][1], bool(flags[i] & 1)) for i in range(start, end + 1)]
        )
        start = end + 1
    return out


def _flatten(contour, steps=12):
    """Approximate a TrueType contour as a polyline.

    TrueType leaves the on-curve point between two consecutive off-curve
    points implied, so those are restored first, then each quadratic is
    sampled.
    """
    points, count = [], len(contour)
    for i, (x, y, on) in enumerate(contour):
        points.append((x, y, on))
        next_x, next_y, next_on = contour[(i + 1) % count]
        if not on and not next_on:
            points.append(((x + next_x) / 2, (y + next_y) / 2, True))

    first = next(i for i, point in enumerate(points) if point[2])
    points = points[first:] + points[:first]

    poly, i = [(points[0][0], points[0][1])], 0
    while i < len(points):
        current, control = points[i], points[(i + 1) % len(points)]
        if control[2]:
            poly.append((control[0], control[1]))
            i += 1
            continue
        end = points[(i + 2) % len(points)]
        for step in range(1, steps + 1):
            t = step / steps
            u = 1 - t
            poly.append(
                (
                    u * u * current[0] + 2 * u * t * control[0] + t * t * end[0],
                    u * u * current[1] + 2 * u * t * control[1] + t * t * end[1],
                )
            )
        i += 2
    return poly


def _span_at(poly, height):
    """Leftmost and rightmost x where a closed polyline crosses a height."""
    crossings = []
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 <= height < y2) or (y2 <= height < y1):
            crossings.append(x1 + (x2 - x1) * (height - y1) / (y2 - y1))
    return (min(crossings), max(crossings)) if crossings else None


# The glyphs the source draws as a bowl beside a stem, leaving the bowl's
# lower terminal hanging just short. Everything else with a bowl — B, R, b, d,
# p, q, thorn and the rest — already runs its bowl into the stem.
OPEN_BOWLS = ("P", "Thorn", "uni01A4", "p.sc", "thorn.sc", "uni01A5.sc")


def connect_bowls(font: TTFont) -> None:
    """Close every bowl the source leaves hanging."""
    for name in OPEN_BOWLS:
        if name in font.getGlyphOrder():
            connect_bowl(font, name)


def connect_bowl(font: TTFont, name: str, overlap: float = 0.30) -> None:
    """Run one glyph's bowl terminal into its stem.

    These are drawn as two contours, a stem and a bowl, with the bowl's lower
    terminal stopping just short of the stem. This stretches that terminal
    toward the stem until it sits well inside it, easing the shift back to zero
    further along the curve so the arm extends rather than the whole bowl
    sliding over. Both contours wind the same way, so the overlap fills solid
    and the buried terminal never shows.

    Everything is measured off the outline, so one pass fits all four styles,
    the capitals, the small capitals and both the upright and the slanted stem.
    """
    glyf = font["glyf"]
    glyph = glyf[name]
    glyph.expand(glyf)
    if glyph.isComposite() or glyph.numberOfContours != 2:
        return
    upem = font["head"].unitsPerEm
    contours = _contours(glyph, glyf)

    # The stem reaches the baseline; the bowl is the other contour.
    stem_index = min(
        range(len(contours)), key=lambda c: min(point[1] for point in contours[c])
    )
    bowl_index = 1 - stem_index
    bowl = contours[bowl_index]
    bowl_top = max(point[1] for point in bowl)
    stem_outline = _flatten(contours[stem_index])

    # The terminal is the bowl's lower half reaching back toward the stem, so
    # it is the leftmost point that still sits clear of the stem's right edge.
    # Measuring against the stem at each point's own height keeps a descending
    # hook, which is drawn as part of the bowl, from being read as the terminal.
    reaching = []
    for x, y, _on in bowl:
        if y >= 0.65 * bowl_top:
            continue
        span = _span_at(stem_outline, y)
        if span and x > span[1]:
            reaching.append((x, y))
    if not reaching:
        return
    terminal_x = min(x for x, _y in reaching)
    tip = [(x, y) for x, y in reaching if x < terminal_x + 0.02 * upem]
    terminal_y = sum(y for _x, y in tip) / len(tip)

    span = _span_at(stem_outline, terminal_y)
    if span is None:
        raise ValueError(f"could not measure the {name} stem at the terminal height")
    stem_left, stem_right = span
    delta = (stem_right - overlap * (stem_right - stem_left)) - terminal_x
    if delta >= 0:
        return  # already connected

    full, zero = terminal_x + 0.025 * upem, terminal_x + 0.075 * upem
    coords, _ends, _flags = glyph.getCoordinates(glyf)
    start = sum(len(contour) for contour in contours[:bowl_index])
    for i, (x, y, _on) in enumerate(bowl):
        if y >= 0.68 * bowl_top or x >= zero or x < stem_left:
            continue
        weight = 1.0 if x <= full else (zero - x) / (zero - full)
        coords[start + i] = (round(x + delta * weight), y)
    glyph.coordinates = coords
    glyph.recalcBounds(glyf)


def set_vertical_metrics(font: TTFont) -> None:
    """Make every browser agree on the line box.

    The three metric tables disagree in most fonts, which is why the same text
    sits at different heights in different browsers. Point them all at the
    typographic values and set the flag that tells Windows to prefer them.
    """
    os2, hhea = font["OS/2"], font["hhea"]
    ascender, descender = os2.sTypoAscender, os2.sTypoDescender

    os2.sTypoLineGap = 0
    hhea.ascent, hhea.descent, hhea.lineGap = ascender, descender, 0
    os2.usWinAscent, os2.usWinDescent = ascender, abs(descender)
    os2.fsSelection |= 1 << 7  # USE_TYPO_METRICS


def rename(font: TTFont, subfamily: str, weight: int, bold: bool, italic: bool) -> None:
    """Replace the name table, as the OFL requires of a modified font."""
    full = FAMILY if subfamily == "Regular" else f"{FAMILY} {subfamily}"
    postscript = f"{FAMILY.replace(' ', '')}-{subfamily.replace(' ', '')}"

    # These four are the classic regular/italic/bold/bold-italic set, so they
    # share one family name and font menus link the styles to each other.
    names = {
        0: f"{SOURCE_COPYRIGHT} Modified as {FAMILY}.",
        1: FAMILY,
        2: subfamily,
        3: f"{DESIGNER}: {full}: {VERSION}",
        4: full,
        5: f"Version {VERSION}",
        6: postscript,
        8: DESIGNER,
        9: "SIL International",
        11: DESIGNER_URL,
        12: "https://software.sil.org/gentium/",
        13: (
            "This Font Software is licensed under the SIL Open Font License, "
            "Version 1.1. See OFL.txt."
        ),
        14: "https://openfontlicense.org",
        16: FAMILY,
        17: subfamily,
    }

    name_table = font["name"]
    name_table.names = []
    for name_id, value in names.items():
        name_table.setName(value, name_id, 3, 1, 0x409)  # Windows, Unicode BMP
        name_table.setName(value, name_id, 1, 0, 0)  # Mac, Roman

    os2 = font["OS/2"]
    os2.usWeightClass = weight
    os2.achVendID = "PZEL"

    # fsSelection and macStyle have to agree or font menus misreport the style.
    os2.fsSelection &= ~((1 << 0) | (1 << 5) | (1 << 6))  # italic, bold, regular
    macstyle = font["head"].macStyle & ~0b11
    if italic:
        os2.fsSelection |= 1 << 0
        macstyle |= 0b10
    if bold:
        os2.fsSelection |= 1 << 5
        macstyle |= 0b01
    if not bold and not italic:
        os2.fsSelection |= 1 << 6
    font["head"].macStyle = macstyle

    for table in ("STAT", "fvar", "MVAR", "DSIG"):
        if table in font:
            del font[table]


def web_subset(font: TTFont) -> None:
    """Trim to the Latin and symbol ranges the site can actually render."""
    unicodes = [cp for start, end in WEB_RANGES for cp in range(start, end + 1)]
    options = subset.Options()
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.notdef_outline = True
    options.recalc_bounds = True
    options.drop_tables = []
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=unicodes)
    subsetter.subset(font)


def write(font: TTFont, path: Path, flavors: tuple[str | None, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for flavor in flavors:
        font.flavor = flavor
        font.save(path.with_suffix(f".{flavor or 'ttf'}"))
    font.flavor = None


def build() -> None:
    print(f"Building {FAMILY} {VERSION} at {WIDTH:.0%} width\n")
    fetch_sources()

    for out in (WEB_OUT, FULL_OUT):
        out.mkdir(parents=True, exist_ok=True)
    shutil.copy(CACHE / "OFL.txt", WEB_OUT / "OFL.txt")

    for key, (source, subfamily, weight, bold, italic) in STYLES.items():
        print(f"  {FAMILY} {subfamily}")
        font = TTFont(CACHE / source)
        connect_bowls(font)
        if WIDTH != 1.0:
            widen(font, WIDTH)
        set_vertical_metrics(font)
        rename(font, subfamily, weight, bold, italic)

        font.save(full_tmp := CACHE / f"{SLUG}-{key}.built.ttf")

        # The full family ships as TTF, which is what desktop apps install.
        write(TTFont(full_tmp), FULL_OUT / f"{SLUG}-{key}.ttf", (None,))

        # The web cut ships as WOFF2, which every browser that can run the site
        # reads. Bold also ships as TTF, for the share-image renderer.
        web = TTFont(full_tmp)
        web_subset(web)
        flavors = ("woff2", None) if key == "bold" else ("woff2",)
        write(web, WEB_OUT / f"{SLUG}-{key}.ttf", flavors)
        full_tmp.unlink()

    report()


def report() -> None:
    print("\n  file                                      glyphs    size")
    total = 0
    for out in (WEB_OUT, FULL_OUT):
        for path in sorted(out.glob(f"{SLUG}-*")):
            font = TTFont(path)
            size = path.stat().st_size / 1024
            total += size
            rel = str(path.relative_to(ROOT))
            print(f"  {rel:<42}{len(font.getBestCmap()):>6}{size:>7.0f}K")
    print(f"  {'':<42}{'total':>6}{total:>7.0f}K")


if __name__ == "__main__":
    try:
        build()
    except Exception as error:  # noqa: BLE001 - a build failure should be readable
        sys.exit(f"font build failed: {error}")
