"""Link-safe local filesystem operations for ESRA state and outputs."""

from __future__ import annotations

import contextlib
import os
import stat
import sys
from pathlib import Path

DESCRIPTOR_PATHS = os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")


def _system_alias(path: Path) -> bool:
    return (sys.platform == "darwin" and str(path) in {"/tmp", "/var", "/etc"}
            and os.readlink(path) in {f"/private{path}", f"private{path}"})


def refuse_symlink(path: Path) -> None:
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if (item.is_symlink() or getattr(item, "is_junction", lambda: False)()) and not (item != path and _system_alias(item)):
            raise ValueError(f"refusing symlinked path: {item}")


@contextlib.contextmanager
def _parent_fd(path: Path, create: bool = False):
    refuse_symlink(path)
    path = Path(os.path.abspath(path))
    if sys.platform == "darwin" and len(path.parts) > 2:
        alias = Path("/") / path.parts[1]
        if alias.is_symlink() and _system_alias(alias):
            path = Path("/private") / path.relative_to("/")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open("/", flags)
    try:
        for part in path.parent.parts[1:]:
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor, path.name
    finally:
        os.close(descriptor)


def secure_dir(path: Path) -> Path:
    refuse_symlink(path)
    if not DESCRIPTOR_PATHS:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        refuse_symlink(path)
        path.chmod(0o700)
        return path
    with _parent_fd(path / ".esra-placeholder", create=True) as (descriptor, _):
        os.fchmod(descriptor, 0o700)
    return path


def secure_open(path: Path, flags: int, mode: int = 0o600) -> int:
    """Open without following links; validate before destructive truncation."""
    open_flags = (flags & ~os.O_TRUNC) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    if DESCRIPTOR_PATHS:
        with _parent_fd(path, create=bool(flags & os.O_CREAT)) as (parent, name):
            descriptor = os.open(name, open_flags, mode, dir_fd=parent)
    else:
        refuse_symlink(path)
        if flags & os.O_CREAT:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        refuse_symlink(path)
        descriptor = os.open(path, open_flags, mode)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError(f"refusing non-regular or hardlinked file: {path}")
        if flags & os.O_TRUNC:
            os.ftruncate(descriptor, 0)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise
