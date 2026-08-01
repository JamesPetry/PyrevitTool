# -*- coding: utf-8 -*-
"""Archive Superseded: which files move, and — more importantly — which don't.

Moving a file is less recoverable than writing one, so these lean on the
refusals rather than the happy path.
"""

import datetime
import os

import pytest

from aecflow import archive, check, contracts, resolve
from aecflow.ops import archive_file
from aecflow.rules import archive_rules

WHEN = datetime.date(2026, 7, 29)
ROOT = os.path.join("P:", os.sep, "Projects", "12345")


def exported(sheet, revision, ext=".pdf"):
    """A file record as extract._read_filesystem would produce it."""
    name = "12345-{0}-Rev{1}{2}".format(sheet, revision, ext)
    return {
        "path": os.path.join(ROOT, "Exports", ext[1:].upper(), name),
        "size": 1024,
        "parsed": {"sheet_number": sheet, "revision": revision},
    }


def snapshot_with(files, revisions=("P03", "P04")):
    return {
        "hash": "h",
        "model": {
            "doc_title": "t", "doc_path": "", "central_path": "",
            "is_workshared": False, "is_read_only": False,
            "project": {"number": "12345", "name": "n"},
            "revisions": [
                {"uid": "r{0}".format(i), "sequence": i + 1,
                 "revision_number": label}
                for i, label in enumerate(revisions)
            ],
            "sheets": [],
        },
        "filesystem": {
            "export_root": ROOT, "root_writable": True, "existing": files,
        },
    }


def run(snapshot):
    intent = archive.build(snapshot, WHEN)
    changeset = resolve.bind(None, snapshot, intent)
    verdict = check.evaluate(snapshot, changeset, archive_rules.ALL_RULES)
    return intent, changeset, verdict


def moved(changeset):
    return sorted(os.path.basename(o["target"]["path"])
                  for o in changeset["operations"])


class TestSupersession(object):
    def test_older_revision_is_archived_and_newer_is_not(self):
        snap = snapshot_with([exported("A101", "P03"), exported("A101", "P04")])
        _i, changeset, _v = run(snap)
        assert moved(changeset) == ["12345-A101-RevP03.pdf"]

    def test_supersession_is_per_sheet_not_per_issue(self):
        """The heart of it. A101 advancing to P04 must not touch A102, which
        is still current at P03."""
        snap = snapshot_with([
            exported("A101", "P03"), exported("A101", "P04"),
            exported("A102", "P03"),
        ])
        _i, changeset, _v = run(snap)
        assert moved(changeset) == ["12345-A101-RevP03.pdf"]

    def test_a_lone_file_is_never_archived(self):
        snap = snapshot_with([exported("A101", "P03")])
        _i, changeset, _v = run(snap)
        assert changeset["operations"] == []

    def test_formats_are_superseded_independently(self):
        """A PDF at P04 does not supersede a DWG at P03 -- different outputs."""
        snap = snapshot_with([
            exported("A101", "P03", ".pdf"), exported("A101", "P04", ".pdf"),
            exported("A101", "P03", ".dwg"),
        ])
        _i, changeset, _v = run(snap)
        assert moved(changeset) == ["12345-A101-RevP03.pdf"]

    def test_more_than_two_revisions_keeps_only_the_newest(self):
        snap = snapshot_with(
            [exported("A101", r) for r in ("P01", "P02", "P03", "P04")],
            revisions=("P01", "P02", "P03", "P04"))
        _i, changeset, _v = run(snap)
        assert len(changeset["operations"]) == 3
        assert "12345-A101-RevP04.pdf" not in moved(changeset)

    def test_unparseable_files_are_left_alone(self):
        """A stray PDF someone dropped in the folder is not ours to move."""
        stray = {"path": os.path.join(ROOT, "Exports", "PDF", "scratch.pdf"),
                 "parsed": {"sheet_number": None, "revision": None}}
        snap = snapshot_with([
            exported("A101", "P03"), exported("A101", "P04"), stray])
        _i, changeset, _v = run(snap)
        assert "scratch.pdf" not in moved(changeset)

    def test_destination_is_a_dated_archive_folder(self):
        snap = snapshot_with([exported("A101", "P03"), exported("A101", "P04")])
        _i, changeset, _v = run(snap)
        dest = changeset["operations"][0]["args"]["dest_path"]
        assert "26-07-29_Archive" in dest
        assert "Archive" in dest


class TestRevisionRanking(object):
    def test_model_sequence_beats_alphabetical_order(self):
        """Model order is authoritative: if the model says B precedes A, that
        wins over the alphabet."""
        snap = snapshot_with(
            [exported("A101", "B"), exported("A101", "A")],
            revisions=("B", "A"))
        _i, changeset, _v = run(snap)
        assert moved(changeset) == ["12345-A101-RevB.pdf"]

    def test_unknown_labels_sort_naturally_not_as_text(self):
        """P9 must rank below P10 -- plain string comparison gets this wrong."""
        snap = snapshot_with(
            [exported("A101", "P9"), exported("A101", "P10")], revisions=())
        _i, changeset, _v = run(snap)
        assert moved(changeset) == ["12345-A101-RevP9.pdf"]


class TestSafetyRules(object):
    def test_a2_blocks_archiving_the_current_revision(self):
        """The safety rule, checked independently of Propose."""
        snap = snapshot_with([exported("A101", "P03"), exported("A101", "P04")])
        intent = archive.build(snap, WHEN)

        # Forge an op that would archive the CURRENT file.
        current = exported("A101", "P04")["path"]
        intent["ops"].append(contracts.make_op(
            contracts.ARCHIVE_FILE,
            contracts.path_target(current),
            {"dest_path": os.path.join(ROOT, "Archive", "x", "y.pdf")},
        ))

        changeset = resolve.bind(None, snap, intent)
        verdict = check.evaluate(snap, changeset, archive_rules.ALL_RULES)
        assert verdict["set_verdict"] == contracts.BLOCK
        assert any(r["rule_id"] == "A2" for r in verdict["results"])

    def test_a_block_approves_nothing(self):
        snap = snapshot_with([exported("A101", "P03"), exported("A101", "P04")])
        intent = archive.build(snap, WHEN)
        intent["ops"].append(contracts.make_op(
            contracts.ARCHIVE_FILE,
            contracts.path_target(exported("A101", "P04")["path"]),
            {"dest_path": os.path.join(ROOT, "Archive", "x", "y.pdf")},
        ))
        changeset = resolve.bind(None, snap, intent)
        verdict = check.evaluate(snap, changeset, archive_rules.ALL_RULES)
        assert check.approved_operations(changeset, verdict) == []

    def test_a1_blocks_a_source_missing_from_the_snapshot(self):
        snap = snapshot_with([exported("A101", "P03"), exported("A101", "P04")])
        intent = archive.build(snap, WHEN)
        snap["filesystem"]["existing"] = []
        changeset = resolve.bind(None, snap, intent)
        verdict = check.evaluate(snap, changeset, archive_rules.ALL_RULES)
        assert any(r["rule_id"] == "A1" for r in verdict["results"])

    def test_a3_blocks_two_files_landing_on_one_destination(self):
        snap = snapshot_with([exported("A101", "P03"), exported("A101", "P04")])
        intent = archive.build(snap, WHEN)
        clash = dict(intent["ops"][0])
        clash["target"] = contracts.path_target(
            os.path.join(ROOT, "Exports", "PDF", "12345-A101-RevP03.pdf"))
        intent["ops"].append(clash)
        changeset = resolve.bind(None, snap, intent)
        verdict = check.evaluate(snap, changeset, archive_rules.ALL_RULES)
        assert any(r["rule_id"] == "A3" for r in verdict["results"])

    def test_a5_blocks_an_over_long_archive_path(self):
        deep = os.path.join("P:", os.sep, *(["a_very_long_folder_name"] * 12))
        snap = snapshot_with([exported("A101", "P03"), exported("A101", "P04")])
        snap["filesystem"]["export_root"] = deep
        _i, _c, verdict = run(snap)
        assert any(r["rule_id"] == "A5" for r in verdict["results"])

    def test_a_clean_archive_passes(self):
        snap = snapshot_with([exported("A101", "P03"), exported("A101", "P04")])
        _i, _c, verdict = run(snap)
        assert verdict["set_verdict"] == contracts.PASS


class TestArchiveOpValidator(object):
    def test_accepts_a_well_formed_op(self):
        op = contracts.make_op(
            contracts.ARCHIVE_FILE,
            contracts.path_target("C:/x/Exports/PDF/a.pdf"),
            {"dest_path": "C:/x/Archive/26-07-29_Archive/a.pdf"})
        assert archive_file.validate(op, None) == []

    def test_rejects_an_element_target(self):
        op = contracts.make_op(
            contracts.ARCHIVE_FILE, contracts.element_target("uid-1"),
            {"dest_path": "C:/x/a.pdf"})
        assert any("target a path" in e for e in archive_file.validate(op, None))

    def test_rejects_moving_a_file_onto_itself(self):
        same = "C:/x/Exports/PDF/a.pdf"
        op = contracts.make_op(
            contracts.ARCHIVE_FILE, contracts.path_target(same),
            {"dest_path": same})
        assert any("same file" in e for e in archive_file.validate(op, None))

    def test_rejects_a_missing_destination(self):
        op = contracts.make_op(
            contracts.ARCHIVE_FILE, contracts.path_target("C:/x/a.pdf"),
            {"dest_path": None})
        assert any("destination" in e for e in archive_file.validate(op, None))


class TestExecutorRefusals(object):
    def test_refuses_when_the_source_is_gone(self, tmp_path):
        op = {"op_id": "op-0000", "kind": contracts.ARCHIVE_FILE,
              "target": contracts.path_target(str(tmp_path / "missing.pdf")),
              "args": {"dest_path": str(tmp_path / "arch" / "missing.pdf")}}
        result = archive_file.execute(None, op, dry_run=False)
        assert not result["written"]
        assert "no longer exists" in result["detail"]

    def test_refuses_rather_than_overwriting_an_archived_file(self, tmp_path):
        source = tmp_path / "a.pdf"
        source.write_text("new")
        archived = tmp_path / "arch" / "a.pdf"
        archived.parent.mkdir()
        archived.write_text("previously archived")

        op = {"op_id": "op-0000", "kind": contracts.ARCHIVE_FILE,
              "target": contracts.path_target(str(source)),
              "args": {"dest_path": str(archived)}}
        result = archive_file.execute(None, op, dry_run=False)

        assert not result["written"]
        assert archived.read_text() == "previously archived"
        assert source.exists(), "source must survive a refused move"

    def test_moves_the_file_and_leaves_no_original(self, tmp_path):
        source = tmp_path / "Exports" / "PDF" / "a.pdf"
        source.parent.mkdir(parents=True)
        source.write_text("content")
        dest = tmp_path / "Archive" / "26-07-29_Archive" / "a.pdf"

        op = {"op_id": "op-0000", "kind": contracts.ARCHIVE_FILE,
              "target": contracts.path_target(str(source)),
              "args": {"dest_path": str(dest)}}
        result = archive_file.execute(None, op, dry_run=False)

        assert result["written"]
        assert dest.read_text() == "content"
        assert not source.exists()

    def test_dry_run_moves_nothing(self, tmp_path):
        source = tmp_path / "a.pdf"
        source.write_text("content")
        op = {"op_id": "op-0000", "kind": contracts.ARCHIVE_FILE,
              "target": contracts.path_target(str(source)),
              "args": {"dest_path": str(tmp_path / "arch" / "a.pdf")}}
        result = archive_file.execute(None, op, dry_run=True)
        assert not result["written"]
        assert source.exists()


class TestArchiveAfterExportWiring(object):
    """The chained flow shares one pipeline with the standalone button.

    flows.plan_archive imports Extract, so it cannot run without Revit -- what
    is asserted here is the wiring, not a live run.
    """

    def test_flows_reuses_the_same_rules_and_proposer(self):
        import inspect
        from aecflow import flows
        source = inspect.getsource(flows.plan_archive)
        assert "archive.build" in source
        assert "archive_rules.ALL_RULES" in source

    def test_flows_recaptures_rather_than_reusing_a_stale_snapshot(self):
        """The files just exported are what make the older ones superseded, so
        reusing the export's snapshot would find nothing to archive."""
        import inspect
        from aecflow import flows
        assert "extract_module.capture" in inspect.getsource(flows.plan_archive)

    @staticmethod
    def gate_source(name):
        """Gates import pyrevit, so they cannot be imported outside Revit --
        by design. Read the file instead."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "lib", "aecflow", "gates", name)
        with open(path) as handle:
            return handle.read()

    def test_scope_carries_the_archive_flag(self):
        """G1 returns archive_after so the button can act on it."""
        source = self.gate_source("g1_scope.py")
        assert "archive_after" in source
        assert "ARCHIVE_OPTION" in source

    def test_archive_only_selection_is_rejected(self):
        """Ticking the tidy-up box but no format is a plausible slip."""
        assert "at least one format" in self.gate_source("g1_scope.py")

    def test_g3_reports_archived_files_separately(self):
        """Moving somebody's previous issue is a different thing from writing
        a new one -- it must not be folded into the export count."""
        source = self.gate_source("g3_summary.py")
        assert "archived" in source
        assert "MOVED, not deleted" in source
