# -*- coding: utf-8 -*-
"""Regression guards for bugs found by audit on 2026-07-29.

All three were live in code that had 129 passing tests. They shared a shape:
the happy path was covered, the adversarial one was not. Each test here names
the real-world input that would have triggered it.
"""

import os

import pytest

from aecflow import check, naming, propose, resolve


class TestFilenameParsingIsUnambiguous(object):
    """BUG 1 -- the worst of the three, and live on real exported files.

    "7765328-33-A-A101-RevP04.pdf" parsed its sheet number as "33-A-A101".
    The separator is a hyphen and project numbers routinely contain hyphens,
    so the project/sheet boundary is genuinely ambiguous without context.
    Archive would have grouped unrelated sheets together and superseded the
    wrong files.
    """

    @pytest.mark.parametrize("project,sheet,revision", [
        ("12345", "A101", "P04"),
        ("7765328-33-A", "A101", "P04"),      # the real sample project number
        ("7765328-33-A", "A-101/1", "P04"),
        ("12345", "A101", "P04-A"),           # revision containing a hyphen
        ("12345", "REV-01", "P04"),           # sheet number containing "REV"
        ("12345", "A101", "C"),
    ])
    def test_every_generated_name_parses_back(self, project, sheet, revision):
        filename = naming.sheet_filename(project, sheet, revision, ".pdf")
        assert naming.parse_export_filename(filename, project) == (
            naming.sanitise(sheet), naming.sanitise(revision))

    def test_hyphenated_project_number_without_context_is_wrong(self):
        """Documents why callers must pass the project number.

        Without it the first token is assumed to be the project, which is
        simply wrong for a hyphenated one. Pinned so nobody 'simplifies' the
        argument away.
        """
        filename = "7765328-33-A-A101-RevP04.pdf"
        assert naming.parse_export_filename(filename) == ("33-A-A101", "P04")
        assert naming.parse_export_filename(filename, "7765328-33-A") == (
            "A101", "P04")

    def test_model_exports_are_not_mistaken_for_sheets(self):
        assert naming.parse_export_filename("12345_Model_RevP04.ifc") is None

    def test_foreign_filenames_are_rejected(self):
        for name in ["scratch.pdf", "notes-Rev.pdf", "-RevP04.pdf",
                     "12345-A101-Rev.pdf"]:
            assert naming.parse_export_filename(name, "12345") is None, name

    def test_a_mismatched_project_number_is_rejected(self):
        """A file from another project sitting in the folder is not ours."""
        assert naming.parse_export_filename(
            "99999-A101-RevP04.pdf", "12345") is None


class TestNoOverwriteHoldsRegardlessOfPathForm(object):
    """BUG 2 -- a safety failure. R2 is what stops an export destroying a
    previous issue, and it compared paths without normalising them. It worked
    only because the caller happened to pass an absolute root."""

    def build(self, existing_path, export_root):
        snapshot = {
            "hash": "h",
            "model": {
                "doc_title": "t", "doc_path": "", "central_path": "",
                "is_workshared": False, "is_read_only": False,
                "project": {"number": "12345", "name": "n"},
                "revisions": [{"uid": "r1", "sequence": 1,
                               "revision_number": "P04"}],
                "sheets": [{"uid": "u1", "number": "A101", "name": "Plan",
                            "is_placeholder": False, "view_count": 1,
                            "current_revision_uid": "r1", "series": "A"}],
            },
            "filesystem": {"export_root": export_root, "root_writable": True,
                           "existing": [{"path": existing_path}]},
        }
        scope = {"series": "A", "formats": ["pdf"],
                 "export_root": export_root}
        intent = propose.build(snapshot, scope)
        changeset = resolve.bind(None, snapshot, intent)
        return snapshot, changeset, check.evaluate(snapshot, changeset)

    def test_relative_snapshot_path_still_blocks(self):
        relative = os.path.join("proj", "12345", "Exports", "PDF",
                                "12345-A101-RevP04.pdf")
        _s, _c, verdict = self.build(relative, os.path.join("proj", "12345"))
        assert any(r["rule_id"] == "R2" for r in verdict["results"]), (
            "R2 missed an existing file and would have overwritten it")

    def test_absolute_snapshot_path_still_blocks(self):
        root = os.path.abspath(os.path.join("proj", "12345"))
        existing = os.path.join(root, "Exports", "PDF", "12345-A101-RevP04.pdf")
        _s, _c, verdict = self.build(existing, root)
        assert any(r["rule_id"] == "R2" for r in verdict["results"])

    def test_a_genuinely_new_file_is_not_blocked(self):
        """Guard against the fix over-firing and blocking everything."""
        root = os.path.abspath(os.path.join("proj", "12345"))
        other = os.path.join(root, "Exports", "PDF", "12345-A999-RevP01.pdf")
        _s, _c, verdict = self.build(other, root)
        assert not any(r["rule_id"] == "R2" for r in verdict["results"])


class TestUnnameableSheetsAreNeverWritten(object):
    """BUG 3 -- a sheet numbered "///" sanitises to "---", which is non-empty
    and legal, producing "12345-----RevP04.pdf": a real file that identifies
    nothing and that Archive can never parse back."""

    @pytest.mark.parametrize("number,nameable", [
        ("A101", True), ("A1", True), ("0", True),
        ("///", False), ("---", False), ("   ", False), ("", False),
        (None, False),
    ])
    def test_is_nameable_requires_an_alphanumeric(self, number, nameable):
        assert naming.is_nameable(number) is nameable

    def test_a_punctuation_only_sheet_number_produces_no_file(self):
        snapshot = {
            "hash": "h",
            "model": {
                "doc_title": "t", "doc_path": "", "central_path": "",
                "is_workshared": False, "is_read_only": False,
                "project": {"number": "12345", "name": "n"},
                "revisions": [{"uid": "r1", "sequence": 1,
                               "revision_number": "P04"}],
                "sheets": [{"uid": "u1", "number": "///", "name": "Plan",
                            "is_placeholder": False, "view_count": 1,
                            "current_revision_uid": "r1", "series": "A"}],
            },
            "filesystem": {"export_root": os.path.join("t", "x"),
                           "root_writable": True, "existing": []},
        }
        scope = {"series": "A", "formats": ["pdf"],
                 "export_root": os.path.join("t", "x")}
        intent = propose.build(snapshot, scope)
        changeset = resolve.bind(None, snapshot, intent)
        verdict = check.evaluate(snapshot, changeset)

        operation = changeset["operations"][0]
        assert operation["args"]["dest_path"] is None
        assert any(r["rule_id"] == "R8" for r in verdict["results"])
        assert check.approved_operations(changeset, verdict) == []


class TestExportRootMisselection(object):
    """Picking Exports/ rather than its parent produced Exports/Exports/PDF.

    Untidy is the least of it: Archive looks for <root>/Exports and writes
    <root>/Archive, so an inconsistent root between runs makes it report
    "nothing superseded" while superseded files sit in plain sight. The folder
    picker opens on the folder just exported into, which makes the mistake
    easy.
    """

    @staticmethod
    def gate_source():
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "lib", "aecflow", "gates", "g1_scope.py")
        with open(path) as handle:
            return handle.read()

    def test_the_guard_exists_and_is_wired_into_the_picker(self):
        source = self.gate_source()
        assert "def resolve_root" in source
        assert "resolve_root(picked or default_root)" in source

    def test_the_guard_keys_off_the_naming_convention(self):
        """Hard-coding "Exports" here would drift if the convention changed."""
        source = self.gate_source()
        assert 'naming.CONVENTION["export_dir"]' in source
        assert 'naming.CONVENTION["archive_dir"]' in source

    def test_the_archive_button_uses_the_same_guard(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "HDR.tab", "Issue.panel",
            "Archive Superseded.pushbutton", "script.py")
        with open(path) as handle:
            source = handle.read()
        assert "g1_scope.resolve_root" in source

    def test_structural_folder_names_are_what_the_tool_creates(self):
        """The guard is only correct if these are the folders being made."""
        from aecflow import naming
        assert naming.CONVENTION["export_dir"] == "Exports"
        assert naming.CONVENTION["archive_dir"] == "Archive"
        built = naming.export_path(os.path.join("P:", os.sep, "proj"),
                                   "12345-A101-RevP04.pdf")
        assert os.path.join("proj", "Exports", "PDF") in built
