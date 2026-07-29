# -*- coding: utf-8 -*-
"""EXTRACT -- the only module that reads the Revit API.

Reads the document and the export folder into a serialisable Snapshot. No
interpretation, no filtering beyond the declared scope. The Snapshot is the
only thing downstream stages see, which is what makes them testable without
Revit at all.

The filesystem is read here too. Archive and overwrite decisions depend on
what is already on disk, so "the world" means both the model and the folder.
"""

import datetime
import hashlib
import json
import os

from aecflow import contracts
from aecflow import naming
from aecflow import series as series_module


def capture(doc, export_root, series_strategy=None, series_param=None):
    """Read (doc, export_root) into a Snapshot."""
    model = _read_model(doc, series_strategy, series_param)
    filesystem = _read_filesystem(export_root)

    snapshot = contracts.make_snapshot(
        model, filesystem, datetime.datetime.now().isoformat()
    )
    snapshot["hash"] = _hash(snapshot)
    return snapshot


# --------------------------------------------------------------------------
# model
# --------------------------------------------------------------------------


def _read_model(doc, series_strategy, series_param):
    from Autodesk.Revit.DB import (
        BuiltInParameter, FilteredElementCollector, ModelPathUtils, Revision,
        ViewSheet,
    )

    info = doc.ProjectInformation

    revisions = []
    collector = FilteredElementCollector(doc).OfClass(Revision)
    for revision in collector:
        revisions.append({
            "uid": revision.UniqueId,
            "sequence": revision.SequenceNumber,
            "revision_number": _revision_label(revision),
            "date": revision.RevisionDate,
            "description": revision.Description,
            "issued": revision.Issued,
        })

    by_id = dict((r.Id.IntegerValue, r.UniqueId)
                 for r in FilteredElementCollector(doc).OfClass(Revision))

    sheets = []
    elements = list(FilteredElementCollector(doc).OfClass(ViewSheet))
    strategy = series_strategy or series_module.DEFAULT_STRATEGY

    for sheet in elements:
        sheets.append({
            "uid": sheet.UniqueId,
            "number": sheet.SheetNumber,
            "name": sheet.Name,
            "is_placeholder": bool(sheet.IsPlaceholder),
            "view_count": _placed_view_count(sheet),
            "current_revision_uid": _current_revision_uid(sheet, by_id),
            "series": series_module.resolve(
                sheet, sheet.SheetNumber, strategy, series_param
            ),
        })

    # Sheet Collections exist in every 2025 model but most projects have not
    # populated them -- the probe found all 55 sheets returning "<None>".
    # Rather than offer the user an empty picker, fall back to sheet-number
    # prefixes, which always yield something. The fallback is recorded so the
    # UI can say which grouping it is actually showing.
    series_fallback = None
    if strategy == series_module.SHEET_COLLECTION and sheets:
        if not any(s["series"] for s in sheets):
            series_fallback = series_module.PREFIX
            for record, sheet in zip(sheets, elements):
                record["series"] = series_module.resolve(
                    sheet, sheet.SheetNumber, series_module.PREFIX
                )

    return {
        "doc_title": doc.Title,
        "doc_path": doc.PathName or "",
        "central_path": _central_path(doc, ModelPathUtils),
        "is_workshared": bool(doc.IsWorkshared),
        "is_read_only": bool(doc.IsReadOnly),
        "series_strategy": series_fallback or strategy,
        "series_fallback": series_fallback,
        "project": {
            "number": _param_string(info, BuiltInParameter.PROJECT_NUMBER),
            "name": _param_string(info, BuiltInParameter.PROJECT_NAME),
        },
        "revisions": sorted(revisions, key=lambda r: r["sequence"]),
        "sheets": sorted(sheets, key=lambda s: s["number"] or ""),
    }


def _revision_label(revision):
    """The revision's displayed number, e.g. "P04".

    RevisionNumber is what appears in the titleblock and therefore what belongs
    in the filename. Falls back to the sequence when a revision has no number
    assigned, so a filename can still be built.
    """
    try:
        label = revision.RevisionNumber
        if label:
            return label
    except AttributeError:
        pass
    return str(revision.SequenceNumber)


def _current_revision_uid(sheet, revision_uids_by_id):
    """UniqueId of the sheet's own current revision, or None.

    GetCurrentRevision returns an ElementId, which is not stable across
    sessions -- it is converted to a UniqueId immediately (Hard Invariant 3).
    """
    try:
        element_id = sheet.GetCurrentRevision()
    except AttributeError:
        return None
    if element_id is None or element_id.IntegerValue < 0:
        return None
    return revision_uids_by_id.get(element_id.IntegerValue)


def _placed_view_count(sheet):
    try:
        return len(list(sheet.GetAllPlacedViews()))
    except Exception:
        return 0


def _central_path(doc, model_path_utils):
    if not doc.IsWorkshared:
        return ""
    try:
        path = doc.GetWorksharingCentralModelPath()
        return model_path_utils.ConvertModelPathToUserVisiblePath(path)
    except Exception:
        return ""


def _param_string(element, built_in):
    try:
        parameter = element.get_Parameter(built_in)
        if parameter is None:
            return ""
        return parameter.AsString() or ""
    except Exception:
        return ""


# --------------------------------------------------------------------------
# filesystem
# --------------------------------------------------------------------------


def _read_filesystem(export_root):
    """What is already on disk under the export root.

    Rule R2 needs this to refuse overwrites, and Archive & Close will need it
    to work out per-sheet supersession.
    """
    existing = []
    exports = os.path.join(export_root, naming.CONVENTION["export_dir"])

    if os.path.isdir(exports):
        for folder, _dirs, files in os.walk(exports):
            for filename in files:
                path = os.path.join(folder, filename)
                parsed = naming.parse_export_filename(filename)
                existing.append({
                    "path": path,
                    "size": _size(path),
                    "parsed": {
                        "sheet_number": parsed[0] if parsed else None,
                        "revision": parsed[1] if parsed else None,
                    },
                })

    return {
        "export_root": export_root,
        "root_writable": _writable(export_root),
        "existing": existing,
    }


def _size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _writable(root):
    """Whether we can actually create files under the export root.

    Checked by probing the nearest existing ancestor: the export folder itself
    usually does not exist yet on a first run, and a missing folder is not the
    same as an unwritable one.
    """
    probe = os.path.abspath(root)
    while probe and not os.path.isdir(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            return False
        probe = parent
    return os.access(probe, os.W_OK)


# --------------------------------------------------------------------------


def _hash(snapshot):
    """Stable digest of the snapshot, for the audit trail.

    Lets a run be tied to exactly the model state it was computed from.
    """
    payload = json.dumps(
        {"model": snapshot["model"], "filesystem": snapshot["filesystem"]},
        sort_keys=True, default=str,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()
