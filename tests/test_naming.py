# -*- coding: utf-8 -*-
"""Unit tests for the naming convention.

Runs without Revit -- this is the point of keeping naming pure. Run with:

    python -m pytest tests/ -q
"""

import datetime
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

from aecflow import naming  # noqa: E402


class TestSanitise(object):
    def test_passes_clean_input_through(self):
        assert naming.sanitise("A101") == "A101"

    def test_substitutes_forward_slash(self):
        # "A-101/1" is a legal Revit sheet number and an illegal filename.
        assert naming.sanitise("A-101/1") == "A-101-1"

    @pytest.mark.parametrize("char", '<>:"/\\|?*')
    def test_substitutes_every_reserved_character(self, char):
        assert char not in naming.sanitise("A{0}101".format(char))

    def test_strips_trailing_dot_and_space(self):
        # Windows will not create a file whose name ends in "." or " ".
        assert naming.sanitise("Plan . ") == "Plan"

    def test_collapses_internal_whitespace(self):
        assert naming.sanitise("Ground   Floor") == "Ground Floor"

    def test_is_idempotent(self):
        once = naming.sanitise("A-101/1 ")
        assert naming.sanitise(once) == once

    def test_returns_empty_for_input_that_sanitises_away(self):
        # Callers must treat "" as a rule R5 failure, not substitute a default.
        assert naming.sanitise("///") == "---"
        assert naming.sanitise("   ") == ""
        assert naming.sanitise(None) == ""


class TestSheetFilename(object):
    def test_matches_the_supplied_convention(self):
        assert (
            naming.sheet_filename("12345", "A101", "P04", ".pdf")
            == "12345-A101-RevP04.pdf"
        )

    def test_sanitises_the_sheet_number(self):
        assert (
            naming.sheet_filename("12345", "A-101/1", "P04", ".dwg")
            == "12345-A-101-1-RevP04.dwg"
        )


class TestModelFilename(object):
    def test_matches_the_supplied_convention(self):
        assert naming.model_filename("12345", "P04", ".ifc") == "12345_Model_RevP04.ifc"
        assert naming.model_filename("12345", "P04", ".rvt") == "12345_Model_RevP04.rvt"


class TestArchiveFolderName(object):
    def test_matches_the_supplied_convention(self):
        assert (
            naming.archive_folder_name(datetime.date(2026, 7, 22))
            == "26-07-22_Archive"
        )

    def test_zero_pads_single_digit_components(self):
        assert (
            naming.archive_folder_name(datetime.date(2026, 1, 5)) == "26-01-05_Archive"
        )


class TestExportPath(object):
    @pytest.mark.parametrize(
        "filename,folder",
        [
            ("12345-A101-RevP04.pdf", "PDF"),
            ("12345-A101-RevP04.dwg", "DWG"),
            ("12345_Model_RevP04.ifc", "IFC"),
            ("12345_Model_RevP04.rvt", "RVT"),
        ],
    )
    def test_routes_by_extension(self, filename, folder):
        path = naming.export_path("P:/12345", filename)
        assert path.replace("\\", "/") == "P:/12345/Exports/{0}/{1}".format(
            folder, filename
        )

    def test_rejects_an_unmapped_extension(self):
        with pytest.raises(ValueError):
            naming.export_path("P:/12345", "notes.txt")


class TestParseExportFilename(object):
    def test_round_trips_a_generated_sheet_name(self):
        generated = naming.sheet_filename("12345", "A101", "P03", ".pdf")
        assert naming.parse_export_filename(generated) == ("A101", "P03")

    def test_handles_a_sheet_number_containing_hyphens(self):
        assert naming.parse_export_filename("12345-A-101-RevP03.pdf") == (
            "A-101",
            "P03",
        )

    def test_returns_none_for_a_foreign_filename(self):
        # Archive & Close must never move a file it cannot identify.
        assert naming.parse_export_filename("scratch notes.pdf") is None
        assert naming.parse_export_filename("12345_Model_RevP04.ifc") is None


class TestPathTooLong(object):
    def test_accepts_a_normal_path(self):
        assert not naming.path_too_long("P:/12345/Exports/PDF/12345-A101-RevP04.pdf")

    def test_rejects_a_path_over_the_windows_limit(self):
        deep = "P:/" + "/".join(["a_very_long_folder_name"] * 12)
        assert naming.path_too_long(
            naming.export_path(deep, "12345-A101-RevP04.pdf")
        )
