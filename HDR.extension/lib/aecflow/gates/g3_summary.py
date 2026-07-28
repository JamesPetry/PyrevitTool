# -*- coding: utf-8 -*-
"""G3 -- what happened, and how to undo it.

Export writes files rather than mutating the model, so Ctrl+Z does NOT reverse
it. Rather than let the user assume otherwise, this gate names the folder to
delete.
"""

import os

from pyrevit import forms

from aecflow import commit


def show(outcome, audit_path, export_root):
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

    lines.append("")
    lines.append("This wrote files; it did not change your model, so Ctrl+Z")
    lines.append("will not undo it. To reverse the run, delete:")
    lines.append("  {0}".format(export_root))

    if audit_path:
        lines.append("")
        lines.append("Audit record: {0}".format(audit_path))

    forms.alert("\n".join(lines), title="Export Issue -- complete")
