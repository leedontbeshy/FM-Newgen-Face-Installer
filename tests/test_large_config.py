"""Synthetic scale tests. No production config is used."""

import hashlib
import time

import pytest

from core.config_manager import ConfigManager


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@pytest.mark.large
@pytest.mark.parametrize("count", [10_000, 100_000, 250_000, 500_000])
def test_streaming_large_file(tmp_path, count):
    path = tmp_path / "config.xml"
    with path.open("wb") as stream:
        stream.write(b'<record>\r\n\t<list id="maps">\r\n')
        for player_id in range(1, count + 1):
            stream.write(
                f'\t\t<record from="{player_id}" to="graphics/pictures/person/{player_id}/portrait"/>\r\n'.encode()
            )
        stream.write(b"\t</list>\r\n</record>")
    before = digest(path)
    manager = ConfigManager(path)
    timing = {}
    for label, player_id in [
        ("first", "1"),
        ("middle", str(count // 2)),
        ("last", str(count)),
        ("missing", "999999999"),
    ]:
        start = time.perf_counter()
        assert manager.mapping_exists(player_id) == (label != "missing")
        timing[label] = round(time.perf_counter() - start, 4)
    start = time.perf_counter()
    assert manager.add_mapping("999999999")
    timing["add"] = round(time.perf_counter() - start, 4)
    start = time.perf_counter()
    assert manager.repair_newgen_mapping("999999999")
    timing["repair"] = round(time.perf_counter() - start, 4)
    assert manager.mapping_target("999999999") == "graphics/pictures/person/r-999999999/portrait"
    added_digest, stamp = digest(path), path.stat().st_mtime_ns
    assert not manager.add_mapping("999999999")
    assert digest(path) == added_digest and path.stat().st_mtime_ns == stamp
    start = time.perf_counter()
    assert manager.remove_mapping("999999999")
    timing["remove"] = round(time.perf_counter() - start, 4)
    assert digest(path) == before  # proves every unrelated byte/order survived
    print(f"\n{count:,} mappings (seconds): {timing}")
