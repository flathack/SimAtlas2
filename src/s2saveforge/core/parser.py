from __future__ import annotations

import json
from pathlib import Path
import re

from s2saveforge.core.models import Household, SaveGame, Sim


class UnsupportedSaveFormatError(RuntimeError):
    pass


class ReadOnlySaveFormatError(RuntimeError):
    pass


class SaveParser:
    SUPPORTED_SUFFIXES = {".json", ".s2json"}
    NEIGHBORHOOD_PATTERN = re.compile(r"^[A-Z]\d{3}$")

    def read(self, path: Path) -> SaveGame:
        if path.is_dir():
            return self._read_directory(path)

        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED_SUFFIXES:
            raise UnsupportedSaveFormatError(
                "Unsupported file format. Current MVP supports only .json and .s2json files."
            )

        payload = json.loads(path.read_text(encoding="utf-8"))
        return SaveGame.from_dict(payload)

    def write(self, path: Path, savegame: SaveGame) -> None:
        if path.is_dir() or savegame.version.startswith("fs-preview:"):
            raise ReadOnlySaveFormatError(
                "Filesystem previews loaded from Sims 2 folders are currently read-only."
            )

        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED_SUFFIXES:
            raise UnsupportedSaveFormatError(
                "Unsupported file format. Current MVP supports only .json and .s2json files."
            )

        content = json.dumps(savegame.to_dict(), indent=2, ensure_ascii=True)
        path.write_text(content + "\n", encoding="utf-8")

    def _read_directory(self, path: Path) -> SaveGame:
        neighborhoods_root = self._resolve_neighborhoods_root(path)
        selected_neighborhood = path if path.is_dir() and self.NEIGHBORHOOD_PATTERN.match(path.name) else None
        if selected_neighborhood is not None:
            neighborhood_dirs = [selected_neighborhood]
        else:
            neighborhood_dirs = sorted(
                entry
                for entry in neighborhoods_root.iterdir()
                if entry.is_dir() and self.NEIGHBORHOOD_PATTERN.match(entry.name)
            )

        if not neighborhood_dirs:
            raise UnsupportedSaveFormatError(
                "No Sims 2 neighborhood folders were found in the selected directory."
            )

        households: list[Household] = []
        sims: list[Sim] = []

        for neighborhood_dir in neighborhood_dirs:
            package_count = len(list(neighborhood_dir.glob("*.package")))
            lot_count = len(list((neighborhood_dir / "Lots").glob("*.package")))
            character_files = sorted((neighborhood_dir / "Characters").glob("*.package"))

            members: list[str] = []
            for package_path in character_files:
                sim_id = package_path.stem
                members.append(sim_id)
                sims.append(
                    Sim(
                        id=sim_id,
                        name=package_path.stem,
                        age_stage="unknown",
                        aspiration="",
                        household_id=neighborhood_dir.name,
                        career="",
                        career_level=1,
                        needs={},
                        skills={},
                    )
                )

            households.append(
                Household(
                    id=neighborhood_dir.name,
                    name=(
                        f"{neighborhood_dir.name} "
                        f"(chars: {len(character_files)}, lots: {lot_count}, packages: {package_count})"
                    ),
                    funds=0,
                    members=members,
                )
            )

        return SaveGame(
            version=f"fs-preview:{neighborhoods_root}",
            households=households,
            sims=sims,
            relationships=[],
        )

    def _resolve_neighborhoods_root(self, path: Path) -> Path:
        if path.name.lower() == "neighborhoods":
            return path

        candidate = path / "Neighborhoods"
        if candidate.is_dir():
            return candidate

        if self.NEIGHBORHOOD_PATTERN.match(path.name):
            return path.parent

        raise UnsupportedSaveFormatError(
            "Select either 'The Sims 2', its 'Neighborhoods' folder, or a neighborhood folder like 'N001'."
        )
