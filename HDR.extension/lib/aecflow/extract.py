# -*- coding: utf-8 -*-
"""EXTRACT [D] -- the only module permitted to read the Revit API.

Reads the document and the export folder into a serialisable Snapshot. No
interpretation, no filtering beyond the declared scope. The Snapshot is the
only thing downstream stages see.

STATUS: skeleton. Lands in M1.
"""


def capture(doc, scope):
    """Read (doc, scope) into a Snapshot dict. See contracts.make_snapshot."""
    raise NotImplementedError("M1")
