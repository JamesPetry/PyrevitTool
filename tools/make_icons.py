# -*- coding: utf-8 -*-
"""Regenerate the pushbutton icons.

Run from the repo root with Pillow installed:

    python tools/make_icons.py

pyRevit reads `icon.png` beside each `script.py` and scales it down to roughly
32x32 on the ribbon, so these are drawn at 96x96 with deliberately heavy
strokes -- thin outlines disappear entirely at ribbon size.

This is a maintenance script, not part of the extension. pyRevit ignores the
`tools` folder because it carries no bundle postfix.
"""

import os

from PIL import Image, ImageDraw

SIZE = 96
SHEET = (250, 250, 252, 255)
EDGE = (90, 98, 112, 255)
RULE = (176, 184, 196, 255)

BLUE = (32, 112, 214, 255)
AMBER = (198, 124, 16, 255)
TEAL = (24, 132, 132, 255)
RED = (196, 48, 48, 255)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PANELS = os.path.join(ROOT, "HDR.tab")


def canvas():
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def sheet(draw, box=(14, 8, 66, 76), rules=3):
    """The document every button acts on: a page with a folded corner."""
    left, top, right, bottom = box
    fold = 16
    draw.polygon(
        [(left, top), (right - fold, top), (right, top + fold),
         (right, bottom), (left, bottom)],
        fill=SHEET, outline=EDGE,
    )
    # The fold itself, so the page reads as paper and not as a plain rectangle.
    draw.line([(right - fold, top), (right - fold, top + fold),
               (right, top + fold)], fill=EDGE, width=3)
    for index in range(rules):
        y = top + 30 + index * 11
        if y < bottom - 8:
            draw.line([(left + 9, y), (right - 11, y)], fill=RULE, width=3)


def arrow(draw, tip, direction, colour, length=26, width=9, head=11):
    """A blunt, high-contrast arrow. Anything finer vanishes at ribbon size."""
    x, y = tip
    if direction == "down":
        draw.line([(x, y - length), (x, y - head + 2)], fill=colour,
                  width=width)
        draw.polygon([(x - head, y - head), (x + head, y - head), (x, y)],
                     fill=colour)
    elif direction == "right":
        draw.line([(x - length, y), (x - head + 2, y)], fill=colour,
                  width=width)
        draw.polygon([(x - head, y - head), (x - head, y + head), (x, y)],
                     fill=colour)


def export_issue():
    """Sheet leaving the model: page plus an arrow driving down and out."""
    image, draw = canvas()
    sheet(draw)
    arrow(draw, (68, 88), "down", BLUE)
    draw.line([(46, 86), (90, 86)], fill=BLUE, width=7)
    return image


def archive_superseded():
    """Sheet dropping into a box: the archive lid is the wide bar."""
    image, draw = canvas()
    sheet(draw, box=(14, 4, 66, 52), rules=1)
    arrow(draw, (44, 74), "down", AMBER, length=22)
    # Archive bin below, deliberately open at the top.
    draw.rectangle([(10, 78), (86, 92)], fill=AMBER)
    draw.line([(14, 78), (14, 66)], fill=AMBER, width=6)
    draw.line([(82, 78), (82, 66)], fill=AMBER, width=6)
    return image


def probe_export():
    """Read-only diagnostic: a magnifier held over the page."""
    image, draw = canvas()
    sheet(draw, box=(10, 6, 62, 74), rules=2)
    draw.ellipse([(40, 36), (86, 82)], outline=TEAL, width=9)
    draw.line([(78, 74), (92, 88)], fill=TEAL, width=10)
    return image


def seed_revisions():
    """The one button that writes to the model -- warning triangle, not a page
    glyph, so it never reads as a safe sibling of the others."""
    image, draw = canvas()
    sheet(draw, box=(8, 6, 56, 66), rules=2)
    draw.polygon([(58, 42), (92, 92), (24, 92)], fill=RED)
    draw.line([(58, 58), (58, 74)], fill=(255, 255, 255, 255), width=7)
    draw.ellipse([(54, 80), (62, 88)], fill=(255, 255, 255, 255))
    return image


ICONS = {
    os.path.join("Issue.panel", "Export Issue.pushbutton"): export_issue,
    os.path.join("Issue.panel", "Archive Superseded.pushbutton"):
        archive_superseded,
    os.path.join("Dev.panel", "Probe Export.pushbutton"): probe_export,
    os.path.join("Dev.panel", "Seed Revisions.pushbutton"): seed_revisions,
}


def main():
    for bundle, builder in ICONS.items():
        target = os.path.join(PANELS, bundle, "icon.png")
        builder().save(target)
        print("wrote {0}".format(target))


if __name__ == "__main__":
    main()
