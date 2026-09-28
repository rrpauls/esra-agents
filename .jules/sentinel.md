## 2024-10-25 - Path Traversal bypass via PurePosixPath
**Vulnerability:** A path traversal check using `PurePosixPath` in `safe_relative` can be bypassed by using backslashes (`\`) instead of forward slashes (`/`), since POSIX paths do not recognize backslashes as path separators.
**Learning:** Functions designed to sanitize paths must explicitly account for multiple path separator styles (like Windows backslashes) when processing input, especially if the sanitized path might later be used on platforms where those separators are active.
**Prevention:** Explicitly reject backslashes (`\`) in path validation before passing the string to Posix-specific path objects, or use cross-platform path validation strategies.
