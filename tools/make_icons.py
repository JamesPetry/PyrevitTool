# -*- coding: utf-8 -*-
"""Regenerate the pushbutton icons, light and dark.

Run from the repo root with Pillow installed:

    python tools/make_icons.py

pyRevit reads `icon.png` beside each `script.py` and scales it to roughly 32x32
on the ribbon, so everything here is drawn 4x oversize and resampled down --
drawing straight at 96x96 gives visibly stepped diagonals on the magnifier and
the arrowheads.

Revit 2024 introduced a dark ribbon, and pyRevit picks up `icon.dark.png` when
it is in use. Only the page and the halo change between themes; the accent
discs are mid-tones that hold up on either background, so a button keeps the
same colour identity in both.

THE SYSTEM
    Every icon is the same page in the same position, with a different accent
    disc badged over its bottom-right corner. The page says "this acts on
    sheets"; the badge says which action, and carries the only colour. Keeping
    the page identical across all four is what makes them read as one set --
    the first version drew it at four different sizes and looked like four
    unrelated icons.

    Silhouettes are deliberately distinct, because colour alone is not a
    reliable difference: arrow-into-tray, carton, magnifier, exclamation.

This is a maintenance script, not part of the extension. pyRevit ignores the
`tools` folder because it carries no bundle postfix.
"""

import os

from PIL import Image, ImageDraw

SIZE = 96
SS = 4                      # supersampling factor
PAD = 6                     # safe margin, keeps strokes off the crop edge

# --- palette ---------------------------------------------------------------
# Accents are shared by both themes. They sit mid-tone on purpose: dark enough
# to hold a white glyph, light enough not to disappear on a dark ribbon.
BLUE = (31, 111, 235, 255)      # export -- files leaving the model
AMBER = (183, 121, 31, 255)     # archive -- files being moved aside
TEAL = (15, 118, 110, 255)      # probe -- read-only diagnostic
RED = (192, 57, 43, 255)        # seed -- the one button that writes to a model

GLYPH = (255, 255, 255, 255)

LIGHT = {
    "paper": (255, 255, 255, 255),
    "edge": (75, 85, 99, 255),
    "rule": (156, 163, 175, 255),
    "halo": (243, 244, 246, 255),   # ~ the light ribbon background
}
DARK = {
    "paper": (201, 207, 216, 255),  # dimmed, or it glares on a dark ribbon
    "edge": (75, 85, 99, 255),
    "rule": (139, 147, 158, 255),
    "halo": (43, 43, 43, 255),      # ~ the dark ribbon background
}

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PANELS = os.path.join(ROOT, "HDR.tab")

# --- geometry, in final 96px units -----------------------------------------
PAGE = (10, 8, 62, 80)      # identical in all four icons
FOLD = 15
BADGE = (66, 66)            # centre
RADIUS = 25


def _s(value):
    """Scale a coordinate into supersampled space."""
    if isinstance(value, (tuple, list)):
        return tuple(_s(v) for v in value)
    return value * SS


class Icon(object):
    """A canvas that takes coordinates in 96px units and draws them 4x up."""

    def __init__(self, theme):
        self.theme = theme
        self.image = Image.new("RGBA", (SIZE * SS, SIZE * SS), (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.image)

    def line(self, points, fill, width):
        self.draw.line([_s(p) for p in points], fill=fill, width=width * SS)

    def polygon(self, points, fill, outline=None, width=1):
        self.draw.polygon([_s(p) for p in points], fill=fill, outline=outline,
                          width=width * SS)

    def rect(self, box, fill, radius=0):
        self.draw.rounded_rectangle(_s(box), radius=radius * SS, fill=fill)

    def disc(self, centre, radius, fill):
        x, y = centre
        self.draw.ellipse(
            _s((x - radius, y - radius, x + radius, y + radius)), fill=fill)

    def ring(self, centre, radius, fill, width):
        x, y = centre
        self.draw.ellipse(
            _s((x - radius, y - radius, x + radius, y + radius)),
            outline=fill, width=width * SS)

    def page(self):
        """The shared sheet: a portrait page with a folded top-right corner."""
        left, top, right, bottom = PAGE
        self.polygon(
            [(left, top), (right - FOLD, top), (right, top + FOLD),
             (right, bottom), (left, bottom)],
            fill=self.theme["paper"], outline=self.theme["edge"], width=2,
        )
        # The fold, so it reads as paper rather than a plain rectangle.
        self.polygon(
            [(right - FOLD, top), (right - FOLD, top + FOLD),
             (right, top + FOLD)],
            fill=self.theme["rule"], outline=self.theme["edge"], width=2,
        )
        # Text rules. Only the top three show; the badge covers the rest.
        for index in range(3):
            y = top + 26 + index * 12
            self.line([(left + 9, y), (right - 12, y)],
                      fill=self.theme["rule"], width=3)

    def badge(self, accent):
        """Accent disc, cut out of the page by a halo in the ribbon colour."""
        self.ring(BADGE, RADIUS + 3, self.theme["halo"], 6)
        self.disc(BADGE, RADIUS, accent)

    def finish(self):
        return self.image.resize((SIZE, SIZE), Image.LANCZOS)


# --- badge glyphs, drawn white inside the disc ------------------------------

def glyph_export(icon):
    """Arrow dropping into a tray -- the standard 'out to disk' sign."""
    x, y = BADGE
    icon.rect((x - 3, y - 15, x + 3, y - 2), GLYPH, radius=1)
    icon.polygon([(x - 9, y - 4), (x + 9, y - 4), (x, y + 7)], fill=GLYPH)
    icon.rect((x - 12, y + 11, x + 12, y + 15), GLYPH, radius=2)


def glyph_archive(icon):
    """Archive carton: lid, body, and a slot where a hand would lift it."""
    x, y = BADGE
    icon.rect((x - 14, y - 13, x + 14, y - 5), GLYPH, radius=2)
    icon.rect((x - 11, y - 3, x + 11, y + 14), GLYPH, radius=2)
    icon.rect((x - 5, y + 2, x + 5, y + 6), icon.theme["paper"], radius=2)


def glyph_probe(icon):
    """Magnifier -- reads, changes nothing."""
    x, y = BADGE
    icon.ring((x - 3, y - 3), 9, GLYPH, 4)
    icon.line([(x + 4, y + 4), (x + 12, y + 12)], fill=GLYPH, width=6)


def glyph_seed(icon):
    """Exclamation -- the only button in the suite that writes to a model."""
    x, y = BADGE
    icon.rect((x - 3, y - 14, x + 3, y + 3), GLYPH, radius=3)
    icon.disc((x, y + 10), 4, GLYPH)


BUTTONS = {
    os.path.join("Issue.panel", "Export Issue.pushbutton"):
        (BLUE, glyph_export),
    os.path.join("Issue.panel", "Archive Superseded.pushbutton"):
        (AMBER, glyph_archive),
    os.path.join("Dev.panel", "Probe Export.pushbutton"):
        (TEAL, glyph_probe),
    os.path.join("Dev.panel", "Seed Revisions.pushbutton"):
        (RED, glyph_seed),
}


def build(theme, accent, glyph):
    icon = Icon(theme)
    icon.page()
    icon.badge(accent)
    glyph(icon)
    return icon.finish()


def main():
    for bundle, (accent, glyph) in BUTTONS.items():
        for theme, filename in ((LIGHT, "icon.png"), (DARK, "icon.dark.png")):
            target = os.path.join(PANELS, bundle, filename)
            build(theme, accent, glyph).save(target)
            print("wrote {0}".format(target))


if __name__ == "__main__":
    main()
