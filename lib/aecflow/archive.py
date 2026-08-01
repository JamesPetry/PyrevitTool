# -*- coding: utf-8 -*-
"""PROPOSE for archiving -- work out which exported files are superseded.

Implements the Archive half of Ryann's structure: Exports/ holds only what is
current, everything it supersedes moves into a dated Archive/ folder.

    Exports/PDF/12345-A101-RevP04.pdf     <- current, stays
    Archive/26-07-22_Archive/
        12345-A101-RevP03.pdf             <- superseded, moved here

SUPERSESSION IS PER SHEET, not per issue. Because Q2 settled on each sheet
exporting at its own current revision, one folder legitimately holds mixed
revisions -- so A101-RevP03 being superseded says nothing about whether
A102-RevP03 beside it is still current. Files are grouped by (sheet, format)
and only the highest revision in each group survives.

Deterministic and pure. Must not import Autodesk.Revit.DB.
"""

import os
import re

from aecflow import contracts
from aecflow import naming

PROPOSER = {"name": "archive_superseded_rules", "version": "1.0",
            "deterministic": True}

_DIGITS = re.compile(r"(\d+)")


def build(snapshot, when):
    """Snapshot + date -> Intent containing archive_file ops.

    `when` is a date or datetime, used for the dated archive folder name.
    """
    export_root = snapshot["filesystem"]["export_root"]
    folder = naming.archive_folder_name(when)
    ranks = _revision_ranks(snapshot)

    ops = []
    for group_key, entries in sorted(_grouped(snapshot).items()):
        if len(entries) < 2:
            continue  # nothing to supersede

        ordered = sorted(entries, key=lambda e: ranks(e["revision"]))
        current = ordered[-1]

        for entry in ordered[:-1]:
            filename = os.path.basename(entry["path"])
            ops.append(contracts.make_op(
                kind=contracts.ARCHIVE_FILE,
                target=contracts.path_target(entry["path"]),
                args={
                    "dest_path": naming.archive_path(
                        export_root, folder, filename),
                    "sheet_number": group_key[0],
                    "revision": entry["revision"],
                    "superseded_by": os.path.basename(current["path"]),
                },
                rationale="{0} superseded by {1}".format(
                    filename, os.path.basename(current["path"])),
            ))

    return contracts.make_intent(snapshot.get("hash", ""), ops, PROPOSER)


def _grouped(snapshot):
    """Existing exports grouped by (sheet number, file extension).

    Files whose names do not parse are excluded entirely. Archive must never
    move something it cannot identify -- a stray PDF someone dropped in the
    folder is not ours to touch.
    """
    groups = {}
    for record in snapshot["filesystem"].get("existing") or []:
        path = record["path"]
        parsed = record.get("parsed") or {}
        sheet_number = parsed.get("sheet_number")
        revision = parsed.get("revision")
        if not sheet_number or not revision:
            continue

        key = (sheet_number, os.path.splitext(path)[1].lower())
        groups.setdefault(key, []).append({
            "path": path,
            "revision": revision,
        })
    return groups


def _revision_ranks(snapshot):
    """Return a function ranking revision labels oldest-to-newest.

    Prefers the model's own revision sequence, which is authoritative. Falls
    back to a natural sort so "P9" ranks below "P10" rather than above it,
    which plain string comparison would get wrong.
    """
    by_label = {}
    for revision in snapshot["model"].get("revisions") or []:
        label = revision.get("revision_number")
        if label:
            by_label[label] = revision.get("sequence", 0)

    def rank(label):
        if label in by_label:
            return (0, by_label[label], "")
        return (1, 0, _natural_key(label))

    return rank


def _natural_key(label):
    """Split digits from text so P9 sorts before P10."""
    parts = _DIGITS.split(label or "")
    key = []
    for part in parts:
        if part.isdigit():
            key.append((1, int(part), ""))
        elif part:
            key.append((0, 0, part))
    return tuple(key)
