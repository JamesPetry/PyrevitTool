# -*- coding: utf-8 -*-
"""RECORD -- audit persistence.

Persists the snapshot hash, Intent, ChangeSet, Verdict and commit outcome as
JSON so every run is reconstructable after the fact. Written for EVERY run,
including cancelled, blocked and dry ones -- an aborted run is exactly the
kind you want a record of.

Audits go beside the exports, in an `_audit` folder, so they travel with the
package rather than living in someone's user profile.
"""

import datetime
import json
import os

from aecflow import contracts

AUDIT_DIR = "_audit"
SCHEMA_VERSION = 1


def write(export_root, snapshot, intent, changeset, verdict, outcome):
    """Persist one run. Returns the audit file path, or None if it could not.

    A failure to write the audit must never take the run down with it: the
    files are already on disk by this point, and losing the record is bad but
    losing the user's export because logging failed is worse.
    """
    stamp = datetime.datetime.now()
    folder = os.path.join(export_root, AUDIT_DIR)
    path = os.path.join(
        folder, "run-{0}.json".format(stamp.strftime("%Y%m%d-%H%M%S"))
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_at": stamp.isoformat(),
        "snapshot_hash": snapshot.get("hash", ""),
        "model": {
            "title": snapshot["model"].get("doc_title"),
            "path": snapshot["model"].get("doc_path"),
            "central": snapshot["model"].get("central_path"),
            "workshared": snapshot["model"].get("is_workshared"),
        },
        "proposer": intent.get("proposer"),
        "counts": {
            "proposed": len(intent.get("ops") or []),
            "resolved": len(changeset.get("operations") or []),
            "dropped": len(changeset.get("dropped") or []),
        },
        "set_verdict": verdict.get("set_verdict"),
        "findings": verdict.get("findings") or [],
        "dropped": changeset.get("dropped") or [],
        "outcome": outcome,
    }

    try:
        if not os.path.isdir(folder):
            os.makedirs(folder)
        # Sheet names arrive from .NET and may carry characters the active code
        # page cannot translate; escaping them keeps the audit writable.
        text = json.dumps(
            contracts.ascii_safe(payload), indent=2, sort_keys=True
        )
        handle = open(path, "w")
        try:
            handle.write(text)
        finally:
            handle.close()
        return path
    except Exception:
        return None
