# -*- coding: utf-8 -*-
"""PROPOSE [P] -- the only stage permitted to be non-deterministic.

In v1 it is not: this is a pure rules engine. Select the sheets carrying the
issue revision, compute their filenames, route them to folders. The contract
is identical to an LLM-backed proposer, so the stage stays swappable.

Must not import Autodesk.Revit.DB (Hard Invariant 6).

STATUS: skeleton. Lands in M1.
"""


def build(snapshot, scope):
    """Snapshot -> Intent. See contracts.make_intent."""
    raise NotImplementedError("M1")
