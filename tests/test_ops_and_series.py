# -*- coding: utf-8 -*-
"""Op validators, series resolution, and the dry-run commit path.

Every op kind needs a negative test -- that is the rule for adding a kind.
"""

import pytest

from aecflow import commit, contracts, propose, resolve, series
from aecflow import ops as ops_pkg
from aecflow.ops import (
    export_model_ifc, export_sheet_dwg, export_sheet_pdf, save_detached_rvt,
)


def op(kind, target, dest):
    built = contracts.make_op(kind, target, {"dest_path": dest})
    built["op_id"] = "op-0000"
    return built


class TestSeriesResolution(object):
    @pytest.mark.parametrize("number,expected", [
        ("A101", "A"), ("SK-12", "SK"), ("a204", "A"), ("101", None),
    ])
    def test_prefix_strategy(self, number, expected):
        assert series.resolve(None, number, series.PREFIX) == expected

    def test_all_strategy_puts_everything_in_one_series(self):
        assert series.resolve(None, "A101", series.ALL) == series.ALL_SERIES_NAME

    def test_sheet_collection_returns_none_without_an_element(self):
        """Pure mode cannot read a parameter -- it must say so, not guess."""
        assert series.resolve(None, "A101", series.SHEET_COLLECTION) is None

    def test_sheet_collection_reads_the_parameter(self):
        class Param(object):
            HasValue = True

            def AsString(self):
                return "Planning Package"

        class Sheet(object):
            def LookupParameter(self, name):
                return Param() if name == "Sheet Collection" else None

        assert series.resolve(
            Sheet(), "A101", series.SHEET_COLLECTION) == "Planning Package"

    @staticmethod
    def sheet_returning(value):
        class Param(object):
            HasValue = True

            def AsString(self):
                return value

            def AsValueString(self):
                return value

        class Sheet(object):
            def LookupParameter(self, name):
                return Param()

        return Sheet()

    def test_a_blank_parameter_is_treated_as_no_series(self):
        assert series.resolve(
            self.sheet_returning("   "), "A101", series.SHEET_COLLECTION) is None

    @pytest.mark.parametrize("value", ["<None>", "<none>", "None", ""])
    def test_revits_unset_sentinel_is_not_a_series_name(self, value):
        """Found by the probe on 2026-07-29.

        Revit reports an unassigned Sheet Collection as the literal string
        "<None>", not as blank or absent. All 55 sheets in the sample model
        returned it. Without this, every unassigned sheet would be grouped
        into a package called "<None>".
        """
        assert series.resolve(
            self.sheet_returning(value), "A101", series.SHEET_COLLECTION) is None

    def test_a_series_genuinely_called_none_something_is_kept(self):
        """Guard against over-matching the sentinel."""
        assert series.resolve(
            self.sheet_returning("Nonstructural"), "A101",
            series.SHEET_COLLECTION) == "Nonstructural"

    def test_unknown_strategy_raises(self):
        with pytest.raises(ValueError):
            series.resolve(None, "A101", "telepathy")

    def test_parameter_strategy_requires_a_name(self):
        with pytest.raises(ValueError):
            series.resolve(None, "A101", series.PARAMETER)

    def test_available_lists_named_series_then_unassigned(self):
        sheets = [
            {"series": "S"}, {"series": "A"}, {"series": None}, {"series": "A"},
        ]
        assert series.available(sheets) == ["A", "S", None]


class TestOpValidators(object):
    def test_pdf_accepts_a_well_formed_op(self):
        good = op(contracts.EXPORT_SHEET_PDF,
                  contracts.element_target("uid-1"), "C:/x/a.pdf")
        assert export_sheet_pdf.validate(good, None) == []

    def test_pdf_rejects_a_document_target(self):
        bad = op(contracts.EXPORT_SHEET_PDF,
                 contracts.document_target(), "C:/x/a.pdf")
        assert export_sheet_pdf.validate(bad, None) != []

    def test_pdf_rejects_the_wrong_extension(self):
        bad = op(contracts.EXPORT_SHEET_PDF,
                 contracts.element_target("uid-1"), "C:/x/a.dwg")
        assert any("not a .pdf" in e for e in export_sheet_pdf.validate(bad, None))

    def test_dwg_rejects_a_document_target(self):
        bad = op(contracts.EXPORT_SHEET_DWG,
                 contracts.document_target(), "C:/x/a.dwg")
        assert export_sheet_dwg.validate(bad, None) != []

    def test_ifc_rejects_an_element_target(self):
        bad = op(contracts.EXPORT_MODEL_IFC,
                 contracts.element_target("uid-1"), "C:/x/m.ifc")
        assert export_model_ifc.validate(bad, None) != []

    def test_rvt_rejects_an_unsaved_model(self):
        good_target = op(contracts.SAVE_DETACHED_RVT,
                         contracts.document_target(), "C:/x/m.rvt")
        snapshot = {"model": {"doc_path": ""}}
        errors = save_detached_rvt.validate(good_target, snapshot)
        assert any("never been saved" in e for e in errors)

    def test_rvt_accepts_a_saved_model(self):
        good = op(contracts.SAVE_DETACHED_RVT,
                  contracts.document_target(), "C:/x/m.rvt")
        snapshot = {"model": {"doc_path": "C:/x/live.rvt"}}
        assert save_detached_rvt.validate(good, snapshot) == []

    def test_every_kind_rejects_a_missing_destination(self):
        snapshot = {"model": {"doc_path": "C:/x/live.rvt"}}
        for kind in contracts.EXPORT_ISSUE_VOCABULARY:
            validator = ops_pkg.validator_for(kind)
            blank = op(kind, contracts.document_target(), None)
            assert any("destination" in e for e in validator(blank, snapshot)), kind


class TestDryRunCommit(object):
    def test_dry_run_writes_nothing_and_reports_every_op(self, snapshot, scope):
        """Hard Invariant 4: a full result with zero mutations."""
        intent = propose.build(snapshot, scope)
        changeset = resolve.bind(None, snapshot, intent)
        writing = [o for o in changeset["operations"]
                   if o["args"].get("dest_path")]

        outcome = commit.apply(None, writing, dry_run=True)

        assert outcome["status"] == commit.DRY_RUN
        assert outcome["attempted"] == len(writing)
        assert len(outcome["written"]) == len(writing)
        assert outcome["failed"] == []
        assert all(not w["written"] for w in outcome["written"])

    def test_cancellation_stops_between_ops_and_records_the_remainder(
            self, snapshot, scope):
        intent = propose.build(snapshot, scope)
        changeset = resolve.bind(None, snapshot, intent)
        writing = [o for o in changeset["operations"]
                   if o["args"].get("dest_path")]

        def progress(index, total, op_):
            return index < 1

        outcome = commit.apply(None, writing, dry_run=True, progress=progress)

        assert outcome["status"] == commit.CANCELLED
        assert len(outcome["written"]) == 1
        assert len(outcome["skipped"]) == len(writing) - 1

    def test_an_unknown_kind_fails_that_op_without_taking_down_the_run(self):
        rogue = op("not_a_real_kind", contracts.document_target(), "C:/x/a.pdf")
        outcome = commit.apply(None, [rogue], dry_run=True)
        assert outcome["failed"] and not outcome["written"]
        assert "no executor" in outcome["failed"][0]["detail"]
