# -*- coding: utf-8 -*-
"""PROPOSE -- select what to export and what to call it.

The only stage permitted to be non-deterministic. In v1 it is not: this is a
pure rules engine over the Snapshot. No network call, no LLM, no transaction.

Selection rule (design doc Q2, answered 2026-07-27):

    every sheet in the chosen series, each at its OWN current revision

The series defines the package; the revision does not. Mixed revisions within
one export folder are the expected and correct output.

Must not import Autodesk.Revit.DB (Hard Invariant 6).
"""

from aecflow import contracts
from aecflow import naming

PROPOSER = {"name": "issue_export_rules", "version": "1.0", "deterministic": True}

# Which op kind writes which extension, in the order they should appear at G2.
SHEET_FORMATS = (
    ("pdf", contracts.EXPORT_SHEET_PDF, ".pdf"),
    ("dwg", contracts.EXPORT_SHEET_DWG, ".dwg"),
)
MODEL_FORMATS = (
    ("ifc", contracts.EXPORT_MODEL_IFC, ".ifc"),
    ("rvt", contracts.SAVE_DETACHED_RVT, ".rvt"),
)


def build(snapshot, scope):
    """Snapshot + scope -> Intent.

    scope = {
        "series":      str,    # the package to export
        "formats":     [str],  # subset of pdf/dwg/ifc/rvt
        "export_root": str,
    }
    """
    model = snapshot["model"]
    project_number = model["project"].get("number") or ""
    export_root = scope["export_root"]
    formats = set(scope.get("formats") or [])

    ops = []

    for sheet in _sheets_in_series(model, scope["series"]):
        revision = _current_revision_label(model, sheet)
        for fmt, kind, ext in SHEET_FORMATS:
            if fmt in formats:
                ops.append(_sheet_op(
                    kind, sheet, revision, project_number, export_root, ext
                ))

    for fmt, kind, ext in MODEL_FORMATS:
        if fmt in formats:
            ops.append(_model_op(
                kind, model, scope["series"], project_number, export_root, ext
            ))

    return contracts.make_intent(snapshot.get("hash", ""), ops, PROPOSER)


# --------------------------------------------------------------------------
# selection
# --------------------------------------------------------------------------


def _sheets_in_series(model, series):
    """Sheets belonging to the requested series, in sheet-number order.

    Placeholder sheets are kept rather than filtered out: they surface at G2
    as a warning (rule R7) so the user can see what would be left out, instead
    of vanishing silently between stages.
    """
    selected = [s for s in model["sheets"] if s.get("series") == series]
    return sorted(selected, key=lambda s: s.get("number") or "")


def _current_revision_label(model, sheet):
    """The sheet's own current revision number, or None if it has none.

    None is not an error here -- it is surfaced at G2 by rule R8 so the user
    decides. A brand-new sheet in an otherwise-issued series is the ordinary
    way to reach this.
    """
    uid = sheet.get("current_revision_uid")
    if not uid:
        return None
    for revision in model.get("revisions") or []:
        if revision.get("uid") == uid:
            return revision.get("revision_number")
    return None


# --------------------------------------------------------------------------
# op construction
# --------------------------------------------------------------------------


def _sheet_op(kind, sheet, revision, project_number, export_root, ext):
    if revision:
        filename = naming.sheet_filename(
            project_number, sheet.get("number"), revision, ext
        )
        dest = naming.export_path(export_root, filename)
        rationale = "Sheet {0} at its current revision {1}".format(
            sheet.get("number"), revision
        )
    else:
        # No revision means no filename. Carried through with dest_path None so
        # it appears at G2 as a flagged row rather than disappearing.
        dest = None
        rationale = "Sheet {0} has no revision -- cannot build a filename".format(
            sheet.get("number")
        )

    return contracts.make_op(
        kind=kind,
        target=contracts.element_target(sheet["uid"]),
        args={
            "dest_path": dest,
            "sheet_number": sheet.get("number"),
            "sheet_name": sheet.get("name"),
            "revision": revision,
        },
        rationale=rationale,
    )


def _model_op(kind, model, series, project_number, export_root, ext):
    """Whole-model exports take the highest revision present in the series.

    A model export is one file for the whole package, so it cannot carry a
    per-sheet revision. The highest revision in the series is the closest
    honest label for what the model represented at export time.
    """
    revision = _highest_revision_in_series(model, series)
    filename = naming.model_filename(project_number, revision or "NA", ext)
    return contracts.make_op(
        kind=kind,
        target=contracts.document_target(),
        args={
            "dest_path": naming.export_path(export_root, filename),
            "revision": revision,
        },
        rationale="Whole model at the highest revision in series {0}".format(series),
    )


def _highest_revision_in_series(model, series):
    """Highest revision sequence carried by any sheet in the series."""
    uids = set()
    for sheet in model["sheets"]:
        if sheet.get("series") == series and sheet.get("current_revision_uid"):
            uids.add(sheet["current_revision_uid"])

    best = None
    for revision in model.get("revisions") or []:
        if revision.get("uid") not in uids:
            continue
        if best is None or revision.get("sequence", 0) > best.get("sequence", 0):
            best = revision
    return best.get("revision_number") if best else None
