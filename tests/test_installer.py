from unittest.mock import patch

import pytest
from PIL import Image

from core.config_manager import ConfigError, ConfigManager
from core.filesystem import FileChangedError, folder_lock
from core.installer import FaceInstaller
from tests.conftest import config_bytes


@pytest.fixture
def setup(tmp_path):
    folder = tmp_path / "faces"
    folder.mkdir()
    source = tmp_path / "source.jpg"
    Image.new("RGB", (80, 120), "green").save(source)
    return FaceInstaller(folder), folder, source


def old_image(folder, player_id="100"):
    path = folder / f"{player_id}.png"
    Image.new("RGBA", (10, 10), "red").save(path)
    return path


def test_install_new_creates_both(setup):
    installer, folder, source = setup
    result = installer.execute(installer.prepare_install(" 100 ", source))
    assert result.kind == "installed"
    assert ConfigManager(folder / "config.xml").mapping_exists("100")
    with Image.open(folder / "100.png") as image:
        assert image.format == "PNG" and image.size == (80, 120)
    assert not (folder / "face.png").exists()


@pytest.mark.parametrize("mapping", [True, False])
def test_cancel_overwrite_changes_nothing(setup, mapping):
    installer, folder, source = setup
    (folder / "config.xml").write_bytes(config_bytes(("100",) if mapping else ()))
    old_image(folder)
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in folder.iterdir()}
    plan = installer.prepare_install("100", source)
    assert plan.needs_confirmation
    assert installer.execute(plan).kind == "cancelled"
    assert {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in folder.iterdir()} == before


def test_replace_keeps_config_byte_for_byte_and_mtime(setup):
    installer, folder, source = setup
    path = folder / "config.xml"
    before = config_bytes(("100",))
    path.write_bytes(before)
    stamp = path.stat().st_mtime_ns
    old_image(folder)
    result = installer.execute(installer.prepare_install("100", source), confirmed=True)
    assert result.kind == "replaced"
    assert path.read_bytes() == before and path.stat().st_mtime_ns == stamp
    assert not (folder / "config.xml.bak").exists()
    with Image.open(folder / "100.png") as image:
        assert image.size == (80, 120)


def test_restore_missing_image_without_confirmation(setup):
    installer, folder, source = setup
    path = folder / "config.xml"
    path.write_bytes(config_bytes(("100",)))
    before, stamp = path.read_bytes(), path.stat().st_mtime_ns
    plan = installer.prepare_install("100", source)
    assert not plan.needs_confirmation
    assert installer.execute(plan).kind == "restored"
    assert (folder / "100.png").exists()
    assert path.read_bytes() == before and path.stat().st_mtime_ns == stamp


def test_orphan_image_requires_confirmation_then_adds_mapping(setup):
    installer, folder, source = setup
    old_image(folder)
    plan = installer.prepare_install("100", source)
    assert plan.needs_confirmation and not plan.mapping_exists
    assert installer.execute(plan, confirmed=True).kind == "installed"
    assert installer.config.mapping_exists("100")


def test_bad_config_leaves_existing_image_untouched(setup):
    installer, folder, source = setup
    image = old_image(folder)
    before = image.read_bytes()
    path = folder / "config.xml"
    bad = b'<record>\n<list id="wrong">\n</list>\n</record>'
    path.write_bytes(bad)
    plan = installer.prepare_install("100", source)
    with pytest.raises(ConfigError):
        installer.execute(plan, confirmed=True)
    assert image.read_bytes() == before and path.read_bytes() == bad
    assert not list(folder.glob("*.tmp"))


@pytest.mark.parametrize("action", ["install", "remove"])
@pytest.mark.parametrize("existing_image", [True, False])
def test_config_commit_failure_rolls_back_image(setup, action, existing_image):
    installer, folder, source = setup
    path = folder / "config.xml"
    path.write_bytes(config_bytes(("100",) if action == "remove" else ()))
    before_config = path.read_bytes()
    target = old_image(folder) if existing_image else folder / "100.png"
    before_image = target.read_bytes() if target.exists() else None
    plan = (
        installer.prepare_install("100", source) if action == "install" else installer.prepare_remove("100")
    )
    with patch("core.config_manager.PreparedConfig.commit", side_effect=OSError("disk error")):
        with pytest.raises(OSError):
            installer.execute(plan, confirmed=True)
    assert path.read_bytes() == before_config
    assert (target.read_bytes() if target.exists() else None) == before_image
    assert not (folder / "config.xml.tmp").exists()


@pytest.mark.parametrize("mapping,image", [(True, True), (True, False), (False, True), (False, False)])
def test_remove_combinations(setup, mapping, image):
    installer, folder, _ = setup
    config = folder / "config.xml"
    config.write_bytes(config_bytes(("100",) if mapping else ()))
    before, stamp = config.read_bytes(), config.stat().st_mtime_ns
    if image:
        old_image(folder)
    plan = installer.prepare_remove("100")
    result = installer.execute(plan, confirmed=True)
    assert result.kind == ("removed" if mapping or image else "nothing")
    assert not (folder / "100.png").exists()
    assert not installer.config.mapping_exists("100")
    if not mapping:
        assert config.read_bytes() == before and config.stat().st_mtime_ns == stamp


def test_cancel_remove(setup):
    installer, folder, _ = setup
    image = old_image(folder)
    before = image.read_bytes()
    assert installer.execute(installer.prepare_remove("100")).kind == "cancelled"
    assert image.read_bytes() == before


@pytest.mark.parametrize("changed", ["image", "config", "source"])
def test_changed_files_invalidate_pending_confirmation(setup, changed):
    installer, folder, source = setup
    plan = installer.prepare_install("100", source)
    path = {"image": folder / "100.png", "config": folder / "config.xml", "source": source}[changed]
    path.write_bytes(b"external change")
    with pytest.raises(FileChangedError):
        installer.execute(plan, confirmed=True)
    assert path.read_bytes() == b"external change"


def test_folder_lock_prevents_second_writer(setup):
    installer, folder, source = setup
    plan = installer.prepare_install("100", source)
    with folder_lock(folder):
        with pytest.raises(OSError, match="Another installer"):
            installer.execute(plan)
    assert not (folder / "100.png").exists()


def test_source_can_be_target_image(setup):
    installer, folder, _ = setup
    source = old_image(folder)
    before = source.read_bytes()
    assert installer.execute(installer.prepare_install("100", source), confirmed=True).kind == "installed"
    assert source.read_bytes() == before


def test_image_write_failure_never_touches_config_or_image(setup):
    installer, folder, source = setup
    target = old_image(folder)
    image_before = target.read_bytes()
    config = folder / "config.xml"
    config.write_bytes(config_bytes(()))
    config_before = config.read_bytes()
    plan = installer.prepare_install("100", source)
    with patch("core.installer.stage_png", side_effect=OSError("image write denied")):
        with pytest.raises(OSError):
            installer.execute(plan, confirmed=True)
    assert target.read_bytes() == image_before
    assert config.read_bytes() == config_before
    assert not (folder / "config.xml.bak").exists()


def test_new_config_commit_failure_leaves_neither_image_nor_config(setup):
    installer, folder, source = setup
    plan = installer.prepare_install("100", source)
    with patch("core.config_manager.PreparedConfig.commit", side_effect=OSError("commit denied")):
        with pytest.raises(OSError):
            installer.execute(plan)
    assert not (folder / "100.png").exists()
    assert not (folder / "config.xml").exists()
    assert not (folder / "config.xml.tmp").exists()
