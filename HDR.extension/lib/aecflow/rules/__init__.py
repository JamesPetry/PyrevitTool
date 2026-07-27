# -*- coding: utf-8 -*-
"""Check rules -- one pure function per file, over (snapshot, changeset).

Export Issue rule set (design doc section 6):

    R1 no_duplicate_destinations   block
    R2 no_overwrite                block   -- makes the two-tool split safe
    R3 target_sheet_exists         block
    R4 path_within_limit           block
    R5 filename_is_legal           block
    R6 export_root_writable        block
    R7 sheet_has_placed_views      warn
    R8 uniform_issue_revision      warn
"""
