from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable

from s2saveforge.core.models import SaveGame
from s2saveforge.core.parser import ReadOnlySaveFormatError, SaveParser
from s2saveforge.core.validators import ValidationIssue, validate_savegame


class SaveSession:
    def __init__(self, parser: SaveParser | None = None) -> None:
        self._parser = parser or SaveParser()
        self._source_path: Path | None = None
        self._current: SaveGame | None = None
        self._history: list[tuple[str, SaveGame]] = []
        self._history_index: int = -1

    @property
    def source_path(self) -> Path | None:
        return self._source_path

    @property
    def current(self) -> SaveGame | None:
        return self._current

    @property
    def history_labels(self) -> list[str]:
        return [label for label, _state in self._history]

    def load(
        self,
        path: Path,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> SaveGame:
        savegame = self._parser.read(path, progress_callback=progress_callback)
        self._source_path = path
        self._current = savegame
        self._history = [("Loaded save", savegame.clone())]
        self._history_index = 0
        return savegame

    def create_backup(self, backup_root: Path | None = None) -> Path:
        if self._source_path is None:
            raise RuntimeError("No loaded savegame to backup.")
        if self._source_path.is_dir():
            raise ReadOnlySaveFormatError(
                "Filesystem previews loaded from Sims 2 folders cannot be backed up from the editor yet."
            )

        root = backup_root or self._source_path.parent / "backups"
        root.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = root / f"{self._source_path.stem}_{timestamp}{self._source_path.suffix}"
        shutil.copy2(self._source_path, backup_file)
        return backup_file

    def apply(self, description: str, mutate: Callable[[SaveGame], None]) -> None:
        if self._current is None:
            raise RuntimeError("No savegame loaded.")

        mutate(self._current)

        # Cut any redo branch once a new edit is applied.
        self._history = self._history[: self._history_index + 1]
        self._history.append((description, self._current.clone()))
        self._history_index += 1

    def can_undo(self) -> bool:
        return self._history_index > 0

    def can_redo(self) -> bool:
        return self._history_index + 1 < len(self._history)

    def undo(self) -> None:
        if not self.can_undo():
            return
        self._history_index -= 1
        self._current = self._history[self._history_index][1].clone()

    def redo(self) -> None:
        if not self.can_redo():
            return
        self._history_index += 1
        self._current = self._history[self._history_index][1].clone()

    def validate(self) -> list[ValidationIssue]:
        if self._current is None:
            return []
        return validate_savegame(self._current)

    def save(self, path: Path | None = None) -> Path:
        if self._current is None:
            raise RuntimeError("No savegame loaded.")

        target = path or self._source_path
        if target is None:
            raise RuntimeError("No target path provided.")
        if target.is_dir():
            raise ReadOnlySaveFormatError(
                "Filesystem previews loaded from Sims 2 folders are currently read-only."
            )

        temp_path = target.with_name(f"{target.stem}.tmp{target.suffix}")
        self._parser.write(temp_path, self._current)
        temp_path.replace(target)
        self._source_path = target
        return target
