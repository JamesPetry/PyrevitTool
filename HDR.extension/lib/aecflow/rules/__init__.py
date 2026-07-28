# -*- coding: utf-8 -*-
"""Check rules -- one pure function per rule, over (snapshot, changeset).

Each rule returns a list of {op_id, verdict, rule_id, message}. A rule that
finds nothing returns []. Rules never mutate their inputs and never touch the
Revit API.

Export Issue rule set (design doc section 6):

    R1 no_duplicate_destinations   block
    R2 no_overwrite                block   -- makes the two-tool split safe
    R3 target_sheet_exists         block
    R4 path_within_limit           block
    R5 filename_is_legal           block
    R6 export_root_writable        block
    R7 sheet_has_placed_views      warn
    R8 sheet_has_a_revision        warn
"""

import os

from aecflow import contracts
from aecflow import naming


def _result(op_id, verdict, rule_id, message):
    return {
        "op_id": op_id,
        "verdict": verdict,
        "rule_id": rule_id,
        "message": message,
    }


def _writing_ops(changeset):
    """Ops that will actually write a file -- those with a destination."""
    return [o for o in changeset["operations"] if o["args"].get("dest_path")]


# --------------------------------------------------------------------------


def r1_no_duplicate_destinations(snapshot, changeset):
    """Two ops writing the same path would silently lose one of them.

    Reachable whenever two sheet numbers sanitise to the same string, for
    example "A-101/1" and "A-101-1".
    """
    seen = {}
    results = []
    for op in _writing_ops(changeset):
        path = os.path.normcase(op["args"]["dest_path"])
        if path in seen:
            results.append(_result(
                op["op_id"], contracts.BLOCK, "R1",
                "writes the same file as {0}: {1}".format(
                    seen[path], os.path.basename(op["args"]["dest_path"])
                ),
            ))
        else:
            seen[path] = op["op_id"]
    return results


def r2_no_overwrite(snapshot, changeset):
    """Export Issue never overwrites. Archiving is a separate, deliberate act.

    This is the rule that makes the two-tool split safe: an export run cannot
    destroy a previous issue.
    """
    existing = set(
        os.path.normcase(f["path"])
        for f in snapshot["filesystem"].get("existing") or []
    )
    results = []
    for op in _writing_ops(changeset):
        if os.path.normcase(op["args"]["dest_path"]) in existing:
            results.append(_result(
                op["op_id"], contracts.BLOCK, "R2",
                "{0} already exists -- archive it first".format(
                    os.path.basename(op["args"]["dest_path"])
                ),
            ))
    return results


def r3_target_sheet_exists(snapshot, changeset):
    """Every element target must still be a sheet in the Snapshot."""
    known = set(s["uid"] for s in snapshot["model"]["sheets"])
    results = []
    for op in changeset["operations"]:
        target = op["target"]
        if target["kind"] != contracts.TARGET_ELEMENT:
            continue
        if target.get("uid") not in known:
            results.append(_result(
                op["op_id"], contracts.BLOCK, "R3",
                "target sheet is no longer in the model",
            ))
    return results


def r4_path_within_limit(snapshot, changeset):
    """Windows MAX_PATH. Not theoretical on deep HDR network paths.

    Failing here with a clear message beats failing at sheet 60 of 64 with a
    Revit exception.
    """
    results = []
    for op in _writing_ops(changeset):
        path = op["args"]["dest_path"]
        if naming.path_too_long(path):
            results.append(_result(
                op["op_id"], contracts.BLOCK, "R4",
                "path is {0} characters, limit is {1}".format(
                    len(path), naming.MAX_PATH
                ),
            ))
    return results


def r5_filename_is_legal(snapshot, changeset):
    """The filename must survive sanitisation with something left of it.

    Revit sheet numbers legally contain characters Windows forbids. Substitution
    is deterministic, but a number consisting only of forbidden characters
    sanitises to nothing, and a blank filename must never be written.
    """
    results = []
    for op in _writing_ops(changeset):
        stem = os.path.splitext(os.path.basename(op["args"]["dest_path"]))[0]
        if not stem.strip():
            results.append(_result(
                op["op_id"], contracts.BLOCK, "R5",
                "filename is empty after sanitisation",
            ))
        elif naming.ILLEGAL_CHARS.search(stem):
            results.append(_result(
                op["op_id"], contracts.BLOCK, "R5",
                "filename still contains illegal characters: {0}".format(stem),
            ))
    return results


def r6_export_root_writable(snapshot, changeset):
    """One set-level check, reported against the first writing op.

    Fails the whole run rather than each file individually -- an unwritable
    root is one problem, not sixty-four.
    """
    fs = snapshot["filesystem"]
    if fs.get("root_writable", True):
        return []
    ops = _writing_ops(changeset)
    if not ops:
        return []
    return [_result(
        ops[0]["op_id"], contracts.BLOCK, "R6",
        "export root is not writable: {0}".format(fs.get("export_root")),
    )]


def r7_sheet_has_placed_views(snapshot, changeset):
    """A placeholder or empty sheet exports a blank page.

    Warn, not block: an intentionally blank cover or divider sheet is
    legitimate, so the user opts in at G2.
    """
    by_uid = dict((s["uid"], s) for s in snapshot["model"]["sheets"])
    results = []
    for op in changeset["operations"]:
        target = op["target"]
        if target["kind"] != contracts.TARGET_ELEMENT:
            continue
        sheet = by_uid.get(target.get("uid"))
        if sheet is None:
            continue
        if sheet.get("is_placeholder"):
            results.append(_result(
                op["op_id"], contracts.WARN, "R7",
                "placeholder sheet -- nothing to export",
            ))
        elif not sheet.get("view_count"):
            results.append(_result(
                op["op_id"], contracts.WARN, "R7",
                "sheet has no placed views -- will export blank",
            ))
    return results


def r8_sheet_has_a_revision(snapshot, changeset):
    """Every sheet needs a revision to build a filename from.

    Inverted 2026-07-27. This rule used to warn when sheets carried DIFFERENT
    revisions, which assumed issue-based selection. Under per-sheet selection
    mixed revisions are the expected output, so the rule now catches the real
    failure: a sheet with no revision at all has nothing to put in the
    Rev{revision} slot.
    """
    results = []
    for op in changeset["operations"]:
        if op["target"]["kind"] != contracts.TARGET_ELEMENT:
            continue
        if not op["args"].get("revision"):
            results.append(_result(
                op["op_id"], contracts.WARN, "R8",
                "sheet {0} has no revision yet -- skipped".format(
                    op["args"].get("sheet_number")
                ),
            ))
    return results


ALL_RULES = (
    r1_no_duplicate_destinations,
    r2_no_overwrite,
    r3_target_sheet_exists,
    r4_path_within_limit,
    r5_filename_is_legal,
    r6_export_root_writable,
    r7_sheet_has_placed_views,
    r8_sheet_has_a_revision,
)
