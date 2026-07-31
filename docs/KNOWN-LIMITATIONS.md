# Known limitations

Written for anyone handing this to a practitioner. It says what has actually
been verified, what has not, and what to watch for.

**Status 2026-07-29:** working end to end on a sample model. 151 tests pass
without Revit. Audited for bugs; three were found and fixed (§3).

---

## 1. Verified

| | How |
|---|---|
| PDF export with exact filenames | Live run, Revit 2025, Snowdon Towers, 7 files |
| Per-sheet revision selection | Live run — mixed P03/P04 in one folder, correctly unflagged |
| Sheets with no revision are held back | Live run — 30 of 37 rows flagged and skipped |
| Filename convention and sanitisation | Unit tested, including round-trip through Archive's parser |
| The eight export and five archive rules | Unit tested, including that a block approves nothing |
| Archive supersession logic | Unit tested against a temp folder, including refusals |
| Degraded/malformed model data | 14 mutations fuzzed across both pipelines, no crashes |

---

## 2. NOT verified — read before relying on this

**DWG, IFC and detached RVT export have never been run.** Only PDF has. The
other three executors are written from the API documentation and compile, but
no file has ever come out of them. `save_detached_rvt` is the least trustworthy
of the three: it opens a second detached document, which nothing has exercised.

**Never run on a workshared model.** The sample is single-user. Element
ownership, sync state and central-file behaviour are entirely untested.

**Never run over a network path.** All testing was on local disk. This matters
for two reasons: the ~100 s figure for 64 sheets could be very different, and
rule R4 (the 260-character path limit) exists precisely for deep network paths
but has only ever been triggered synthetically.

**Never run by anyone other than its author.** No second person has followed
`SETUP.md` from scratch.

**Sheet Collections have never been seen populated.** Every sheet in the sample
returns `<None>`, so the tool falls back to sheet-number prefixes. The Sheet
Collection code path is unit tested with a fake, never against a real one.

---

## 3. Bugs found by audit on 2026-07-29

All three were live in code with 129 passing tests. Each is now pinned by a
regression test in `tests/test_regressions.py`.

### 3.1 Sheet numbers misparsed for hyphenated project numbers

`7765328-33-A-A101-RevP04.pdf` parsed its sheet number as `33-A-A101` rather
than `A101`. The separator is a hyphen and project numbers routinely contain
hyphens, so the boundary is genuinely ambiguous.

**Impact:** Archive would have grouped unrelated sheets together and superseded
the wrong files. This was live on files already exported from the sample model.

**Fix:** `parse_export_filename()` now takes the project number as context and
reads the revision from the last `-Rev`, which also allows revisions containing
hyphens (`P04-A`).

### 3.2 The no-overwrite rule could silently miss

R2 is what stops an export destroying a previous issue. It compared snapshot
paths against destination paths without normalising them, so a relative path on
one side and an absolute path on the other simply failed to match.

**Impact:** a previous issue could have been overwritten. It held in practice
only because the caller happened to pass an absolute root — the safety did not
hold on its own.

**Fix:** both rule sets canonicalise paths before comparing, and Extract
absolutises what it reads.

### 3.3 Meaningless filenames could be written

A sheet numbered `///` sanitises to `---`, which is non-empty and contains no
illegal characters, so it passed every rule and produced
`12345-----RevP04.pdf` — a real file identifying nothing, which Archive could
never parse back.

**Fix:** `naming.is_nameable()` requires at least one alphanumeric character,
and such sheets are now flagged and skipped exactly like unrevised ones.

---

## 4. Behaviour worth knowing

**Exports are not undoable with Ctrl+Z.** The tool writes files and never
touches the model, so there is nothing for Revit to undo. To reverse a run,
delete the export folder — G3 names it.

**Archive moves files, it never deletes them.** To reverse an archive run, move
the files back out of the dated folder.

**Only files matching the naming convention are ever touched.** Anything else
in the export folder is left alone, including files from other projects.

**Flagged rows are opt-in.** Nothing flagged is ever included by default; the
user has to ask for it.

**Seed Revisions modifies the model.** It is a development tool for sample
models only. Everything else in the suite is read-only against the model.

---

## 5. Recommended before wider release

1. Run all four formats once, not just PDF.
2. Run on a workshared model on a real network path.
3. Have somebody else follow `SETUP.md` cold.
4. Confirm with the practitioner whether Sheet Collections will be populated,
   or whether the prefix fallback is the intended grouping (design doc Q9).
