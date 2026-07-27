# -*- coding: utf-8 -*-
"""COMMIT [D] -- the only stage that writes anything.

Export Issue writes files and opens no transaction; there is nothing for
Ctrl+Z to reverse, and we do not pretend otherwise (design doc 7.1).
Archive & Close does open transactions and must wrap them in a
TransactionGroup with Assimilate() so the whole run is a single undo.

Registers an IFailuresPreprocessor so expected warnings resolve
deterministically instead of surfacing modal dialogs mid-commit.

STATUS: skeleton. Lands in M1.
"""


def apply(doc, changeset, dry_run=True):
    """Execute the approved operations. Returns an outcome record."""
    raise NotImplementedError("M1")
