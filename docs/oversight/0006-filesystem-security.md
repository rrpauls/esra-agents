# Filesystem security hardening

Reject dangling and ancestor symlinks before file operations, and open writable
files through directory descriptors without following links. Reject hardlinked
or non-regular output files before truncation. Preserve only the known macOS
system aliases `/tmp`, `/var`, and `/etc` when they point into `/private`.

Validate snapshot identifiers and trees before rollback; reject unsafe ZIP
member paths and symlink members; refuse linked packaging inputs and outputs.
Keep prior portable distribution work in the release commit. Test traversal,
links, unchanged external files, and valid workflow behavior before publishing.
