# -*- coding: utf-8 -*-
"""RESOLVE [D] -- lower Intent into a fully-bound ChangeSet.

Rebinds UniqueIds against the live document, absolutises destination paths,
and coerces export options to their Revit types. Any op that cannot be fully
bound is dropped here with a recorded reason -- never guessed at.

STATUS: skeleton. Lands in M1.
"""


def bind(doc, snapshot, intent):
    """Intent -> ChangeSet. See contracts.make_changeset."""
    raise NotImplementedError("M1")
