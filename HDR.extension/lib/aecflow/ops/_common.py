# -*- coding: utf-8 -*-
"""Shared helpers for op executors.

Nothing here imports the Revit API at module level.
"""

import os


def ensure_parent(path):
    """Create the destination folder if it is not already there.

    Folder creation is an implicit precondition of every path-producing op
    rather than an op in its own right -- making it an op would add a fifth
    validator to express `mkdir -p`. It is still recorded in the audit trail
    by the caller.
    """
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    return folder


def base_validate(op, snapshot):
    """Checks every op kind shares."""
    errors = []
    if not op["args"].get("dest_path"):
        errors.append("no destination path")
    return errors


def result(op, written, detail=""):
    return {
        "op_id": op.get("op_id"),
        "kind": op["kind"],
        "dest_path": op["args"].get("dest_path"),
        "written": written,
        "detail": detail,
    }


def element_id_for(doc, uid):
    """Resolve a UniqueId to a live ElementId.

    Rebinding happens here, at the last possible moment, because ElementIds are
    not stable across sessions (Hard Invariant 3).
    """
    element = doc.GetElement(uid)
    if element is None:
        raise KeyError("no element for UniqueId {0}".format(uid))
    return element.Id
