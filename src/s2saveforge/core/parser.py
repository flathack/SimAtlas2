from __future__ import annotations

import json
from pathlib import Path

from s2saveforge.core.models import SaveGame


class UnsupportedSaveFormatError(RuntimeError):
    pass


class SaveParser:
    SUPPORTED_SUFFIXES = {".json", ".s2json"}

    def read(self, path: Path) -> SaveGame:
        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED_SUFFIXES:
            raise UnsupportedSaveFormatError(
                "Unsupported file format. Current MVP supports only .json and .s2json files."
            )

        payload = json.loads(path.read_text(encoding="utf-8"))
        return SaveGame.from_dict(payload)

    def write(self, path: Path, savegame: SaveGame) -> None:
        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED_SUFFIXES:
            raise UnsupportedSaveFormatError(
                "Unsupported file format. Current MVP supports only .json and .s2json files."
            )

        content = json.dumps(savegame.to_dict(), indent=2, ensure_ascii=True)
        path.write_text(content + "\n", encoding="utf-8")
