from __future__ import annotations

import json
from pathlib import Path
import re
import struct
from collections import Counter

from s2saveforge.core.models import Household, SaveGame, Sim
from s2saveforge.core.simpe_reference import SimPEReferenceCatalog, load_simpe_reference_catalog


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}


class UnsupportedSaveFormatError(RuntimeError):
    pass


class ReadOnlySaveFormatError(RuntimeError):
    pass


DBPF_RESOURCE_TYPE_NAMES: dict[int, str] = {
    0x0BF999E7: "Lot Description",
    0x0C560F39: "Binary Index",
    0x104F6A6E: "Business Info",
    0x2A51171B: "3D Array",
    0x3053CF74: "Sim: Scores",
    0x46414D49: "Family Information",
    0x484F5553: "House Descriptor",
    0x4D51F042: "Cinematic Scene",
    0x4E474248: "Neighborhood/Memory",
    0x53494D49: "Sim Information",
    0x6B943B43: "Lot Terrain Geometry",
    0x6C589723: "Lot Definition",
    0x8C870743: "Family Ties",
    0xAACE2EFB: "Sim Description",
    0xCC364C2A: "Sim Relations",
    0xCD95548E: "Sim Wants and Fears",
    0xE86B1EEF: "Directory of Compressed Files",
    0xEBFEE33F: "Sim DNA",
}

DBPF_RESOURCE_SHORT_NAMES: dict[int, str] = {
    0x0BF999E7: "LTXT",
    0x0C560F39: "BINX",
    0x104F6A6E: "BNFO",
    0x2A51171B: "3ARY",
    0x3053CF74: "SCOR",
    0x46414D49: "FAMI",
    0x484F5553: "HOUS",
    0x4D51F042: "CINE",
    0x4E474248: "NGBH",
    0x53494D49: "SIMI",
    0x6B943B43: "LOTG",
    0x6C589723: "LOTD",
    0x8C870743: "FAMT",
    0xAACE2EFB: "SDSC",
    0xCC364C2A: "SREL",
    0xCD95548E: "SWAF",
    0xE86B1EEF: "CLST",
    0xEBFEE33F: "SDNA",
}

DBPF_DOMAIN_HINTS: dict[int, str] = {
    0x0BF999E7: "Lot",
    0x104F6A6E: "Business",
    0x3053CF74: "Sim",
    0x46414D49: "Family",
    0x484F5553: "Lot",
    0x4D51F042: "Neighborhood",
    0x4E474248: "Neighborhood",
    0x53494D49: "Sim",
    0x6B943B43: "Lot",
    0x6C589723: "Lot",
    0x8C870743: "Family",
    0xAACE2EFB: "Sim",
    0xCC364C2A: "Relationship",
    0xCD95548E: "Sim",
    0xE86B1EEF: "Compression",
    0xEBFEE33F: "Sim",
}


class SaveParser:
    SUPPORTED_SUFFIXES = {".json", ".s2json"}
    NEIGHBORHOOD_PATTERN = re.compile(r"^[A-Z]\d{3}$")

    def __init__(self, simpe_path: str | None = None) -> None:
        self._simpe_reference: SimPEReferenceCatalog | None = load_simpe_reference_catalog(simpe_path)

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
        package_role_counts: Counter[str] = Counter()
        neighborhood_file_role_counts: Counter[str] = Counter()
        neighborhood_file_extension_counts: Counter[str] = Counter()
        total_neighborhood_file_count = 0
        total_neighborhood_file_size = 0

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
            thumbnail_packages = sorted(thumbnails_dir.glob("*.package"))
            story_entries = sorted(storytelling_dir.glob("webentry_*.xml"))
            total_story_entries += len(story_entries)
            main_package_info = self._inspect_dbpf_package(main_package_path)
            suburb_package_infos = [self._inspect_dbpf_package(package) for package in suburb_packages]
            thumbnail_package_infos = [self._inspect_dbpf_package(package) for package in thumbnail_packages]
            file_inventory = self._scan_neighborhood_file_inventory(neighborhood_dir)
            neighborhood_file_role_counts.update(
                {entry["role"]: entry["count"] for entry in file_inventory["role_profile"]}
            )
            neighborhood_file_extension_counts.update(
                {entry["extension"]: entry["count"] for entry in file_inventory["extension_profile"]}
            )
            total_neighborhood_file_count += int(file_inventory["total_file_count"])
            total_neighborhood_file_size += int(file_inventory["total_size"])
            package_role_counts.update([str(main_package_info.get("package_role", "Unknown"))])

            members: list[str] = []
            for package_path in character_files:
                sim_id = package_path.stem
                members.append(sim_id)
                package_info = self._inspect_dbpf_package(package_path)
                package_role_counts.update([str(package_info.get("package_role", "Unknown"))])
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
                        "thumbnail_package_count": len(thumbnail_packages),
                        "story_entry_count": len(story_entries),
                        "top_level_package_count": package_count,
                        "character_package_total_size": sum(path.stat().st_size for path in character_files),
                        "lot_package_total_size": sum(path.stat().st_size for path in lot_files),
                        "main_package_info": main_package_info,
                        "suburb_package_paths": [str(package) for package in suburb_packages],
                        "suburb_package_infos": suburb_package_infos,
                        "thumbnail_package_paths": [str(package) for package in thumbnail_packages],
                        "thumbnail_package_infos": thumbnail_package_infos,
                        "file_inventory": file_inventory,
                    },
                )
            )
            for suburb_package_info in suburb_package_infos:
                package_role_counts.update([str(suburb_package_info.get("package_role", "Unknown"))])
            for thumbnail_package_info in thumbnail_package_infos:
                package_role_counts.update([str(thumbnail_package_info.get("package_role", "Unknown"))])
            for lot_package in lot_files:
                package_role_counts.update([str(self._inspect_dbpf_package(lot_package).get("package_role", "Unknown"))])

        neighborhood_manager_path = neighborhoods_root / "NeighborhoodManager.package"
        neighborhood_manager_info = self._inspect_dbpf_package(neighborhood_manager_path)
        package_role_counts.update([str(neighborhood_manager_info.get("package_role", "Unknown"))])
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
                "neighborhood_manager_info": neighborhood_manager_info,
                "total_story_entries": total_story_entries,
                "neighborhood_file_count": total_neighborhood_file_count,
                "neighborhood_file_total_size": total_neighborhood_file_size,
                "neighborhood_file_role_profile": [
                    {"role": role, "count": count}
                    for role, count in neighborhood_file_role_counts.most_common()
                ],
                "neighborhood_file_extension_profile": [
                    {"extension": extension, "count": count}
                    for extension, count in neighborhood_file_extension_counts.most_common()
                ],
                "simpe_reference": {
                    "loaded": self._simpe_reference is not None,
                    "source_path": self._simpe_reference.source_path if self._simpe_reference else "",
                    "known_hood_kinds": list(self._simpe_reference.hood_kinds) if self._simpe_reference else [],
                },
                "package_role_profile": [
                    {"role": role, "count": count}
                    for role, count in package_role_counts.most_common()
                ],
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

    def _scan_neighborhood_file_inventory(self, neighborhood_dir: Path) -> dict[str, object]:
        files = sorted(path for path in neighborhood_dir.rglob("*") if path.is_file())
        extension_counts: Counter[str] = Counter()
        extension_sizes: Counter[str] = Counter()
        role_counts: Counter[str] = Counter()
        role_sizes: Counter[str] = Counter()
        noteworthy_files: list[dict[str, object]] = []
        total_size = 0

        for file_path in files:
            size = file_path.stat().st_size
            total_size += size
            extension = file_path.suffix.lower() or "<none>"
            role = self._classify_neighborhood_file_role(neighborhood_dir, file_path)

            extension_counts.update([extension])
            extension_sizes[extension] += size
            role_counts.update([role])
            role_sizes[role] += size

            if len(noteworthy_files) < 20 and role not in {"Character Package", "Storytelling Image"}:
                noteworthy_files.append(
                    {
                        "relative_path": str(file_path.relative_to(neighborhood_dir)),
                        "role": role,
                        "extension": extension,
                        "size": size,
                    }
                )

        return {
            "total_file_count": len(files),
            "total_size": total_size,
            "extension_profile": [
                {"extension": extension, "count": count, "total_size": extension_sizes[extension]}
                for extension, count in extension_counts.most_common()
            ],
            "role_profile": [
                {"role": role, "count": count, "total_size": role_sizes[role]}
                for role, count in role_counts.most_common()
            ],
            "noteworthy_files": noteworthy_files,
        }

    def _classify_neighborhood_file_role(self, neighborhood_dir: Path, file_path: Path) -> str:
        relative = file_path.relative_to(neighborhood_dir)
        relative_parts = [part.lower() for part in relative.parts]
        name = file_path.name
        lower_name = name.lower()
        suffix = file_path.suffix.lower()

        if relative_parts and relative_parts[0] == "characters" and suffix == ".package":
            return "Character Package"
        if relative_parts and relative_parts[0] == "lots" and suffix == ".package":
            return "Lot Package"
        if relative_parts and relative_parts[0] == "thumbnails" and suffix == ".package":
            return "Thumbnail Package"
        if relative_parts and relative_parts[0] == "storytelling" and suffix == ".xml":
            return "Storytelling Entry"
        if relative_parts and relative_parts[0] == "storytelling" and suffix in IMAGE_SUFFIXES:
            return "Storytelling Image"
        if lower_name == f"{neighborhood_dir.name.lower()}_neighborhood.package":
            return "Neighborhood Main Package"
        if lower_name.startswith(f"{neighborhood_dir.name.lower()}_suburb") and suffix == ".package":
            return "Suburb Package"
        if lower_name == f"{neighborhood_dir.name.lower()}_neighborhood.png":
            return "Neighborhood Preview Image"
        if lower_name.startswith(f"{neighborhood_dir.name.lower()}_suburb") and suffix == ".png":
            return "Suburb Preview Image"
        if suffix == ".reia":
            return "Neighborhood Metadata"
        if suffix == ".dat":
            return "Raw Data"
        if suffix == ".xml":
            return "XML Data"
        if suffix == ".package":
            return "Other Package"
        if suffix in IMAGE_SUFFIXES:
            return "Image Asset"
        return "Other File"

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
        package_role = self._classify_package_role(path)
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
            "package_role": package_role,
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
                "type_short_name": self._resource_short_name(values[0]),
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
        if self._simpe_reference is not None and type_id in self._simpe_reference.type_entries:
            return self._simpe_reference.type_entries[type_id].name
        return DBPF_RESOURCE_TYPE_NAMES.get(type_id, "Unknown Resource")

    def _resource_short_name(self, type_id: int) -> str:
        if self._simpe_reference is not None and type_id in self._simpe_reference.type_entries:
            return self._simpe_reference.type_entries[type_id].short_name
        return DBPF_RESOURCE_SHORT_NAMES.get(type_id, "UNK")

    def _resource_domain_hint(self, type_id: int) -> str:
        return DBPF_DOMAIN_HINTS.get(type_id, "Unknown")

    def _build_domain_profile(self, index_entries: list[dict[str, int | str]]) -> list[dict[str, int | str]]:
        counts = Counter(str(entry.get("domain_hint", "Unknown")) for entry in index_entries)
        return [
            {"domain": domain, "count": count}
            for domain, count in counts.most_common(6)
        ]

    def _classify_package_role(self, path: Path) -> str:
        name = path.name
        parent_name = path.parent.name.lower()
        if name == "NeighborhoodManager.package":
            return "Neighborhood Manager"
        if name.endswith("_Neighborhood.package"):
            return "Neighborhood Main"
        if "_Suburb" in name:
            return "Suburb"
        if parent_name == "characters":
            return "Character/Sim"
        if parent_name == "lots":
            return "Lot"
        return "Other Package"
