# -*- coding: utf-8 -*-
"""Filename and folder conventions.

Every naming decision the tool makes lives here, so changing the convention is
one edit rather than a search across the codebase. Pure functions over plain
strings -- no Revit API, no filesystem access, fully unit testable.

Conventions are drawn from the structure supplied by Ryann:

    Exports/PDF/12345-A101-RevP04.pdf
    Exports/IFC/12345_Model_RevP04.ifc
    Archive/26-07-22_Archive/

Note the separator inconsistency (hyphens for sheets, underscores for models).
It is reproduced faithfully pending confirmation -- see Q3 in the design doc.
"""

import os
import re

# --------------------------------------------------------------------------
# Convention
# --------------------------------------------------------------------------

CONVENTION = {
    "sheet": "{project_number}-{sheet_number}-Rev{revision}{ext}",
    "model": "{project_number}_Model_Rev{revision}{ext}",
    "archive_folder": "{yy}-{mm}-{dd}_Archive",
    "export_dir": "Exports",
    "archive_dir": "Archive",
    "format_dirs": {
        ".pdf": "PDF",
        ".dwg": "DWG",
        ".ifc": "IFC",
        ".rvt": "RVT",
    },
}

# Windows reserves these in filenames. Revit sheet numbers legally contain
# some of them -- "A-101/1" is common -- so substitution is mandatory, and
# deterministic: same input, same output, every run.
ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
SUBSTITUTE = "-"

# Windows MAX_PATH. Enforced as Check rule R4 rather than silently truncating:
# a truncated filename is a wrong filename.
MAX_PATH = 260

# Trailing dots and spaces are legal to construct but not to create on Windows.
_TRAILING = " ."


def sanitise(value):
    """Make a string safe for use as a Windows filename component.

    Deterministic and idempotent. Returns "" for input that sanitises away
    entirely, which callers must treat as an error (rule R5) rather than
    substituting a placeholder.
    """
    if value is None:
        return ""
    cleaned = ILLEGAL_CHARS.sub(SUBSTITUTE, value.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.rstrip(_TRAILING)
    return cleaned


def sheet_filename(project_number, sheet_number, revision, ext):
    """Build a sheet export filename.

    >>> sheet_filename("12345", "A101", "P04", ".pdf")
    '12345-A101-RevP04.pdf'
    >>> sheet_filename("12345", "A-101/1", "P04", ".pdf")
    '12345-A-101-1-RevP04.pdf'
    """
    return CONVENTION["sheet"].format(
        project_number=sanitise(project_number),
        sheet_number=sanitise(sheet_number),
        revision=sanitise(revision),
        ext=ext,
    )


def model_filename(project_number, revision, ext):
    """Build a whole-model export filename.

    >>> model_filename("12345", "P04", ".ifc")
    '12345_Model_RevP04.ifc'
    """
    return CONVENTION["model"].format(
        project_number=sanitise(project_number),
        revision=sanitise(revision),
        ext=ext,
    )


def archive_folder_name(when):
    """Dated archive folder name from a date or datetime.

    >>> import datetime
    >>> archive_folder_name(datetime.date(2026, 7, 22))
    '26-07-22_Archive'
    """
    return CONVENTION["archive_folder"].format(
        yy="{0:02d}".format(when.year % 100),
        mm="{0:02d}".format(when.month),
        dd="{0:02d}".format(when.day),
    )


def export_path(export_root, filename):
    """Absolute destination for an export, routed by extension.

    >>> export_path("P:/12345", "12345-A101-RevP04.pdf").replace("\\\\", "/")
    'P:/12345/Exports/PDF/12345-A101-RevP04.pdf'
    """
    ext = os.path.splitext(filename)[1].lower()
    sub = CONVENTION["format_dirs"].get(ext)
    if sub is None:
        raise ValueError("no export folder mapped for extension: {0}".format(ext))
    return os.path.join(export_root, CONVENTION["export_dir"], sub, filename)


def archive_path(export_root, folder_name, filename):
    """Absolute destination inside a dated archive folder."""
    return os.path.join(
        export_root, CONVENTION["archive_dir"], folder_name, filename
    )


def parse_export_filename(filename):
    """Recover (sheet_number, revision) from a sheet export filename.

    Archive & Close needs this to decide which files belong to a superseded
    issue. Returns None when the name does not match the convention -- callers
    must not archive what they cannot parse.

    >>> parse_export_filename("12345-A101-RevP03.pdf")
    ('A101', 'P03')
    >>> parse_export_filename("scratch notes.pdf") is None
    True
    """
    stem = os.path.splitext(os.path.basename(filename))[0]
    match = re.match(r"^(?P<project>[^-]+)-(?P<sheet>.+)-Rev(?P<rev>[^-]+)$", stem)
    if not match:
        return None
    return (match.group("sheet"), match.group("rev"))


def path_too_long(path):
    """True when a destination exceeds the Windows path limit (rule R4)."""
    return len(os.path.abspath(path)) > MAX_PATH
