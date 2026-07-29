# -*- coding: utf-8 -*-
"""archive_file -- move a superseded export into the dated Archive folder.

MOVE, NEVER DELETE. Nothing in this toolset deletes a file. If an archive
destination is somehow occupied the op fails rather than overwriting, because
the occupant would be a previously archived issue.

This is the only op that targets a path rather than a Revit element, and the
only one in the suite that touches a file the user already had.
"""

import os
import shutil

from aecflow.ops import _common

KIND = "archive_file"


def validate(op, snapshot):
    errors = _common.base_validate(op, snapshot)

    if op["target"]["kind"] != "path":
        errors.append("archive must target a path")
    elif not op["target"].get("path"):
        errors.append("archive target has no source path")

    source = op["target"].get("path")
    dest = op["args"].get("dest_path")
    if source and dest and os.path.normcase(source) == os.path.normcase(dest):
        errors.append("source and destination are the same file")

    return errors


def execute(doc, op, dry_run=True):
    source = op["target"]["path"]
    dest = op["args"]["dest_path"]

    if dry_run:
        return _common.result(op, False, "dry run")

    if not os.path.isfile(source):
        return _common.result(op, False, "source no longer exists")

    # Refuse rather than overwrite. An occupied destination means a previous
    # archive run already put something there, and losing it would be silent.
    if os.path.exists(dest):
        return _common.result(
            op, False, "destination already exists: {0}".format(
                os.path.basename(dest)))

    _common.ensure_parent(dest)
    shutil.move(source, dest)

    if not os.path.isfile(dest):
        return _common.result(op, False, "move reported success but file is absent")
    return _common.result(op, True)
