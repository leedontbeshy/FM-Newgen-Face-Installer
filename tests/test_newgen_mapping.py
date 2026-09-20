"""FM24 uses r-ID only in the target; source filenames stay ID.png."""

import codecs
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from core.config_manager import ConfigError, ConfigManager
from core.installer import FaceInstaller
from core.validation import ValidationError
from tests.conftest import config_bytes


@pytest.mark.parametrize("newgen,prefix", [(True, "r-"), (False, "")])
def test_install_uses_player_type_in_target_only(tmp_path, newgen, prefix):
    source = tmp_path / "face.jpg"
    Image.new("RGB", (19, 23), "green").save(source)
    folder = tmp_path / "faces"
    installer = FaceInstaller(folder, newgen=newgen)
    installer.execute(installer.prepare_install("2002092570", source))
    assert (folder / "2002092570.png").exists()
    assert not (folder / "r-2002092570.png").exists()
    assert (
        installer.config.mapping_target("2002092570")
        == f"graphics/pictures/person/{prefix}2002092570/portrait"
    )
    assert b'from="2002092570"' in (folder / "config.xml").read_bytes()


@pytest.mark.parametrize(
    "encoding,bom",
    [
        ("utf-8", b""),
        ("utf-8", codecs.BOM_UTF8),
        ("utf-16-le", codecs.BOM_UTF16_LE),
        ("utf-16-be", codecs.BOM_UTF16_BE),
        ("windows-1252", b""),
    ],
)
@pytest.mark.parametrize("newline", ["\r\n", "\n"])
def test_explicit_repair_changes_only_target_bytes(tmp_path, encoding, bom, newline):
    declared = "UTF-16" if encoding.startswith("utf-16") else encoding
    text = config_bytes(("100", "1000", "2002092570"), newline).decode().replace("UTF-8", declared)
    text = text.replace('from="2002092570" to="', "from = '2002092570'   to = '").replace(
        '2002092570/portrait"', "2002092570/portrait'"
    )
    path = tmp_path / "config.xml"
    before = bom + text.encode(encoding)
    path.write_bytes(before)
    manager = ConfigManager(path)
    assert manager.repair_newgen_mapping("2002092570")
    expected = before.replace(
        "person/2002092570/portrait".encode(encoding), "person/r-2002092570/portrait".encode(encoding), 1
    )
    assert path.read_bytes() == expected
    assert path.with_suffix(".xml.bak").read_bytes() == before
    stamp = path.stat().st_mtime_ns
    assert not manager.repair_newgen_mapping("2002092570")
    assert path.stat().st_mtime_ns == stamp and path.read_bytes() == expected


def test_repair_missing_mapping_is_read_only(tmp_path):
    path = tmp_path / "config.xml"
    assert not ConfigManager(path).repair_newgen_mapping("100")
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("ids,target", [(("100", "100"), "100"), (("100",), "999")])
def test_refuse_duplicate_or_unexpected_target(tmp_path, ids, target):
    path = tmp_path / "config.xml"
    before = config_bytes(ids).replace(b"person/100/", f"person/{target}/".encode())
    path.write_bytes(before)
    with pytest.raises(ConfigError):
        ConfigManager(path).repair_newgen_mapping("100")
    assert path.read_bytes() == before


def test_ordinary_add_never_repairs_existing_mapping(tmp_path):
    path = tmp_path / "config.xml"
    path.write_bytes(config_bytes(("100",)))
    before, stamp = path.read_bytes(), path.stat().st_mtime_ns
    assert not ConfigManager(path).add_mapping("100", newgen=True)
    assert path.read_bytes() == before and path.stat().st_mtime_ns == stamp


def test_repair_requires_confirmation_and_preserves_image(tmp_path):
    config = tmp_path / "config.xml"
    config.write_bytes(config_bytes(("100",)))
    image = tmp_path / "100.png"
    Image.new("RGBA", (20, 30), "red").save(image)
    image_before, image_stamp = image.read_bytes(), image.stat().st_mtime_ns
    before = config.read_bytes()
    installer = FaceInstaller(tmp_path, newgen=True)
    plan = installer.prepare_repair("100")
    assert plan.needs_confirmation
    assert installer.execute(plan).kind == "cancelled"
    assert config.read_bytes() == before
    assert installer.execute(plan, confirmed=True).kind == "repaired"
    assert image.read_bytes() == image_before and image.stat().st_mtime_ns == image_stamp
    assert config.read_bytes() == before.replace(b"person/100/", b"person/r-100/")


def test_existing_correct_newgen_replace_does_not_rewrite_config(tmp_path):
    config = tmp_path / "config.xml"
    before = config_bytes(("100",)).replace(b"person/100/", b"person/r-100/")
    config.write_bytes(before)
    source = tmp_path / "source.jpg"
    Image.new("RGB", (20, 30), "green").save(source)
    Image.new("RGBA", (10, 15), "red").save(tmp_path / "100.png")
    stamp = config.stat().st_mtime_ns
    installer = FaceInstaller(tmp_path, newgen=True)
    assert installer.execute(installer.prepare_install("100", source), confirmed=True).kind == "replaced"
    assert config.read_bytes() == before and config.stat().st_mtime_ns == stamp


def test_wrong_newgen_target_blocks_misleading_install_success(tmp_path):
    config = tmp_path / "config.xml"
    config.write_bytes(config_bytes(("100",)))
    before = config.read_bytes()
    source = tmp_path / "face.jpg"
    Image.new("RGB", (20, 30)).save(source)
    installer = FaceInstaller(tmp_path, newgen=True)
    with pytest.raises(ValidationError, match="Fix Mapping"):
        installer.execute(installer.prepare_install("100", source), confirmed=True)
    assert config.read_bytes() == before and not (tmp_path / "100.png").exists()


def test_repair_commit_failure_preserves_original(tmp_path):
    path = tmp_path / "config.xml"
    path.write_bytes(config_bytes(("100",)))
    before = path.read_bytes()
    import os

    real_replace = os.replace

    def fail_commit(source, destination):
        if Path(destination) == path:
            raise PermissionError("injected commit failure")
        return real_replace(source, destination)

    with patch("core.config_manager.os.replace", side_effect=fail_commit):
        with pytest.raises(PermissionError):
            ConfigManager(path).repair_newgen_mapping("100")
    assert path.read_bytes() == before
    assert path.with_suffix(".xml.bak").read_bytes() == before
    assert not path.with_suffix(".xml.tmp").exists()
