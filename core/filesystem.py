"""Small, bounded filesystem primitives shared by core operations."""

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path


class FileChangedError(RuntimeError):
    pass


def fingerprint(path: Path) -> tuple | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    if not path.is_file() or path.is_symlink():
        raise OSError(f"Expected a regular file, not a directory or link: {path}")
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def assert_unchanged(path: Path, expected: tuple | None) -> None:
    if fingerprint(path) != expected:
        raise FileChangedError(f"{path.name} changed while this operation was pending. Please try again.")


def flush_file(stream) -> None:
    stream.flush()
    os.fsync(stream.fileno())


def temporary_path(folder: Path, suffix: str) -> Path:
    fd, name = tempfile.mkstemp(prefix=".fm-face-", suffix=suffix, dir=folder)
    os.close(fd)
    return Path(name)


def copy_durable(source: Path, destination: Path) -> None:
    with source.open("rb") as src, destination.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=128 * 1024)
        flush_file(dst)


@contextmanager
def folder_lock(folder: Path):
    """OS lock: released even if a process crashes; the tiny lock file stays."""
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ".fm-face-installer.lock").open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise OSError(
                "Another installer operation is using this face folder. Try again shortly."
            ) from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
