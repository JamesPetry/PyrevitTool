# -*- coding: utf-8 -*-
"""CHECK -- evaluate a ChangeSet against the rule set.

Rules are pure functions over (snapshot, changeset), one per function in
rules/. A block on any operation blocks the whole set (Hard Invariant 7).

Must not import Autodesk.Revit.DB (Hard Invariant 6).
"""

from aecflow import contracts
from aecflow import rules

_SEVERITY = {contracts.PASS: 0, contracts.WARN: 1, contracts.BLOCK: 2}


def evaluate(snapshot, changeset, rule_set=None):
    """(Snapshot, ChangeSet) -> Verdict.

    Every rule runs against every op, even after one has failed: the review
    table should show all the reasons a row is flagged, not just the first.
    """
    findings = []
    for rule in (rule_set or rules.ALL_RULES):
        findings.extend(rule(snapshot, changeset) or [])

    # Ops with no finding pass. Ops with several keep their worst.
    worst = {}
    for finding in findings:
        current = worst.get(finding["op_id"])
        if current is None or _SEVERITY[finding["verdict"]] > _SEVERITY[current["verdict"]]:
            worst[finding["op_id"]] = finding

    results = []
    for op in changeset["operations"]:
        finding = worst.get(op["op_id"])
        if finding is None:
            results.append({
                "op_id": op["op_id"],
                "verdict": contracts.PASS,
                "rule_id": None,
                "message": "",
            })
        else:
            results.append(finding)

    verdict = contracts.make_verdict(results)
    verdict["findings"] = findings
    return verdict


def approved_operations(changeset, verdict, selected_ids=None):
    """Operations cleared to run: passing, selected, and with a destination.

    Warn rows are excluded unless explicitly selected at G2 -- the user opts
    in, never out. A blocked set returns nothing regardless of selection.
    """
    if verdict["set_verdict"] == contracts.BLOCK:
        return []

    by_id = dict((r["op_id"], r) for r in verdict["results"])
    approved = []
    for op in changeset["operations"]:
        if not op["args"].get("dest_path"):
            continue
        result = by_id.get(op["op_id"])
        if result is None:
            continue
        if selected_ids is None:
            if result["verdict"] == contracts.PASS:
                approved.append(op)
        elif op["op_id"] in selected_ids:
            approved.append(op)
    return approved
