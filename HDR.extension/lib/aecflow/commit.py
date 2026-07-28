# -*- coding: utf-8 -*-
"""COMMIT -- the only stage that writes anything.

Export Issue writes files and opens NO transaction. It reads the model and
produces output beside it, so there is nothing for Ctrl+Z to reverse and
Hard Invariant 5 does not apply here -- see design doc section 7.1. The
compensating controls are dry-run by default, rule R2 making overwrites
impossible, and the destination of every file being visible at G2 first.

Archive & Close does mutate the model, and must wrap its work in a
TransactionGroup with Assimilate() so the whole run is a single undo.
"""

import traceback

from aecflow import ops

CANCELLED = "cancelled"
COMPLETE = "complete"
DRY_RUN = "dry_run"


def apply(doc, operations, dry_run=True, progress=None):
    """Execute approved operations, one export call per file.

    `progress` is an optional callable (index, total, op) -> bool. Returning
    False cancels. Cancellation is checked BETWEEN ops and never mid-op, so a
    cancelled run leaves whole files behind, never truncated ones.

    Returns an outcome record; never raises for a single failed op, because a
    partial result the user can see beats an exception that loses the audit.
    """
    total = len(operations)
    written = []
    failed = []
    skipped = []
    status = DRY_RUN if dry_run else COMPLETE

    for index, op in enumerate(operations):
        if progress is not None and not progress(index, total, op):
            status = CANCELLED
            skipped = operations[index:]
            break

        executor = ops.executor_for(op["kind"])
        if executor is None:
            failed.append(_failure(op, "no executor for kind {0}".format(op["kind"])))
            continue

        try:
            outcome = executor(doc, op, dry_run=dry_run)
        except Exception as error:
            failed.append(_failure(op, "{0}: {1}".format(
                type(error).__name__, error), traceback.format_exc()))
            continue

        if outcome.get("written") or dry_run:
            written.append(outcome)
        else:
            failed.append(outcome)

    return {
        "status": status,
        "dry_run": dry_run,
        "attempted": total,
        "written": written,
        "failed": failed,
        "skipped": [
            {"op_id": o["op_id"], "dest_path": o["args"].get("dest_path")}
            for o in skipped
        ],
    }


def _failure(op, detail, trace=None):
    record = {
        "op_id": op.get("op_id"),
        "kind": op.get("kind"),
        "dest_path": op["args"].get("dest_path"),
        "written": False,
        "detail": detail,
    }
    if trace:
        record["traceback"] = trace
    return record
