# -*- coding: utf-8 -*-
"""Sheet series resolution -- what defines the package being exported.

Q2's answer introduced the concept ("every sheet in the series, each at its own
current revision"); Q9 has not yet settled the mechanism. Rather than guess,
the strategy is pluggable and the default is the one native to Revit 2025.

    SHEET_COLLECTION  Revit 2025's Sheet Collections. Sheets carry a
                      "Sheet Collection" parameter and Revit's own Export/Print
                      dialog already filters by it. Recommended.
    PARAMETER         Any other sheet parameter, named in config. Use when HDR
                      already has a shared parameter for this.
    PREFIX            Leading letters of the sheet number: A101 -> "A".
                      Zero setup, works on any model, but encodes discipline
                      rather than package.
    ALL               One series containing every sheet. Escape hatch for
                      models with no grouping at all.

Switching strategies is a config change, not a rewrite -- which is the point,
since the answer to Q9 may differ per project.
"""

import re

SHEET_COLLECTION = "sheet_collection"
PARAMETER = "parameter"
PREFIX = "prefix"
ALL = "all"

DEFAULT_STRATEGY = SHEET_COLLECTION
SHEET_COLLECTION_PARAM = "Sheet Collection"
ALL_SERIES_NAME = "All sheets"

_PREFIX = re.compile(r"^([A-Za-z]+)")


def resolve(sheet_element, sheet_number, strategy=None, param_name=None):
    """Series name for one sheet, or None when it belongs to none.

    `sheet_element` is a live Revit ViewSheet, or None in pure/test mode, in
    which case only the number-derived strategies can answer.
    """
    strategy = strategy or DEFAULT_STRATEGY

    if strategy == ALL:
        return ALL_SERIES_NAME

    if strategy == PREFIX:
        return _from_prefix(sheet_number)

    if strategy == SHEET_COLLECTION:
        return _from_parameter(sheet_element, SHEET_COLLECTION_PARAM)

    if strategy == PARAMETER:
        if not param_name:
            raise ValueError("PARAMETER strategy needs a param_name")
        return _from_parameter(sheet_element, param_name)

    raise ValueError("unknown series strategy: {0}".format(strategy))


def _from_prefix(sheet_number):
    match = _PREFIX.match((sheet_number or "").strip())
    return match.group(1).upper() if match else None


# Revit reports an unassigned Sheet Collection as the literal string "<None>"
# rather than as a blank or an absent value. Confirmed by the probe on
# 2026-07-29: all 55 sheets in the sample model returned "<None>". Treating it
# as a series name would silently group every unassigned sheet into a package
# called "<None>".
UNSET_VALUES = ("<none>", "none", "")


def _from_parameter(sheet_element, param_name):
    """Read a named parameter off the sheet.

    Looked up by name rather than BuiltInParameter: Sheet Collections are new
    in 2025 and the built-in enum member is not something to assume. Name
    lookup also makes the PARAMETER strategy free.
    """
    if sheet_element is None:
        return None
    lookup = getattr(sheet_element, "LookupParameter", None)
    if lookup is None:
        return None
    try:
        parameter = lookup(param_name)
        if parameter is None or not parameter.HasValue:
            return None
        value = parameter.AsString() or parameter.AsValueString()
    except Exception:
        return None

    if not value:
        return None
    cleaned = value.strip()
    if cleaned.lower() in UNSET_VALUES:
        return None
    return cleaned


def available(sheets):
    """Distinct series present across a list of snapshot sheet records.

    Feeds the G1 picker. Sheets with no series are grouped under None so the
    user can see that some are unassigned rather than silently losing them.
    """
    found = []
    for sheet in sheets:
        name = sheet.get("series")
        if name not in found:
            found.append(name)
    named = sorted([f for f in found if f])
    return named + ([None] if None in found else [])
