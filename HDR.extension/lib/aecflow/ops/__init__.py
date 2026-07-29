# -*- coding: utf-8 -*-
"""Op validators and executors, colocated one module per kind.

Adding a kind requires a validator, an executor, and a negative test. No
exceptions -- an op outside the vocabulary means the task is out of scope.

**Revit imports are deliberately lazy.** Each `execute()` imports
Autodesk.Revit.DB inside the function body rather than at module level, so
Check can import a validator without dragging the Revit API into stages 2-4
(Hard Invariant 6). The invariant is about the import graph, and this keeps it
clean while still colocating the pair.
"""

from aecflow.ops import export_sheet_pdf
from aecflow.ops import export_sheet_dwg
from aecflow.ops import export_model_ifc
from aecflow.ops import save_detached_rvt
from aecflow.ops import archive_file

_MODULES = (
    export_sheet_pdf,
    export_sheet_dwg,
    export_model_ifc,
    save_detached_rvt,
    archive_file,
)

REGISTRY = dict((m.KIND, m) for m in _MODULES)


def validator_for(kind):
    module = REGISTRY.get(kind)
    return module.validate if module else None


def executor_for(kind):
    module = REGISTRY.get(kind)
    return module.execute if module else None
