# Workstation UI Shell Recovery Fix

Corrects a layout regression caused by legacy global `aside`, `.content`, and responsive rules colliding with the modernized workstation shell.

The fix:
- scopes sidebar and main-canvas geometry to `.workstation-shell`;
- guarantees the main route canvas has a nonzero width;
- prevents the desktop sidebar from overlaying the main page;
- restores correct mobile drawer behavior;
- adds a visible per-route React error boundary instead of a blank workspace.

No backend API, database, scanner, opportunity, intelligence, or execution behavior is changed.
