# -*- coding: utf-8 -*-
"""G3 -- what happened, and how to undo it.

Export writes files rather than mutating the model, so Ctrl+Z does NOT reverse
it. Rather than let the user assume otherwise, this gate names the folder to
delete.
"""

import os

from pyrevit import forms

from aecflow import commit


def show(outcome, audit_path, export_root, archived=None):
    """`archived` is the archive outcome when the tidy-up option was ticked,
    or None. It is reported explicitly rather than folded into the export
    count, because moving somebody's previous issue is a separate thing from
    writing a new one and they should see it named."""
    written = outcome["written"]
    failed = outcome["failed"]

    if outcome["dry_run"]:
        forms.alert(
            "Dry run complete.\n\n"
            "{0} file(s) would be written to:\n{1}\n\n"
            "Nothing was created.".format(len(written), export_root),
            title="Export Issue -- dry run",
        )
        return

    lines = ["{0} file(s) written to:".format(len(written)), export_root]

    if outcome["status"] == commit.CANCELLED:
        lines.append("")
        lines.append("Cancelled -- {0} file(s) were not written.".format(
            len(outcome["skipped"])
        ))
        lines.append("Files completed before cancelling are still on disk.")

    if failed:
        lines.append("")
        lines.append("{0} failed:".format(len(failed)))
        for failure in failed[:8]:
            lines.append("  {0} -- {1}".format(
                os.path.basename(failure.get("dest_path") or "?"),
                failure.get("detail", ""),
            ))

    if archived is not None:
        moved = len(archived["written"])
        lines.append("")
        if moved:
            lines.append("{0} superseded file(s) moved to Archive.".format(moved))
            lines.append("Exports now holds only the current revision of each")
            lines.append("sheet. They were MOVED, not deleted:")
            lines.append("  {0}".format(
                os.path.join(export_root, "Archive")))
        else:
            lines.append("Nothing was superseded -- Exports was already tidy.")
        if archived["failed"]:
            lines.append("{0} file(s) could not be archived.".format(
                len(archived["failed"])))

    lines.append("")
    lines.append("This wrote files; it did not change your model, so Ctrl+Z")
    lines.append("will not undo it. To reverse the run, delete:")
    lines.append("  {0}".format(export_root))

    if audit_path:
        lines.append("")
        lines.append("Audit record: {0}".format(audit_path))

    forms.alert("\n".join(lines), title="Export Issue -- complete")
