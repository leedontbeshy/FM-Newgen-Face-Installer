"""Reviewable plans and coordinated image/config transactions for the UI."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from core.config_manager import ConfigManager
from core.filesystem import assert_unchanged, copy_durable, fingerprint, folder_lock, temporary_path
from core.image_manager import stage_png, validate_image
from core.validation import ValidationError, validate_player_id


@dataclass(frozen=True)
class OperationPlan:
    action: str
    folder: Path
    player_id: str
    source: Path | None
    mapping_exists: bool
    image_state: tuple | None
    config_state: tuple | None
    source_state: tuple | None
    mapping_target: str | None = None
    newgen: bool = False

    @property
    def image_exists(self) -> bool:
        return self.image_state is not None

    @property
    def needs_confirmation(self) -> bool:
        if self.action == "repair":
            return self.mapping_exists and self.mapping_target == ConfigManager.portrait_target(
                self.player_id
            )
        return self.image_exists if self.action == "install" else (self.image_exists or self.mapping_exists)

    @property
    def confirmation(self) -> str:
        if self.action == "repair":
            return (
                f"Fix the mapping for newgen {self.player_id} in FM24?\n\n"
                f"The target will change to person/r-{self.player_id}/portrait.\n"
                "The image and all other mappings will stay unchanged."
            )
        if self.action == "remove":
            return f"Remove face for Player ID {self.player_id}?\n\nThe image and its config mapping will be removed, if present."
        if self.mapping_exists:
            return (
                f"Player ID {self.player_id} already has a face mapping.\n"
                "Replace the existing face image?\n\nThe config mapping will stay unchanged."
            )
        return (
            f"The image for Player ID {self.player_id} already exists, but has no mapping in config.xml.\n"
            "Replace the image and create a mapping?"
        )


@dataclass(frozen=True)
class OperationResult:
    kind: str
    message: str


def _cleanup(path: Path | None) -> None:
    if path:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logging.exception("Could not clean up temporary file: %s", path)


class FaceInstaller:
    def __init__(self, folder: str | Path, *, newgen: bool = False):
        if not str(folder).strip():
            raise ValidationError("Choose your Custom Face Folder in Settings first.")
        self.folder = Path(folder).resolve()
        self.config = ConfigManager(self.folder / "config.xml")
        self.newgen = newgen

    def _plan(self, action: str, player_id: str, source: Path | None = None) -> OperationPlan:
        player_id = validate_player_id(player_id)
        if self.folder.exists() and not self.folder.is_dir():
            raise ValidationError("The Custom Face Folder path is not a folder.")
        source_state = fingerprint(source) if source else None
        if source:
            validate_image(source)
            assert_unchanged(source, source_state)
        config_state = fingerprint(self.config.path)
        mapping_target = self.config.mapping_target(player_id)
        mapping = mapping_target is not None
        assert_unchanged(self.config.path, config_state)
        return OperationPlan(
            action,
            self.folder,
            player_id,
            source,
            mapping,
            fingerprint(self.folder / f"{player_id}.png"),
            config_state,
            source_state,
            mapping_target,
            self.newgen,
        )

    def prepare_install(self, player_id: str, source: str | Path | None) -> OperationPlan:
        validate_player_id(player_id)
        if not source:
            raise ValidationError("Select a face image first.")
        return self._plan("install", player_id, Path(source).resolve())

    def prepare_remove(self, player_id: str) -> OperationPlan:
        return self._plan("remove", player_id)

    def prepare_repair(self, player_id: str) -> OperationPlan:
        return self._plan("repair", player_id)

    def execute(self, plan: OperationPlan, *, confirmed: bool = False) -> OperationResult:
        if (
            plan.folder != self.folder
            or plan.newgen != self.newgen
            or plan.action not in {"install", "remove", "repair"}
        ):
            raise ValueError("This operation plan does not belong to this installer.")
        validate_player_id(plan.player_id)
        if plan.needs_confirmation and not confirmed:
            return OperationResult("cancelled", "Cancelled. No files were changed.")
        if plan.action == "remove" and not plan.mapping_exists and not plan.image_exists:
            return OperationResult("nothing", "Nothing to remove.")
        if plan.action == "repair":
            if not plan.mapping_exists:
                return OperationResult("nothing", "No mapping to repair. Use Install Face to create one.")
            if plan.mapping_target == self.config.portrait_target(plan.player_id, newgen=True):
                return OperationResult("nothing", "This mapping already uses the FM24 newgen format.")
            if plan.mapping_target != self.config.portrait_target(plan.player_id):
                raise ValidationError("This record has a custom target. It cannot be repaired automatically.")
        if plan.action == "install" and plan.newgen and plan.mapping_exists:
            if plan.mapping_target == self.config.portrait_target(plan.player_id):
                raise ValidationError(
                    "This mapping uses the real-player format. Click Fix Mapping, "
                    "then install the image again. No image or config files were changed."
                )
        with folder_lock(self.folder):
            target = self.folder / f"{plan.player_id}.png"
            assert_unchanged(self.config.path, plan.config_state)
            assert_unchanged(target, plan.image_state)
            if plan.source:
                assert_unchanged(plan.source, plan.source_state)
            if plan.action == "repair":
                prepared = self.config.prepare_newgen_repair(plan.player_id)
                if prepared:
                    try:
                        prepared.commit()
                    finally:
                        _cleanup(prepared.temporary)
                return OperationResult(
                    "repaired",
                    f"✓ Newgen mapping for {plan.player_id} fixed\n"
                    "✓ Image and other mappings kept unchanged\nClear the Football Manager cache, then reload the skin.",
                )
            if plan.action == "install":
                return self._install(plan, target)
            return self._remove(plan, target)

    def _install(self, plan: OperationPlan, target: Path) -> OperationResult:
        staged = backup = prepared = None
        image_changed = False
        try:
            staged = stage_png(plan.source, self.folder)
            assert_unchanged(plan.source, plan.source_state)
            # Validate config and its temp before changing the destination image.
            if not plan.mapping_exists:
                prepared = self.config.prepare_add(plan.player_id, newgen=plan.newgen)
            if plan.image_exists:
                backup = temporary_path(self.folder, ".image-backup")
                copy_durable(target, backup)
            assert_unchanged(target, plan.image_state)
            assert_unchanged(self.config.path, plan.config_state)
            os.replace(staged, target)
            image_changed = True
            if prepared:
                prepared.commit()
        except BaseException as error:
            if image_changed:
                try:
                    if backup:
                        os.replace(backup, target)
                    else:
                        target.unlink(missing_ok=True)
                except OSError as rollback_error:
                    recovery = str(backup) if backup else str(target)
                    backup = None  # keep recovery data; never silently discard it
                    raise OSError(
                        f"Operation failed; image rollback also failed. Recovery file: {recovery}. "
                        f"Original error: {error}; rollback: {rollback_error}"
                    ) from error
            raise
        finally:
            _cleanup(staged)
            _cleanup(backup)
            if prepared:
                _cleanup(prepared.temporary)
        if plan.mapping_exists:
            kind = "replaced" if plan.image_exists else "restored"
            return OperationResult(
                kind,
                f"✓ {plan.player_id}.png {kind}\n"
                "✓ Existing config mapping kept unchanged\nReload your Football Manager skin.",
            )
        return OperationResult(
            "installed",
            f"✓ {plan.player_id}.png installed\n"
            "✓ config.xml mapping added\nReload your Football Manager skin.",
        )

    def _remove(self, plan: OperationPlan, target: Path) -> OperationResult:
        prepared = backup = None
        image_changed = False
        try:
            if plan.mapping_exists:
                prepared = self.config.prepare_remove(plan.player_id)
            assert_unchanged(target, plan.image_state)
            assert_unchanged(self.config.path, plan.config_state)
            if plan.image_exists:
                backup = temporary_path(self.folder, ".removed-image")
                os.replace(target, backup)
                image_changed = True
            if prepared:
                prepared.commit()
        except BaseException as error:
            if image_changed:
                try:
                    os.replace(backup, target)
                except OSError as rollback_error:
                    recovery = backup
                    backup = None
                    raise OSError(
                        f"Operation failed; restore the image from {recovery}. "
                        f"Original error: {error}; rollback: {rollback_error}"
                    ) from error
            raise
        finally:
            _cleanup(backup)
            if prepared:
                _cleanup(prepared.temporary)
        image_line = f"✓ {plan.player_id}.png removed" if plan.image_exists else "No image file was present"
        config_line = "✓ config.xml mapping removed" if plan.mapping_exists else "✓ config.xml kept unchanged"
        return OperationResult("removed", f"{image_line}\n{config_line}\nReload your Football Manager skin.")
