from __future__ import annotations

import json
from pathlib import Path
import re
import struct
from collections import Counter

from s2saveforge.core.models import Household, SaveGame, Sim


class UnsupportedSaveFormatError(RuntimeError):
    pass


class ReadOnlySaveFormatError(RuntimeError):
    pass


DBPF_RESOURCE_TYPE_NAMES: dict[int, str] = {
    0x0C560F39: "Behavior Constant",
    0x0F9F0C21: "Lot Description",
    0x1C0532FA: "Texture Image",
    0x2C1FD8A1: "Property Set",
    0x42484156: "Behavior Function",
    0x46414D49: "Family Information",
    0x4D51F042: "Neighborhood Terrain",
    0x6B943B43: "Text List",
    0x8C870743: "Sim Information",
    0x8C151C70: "Object Data",
    0x9A809646: "Slot Resource",
    0xAACE2EFB: "Catalog Description",
    0xAC506764: "Geometric Node",
    0xCC364C2A: "3D Array",
    0xCD95548E: "Name Reference",
    0xCDB467B8: "Scene Node",
    0xE519C933: "Material Definition",
    0xEBFEE33F: "String Set",
}

DBPF_DOMAIN_HINTS: dict[int, str] = {
    0x0F9F0C21: "Lot",
    0x46414D49: "Family",
    0x4D51F042: "Neighborhood",
    0x8C870743: "Sim",
    0xCC364C2A: "Rendering",
    0xEBFEE33F: "Strings",
    0xCD95548E: "Names",
    0xAC506764: "Rendering",
    0x0C560F39: "Behavior",
    0x42484156: "Behavior",
    0x8C151C70: "Object",
}


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
        total_story_entries = 0

        for neighborhood_dir in neighborhood_dirs:
            characters_dir = neighborhood_dir / "Characters"
            lots_dir = neighborhood_dir / "Lots"
            storytelling_dir = neighborhood_dir / "Storytelling"
            thumbnails_dir = neighborhood_dir / "Thumbnails"
            main_package_path = neighborhood_dir / f"{neighborhood_dir.name}_Neighborhood.package"
            package_count = len(list(neighborhood_dir.glob("*.package")))
            lot_files = sorted(lots_dir.glob("*.package"))
            lot_count = len(lot_files)
            character_files = sorted(characters_dir.glob("*.package"))
            suburb_packages = sorted(neighborhood_dir.glob(f"{neighborhood_dir.name}_Suburb*.package"))
            story_entries = sorted(storytelling_dir.glob("webentry_*.xml"))
            total_story_entries += len(story_entries)
            main_package_info = self._inspect_dbpf_package(main_package_path)

            members: list[str] = []
            for package_path in character_files:
                sim_id = package_path.stem
                members.append(sim_id)
                package_info = self._inspect_dbpf_package(package_path)
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
                        metadata={
                            "package_path": str(package_path),
                            "package_size": package_path.stat().st_size,
                            "neighborhood_id": neighborhood_dir.name,
                            "package_info": package_info,
                        },
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
                    metadata={
                        "kind": "neighborhood_preview",
                        "directory_path": str(neighborhood_dir),
                        "main_package_path": str(main_package_path),
                        "main_package_exists": main_package_path.exists(),
                        "characters_dir_exists": characters_dir.is_dir(),
                        "lots_dir_exists": lots_dir.is_dir(),
                        "storytelling_dir_exists": storytelling_dir.is_dir(),
                        "thumbnails_dir_exists": thumbnails_dir.is_dir(),
                        "character_count": len(character_files),
                        "lot_count": lot_count,
                        "suburb_count": len(suburb_packages),
                        "story_entry_count": len(story_entries),
                        "top_level_package_count": package_count,
                        "character_package_total_size": sum(path.stat().st_size for path in character_files),
                        "lot_package_total_size": sum(path.stat().st_size for path in lot_files),
                        "main_package_info": main_package_info,
                        "suburb_package_paths": [str(package) for package in suburb_packages],
                    },
                )
            )

        neighborhood_manager_path = neighborhoods_root / "NeighborhoodManager.package"
        return SaveGame(
            version=f"fs-preview:{neighborhoods_root}",
            households=households,
            sims=sims,
            relationships=[],
            metadata={
                "source_kind": "folder_preview",
                "neighborhoods_root": str(neighborhoods_root),
                "neighborhood_count": len(households),
                "neighborhood_manager_exists": neighborhood_manager_path.exists(),
                "neighborhood_manager_path": str(neighborhood_manager_path),
                "neighborhood_manager_info": self._inspect_dbpf_package(neighborhood_manager_path),
                "total_story_entries": total_story_entries,
            },
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

    def _inspect_dbpf_package(self, path: Path) -> dict[str, int | str | bool]:
        if not path.exists() or not path.is_file():
            return {
                "exists": False,
                "path": str(path),
            }

        with path.open("rb") as handle:
            header = handle.read(96)

        if len(header) < 96:
            return {
                "exists": True,
                "path": str(path),
                "size": path.stat().st_size,
                "is_dbpf": False,
                "error": "header_too_small",
            }

        magic, *values = struct.unpack("<4s23I", header)
        is_dbpf = magic == b"DBPF"
        index_version_major = values[7]
        index_entry_count = values[8]
        index_offset = values[9]
        index_size = values[10]
        index_entries, index_entry_size = self._read_dbpf_index(path, index_offset, index_size, index_entry_count)
        resource_type_counts = Counter(entry["type_hex"] for entry in index_entries)
        top_resource_types = [
            {
                "type_hex": resource_type,
                "type_name": self._resource_type_name(int(resource_type, 16)),
                "domain_hint": self._resource_domain_hint(int(resource_type, 16)),
                "count": count,
            }
            for resource_type, count in resource_type_counts.most_common(5)
        ]
        domain_profile = self._build_domain_profile(index_entries)
        return {
            "exists": True,
            "path": str(path),
            "size": path.stat().st_size,
            "is_dbpf": is_dbpf,
            "magic": magic.decode("ascii", errors="replace"),
            "dbpf_version_major": values[0],
            "dbpf_version_minor": values[1],
            "index_version_major": index_version_major,
            "index_entry_count": index_entry_count,
            "index_offset": index_offset,
            "index_size": index_size,
            "hole_entry_count": values[11],
            "hole_offset": values[12],
            "hole_size": values[13],
            "index_version_minor": values[14],
            "index_entry_size": index_entry_size,
            "index_entries_preview": index_entries[:10],
            "parsed_index_entry_count": len(index_entries),
            "top_resource_types": top_resource_types,
            "domain_profile": domain_profile,
        }

    def _read_dbpf_index(
        self,
        path: Path,
        index_offset: int,
        index_size: int,
        index_entry_count: int,
    ) -> tuple[list[dict[str, int | str]], int]:
        if index_entry_count <= 0 or index_size <= 0:
            return [], 0

        if index_size % index_entry_count != 0:
            return [], 0

        entry_size = index_size // index_entry_count
        if entry_size not in (20, 24):
            return [], entry_size

        with path.open("rb") as handle:
            handle.seek(index_offset)
            index_data = handle.read(index_size)

        entries: list[dict[str, int | str]] = []
        for offset in range(0, len(index_data), entry_size):
            chunk = index_data[offset : offset + entry_size]
            if len(chunk) != entry_size:
                continue

            values = struct.unpack("<" + ("I" * (entry_size // 4)), chunk)
            entry = {
                "type_id": values[0],
                "type_hex": f"0x{values[0]:08X}",
                "type_name": self._resource_type_name(values[0]),
                "domain_hint": self._resource_domain_hint(values[0]),
                "group_id": values[1],
                "group_hex": f"0x{values[1]:08X}",
                "instance_id": values[2],
                "instance_hex": f"0x{values[2]:08X}",
                "resource_id": 0,
                "resource_hex": "0x00000000",
                "file_offset": values[3],
                "file_size": values[4],
            }
            if entry_size == 24:
                entry["resource_id"] = values[3]
                entry["resource_hex"] = f"0x{values[3]:08X}"
                entry["file_offset"] = values[4]
                entry["file_size"] = values[5]

            entries.append(entry)

        return entries, entry_size

    def _resource_type_name(self, type_id: int) -> str:
        return DBPF_RESOURCE_TYPE_NAMES.get(type_id, "Unknown Resource")

    def _resource_domain_hint(self, type_id: int) -> str:
        return DBPF_DOMAIN_HINTS.get(type_id, "Unknown")

    def _build_domain_profile(self, index_entries: list[dict[str, int | str]]) -> list[dict[str, int | str]]:
        counts = Counter(str(entry.get("domain_hint", "Unknown")) for entry in index_entries)
        return [
            {"domain": domain, "count": count}
            for domain, count in counts.most_common(6)
        ]
