# -*- coding: utf-8 -*-
"""G1 -- confirm scope before Extract.

Which series, which formats, which export root. Nothing is read from the model
until the user has confirmed what will be looked at, which is what prevents an
accidental whole-project export.
"""

import os

from pyrevit import forms

FORMATS = ("pdf", "dwg", "ifc", "rvt")
FORMAT_LABELS = {
    "pdf": "PDF (one file per sheet)",
    "dwg": "DWG (one file per sheet)",
    "ifc": "IFC (whole model)",
    "rvt": "Detached RVT (whole model)",
}
DEFAULT_FORMATS = ("pdf",)

# Offered alongside the formats rather than as a fourth dialog. Ticking it
# tidies Exports straight after the export, so the folder is left holding only
# the current revision of each sheet.
ARCHIVE_OPTION = "Archive superseded files afterwards (tidy Exports)"


def prompt(doc, available_series, default_root, series_fallback=None):
    """Returns a scope dict, or None if the user cancelled."""
    if not available_series:
        forms.alert(
            "No sheet series found in this model.\n\n"
            "Series come from Revit 2025 Sheet Collections by default. If this "
            "project does not use them, the series strategy needs changing in "
            "the tool configuration.",
            title="Nothing to export",
        )
        return None

    # Say which grouping is on screen. Most projects have not populated Sheet
    # Collections, so the list is often sheet-number prefixes instead -- the
    # user should not have to guess which they are looking at.
    if series_fallback:
        title = "Which sheet series?  (grouped by sheet number prefix)"
    else:
        title = "Which sheet series?  (Sheet Collections)"

    labels = [s if s else "(sheets with no series)" for s in available_series]
    chosen_label = forms.SelectFromList.show(
        labels, title=title, multiselect=False, button_name="Next",
    )
    if not chosen_label:
        return None
    series = available_series[labels.index(chosen_label)]

    chosen_formats = forms.SelectFromList.show(
        [FORMAT_LABELS[f] for f in FORMATS] + [ARCHIVE_OPTION],
        title="Which formats?", multiselect=True, button_name="Next",
    )
    if not chosen_formats:
        return None

    formats = [f for f in FORMATS if FORMAT_LABELS[f] in chosen_formats]
    archive_after = ARCHIVE_OPTION in chosen_formats

    # Ticking only the archive option is a plausible slip -- there would be
    # nothing to export and nothing newly superseded.
    if not formats:
        forms.alert("Pick at least one format to export.", title="Export Issue")
        return None

    # pick_folder's signature has varied across pyRevit versions; fall back to
    # the model's own folder rather than failing the run over a keyword.
    try:
        picked = forms.pick_folder(title="Export to")
    except TypeError:
        picked = forms.pick_folder()
    except Exception:
        picked = None

    export_root = picked or default_root
    if not export_root:
        return None

    return {
        "series": series,
        "formats": formats,
        "archive_after": archive_after,
        "export_root": os.path.abspath(export_root),
    }
