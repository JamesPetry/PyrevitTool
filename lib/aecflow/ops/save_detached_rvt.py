# -*- coding: utf-8 -*-
"""save_detached_rvt -- a detached copy of the model.

Detaching requires opening a SECOND document with DetachFromCentral, saving
that, and closing it -- the open document cannot detach itself. The original
document is never modified, which is what keeps Export Issue's promise that it
does not touch your model.

This is the riskiest executor in the tool and the least verifiable without a
workshared model. Treat it as unproven until the spike in ADR-003 has run.
"""

import os

from aecflow.ops import _common

KIND = "save_detached_rvt"


def validate(op, snapshot):
    errors = _common.base_validate(op, snapshot)
    if op["target"]["kind"] != "document":
        errors.append("detached save must target the document")
    path = op["args"].get("dest_path") or ""
    if path and not path.lower().endswith(".rvt"):
        errors.append("destination is not a .rvt")
    if not (snapshot["model"].get("doc_path") or "").strip():
        errors.append("model has never been saved -- nothing to detach from")
    return errors


def execute(doc, op, dry_run=True):
    path = op["args"]["dest_path"]
    if dry_run:
        return _common.result(op, False, "dry run")

    from Autodesk.Revit.DB import (
        DetachFromCentralOption, ModelPathUtils, OpenOptions,
        SaveAsOptions, WorksharingSaveAsOptions,
    )

    _common.ensure_parent(path)

    source = doc.PathName
    if not source:
        return _common.result(op, False, "model has no path on disk")

    model_path = ModelPathUtils.ConvertUserVisiblePathToModelPath(source)

    open_options = OpenOptions()
    open_options.DetachFromCentralOption = (
        DetachFromCentralOption.DetachAndPreserveWorksets
    )

    detached = doc.Application.OpenDocumentFile(model_path, open_options)
    try:
        save_options = SaveAsOptions()
        save_options.OverwriteExistingFile = False
        if detached.IsWorkshared:
            ws_options = WorksharingSaveAsOptions()
            ws_options.SaveAsCentral = True
            save_options.SetWorksharingOptions(ws_options)
        detached.SaveAs(
            ModelPathUtils.ConvertUserVisiblePathToModelPath(path), save_options
        )
    finally:
        detached.Close(False)

    if not os.path.isfile(path):
        return _common.result(
            op, False, "{0} is not on disk".format(os.path.basename(path))
        )
    return _common.result(op, True)
