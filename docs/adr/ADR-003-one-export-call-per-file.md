# ADR-003 — One export call per output file

**Status:** **Accepted — confirmed by measurement 2026-07-29**

## Context

The naming convention requires exact filenames: `12345-A101-RevP04.pdf`. Revit's export API
does not straightforwardly provide them.

**PDF.** `PDFExportOptions` behaves differently depending on `Combine`:

| `Combine` | Filename source | Control |
|---|---|---|
| `true` | `PDFExportOptions.FileName` | Exact |
| `false` | `NamingRule` — `FileName` is ignored | Parameter-driven only |

`NamingRule` is an `IList<TableCellCombinedParameterData>`: the filename is assembled from
**Revit parameters** (CategoryId, ParamId, Prefix, Suffix, Separator), not from a string. Our
convention is only expressible if Project Number, Sheet Number and Current Revision all
resolve as sheet parameters, combined with literal prefixes.

That path has two documented failure modes. `"The naming rule cannot be applied to the
selected views or sheets"` is a common error, most often when a parameter is taken from the
Views category rather than Sheets. And `IsValidNamingRule()` is reported to return `true`
unconditionally, so the validation hook cannot be trusted.

**DWG.** `Document.Export(folder, name, views, DWGExportOptions)` treats `name` as "the name
of a single file **or a prefix** for a set of files". Autodesk's documentation states the API
"does not provide full access to directly and completely control the output file name" for
multi-view exports. A batch export yields `Prefix Floor Plan Level 1.dwg`.

**IFC and RVT.** Both take an explicit folder and filename. No difficulty.

## Decision

**Export one file per API call, with an explicit filename.**

- PDF — `Combine = true` with a **single-sheet** list. Produces a one-page PDF named exactly
  as `FileName` specifies, bypassing `NamingRule` entirely.
- DWG — one sheet per `Export` call, `name` being the full filename.
- IFC / RVT — explicit filename, as the API already allows.

`NamingRule` is not used anywhere in the tool.

## Consequences

**Good.** Filenames are deterministic and match the convention exactly, with no post-export
rename step and no dependency on which parameters happen to exist in a given project. It also
maps cleanly onto the op vocabulary already chosen in §4 of the design doc — one op, one
file, one Check verdict, one audit line — so per-op progress reporting and cancellation
between ops come for free.

**Cost.** A 64-sheet issue becomes 64 `Export` calls rather than one. Per-call overhead is
unknown and may be significant.

**Measured 2026-07-29.** Revit 2025 (25.4.60.9), Snowdon Towers sample model, 55 sheets,
non-workshared, local disk.

| Test | Result |
|---|---|
| One sheet, `Combine=true`, `FileName="12345-A100-RevP04"` | Produced exactly `12345-A100-RevP04.pdf` — **exact match** |
| 10 sheets, one call each | 19.6 s |
| 10 sheets, one batch call (`Combine=false`) | 16.0 s |
| Ratio | Per-sheet **1.2× slower** |
| Extrapolated to 64 sheets | ~126 s |

Names Revit chose for itself in batch mode: `Sheet-Fifth Floor Plan.pdf`,
`Sheet-First Floor Plan.pdf`, `Sheet-Green Roof.pdf`. No project number, no sheet number, no
revision — unusable, exactly as the documentation predicted.

The decision holds comfortably. Per-sheet costs roughly 20% more wall time and buys correct
filenames outright; two minutes for a 64-sheet issue is well inside what the progress bar
makes tolerable. `DRY_RUN` was flipped to `False` on the strength of this.

**Fallback, now unnecessary.** Batch export then rename remains theoretically available —
every destination path is known before the run begins, so the rename would be deterministic —
but it widens the failure window between writing and naming for a 20% saving. Not worth it.

**Still unmeasured.** The sample model is not workshared and sits on local disk. Per-sheet
cost over a network path, and on a workshared central, could differ materially. Worth
re-running the probe on a real project model before anyone relies on the 126 s figure.

**Incidental confirmation.** The characters Revit rejects in a naming rule
(`\ / : * ? " < > |`) are exactly the set `naming.sanitise()` already substitutes, which
validates Check rule R5 against real API behaviour.

## References

- [PDFExportOptions.Combine, Revit 2025](https://rvtdocs.com/2025/65f97585-8c92-b52e-93dd-8a6b4bfc5a1a)
- [PDFExportOptions.FileName](https://www.revitapidocs.com/2022/26f04248-487f-bb5a-d04a-95c7b63a4394.htm)
- [PDFExportOptions.SetNamingRule](https://www.revitapidocs.com/2023/87d53eae-bd18-3ff0-e5e6-38de5a018cdf.htm)
- [IsValidNamingRule always returns true](https://forums.autodesk.com/t5/revit-api-forum/revit-2022-pdfexportoptions-isvalidnamingrule-always-return-true/td-p/11119662)
- [The naming rule cannot be applied](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/The-naming-rule-cannot-be-applied-when-exporting-Revit-Sheets-to-PDF-with-custom-naming-rule.html)
- [File names for exported files](https://knowledge.autodesk.com/support/revit-products/learn-explore/caas/CloudHelp/cloudhelp/2016/ENU/Revit-DocumentPresent/files/GUID-216E3E48-E30D-4B88-A3DA-78F360581982-htm.html)
- [Document.Export (DWG)](https://www.revitapidocs.com/2023/44ee91ff-c9f3-7df5-b8c0-81c17ac75dc7.htm)
- [pyrevit.interop.ifc](https://docs.pyrevitlabs.io/reference/pyrevit/interop/ifc/)
