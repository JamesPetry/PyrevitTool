# -*- coding: utf-8 -*-
"""Human-in-the-loop gates.

    g1_scope    what the tool will look at, before Extract
    g2_diff     the destination table -- nothing commits without passing it
    g3_summary  what was written, where the audit landed, how to undo it

G2 is where this architecture earns practitioner trust, so it is built first
and given the most care. pyRevit's forms carry it without a WPF build.
"""
