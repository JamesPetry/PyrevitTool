# -*- coding: utf-8 -*-
"""RESOLVE -- lower an Intent into a fully-bound ChangeSet.

Rebinds UniqueIds against the live document, absolutises destination paths and
gives every operation a stable id for the audit trail. Anything that cannot be
fully bound is dropped here with a recorded reason, never guessed at.

`doc` may be None, which runs the stage in pure mode for tests and golden
fixtures. With a document supplied, element targets are checked for existence;
without one, they are taken on trust from the Snapshot.

Must not import Autodesk.Revit.DB (Hard Invariant 6). The document is touched
only through duck-typed calls, so this module stays importable outside Revit.
"""

import os

from aecflow import contracts


def bind(doc, snapshot, intent):
    """Intent -> ChangeSet."""
    operations = []
    dropped = []

    known_uids = set(s["uid"] for s in snapshot["model"]["sheets"])

    for index, op in enumerate(intent["ops"]):
        reason = _unbindable_reason(doc, op, known_uids)
        if reason:
            dropped.append({"source_op": op, "reason": reason})
            continue

        args = dict(op["args"])
        if args.get("dest_path"):
            args["dest_path"] = os.path.abspath(args["dest_path"])

        operations.append({
            "op_id": "op-{0:04d}".format(index),
            "kind": op["kind"],
            "target": op["target"],
            "args": args,
            "confidence": op["confidence"],
            "rationale": op["rationale"],
        })

    return contracts.make_changeset(
        intent.get("snapshot_hash", ""), operations, dropped
    )


def _unbindable_reason(doc, op, known_uids):
    """Why this op cannot be bound, or None if it can.

    A missing destination path is NOT a binding failure. An op for a sheet with
    no revision is deliberately carried through so it reaches the review table,
    where rule R8 explains it. Dropping it here would make it vanish.
    """
    target = op["target"]

    if target["kind"] == contracts.TARGET_ELEMENT:
        uid = target.get("uid")
        if uid not in known_uids:
            return "sheet {0} is not in the snapshot".format(uid)
        if doc is not None and _element_missing(doc, uid):
            return "sheet {0} no longer exists in the document".format(uid)

    return None


def _element_missing(doc, uid):
    """True when the document no longer holds this UniqueId.

    Guarded so a document object without GetElement -- a test double, or a
    document closed underneath us -- does not crash the stage.
    """
    getter = getattr(doc, "GetElement", None)
    if getter is None:
        return False
    try:
        return getter(uid) is None
    except Exception:
        return True
