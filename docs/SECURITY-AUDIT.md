# Local security audit — 2026-09-30

Reviewed runtime state/output paths, controller promotion and rollback,
Hermes installation, OpenClaw subprocess construction, distribution builders,
archive validation, and the release workflow.

Fixed:

- Output/state guards checked only an existing final symlink. Dangling links
  and linked ancestors could redirect writes. Guards now check the complete
  path; POSIX file writes use directory descriptors and `O_NOFOLLOW`.
- Output truncation could overwrite another file through a hardlink. Outputs
  are checked as regular, singly linked files before truncation.
- Rollback trusted persisted revision paths and snapshot contents. Revision
  identifiers, snapshot availability, and snapshot links are now checked before
  restoring or deleting live content. Staging and pruning also reject links.
- Archive validation allowed unsafe extra members. Absolute paths, traversal,
  Windows drive/alternate-stream paths, backslashes, symlink entries, duplicate
  members, and archives over 100 MB uncompressed are rejected before inspection.
- Packaging could read linked sources or overwrite linked output files. Both
  input trees and outputs now reject links. The Hermes installer also checks
  destination ancestors and all copied source inputs, and creates its final
  destination exclusively.

Regression coverage includes external-file preservation, missing outputs,
linked state roots, changed skill roots, malicious snapshots, unsafe ZIP paths,
linked packaging inputs/outputs, and installer rejection.

Scope: local source review and tests, not a penetration test of native hosts.
No arbitrary sandbox is promised for operator-authorized experiment commands.
On systems without POSIX directory descriptors, path/junction checks are used;
concurrent path replacement there is not covered by the POSIX no-follow guarantee.
The controller and shell installer still require trusted, user-owned working
directories; they are not secure against an attacker controlling the same
account or concurrently replacing entire trees during promotion/install.
