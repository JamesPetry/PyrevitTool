# -*- coding: utf-8 -*-
"""RECORD [D] -- audit persistence.

Persists snapshot hash, Intent, ChangeSet, Verdict and commit outcome as JSON
so every run is reconstructable after the fact. Written for every run,
including cancelled and blocked ones.

STATUS: skeleton. Lands in M1.
"""


def write(snapshot, intent, changeset, verdict, outcome):
    """Persist the run. Returns the audit file path."""
    raise NotImplementedError("M1")
