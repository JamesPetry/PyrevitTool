# -*- coding: utf-8 -*-
"""Check rules for archiving. Pure functions over (snapshot, changeset).

The export rules guard against writing the wrong file. These guard against
moving the wrong one, which is the more dangerous direction: an unwanted export
is deleted, but a wrongly-moved issue has to be found again.

    A1 source_exists            block
    A2 never_archive_current    block   -- the safety rule
    A3 no_duplicate_destination block
    A4 destination_is_free      block
    A5 path_within_limit        block
"""

import os

from aecflow import contracts
from aecflow import naming


def _result(op_id, verdict, rule_id, message):
    return {"op_id": op_id, "verdict": verdict,
            "rule_id": rule_id, "message": message}


def _archive_ops(changeset):
    return [o for o in changeset["operations"]
            if o["kind"] == contracts.ARCHIVE_FILE]


def a1_source_exists(snapshot, changeset):
    """The file being moved must still be on disk per the Snapshot."""
    known = set(os.path.normcase(f["path"])
                for f in snapshot["filesystem"].get("existing") or [])
    results = []
    for op in _archive_ops(changeset):
        source = op["target"].get("path") or ""
        if os.path.normcase(source) not in known:
            results.append(_result(
                op["op_id"], contracts.BLOCK, "A1",
                "source file is not in the snapshot: {0}".format(
                    os.path.basename(source)),
            ))
    return results


def a2_never_archive_current(snapshot, changeset):
    """The newest revision of a sheet must never be archived.

    The safety rule. Archiving the current issue would empty Exports/ of the
    thing people actually need, and the mistake would not be obvious until
    somebody went looking for a drawing.

    Recomputed here independently of Propose rather than trusting it -- Check
    exists to disagree with Propose, not to echo it.
    """
    from aecflow import archive

    groups = archive._grouped(snapshot)
    ranks = archive._revision_ranks(snapshot)

    current_paths = set()
    for entries in groups.values():
        newest = sorted(entries, key=lambda e: ranks(e["revision"]))[-1]
        current_paths.add(os.path.normcase(newest["path"]))

    results = []
    for op in _archive_ops(changeset):
        source = os.path.normcase(op["target"].get("path") or "")
        if source in current_paths:
            results.append(_result(
                op["op_id"], contracts.BLOCK, "A2",
                "{0} is the current revision -- refusing to archive it".format(
                    os.path.basename(op["target"]["path"])),
            ))
    return results


def a3_no_duplicate_destination(snapshot, changeset):
    """Two files must not be moved onto the same archive path."""
    seen = {}
    results = []
    for op in _archive_ops(changeset):
        dest = os.path.normcase(op["args"].get("dest_path") or "")
        if dest in seen:
            results.append(_result(
                op["op_id"], contracts.BLOCK, "A3",
                "would overwrite the file archived by {0}".format(seen[dest]),
            ))
        else:
            seen[dest] = op["op_id"]
    return results


def a4_destination_is_free(snapshot, changeset):
    """An occupied archive slot means a previous run already put something
    there. Refuse rather than overwrite it."""
    results = []
    for op in _archive_ops(changeset):
        dest = op["args"].get("dest_path")
        if dest and os.path.exists(dest):
            results.append(_result(
                op["op_id"], contracts.BLOCK, "A4",
                "already archived: {0}".format(os.path.basename(dest)),
            ))
    return results


def a5_path_within_limit(snapshot, changeset):
    """Archive paths are deeper than export paths and hit MAX_PATH sooner."""
    results = []
    for op in _archive_ops(changeset):
        dest = op["args"].get("dest_path")
        if dest and naming.path_too_long(dest):
            results.append(_result(
                op["op_id"], contracts.BLOCK, "A5",
                "archive path is {0} characters, limit is {1}".format(
                    len(dest), naming.MAX_PATH),
            ))
    return results


ALL_RULES = (
    a1_source_exists,
    a2_never_archive_current,
    a3_no_duplicate_destination,
    a4_destination_is_free,
    a5_path_within_limit,
)
