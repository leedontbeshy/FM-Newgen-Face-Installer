from unittest.mock import patch

import pytest

from core.settings_manager import Settings, SettingsManager


def test_settings_roundtrip_outside_face_folder(tmp_path):
    manager = SettingsManager(tmp_path / "local" / "settings.json")
    assert manager.load() == Settings()
    settings = Settings(str(tmp_path / "Khuôn mặt"), str(tmp_path / "Downloads"))
    manager.save(settings)
    assert manager.load() == settings


@pytest.mark.parametrize("bad", ["{oops", "[]", '{"face_folder": 9}'])
def test_bad_settings_reported_and_left_intact(tmp_path, bad):
    path = tmp_path / "settings.json"
    path.write_text(bad)
    manager = SettingsManager(path)
    assert manager.load() == Settings()
    assert manager.warning and path.read_text() == bad


def test_settings_atomic_failure_keeps_previous(tmp_path):
    manager = SettingsManager(tmp_path / "settings.json")
    manager.save(Settings("original"))
    before = manager.path.read_bytes()
    with patch("core.settings_manager.os.replace", side_effect=PermissionError("locked")):
        with pytest.raises(PermissionError):
            manager.save(Settings("new"))
    assert manager.path.read_bytes() == before
