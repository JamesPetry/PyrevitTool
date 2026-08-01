# -*- coding: utf-8 -*-
"""export_sheet_dwg -- one sheet, one DWG, exact filename.

Autodesk's documentation states the `name` argument is "the name of a single
file or a prefix for a set of files", and that the API does not provide full
control of output names for multi-view exports. Exporting one sheet per call
makes `name` the filename outright.
"""

import os

from aecflow.ops import _common

KIND = "export_sheet_dwg"


def validate(op, snapshot):
    errors = _common.base_validate(op, snapshot)
    if op["target"]["kind"] != "element":
        errors.append("dwg export must target a sheet element")
    path = op["args"].get("dest_path") or ""
    if path and not path.lower().endswith(".dwg"):
        errors.append("destination is not a .dwg")
    return errors


def execute(doc, op, dry_run=True):
    path = op["args"]["dest_path"]
    if dry_run:
        return _common.result(op, False, "dry run")

    from Autodesk.Revit.DB import DWGExportOptions, ElementId
    from System.Collections.Generic import List

    folder = _common.ensure_parent(path)
    stem = os.path.splitext(os.path.basename(path))[0]

    options = DWGExportOptions()
    options.MergedViews = True

    views = List[ElementId]()
    views.Add(_common.element_id_for(doc, op["target"]["uid"]))

    doc.Export(folder, stem, views, options)

    if not os.path.isfile(path):
        return _common.result(
            op, False,
            "expected {0}; Revit may have applied its own suffix".format(
                os.path.basename(path)
            ),
        )
    return _common.result(op, True)
