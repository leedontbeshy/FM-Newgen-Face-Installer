import codecs
from pathlib import Path
from unittest.mock import patch

import pytest

from core.config_manager import ConfigError, ConfigManager
from tests.conftest import config_bytes


def test_lookup_exact_and_ignores_comments(config_path):
    config_path.write_bytes(
        config_bytes(("1000",)).replace(
            b'    <list id="maps">', b'    <list id="maps">\r\n<!-- <record from="100" to="fake"/> -->'
        )
    )
    manager = ConfigManager(config_path)
    assert manager.mapping_exists("1000")
    assert not manager.mapping_exists("100")


def test_lookup_supports_attribute_order_and_single_quotes(config_path):
    config_path.write_bytes(
        b"<record>\n<list id='maps'>\n<record to='portrait' from='123'/>\n</list>\n</record>"
    )
    assert ConfigManager(config_path).mapping_exists("123")


def test_lookup_stops_before_invalid_suffix(config_path):
    config_path.write_bytes(b'<record>\n<list id="maps">\n<record from="123"/>\nBROKEN <')
    assert ConfigManager(config_path).mapping_exists("123")


def test_ignores_records_in_wrong_list(config_path):
    config_path.write_bytes(
        config_bytes(()).replace(
            b'    <list id="maps">',
            b'    <list id="other"><record from="123"/></list>\r\n    <list id="maps">',
        )
    )
    assert not ConfigManager(config_path).mapping_exists("123")


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("indent", ["        ", "\t\t"])
def test_add_preserves_every_other_byte_and_order(config_path, newline, indent):
    before = config_bytes(("500", "2", "90"), newline, indent)
    config_path.write_bytes(before)
    manager = ConfigManager(config_path)
    assert manager.add_mapping("123")
    added = (f'{indent}<record from="123" to="graphics/pictures/person/123/portrait"/>{newline}').encode()
    after = config_path.read_bytes()
    assert after == before.replace(b"    </list>", added + b"    </list>", 1)
    assert config_path.with_suffix(".xml.bak").read_bytes() == before
    assert manager.validate_tail_structure()
    assert not config_path.with_suffix(".xml.tmp").exists()


def test_add_existing_no_duplicate_no_rewrite(config_path):
    before, stat = config_path.read_bytes(), config_path.stat()
    assert not ConfigManager(config_path).add_mapping("100")
    assert config_path.read_bytes() == before
    assert config_path.stat().st_mtime_ns == stat.st_mtime_ns
    assert not config_path.with_suffix(".xml.bak").exists()


def test_create_missing(tmp_path):
    manager = ConfigManager(tmp_path / "new" / "config.xml")
    assert not manager.mapping_exists("123")
    assert manager.add_mapping("123")
    assert manager.validate_tail_structure()
    assert manager.mapping_exists("123")


@pytest.mark.parametrize(
    "encoding,bom",
    [
        ("utf-8", codecs.BOM_UTF8),
        ("utf-16-le", codecs.BOM_UTF16_LE),
        ("utf-16-be", codecs.BOM_UTF16_BE),
        ("iso-8859-1", b""),
        ("windows-1252", b""),
    ],
)
def test_encoding_preserved(config_path, encoding, bom):
    declared = "UTF-16" if encoding.startswith("utf-16") else encoding
    text = config_bytes().decode().replace("UTF-8", declared).replace("Preserve", "Café preserve")
    before = bom + text.encode(encoding)
    config_path.write_bytes(before)
    manager = ConfigManager(config_path)
    assert manager.add_mapping("123")
    addition = ('        <record from="123" to="graphics/pictures/person/123/portrait"/>\r\n').encode(
        encoding
    )
    assert config_path.read_bytes() == before.replace(
        "    </list>".encode(encoding), addition + "    </list>".encode(encoding)
    )
    assert manager.remove_mapping("123")
    assert config_path.read_bytes() == before


@pytest.mark.parametrize(
    "bad",
    [
        b'<record>\n<list id="maps">\n</record>',
        b'<record>\n<list id="other">\n</list>\n</record>',
        b'<record>\n<list id="maps">\n</list>\n<list id="other">\n</list>\n</record>',
        b'<record>\n<list id="maps">\n</list>\n<list id="maps">\n</list>\n</record>',
        b'<record>\n<list id="maps"/>\n</record>',
        b'<record>\n<list id="maps">\n</list>\n<!-- tail -->\n</record>',
        b'<record>\n<list id="maps">\n</list>\n</record>\n<record/>',
        b'<!DOCTYPE record [<!ENTITY x "test">]><record>\n<list id="maps">\n</list>\n</record>',
    ],
)
def test_malformed_or_ambiguous_tail_never_modified(config_path, bad):
    config_path.write_bytes(bad)
    manager = ConfigManager(config_path)
    assert not manager.validate_tail_structure()
    with pytest.raises(ConfigError):
        manager.add_mapping("123")
    assert config_path.read_bytes() == bad
    assert not config_path.with_suffix(".xml.tmp").exists()
    assert not config_path.with_suffix(".xml.bak").exists()


def test_remove_exact_line(config_path):
    before = config_path.read_bytes()
    assert ConfigManager(config_path).remove_mapping("100")
    expected = b"".join(line for line in before.splitlines(keepends=True) if b'from="100"' not in line)
    assert config_path.read_bytes() == expected
    assert config_path.with_suffix(".xml.bak").read_bytes() == before


def test_remove_non_self_closing_record(config_path):
    config_path.write_bytes(config_bytes(("100",)).replace(b'/portrait"/>', b'/portrait"></record>'))
    assert ConfigManager(config_path).remove_mapping("100")
    assert b'from="100"' not in config_path.read_bytes()


def test_remove_missing_is_read_only(config_path):
    before, stat = config_path.read_bytes(), config_path.stat()
    assert not ConfigManager(config_path).remove_mapping("123")
    assert config_path.read_bytes() == before
    assert config_path.stat().st_mtime_ns == stat.st_mtime_ns
    assert sorted(p.name for p in config_path.parent.iterdir()) == ["config.xml"]


def test_refuses_to_remove_ambiguous_duplicates(config_path):
    before = config_bytes(("100", "100"))
    config_path.write_bytes(before)
    with pytest.raises(ConfigError, match="Multiple"):
        ConfigManager(config_path).remove_mapping("100")
    assert config_path.read_bytes() == before


def test_atomic_replace_failure_preserves_original(config_path):
    before = config_path.read_bytes()
    import os

    real_replace = os.replace

    def fail_commit(source, destination):
        if Path(destination) == config_path:
            raise PermissionError("injected replacement failure")
        return real_replace(source, destination)

    with patch("core.config_manager.os.replace", side_effect=fail_commit):
        with pytest.raises(PermissionError):
            ConfigManager(config_path).add_mapping("123")
    assert config_path.read_bytes() == before
    assert config_path.with_suffix(".xml.bak").read_bytes() == before
    assert not config_path.with_suffix(".xml.tmp").exists()


def test_fsync_failure_preserves_original(config_path):
    before = config_path.read_bytes()
    with patch("core.config_manager.flush_file", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            ConfigManager(config_path).add_mapping("123")
    assert config_path.read_bytes() == before
    assert not config_path.with_suffix(".xml.tmp").exists()


def test_preexisting_temp_not_destroyed(config_path):
    temporary = config_path.with_suffix(".xml.tmp")
    temporary.write_bytes(b"recovery data")
    before = config_path.read_bytes()
    with pytest.raises(ConfigError, match="already exists"):
        ConfigManager(config_path).add_mapping("123")
    assert temporary.read_bytes() == b"recovery data"
    assert config_path.read_bytes() == before


def test_temp_validation_failure_preserves_original(config_path):
    from core.config_manager import _inspect

    before = config_path.read_bytes()

    def reject_temporary(path, *args):
        if path.name.endswith(".tmp"):
            raise ConfigError("injected invalid temporary XML")
        return _inspect(path, *args)

    with patch("core.config_manager._inspect", side_effect=reject_temporary):
        with pytest.raises(ConfigError):
            ConfigManager(config_path).add_mapping("123")
    assert config_path.read_bytes() == before
    assert not config_path.with_suffix(".xml.tmp").exists()


def test_backup_failure_preserves_config_and_prior_backup(config_path):
    before = config_path.read_bytes()
    backup = config_path.with_suffix(".xml.bak")
    backup.write_bytes(b"previous backup")
    with patch("core.config_manager.copy_durable", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            ConfigManager(config_path).add_mapping("123")
    assert config_path.read_bytes() == before
    assert backup.read_bytes() == b"previous backup"
    assert not config_path.with_suffix(".xml.tmp").exists()
