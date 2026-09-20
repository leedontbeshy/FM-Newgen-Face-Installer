"""Read a supplied sample, mutate only a temporary COPY, and report evidence."""

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config_manager import ConfigManager


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sample", type=Path)
    parser.add_argument("--lookup-id", help="Optionally time an exact lookup for this player ID")
    args = parser.parse_args()
    sample = args.sample.resolve()
    before = digest(sample)
    stamp = sample.stat().st_mtime_ns
    with sample.open("rb") as stream:
        lines = sum(1 for _ in stream)
    report = {"sample": str(sample), "bytes": sample.stat().st_size, "lines": lines, "sha256": before}
    with tempfile.TemporaryDirectory(prefix="fm-sample-check-") as directory:
        copy = Path(directory) / "config.xml"
        shutil.copyfile(sample, copy)
        manager = ConfigManager(copy)
        assert manager.validate_tail_structure(), "Sample does not have a supported maps tail"
        if args.lookup_id is not None:
            start = time.perf_counter()
            report["lookup_found"] = manager.mapping_exists(args.lookup_id)
            report["lookup_seconds"] = round(time.perf_counter() - start, 4)
        player_id = "2002999999"
        while manager.mapping_exists(player_id):
            player_id = str(int(player_id) + 1)
        start = time.perf_counter()
        assert manager.add_mapping(player_id)
        report["add_seconds"] = round(time.perf_counter() - start, 4)
        after_add = digest(copy)
        added_stamp = copy.stat().st_mtime_ns
        assert not manager.add_mapping(player_id)
        assert digest(copy) == after_add and copy.stat().st_mtime_ns == added_stamp
        start = time.perf_counter()
        assert manager.remove_mapping(player_id)
        report["remove_seconds"] = round(time.perf_counter() - start, 4)
        assert digest(copy) == before, "Unrelated bytes changed after add/remove roundtrip"
        report["roundtrip_byte_identical"] = True
    assert digest(sample) == before and sample.stat().st_mtime_ns == stamp
    report["original_untouched"] = True
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
