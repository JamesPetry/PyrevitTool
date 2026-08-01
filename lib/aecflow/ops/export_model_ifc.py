# -*- coding: utf-8 -*-
"""export_model_ifc -- whole model to IFC.

IFC takes an explicit folder and filename, so there is no naming difficulty
here. The export configuration is the open part: pyRevit ships
`pyrevit.interop.ifc`, which parses the IFC exporter's JSON config, and that
is the route to HDR's own IFC setup once someone supplies it (design doc Q6).
"""

import os

from aecflow.ops import _common

KIND = "export_model_ifc"


def validate(op, snapshot):
    errors = _common.base_validate(op, snapshot)
    if op["target"]["kind"] != "document":
        errors.append("ifc export must target the document")
    path = op["args"].get("dest_path") or ""
    if path and not path.lower().endswith(".ifc"):
        errors.append("destination is not a .ifc")
    return errors


def execute(doc, op, dry_run=True):
    path = op["args"]["dest_path"]
    if dry_run:
        return _common.result(op, False, "dry run")

    from Autodesk.Revit.DB import IFCExportOptions

    folder = _common.ensure_parent(path)
    name = os.path.basename(path)

    # Default configuration until HDR's IFC setup is supplied -- see Q6.
    options = IFCExportOptions()

    doc.Export(folder, name, options)

    if not os.path.isfile(path):
        return _common.result(op, False, "{0} is not on disk".format(name))
    return _common.result(op, True)
