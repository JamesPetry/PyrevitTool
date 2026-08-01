# -*- coding: utf-8 -*-
"""export_sheet_pdf -- one sheet, one PDF, exact filename.

Per ADR-003, the filename is only under our control when Combine is true.
With Combine false Revit generates names from a parameter-driven NamingRule
and ignores FileName entirely, so this executor exports ONE sheet per call
with Combine=True. That yields a single-page PDF named exactly as specified
and bypasses NamingRule completely.
"""

import os

from aecflow.ops import _common

KIND = "export_sheet_pdf"


def validate(op, snapshot):
    errors = _common.base_validate(op, snapshot)
    if op["target"]["kind"] != "element":
        errors.append("pdf export must target a sheet element")
    path = op["args"].get("dest_path") or ""
    if path and not path.lower().endswith(".pdf"):
        errors.append("destination is not a .pdf")
    return errors


def execute(doc, op, dry_run=True):
    path = op["args"]["dest_path"]
    if dry_run:
        return _common.result(op, False, "dry run")

    from Autodesk.Revit.DB import ElementId, PDFExportOptions
    from System.Collections.Generic import List

    folder = _common.ensure_parent(path)
    stem = os.path.splitext(os.path.basename(path))[0]

    options = PDFExportOptions()
    # Combine=True with a single sheet is what makes FileName authoritative.
    options.Combine = True
    options.FileName = stem

    views = List[ElementId]()
    views.Add(_common.element_id_for(doc, op["target"]["uid"]))

    doc.Export(folder, views, options)

    if not os.path.isfile(path):
        return _common.result(
            op, False,
            "Revit reported success but {0} is not on disk".format(
                os.path.basename(path)
            ),
        )
    return _common.result(op, True)
