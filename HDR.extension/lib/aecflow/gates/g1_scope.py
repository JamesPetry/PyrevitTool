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


def prompt(doc, available_series, default_root):
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

    labels = [s if s else "(sheets with no series)" for s in available_series]
    chosen_label = forms.SelectFromList.show(
        labels, title="Which sheet series?", multiselect=False, button_name="Next",
    )
    if not chosen_label:
        return None
    series = available_series[labels.index(chosen_label)]

    chosen_formats = forms.SelectFromList.show(
        [FORMAT_LABELS[f] for f in FORMATS],
        title="Which formats?", multiselect=True, button_name="Next",
    )
    if not chosen_formats:
        return None
    formats = [f for f in FORMATS if FORMAT_LABELS[f] in chosen_formats]

    export_root = forms.pick_folder(title="Export to") or default_root
    if not export_root:
        return None

    return {
        "series": series,
        "formats": formats,
        "export_root": os.path.abspath(export_root),
    }
