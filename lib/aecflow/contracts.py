# -*- coding: utf-8 -*-
"""Typed contracts passed between pipeline stages.

Every stage boundary in the AECFlow pipeline is a plain, JSON-serialisable dict
defined here. Nothing in this module imports the Revit API, and nothing in it
does any work -- these are shapes plus their validators.

Shapes are documented in docstrings rather than declared with TypedDict or
dataclasses so this module runs unchanged under IronPython 2.7. See ADR-002.

    Snapshot  --propose-->  Intent  --resolve-->  ChangeSet  --check-->  Verdict
"""

SCHEMA_VERSION = 1


def ascii_safe(value):
    """Recursively coerce a structure so json.dumps cannot fail on encoding.

    Revit strings reach us through .NET and may carry characters that the
    active code page cannot translate -- a sheet named "Cafe\xe9" crashed the
    snapshot hash with UnicodeDecodeError before this existed. Since both the
    hash and the audit record only need a faithful, stable representation
    rather than a readable one, non-ASCII characters are escaped rather than
    dropped, so two different names never collapse to the same text.

    Handles both engines: `unicode` exists under IronPython 2.7 and not under
    CPython 3.
    """
    if isinstance(value, dict):
        return dict((ascii_safe(k), ascii_safe(v)) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return [ascii_safe(v) for v in value]
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value

    try:
        text_types = (str, unicode)      # noqa: F821 -- IronPython 2.7
    except NameError:
        text_types = (str,)              # CPython 3

    if not isinstance(value, text_types):
        try:
            value = str(value)
        except Exception:
            return "<unrepresentable>"

    try:
        return value.encode("ascii", "backslashreplace").decode("ascii")
    except Exception:
        try:
            return "".join(c for c in value if ord(c) < 128)
        except Exception:
            return "<unrepresentable>"

# --------------------------------------------------------------------------
# Targets
# --------------------------------------------------------------------------
# Identity is UniqueId for elements, never ElementId (Hard Invariant 3).
# Document- and path-scoped ops have no UniqueId, so targets are tagged.
#
#   {"kind": "element",  "uid": "8f3a...-000a1b2c"}
#   {"kind": "document"}
#   {"kind": "path",     "path": "P:/12345/Exports/PDF/12345-A101-RevP03.pdf"}

TARGET_ELEMENT = "element"
TARGET_DOCUMENT = "document"
TARGET_PATH = "path"

_TARGET_KINDS = (TARGET_ELEMENT, TARGET_DOCUMENT, TARGET_PATH)


def element_target(unique_id):
    """Target a Revit element by UniqueId."""
    return {"kind": TARGET_ELEMENT, "uid": unique_id}


def document_target():
    """Target the active document as a whole."""
    return {"kind": TARGET_DOCUMENT}


def path_target(path):
    """Target a file on disk. Used by Archive & Close only."""
    return {"kind": TARGET_PATH, "path": path}


# --------------------------------------------------------------------------
# Op vocabulary (closed)
# --------------------------------------------------------------------------
# Adding a kind requires a validator AND an executor in aecflow/ops/, plus a
# negative test. There is no escape hatch: an operation that does not fit the
# vocabulary means the task is out of scope for the tool.

EXPORT_SHEET_PDF = "export_sheet_pdf"
EXPORT_SHEET_DWG = "export_sheet_dwg"
EXPORT_MODEL_IFC = "export_model_ifc"
SAVE_DETACHED_RVT = "save_detached_rvt"

EXPORT_ISSUE_VOCABULARY = (
    EXPORT_SHEET_PDF,
    EXPORT_SHEET_DWG,
    EXPORT_MODEL_IFC,
    SAVE_DETACHED_RVT,
)

# Archive & Close (M3) -- declared here so the shared Check engine knows them.
ARCHIVE_FILE = "archive_file"
PURGE_UNUSED = "purge_unused"
AUDIT_SAVE_AS = "audit_save_as"
CLOSE_MODEL = "close_model"

ARCHIVE_CLOSE_VOCABULARY = (
    ARCHIVE_FILE,
    PURGE_UNUSED,
    AUDIT_SAVE_AS,
    CLOSE_MODEL,
)


def make_op(kind, target, args, confidence=1.0, rationale=""):
    """An operation emitted by Propose.

    kind        one of the vocabulary constants above
    target      a target dict (see above)
    args        dict, schema per kind, validated in aecflow/ops/
    confidence  0.0-1.0. Always 1.0 while Propose is deterministic.
    rationale   display-only string shown at gate G2. Never reaches the API.
    """
    return {
        "kind": kind,
        "target": target,
        "args": args,
        "confidence": confidence,
        "rationale": rationale,
    }


def validate_op(op, vocabulary):
    """Structural validation of an op. Returns a list of error strings.

    Per-kind argument validation lives with each kind's executor in
    aecflow/ops/; this checks only the envelope.
    """
    errors = []

    kind = op.get("kind")
    if kind not in vocabulary:
        errors.append("unknown op kind: {0}".format(kind))

    target = op.get("target") or {}
    target_kind = target.get("kind")
    if target_kind not in _TARGET_KINDS:
        errors.append("unknown target kind: {0}".format(target_kind))
    elif target_kind == TARGET_ELEMENT and not target.get("uid"):
        errors.append("element target missing uid")
    elif target_kind == TARGET_PATH and not target.get("path"):
        errors.append("path target missing path")

    # Invariant 3: an ElementId must never survive into a contract.
    if "element_id" in target or "id" in target:
        errors.append("target carries an ElementId; use UniqueId only")

    if not isinstance(op.get("args"), dict):
        errors.append("args must be a dict")

    confidence = op.get("confidence")
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        errors.append("confidence must be a number in [0.0, 1.0]")

    return errors


# --------------------------------------------------------------------------
# Stage payloads
# --------------------------------------------------------------------------


def make_snapshot(model, filesystem, captured_at):
    """The only view of the world that stages 2-4 are permitted to see.

    model       ModelSnapshot -- see extract.py. Read from the Revit API.
      .doc_title .doc_path .central_path .is_workshared .is_read_only
      .project    {number, name, client, status}
      .revisions  [{uid, sequence, revision_number, date, description, issued}]
      .sheets     [{uid, number, name, is_placeholder, view_count,
                    revision_uids, current_revision_uid, titleblock_size,
                    series}]

    'series' is the sheet's package membership -- the Sheet Collection in
    Revit 2025, or a print set / shared parameter in a fallback model. It
    scopes what an export run covers; each sheet then exports at its own
    current revision, so one folder legitimately holds mixed revisions.

    filesystem  FsSnapshot -- read from disk. Archive decisions depend on
                what is already there, so it belongs in the Snapshot too.
      .project_root .export_root .roots_writable
      .existing   [{path, size, mtime, parsed: {sheet_number, revision}}]

    Both are deterministic reads. Nothing after Extract touches the Document
    or the filesystem for reads (Hard Invariant 6).
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "captured_at": captured_at,
        "model": model,
        "filesystem": filesystem,
    }


def make_intent(snapshot_hash, ops, proposer):
    """Output of Propose.

    proposer  {"name": str, "version": str, "deterministic": bool}
              Recorded so the audit trail distinguishes a rules-engine run
              from a future model-backed one.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_hash": snapshot_hash,
        "proposer": proposer,
        "ops": ops,
    }


def make_changeset(snapshot_hash, operations, dropped):
    """Output of Resolve: fully-bound operations, ready to execute.

    operations  [{op_id, kind, target, args, source_op}] -- every value
                coerced to its Revit type, every UniqueId rebound against the
                live document, every path absolute.
    dropped     [{source_op, reason}] -- anything that could not be fully
                bound. Dropped with a recorded reason, never guessed at.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_hash": snapshot_hash,
        "operations": operations,
        "dropped": dropped,
    }


PASS = "pass"
WARN = "warn"
BLOCK = "block"

_SEVERITY = {PASS: 0, WARN: 1, BLOCK: 2}


def make_verdict(results):
    """Output of Check.

    results  [{op_id, verdict, rule_id, message}]

    The set-level verdict is the worst individual verdict. A single block
    blocks the whole set -- no partial apply (Hard Invariant 7).
    """
    worst = PASS
    for result in results:
        if _SEVERITY[result["verdict"]] > _SEVERITY[worst]:
            worst = result["verdict"]
    return {
        "schema_version": SCHEMA_VERSION,
        "set_verdict": worst,
        "results": results,
    }
