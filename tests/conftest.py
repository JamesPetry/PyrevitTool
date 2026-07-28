# -*- coding: utf-8 -*-
"""Shared fixtures. Runs without Revit -- that is the point of the Snapshot."""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "HDR.extension",
        "lib",
    ),
)

EXPORT_ROOT = os.path.join("P:", os.sep, "Projects", "12345")


def revision(uid, sequence, number):
    return {
        "uid": uid,
        "sequence": sequence,
        "revision_number": number,
        "date": "27.07.26",
        "description": "Issue",
        "issued": True,
    }


def sheet(uid, number, name, revision_uid, series="A", views=3,
          placeholder=False):
    return {
        "uid": uid,
        "number": number,
        "name": name,
        "is_placeholder": placeholder,
        "view_count": views,
        "current_revision_uid": revision_uid,
        "series": series,
    }


@pytest.fixture
def snapshot():
    """A realistic series: mixed revisions, one unrevised sheet, one other
    series that must not leak into the export."""
    return {
        "schema_version": 1,
        "captured_at": "2026-07-27T12:00:00",
        "hash": "testhash",
        "model": {
            "doc_title": "12345-Riverside",
            "doc_path": os.path.join(EXPORT_ROOT, "12345-Riverside.rvt"),
            "central_path": "",
            "is_workshared": True,
            "is_read_only": False,
            "project": {"number": "12345", "name": "Riverside Health Campus"},
            "revisions": [
                revision("rev-p03", 3, "P03"),
                revision("rev-p04", 4, "P04"),
            ],
            "sheets": [
                sheet("uid-a101", "A101", "Ground Floor Plan", "rev-p04"),
                sheet("uid-a102", "A102", "First Floor Plan", "rev-p04"),
                # Older revision than its neighbours -- CORRECT output under
                # per-sheet selection, must not be flagged.
                sheet("uid-a103", "A103", "Roof Plan", "rev-p03"),
                # No revision yet -- R8 warns.
                sheet("uid-a104", "A104", "Site Plan", None),
                # Different series -- must not appear in an "A" export.
                sheet("uid-s101", "S101", "Foundation Plan", "rev-p04",
                      series="S"),
            ],
        },
        "filesystem": {
            "export_root": EXPORT_ROOT,
            "root_writable": True,
            "existing": [],
        },
    }


@pytest.fixture
def scope():
    return {"series": "A", "formats": ["pdf"], "export_root": EXPORT_ROOT}
