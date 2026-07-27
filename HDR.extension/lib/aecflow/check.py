# -*- coding: utf-8 -*-
"""CHECK [D] -- evaluate a ChangeSet against the rule set.

Rules are pure functions over (snapshot, changeset), one per file in rules/.
A block on any operation blocks the whole set (Hard Invariant 7).

Must not import Autodesk.Revit.DB (Hard Invariant 6).

STATUS: skeleton. Lands in M1.
"""


def evaluate(snapshot, changeset):
    """(Snapshot, ChangeSet) -> Verdict. See contracts.make_verdict."""
    raise NotImplementedError("M1")
