from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET


@dataclass(frozen=True, slots=True)
class SimPETypeEntry:
    type_id: int
    name: str
    short_name: str


@dataclass(frozen=True, slots=True)
class SimPEReferenceCatalog:
    source_path: str
    type_entries: dict[int, SimPETypeEntry]
    hood_kinds: tuple[str, ...]


def detect_default_simpe_path() -> Path | None:
    configured = os.environ.get("S2ATLAS_SIMPE_PATH", "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))

    repo_root = Path(__file__).resolve().parents[3]
    candidates.append(repo_root.parent / "Sims2-Savegame" / "SimPE-Sims2Editor")

    for candidate in candidates:
        if (candidate / "Data" / "tgi.xml").is_file():
            return candidate
    return None


@lru_cache(maxsize=2)
def load_simpe_reference_catalog(base_path_text: str | None = None) -> SimPEReferenceCatalog | None:
    if base_path_text:
        base_path = Path(base_path_text)
    else:
        base_path = detect_default_simpe_path()
        if base_path is None:
            return None

    tgi_path = base_path / "Data" / "tgi.xml"
    if not tgi_path.is_file():
        return None

    type_entries: dict[int, SimPETypeEntry] = {}
    tree = ET.parse(tgi_path)
    root = tree.getroot()
    for node in root.findall("type"):
        value_text = node.get("value", "").strip()
        name = (node.findtext("name") or "").strip()
        short_name = (node.findtext("shortname") or "").strip()
        if not value_text or not name:
            continue
        try:
            type_id = int(value_text, 16)
        except ValueError:
            continue
        type_entries[type_id] = SimPETypeEntry(type_id=type_id, name=name, short_name=short_name)

    hoods_path = base_path / "Data" / "hoods.xml"
    hood_kinds: tuple[str, ...] = ()
    if hoods_path.is_file():
        hood_tree = ET.parse(hoods_path)
        hood_root = hood_tree.getroot()
        hood_kinds = tuple(
            hood.get("name", "").strip()
            for hood in hood_root.findall("hood")
            if hood.get("name", "").strip()
        )

    return SimPEReferenceCatalog(
        source_path=str(base_path),
        type_entries=type_entries,
        hood_kinds=hood_kinds,
    )
