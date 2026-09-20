"""Streaming FM config access. No DOM, reserialization or whole-file reads.

Expat supplies structural validation and byte offsets. All existing content is
copied as bytes, so only the inserted/removed mapping can differ.
"""

import codecs
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from xml.parsers import expat

from core.filesystem import (
    assert_unchanged,
    copy_durable,
    fingerprint,
    flush_file,
    folder_lock,
    temporary_path,
)
from core.validation import validate_player_id

CHUNK_SIZE = 64 * 1024
TAIL_ERROR = "Could not verify the end of the maps list in config.xml. No face or config files were changed."
DEFAULT_CONFIG = (
    '<?xml version="1.0" encoding="UTF-8"?>\r\n'
    "<record>\r\n"
    '    <boolean id="preload" value="false"/>\r\n'
    '    <boolean id="amap" value="false"/>\r\n'
    '    <list id="maps">\r\n'
    "    </list>\r\n"
    "</record>\r\n"
).encode("utf-8")


class ConfigError(ValueError):
    pass


class _Found(Exception):
    pass


@dataclass
class _Scan:
    maps_count: int = 0
    maps_end: int = -1
    root_end: int = -1
    final_child_maps: bool = False
    matches: int = 0
    match_start: int = -1
    match_end: int = -1
    last_record_start: int = -1
    match_to: str | None = None


@dataclass
class _Layout:
    encoding: str
    newline: str
    insertion: int
    indent: str
    scan: _Scan


@dataclass
class PreparedConfig:
    """An already validated temp file. Caller holds the folder lock."""

    destination: Path
    temporary: Path
    original: tuple | None

    def commit(self) -> None:
        assert_unchanged(self.destination, self.original)
        os.replace(self.temporary, self.destination)

    def discard(self) -> None:
        self.temporary.unlink(missing_ok=True)


def _scan_file(path: Path, player_id: str | None = None, *, early: bool = False) -> _Scan:
    result = _Scan()
    parser = expat.ParserCreate()
    stack: list[str] = []
    in_maps = False
    active_target = False

    def reject_dtd(*args):
        raise ConfigError("DTD/entity declarations are unsupported. config.xml was not changed.")

    def start(name, attrs):
        nonlocal in_maps, active_target
        if not stack and name != "record":
            raise ConfigError(TAIL_ERROR)
        if len(stack) >= 64:
            raise ConfigError("config.xml nesting is too deep. File was not changed.")
        if len(stack) == 1:
            in_maps = name == "list" and attrs.get("id") == "maps"
            result.final_child_maps = in_maps
            if in_maps:
                result.maps_count += 1
        if in_maps and len(stack) == 2 and name == "record":
            result.last_record_start = parser.CurrentByteIndex
            active_target = player_id is not None and attrs.get("from") == player_id
            if active_target:
                result.match_to = attrs.get("to", "")
                if early:
                    raise _Found
                result.matches += 1
                result.match_start = parser.CurrentByteIndex
        stack.append(name)

    def end(name):
        nonlocal in_maps, active_target
        if in_maps and len(stack) == 3 and name == "record" and active_target:
            result.match_end = parser.CurrentByteIndex
            active_target = False
        if in_maps and len(stack) == 2:
            result.maps_end = parser.CurrentByteIndex
            in_maps = False
        if len(stack) == 1:
            result.root_end = parser.CurrentByteIndex
        stack.pop()

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.StartDoctypeDeclHandler = reject_dtd
    parser.EntityDeclHandler = reject_dtd
    parser.ExternalEntityRefHandler = reject_dtd
    try:
        with path.open("rb") as stream:
            # readline stops early lookups at the matching line. The size cap
            # also bounds input memory for unusually long lines and UTF-16.
            while data := stream.readline(CHUNK_SIZE) if early else stream.read(CHUNK_SIZE):
                parser.Parse(data, False)
            parser.Parse(b"", True)
    except _Found:
        result.matches = 1
        return result
    except (expat.ExpatError, LookupError, UnicodeError, ValueError) as error:
        if isinstance(error, ConfigError):
            raise
        raise ConfigError(f"config.xml is invalid or uses an unsupported encoding: {error}") from error
    return result


def _encoding(path: Path) -> str:
    with path.open("rb") as stream:
        header = stream.read(512)
    if header.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        raise ConfigError("UTF-32 config files are unsupported. File was not changed.")
    if header.startswith(codecs.BOM_UTF16_LE) or header.startswith(b"<\x00"):
        return "utf-16-le"
    if header.startswith(codecs.BOM_UTF16_BE) or header.startswith(b"\x00<"):
        return "utf-16-be"
    declaration = re.search(rb'<\?xml\s[^?]*encoding\s*=\s*[\'"]([^\'"]+)', header)
    try:
        encoding = codecs.lookup(declaration[1].decode("ascii") if declaration else "utf-8").name
    except (LookupError, UnicodeError) as error:
        raise ConfigError("Unsupported XML encoding. File was not changed.") from error
    if encoding == "utf-8-sig":
        encoding = "utf-8"
    if "<record>\r\n".encode(encoding) != b"<record>\r\n":
        raise ConfigError("Unsupported XML encoding. File was not changed.")
    return encoding


def _line_prefix(path: Path, offset: int, encoding: str) -> tuple[int, str]:
    start = max(0, offset - CHUNK_SIZE)
    if encoding.startswith("utf-16"):
        start -= start % 2
    with path.open("rb") as stream:
        stream.seek(start)
        before = stream.read(offset - start)
    marker = "\n".encode(encoding)
    pos = before.rfind(marker)
    if pos < 0 and start:
        raise ConfigError(TAIL_ERROR)
    prefix = before[pos + len(marker) :] if pos >= 0 else before
    try:
        text = prefix.decode(encoding)
    except UnicodeError as error:
        raise ConfigError(TAIL_ERROR) from error
    if text.strip(" \t"):
        raise ConfigError("The maps list and mapping records must use separate lines. File was not changed.")
    return offset - len(prefix), text


def _inspect(path: Path, player_id: str | None = None) -> _Layout:
    scan = _scan_file(path, player_id)
    if scan.maps_count != 1 or not scan.final_child_maps or scan.maps_end < 0 or scan.root_end < 0:
        raise ConfigError(TAIL_ERROR)
    encoding = _encoding(path)
    insertion, closing_indent = _line_prefix(path, scan.maps_end, encoding)
    with path.open("rb") as stream:
        stream.seek(scan.maps_end)
        tail = stream.read(CHUNK_SIZE + 1)
    if len(tail) > CHUNK_SIZE:
        raise ConfigError(TAIL_ERROR)
    try:
        tail_text = tail.decode(encoding)
    except UnicodeError as error:
        raise ConfigError(TAIL_ERROR) from error
    if not re.fullmatch(r"</list>[ \t]*(\r?\n)[ \t]*</record>[ \t\r\n]*", tail_text):
        raise ConfigError(TAIL_ERROR)
    # Use the newline immediately preceding </list>, not the OS default.
    with path.open("rb") as stream:
        stream.seek(max(0, insertion - 4))
        preceding = stream.read(min(4, insertion))
    newline = "\r\n" if preceding.endswith("\r\n".encode(encoding)) else "\n"
    indent = closing_indent + ("\t" if "\t" in closing_indent else "    ")
    if scan.last_record_start >= 0:
        _, indent = _line_prefix(path, scan.last_record_start, encoding)
    return _Layout(encoding, newline, insertion, indent, scan)


def _removal_range(path: Path, layout: _Layout) -> tuple[int, int]:
    scan, encoding = layout.scan, layout.encoding
    start, _ = _line_prefix(path, scan.match_start, encoding)
    with path.open("rb") as stream:
        stream.seek(scan.match_end)
        after = stream.read(CHUNK_SIZE)
    # Expat points past '/>' for empty tags, or at '</record>' otherwise.
    closing = "</record>".encode(encoding)
    end = scan.match_end
    if after.startswith(closing):
        end += len(closing)
        after = after[len(closing) :]
    newline = "\n".encode(encoding)
    index = after.find(newline)
    if index < 0:
        raise ConfigError("Mapping is not on a removable line. File was not changed.")
    suffix = after[: index + len(newline)]
    if suffix.decode(encoding).strip():
        raise ConfigError("Mapping shares a line with other XML content. File was not changed.")
    return start, end + len(suffix)


def _copy_bytes(source, destination, count: int) -> None:
    while count:
        chunk = source.read(min(count, CHUNK_SIZE))
        if not chunk:
            raise ConfigError("config.xml changed during copying. File was not changed.")
        destination.write(chunk)
        count -= len(chunk)


class ConfigManager:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def mapping_exists(self, player_id: str) -> bool:
        return self.mapping_target(player_id) is not None

    def mapping_target(self, player_id: str) -> str | None:
        """Read the exact record's target without scanning past its first hit."""
        player_id = validate_player_id(player_id)
        if not self.path.exists():
            return None
        return _scan_file(self.path, player_id, early=True).match_to

    @staticmethod
    def portrait_target(player_id: str, *, newgen: bool = False) -> str:
        player_id = validate_player_id(player_id)
        return f"graphics/pictures/person/{'r-' if newgen else ''}{player_id}/portrait"

    def validate_tail_structure(self) -> bool:
        try:
            _inspect(self.path)
            return True
        except (ConfigError, OSError):
            return False

    def _backup(self, expected: tuple) -> None:
        temporary = temporary_path(self.path.parent, ".backup")
        try:
            copy_durable(self.path, temporary)
            assert_unchanged(self.path, expected)
            os.replace(temporary, self.path.with_name(self.path.name + ".bak"))
        finally:
            temporary.unlink(missing_ok=True)

    def prepare_add(self, player_id: str, *, newgen: bool = False) -> PreparedConfig | None:
        """Stage under folder_lock; return None without writes for existing IDs."""
        player_id = validate_player_id(player_id)
        original = fingerprint(self.path)
        if original is not None and self.mapping_exists(player_id):
            return None
        layout = _inspect(self.path, player_id) if original is not None else None
        return self._prepare(player_id, original, layout, remove=False, newgen=newgen)

    def prepare_remove(self, player_id: str) -> PreparedConfig | None:
        player_id = validate_player_id(player_id)
        original = fingerprint(self.path)
        if original is None or not self.mapping_exists(player_id):
            return None
        layout = _inspect(self.path, player_id)
        if layout.scan.matches != 1:
            raise ConfigError("Multiple mappings for this Player ID. Resolve duplicates before removing it.")
        return self._prepare(player_id, original, layout, remove=True)

    def prepare_newgen_repair(self, player_id: str) -> PreparedConfig | None:
        """Explicit repair only: change this ID's legacy portrait target to r-ID.

        This is deliberately separate from add/replace: existing mappings are
        never silently rewritten by an ordinary image installation.
        """
        player_id = validate_player_id(player_id)
        original = fingerprint(self.path)
        if original is None:
            return None
        layout = _inspect(self.path, player_id)
        scan = layout.scan
        if not scan.matches:
            return None
        if scan.matches != 1:
            raise ConfigError("Multiple mappings for this Player ID. Resolve duplicates before repairing it.")
        desired = self.portrait_target(player_id, newgen=True)
        if scan.match_to == desired:
            return None
        if scan.match_to != self.portrait_target(player_id):
            raise ConfigError("This record has a custom target. It cannot be repaired automatically.")
        length = scan.match_end - scan.match_start
        if length <= 0 or length > CHUNK_SIZE:
            raise ConfigError("Mapping is too large to repair safely. File was not changed.")
        with self.path.open("rb") as stream:
            stream.seek(scan.match_start)
            record = stream.read(length).decode(layout.encoding)
        # Tokenize the opening tag's attributes, preserving every surrounding
        # quote, space, newline and byte. XML syntax was already validated.
        cursor = len("<record")
        attribute = re.compile(r'\s+([\w:.-]+)\s*=\s*([\'"])(.*?)\2', re.DOTALL)
        while match := attribute.match(record, cursor):
            if match[1] == "to":
                start = scan.match_start + len(record[: match.start(3)].encode(layout.encoding))
                end = scan.match_start + len(record[: match.end(3)].encode(layout.encoding))
                correction = (start, end, desired.encode(layout.encoding))
                return self._prepare(
                    player_id, original, layout, remove=False, newgen=True, correction=correction
                )
            cursor = match.end()
        raise ConfigError("Could not identify the mapping target safely. File was not changed.")

    def _prepare(self, player_id, original, layout, *, remove, newgen=False, correction=None):
        # Validate the removal range before creating backup or temp files.
        removed = _removal_range(self.path, layout) if remove else None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        if temporary.exists():
            raise ConfigError(
                f"{temporary.name} already exists (possibly from an interrupted run). "
                "Move it aside after checking config.xml, then try again."
            )
        if original is not None:
            self._backup(original)
        created = False
        try:
            with temporary.open("xb") as destination:
                created = True
                if layout is None:
                    marker = b"    </list>"
                    record = self._record(player_id, "        ", "\r\n", newgen=newgen).encode("utf-8")
                    destination.write(DEFAULT_CONFIG.replace(marker, record + marker, 1))
                else:
                    with self.path.open("rb") as source:
                        if correction:
                            start, end, replacement = correction
                            _copy_bytes(source, destination, start)
                            destination.write(replacement)
                            source.seek(end)
                        elif remove:
                            start, end = removed
                            _copy_bytes(source, destination, start)
                            source.seek(end)
                        else:
                            _copy_bytes(source, destination, layout.insertion)
                            destination.write(
                                self._record(player_id, layout.indent, layout.newline, newgen=newgen).encode(
                                    layout.encoding
                                )
                            )
                        shutil.copyfileobj(source, destination, CHUNK_SIZE)
                flush_file(destination)
            checked = _inspect(temporary, player_id)
            if checked.scan.matches != (0 if remove else 1):
                raise ConfigError("Temporary config validation failed. Original config was not changed.")
            if not remove and checked.scan.match_to != self.portrait_target(player_id, newgen=newgen):
                raise ConfigError(
                    "Temporary mapping target validation failed. Original config was not changed."
                )
            assert_unchanged(self.path, original)
            return PreparedConfig(self.path, temporary, original)
        except BaseException:
            if created:
                temporary.unlink(missing_ok=True)
            raise

    @classmethod
    def _record(cls, player_id: str, indent: str, newline: str, *, newgen=False) -> str:
        return (
            f'{indent}<record from="{player_id}" '
            f'to="{cls.portrait_target(player_id, newgen=newgen)}"/>{newline}'
        )

    def add_mapping(self, player_id: str, *, newgen: bool = False) -> bool:
        validate_player_id(player_id)
        with folder_lock(self.path.parent):
            prepared = self.prepare_add(player_id, newgen=newgen)
            if prepared is None:
                return False
            try:
                prepared.commit()
                return True
            finally:
                prepared.discard()

    def repair_newgen_mapping(self, player_id: str) -> bool:
        validate_player_id(player_id)
        if not self.mapping_exists(player_id):
            return False
        with folder_lock(self.path.parent):
            prepared = self.prepare_newgen_repair(player_id)
            if prepared is None:
                return False
            try:
                prepared.commit()
                return True
            finally:
                prepared.discard()

    def remove_mapping(self, player_id: str) -> bool:
        validate_player_id(player_id)
        # A missing mapping is a truly read-only operation.
        if not self.mapping_exists(player_id):
            return False
        with folder_lock(self.path.parent):
            prepared = self.prepare_remove(player_id)
            if prepared is None:
                return False
            try:
                prepared.commit()
                return True
            finally:
                prepared.discard()
