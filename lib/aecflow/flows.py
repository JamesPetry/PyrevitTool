# -*- coding: utf-8 -*-
"""Orchestration helpers -- stage sequences shared between buttons.

Unlike the pure stages, modules here are permitted to reach the Revit API
indirectly through Extract. They contain no logic of their own: they only wire
existing stages together, so both the standalone Archive button and the
archive-after-export option run exactly the same pipeline.
"""

import datetime

from aecflow import archive, check, resolve
from aecflow import extract as extract_module
from aecflow.rules import archive_rules


def plan_archive(doc, export_root, when=None):
    """Run Extract -> Propose -> Resolve -> Check for archiving.

    Returns (snapshot, intent, changeset, verdict). Committing is the caller's
    decision, because the two entry points gate it differently: the standalone
    button always reviews, while the post-export option reviews only when
    something is flagged.

    Extract is re-run rather than reusing the export's snapshot -- the files
    just written are what makes the older ones superseded, so a stale
    filesystem read would find nothing to archive.
    """
    snapshot = extract_module.capture(doc, export_root)
    intent = archive.build(snapshot, when or datetime.datetime.now())
    changeset = resolve.bind(doc, snapshot, intent)
    verdict = check.evaluate(snapshot, changeset, archive_rules.ALL_RULES)
    return snapshot, intent, changeset, verdict
