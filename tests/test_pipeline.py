# -*- coding: utf-8 -*-
"""Propose -> Resolve -> Check, end to end, without Revit.

These are the tests that verify the selection rule Ryann confirmed on
2026-07-27: every sheet in the series, each at its OWN current revision.
"""

import os

import pytest

from aecflow import check, contracts, propose, resolve
from aecflow import rules


def run(snapshot, scope):
    intent = propose.build(snapshot, scope)
    changeset = resolve.bind(None, snapshot, intent)
    verdict = check.evaluate(snapshot, changeset)
    return intent, changeset, verdict


def dest_names(changeset):
    return sorted(
        os.path.basename(o["args"]["dest_path"])
        for o in changeset["operations"] if o["args"].get("dest_path")
    )


def verdict_for(verdict, op_id):
    return next(r for r in verdict["results"] if r["op_id"] == op_id)


def op_for_sheet(changeset, sheet_number):
    return next(o for o in changeset["operations"]
                if o["args"].get("sheet_number") == sheet_number)


class TestSelection(object):
    def test_exports_only_the_chosen_series(self, snapshot, scope):
        _i, changeset, _v = run(snapshot, scope)
        numbers = set(o["args"].get("sheet_number")
                      for o in changeset["operations"])
        assert "S101" not in numbers, "sheet from another series leaked in"
        assert {"A101", "A102", "A103", "A104"} <= numbers

    def test_each_sheet_takes_its_own_revision(self, snapshot, scope):
        """The core rule. A103 is at P03 while its neighbours are at P04."""
        _i, changeset, _v = run(snapshot, scope)
        assert dest_names(changeset) == [
            "12345-A101-RevP04.pdf",
            "12345-A102-RevP04.pdf",
            "12345-A103-RevP03.pdf",
        ]

    def test_mixed_revisions_are_not_flagged(self, snapshot, scope):
        """Regression guard on the rule inverted 2026-07-27.

        A103 sitting at P03 beside P04 sheets is correct output, not a warning.
        """
        _i, changeset, verdict = run(snapshot, scope)
        op = op_for_sheet(changeset, "A103")
        assert verdict_for(verdict, op["op_id"])["verdict"] == contracts.PASS

    def test_sheet_without_a_revision_warns_and_has_no_destination(
            self, snapshot, scope):
        _i, changeset, verdict = run(snapshot, scope)
        op = op_for_sheet(changeset, "A104")
        result = verdict_for(verdict, op["op_id"])
        assert op["args"]["dest_path"] is None
        assert result["verdict"] == contracts.WARN
        assert result["rule_id"] == "R8"

    def test_unrevised_sheet_survives_to_the_review_table(self, snapshot, scope):
        """It must be visible at G2, not silently dropped between stages."""
        _i, changeset, _v = run(snapshot, scope)
        assert changeset["dropped"] == []
        assert op_for_sheet(changeset, "A104") is not None

    def test_set_verdict_is_warn_not_block(self, snapshot, scope):
        _i, _c, verdict = run(snapshot, scope)
        assert verdict["set_verdict"] == contracts.WARN

    def test_only_passing_rows_are_approved_by_default(self, snapshot, scope):
        _i, changeset, verdict = run(snapshot, scope)
        approved = check.approved_operations(changeset, verdict)
        assert len(approved) == 3
        assert all(o["args"]["revision"] for o in approved)


class TestFormats(object):
    def test_multiple_sheet_formats_produce_one_op_each(self, snapshot, scope):
        scope["formats"] = ["pdf", "dwg"]
        _i, changeset, _v = run(snapshot, scope)
        assert len(dest_names(changeset)) == 6

    def test_model_formats_use_the_highest_revision_in_the_series(
            self, snapshot, scope):
        scope["formats"] = ["ifc"]
        _i, changeset, _v = run(snapshot, scope)
        assert dest_names(changeset) == ["12345_Model_RevP04.ifc"]

    def test_model_export_ignores_other_series_revisions(self, snapshot, scope):
        """S101 is at P04 too, but a series-A export must not consult it."""
        snapshot["model"]["revisions"].append({
            "uid": "rev-p09", "sequence": 9, "revision_number": "P09",
            "date": "", "description": "", "issued": True,
        })
        for sheet in snapshot["model"]["sheets"]:
            if sheet["number"] == "S101":
                sheet["current_revision_uid"] = "rev-p09"
        scope["formats"] = ["ifc"]
        _i, changeset, _v = run(snapshot, scope)
        assert dest_names(changeset) == ["12345_Model_RevP04.ifc"]

    def test_unselected_formats_produce_nothing(self, snapshot, scope):
        scope["formats"] = []
        _i, changeset, _v = run(snapshot, scope)
        assert changeset["operations"] == []


class TestRules(object):
    def test_r2_blocks_when_the_file_already_exists(self, snapshot, scope):
        existing = os.path.abspath(os.path.join(
            snapshot["filesystem"]["export_root"],
            "Exports", "PDF", "12345-A101-RevP04.pdf",
        ))
        snapshot["filesystem"]["existing"] = [{"path": existing}]
        _i, changeset, verdict = run(snapshot, scope)
        op = op_for_sheet(changeset, "A101")
        result = verdict_for(verdict, op["op_id"])
        assert result["verdict"] == contracts.BLOCK
        assert result["rule_id"] == "R2"
        assert verdict["set_verdict"] == contracts.BLOCK

    def test_a_block_approves_nothing_at_all(self, snapshot, scope):
        """Invariant 7: no partial apply on block."""
        existing = os.path.abspath(os.path.join(
            snapshot["filesystem"]["export_root"],
            "Exports", "PDF", "12345-A101-RevP04.pdf",
        ))
        snapshot["filesystem"]["existing"] = [{"path": existing}]
        _i, changeset, verdict = run(snapshot, scope)
        assert check.approved_operations(changeset, verdict) == []

    def test_r1_blocks_two_sheets_that_sanitise_to_one_filename(
            self, snapshot, scope):
        """"A-101/1" and "A-101-1" both become "A-101-1"."""
        sheets = snapshot["model"]["sheets"]
        sheets[0]["number"] = "A-101/1"
        sheets[1]["number"] = "A-101-1"
        _i, changeset, verdict = run(snapshot, scope)
        blocked = [r for r in verdict["results"] if r["rule_id"] == "R1"]
        assert len(blocked) == 1
        assert blocked[0]["verdict"] == contracts.BLOCK

    def test_r4_blocks_an_over_long_path(self, snapshot, scope):
        scope["export_root"] = os.path.join(
            "P:", os.sep, *(["a_very_long_folder_name"] * 12))
        _i, changeset, verdict = run(snapshot, scope)
        assert any(r["rule_id"] == "R4" and r["verdict"] == contracts.BLOCK
                   for r in verdict["results"])

    def test_r6_blocks_an_unwritable_root(self, snapshot, scope):
        snapshot["filesystem"]["root_writable"] = False
        _i, _c, verdict = run(snapshot, scope)
        assert any(r["rule_id"] == "R6" for r in verdict["results"])
        assert verdict["set_verdict"] == contracts.BLOCK

    def test_r7_warns_on_a_sheet_with_no_placed_views(self, snapshot, scope):
        for sheet in snapshot["model"]["sheets"]:
            if sheet["number"] == "A102":
                sheet["view_count"] = 0
        _i, changeset, verdict = run(snapshot, scope)
        op = op_for_sheet(changeset, "A102")
        assert verdict_for(verdict, op["op_id"])["rule_id"] == "R7"

    def test_r7_warns_on_a_placeholder_sheet(self, snapshot, scope):
        for sheet in snapshot["model"]["sheets"]:
            if sheet["number"] == "A102":
                sheet["is_placeholder"] = True
        _i, changeset, verdict = run(snapshot, scope)
        op = op_for_sheet(changeset, "A102")
        result = verdict_for(verdict, op["op_id"])
        assert result["verdict"] == contracts.WARN
        assert "placeholder" in result["message"]

    def test_a_clean_snapshot_passes_every_rule(self, snapshot, scope):
        snapshot["model"]["sheets"] = [
            s for s in snapshot["model"]["sheets"] if s["number"] != "A104"
        ]
        _i, _c, verdict = run(snapshot, scope)
        assert verdict["set_verdict"] == contracts.PASS


class TestResolve(object):
    def test_absolutises_destination_paths(self, snapshot, scope):
        scope["export_root"] = os.path.join("relative", "root")
        _i, changeset, _v = run(snapshot, scope)
        for op in changeset["operations"]:
            if op["args"].get("dest_path"):
                assert os.path.isabs(op["args"]["dest_path"])

    def test_drops_an_op_whose_sheet_left_the_snapshot(self, snapshot, scope):
        intent = propose.build(snapshot, scope)
        snapshot["model"]["sheets"] = [
            s for s in snapshot["model"]["sheets"] if s["number"] != "A101"
        ]
        changeset = resolve.bind(None, snapshot, intent)
        assert len(changeset["dropped"]) == 1
        assert "not in the snapshot" in changeset["dropped"][0]["reason"]

    def test_op_ids_are_unique(self, snapshot, scope):
        scope["formats"] = ["pdf", "dwg", "ifc"]
        _i, changeset, _v = run(snapshot, scope)
        ids = [o["op_id"] for o in changeset["operations"]]
        assert len(ids) == len(set(ids))


class TestContracts(object):
    def test_every_proposed_op_validates(self, snapshot, scope):
        scope["formats"] = ["pdf", "dwg", "ifc", "rvt"]
        intent = propose.build(snapshot, scope)
        for op in intent["ops"]:
            errors = contracts.validate_op(op, contracts.EXPORT_ISSUE_VOCABULARY)
            assert errors == [], errors

    def test_an_op_carrying_an_elementid_is_rejected(self):
        op = contracts.make_op(
            contracts.EXPORT_SHEET_PDF,
            {"kind": "element", "uid": "x", "element_id": 12345},
            {"dest_path": "x.pdf"},
        )
        errors = contracts.validate_op(op, contracts.EXPORT_ISSUE_VOCABULARY)
        assert any("ElementId" in e for e in errors)

    def test_an_unknown_kind_is_rejected(self):
        op = contracts.make_op(
            "delete_everything", contracts.document_target(), {})
        errors = contracts.validate_op(op, contracts.EXPORT_ISSUE_VOCABULARY)
        assert any("unknown op kind" in e for e in errors)


class TestInvariants(object):
    """Grep-style checks the pipeline context asks for by name."""

    LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "lib", "aecflow",
    )

    @staticmethod
    def module_level_imports(path):
        """Import lines at column 0. Indented imports are lazy, and docstrings
        that merely name the API are not imports."""
        found = []
        with open(path) as handle:
            for line in handle:
                if line.startswith(("import ", "from ")):
                    found.append(line.strip())
        return found

    @pytest.mark.parametrize("module", [
        "propose.py", "resolve.py", "check.py", "rules/__init__.py",
    ])
    def test_stages_2_to_4_do_not_import_the_revit_api(self, module):
        """Hard Invariant 6, enforced rather than trusted."""
        imports = self.module_level_imports(os.path.join(self.LIB, module))
        offenders = [i for i in imports if "Autodesk.Revit" in i]
        assert offenders == [], (
            "{0} imports the Revit API; model data belongs in the "
            "Snapshot: {1}".format(module, offenders)
        )

    def test_op_executors_do_not_import_revit_at_module_level(self):
        """Lazy imports keep Check's import graph free of the Revit API."""
        ops_dir = os.path.join(self.LIB, "ops")
        for filename in sorted(os.listdir(ops_dir)):
            if not filename.endswith(".py"):
                continue
            imports = self.module_level_imports(os.path.join(ops_dir, filename))
            offenders = [i for i in imports if "Autodesk.Revit" in i]
            assert offenders == [], (
                "{0} imports Revit at module level: {1}".format(
                    filename, offenders)
            )

    # Executors that must reach the Revit API somewhere, lazily. Guards against
    # the module-level test above passing simply because nobody imports Revit.
    REVIT_EXECUTORS = ("export_sheet_pdf.py", "export_sheet_dwg.py",
                       "export_model_ifc.py", "save_detached_rvt.py")

    @pytest.mark.parametrize("filename", REVIT_EXECUTORS)
    def test_revit_executors_do_import_revit_lazily(self, filename):
        with open(os.path.join(self.LIB, "ops", filename)) as handle:
            assert "Autodesk.Revit" in handle.read(), (
                "{0} never imports Revit -- is it really an "
                "executor?".format(filename)
            )

    def test_archive_file_needs_no_revit_at_all(self):
        """archive_file moves files on disk and touches no model, which is why
        its executor is fully unit-testable against a temp folder."""
        with open(os.path.join(self.LIB, "ops", "archive_file.py")) as handle:
            assert "Autodesk.Revit" not in handle.read()

    def test_every_executor_is_registered(self):
        from aecflow import ops as ops_pkg
        ops_dir = os.path.join(self.LIB, "ops")
        modules = [f[:-3] for f in os.listdir(ops_dir)
                   if f.endswith(".py") and not f.startswith("_")
                   and f != "__init__.py"]
        assert len(ops_pkg.REGISTRY) == len(modules)

    def test_every_op_kind_has_a_validator_and_an_executor(self):
        from aecflow import ops as ops_pkg
        for kind in contracts.EXPORT_ISSUE_VOCABULARY:
            assert ops_pkg.validator_for(kind) is not None, kind
            assert ops_pkg.executor_for(kind) is not None, kind

    def test_the_vocabulary_stays_under_the_six_op_budget(self):
        assert len(contracts.EXPORT_ISSUE_VOCABULARY) <= 6
        assert len(contracts.ARCHIVE_CLOSE_VOCABULARY) <= 6

    def test_all_eight_rules_are_registered(self):
        assert len(rules.ALL_RULES) == 8
