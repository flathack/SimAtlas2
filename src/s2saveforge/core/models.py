from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Sim:
    id: str
    name: str
    age_stage: str
    aspiration: str
    household_id: str
    career: str = ""
    career_level: int = 1
    needs: dict[str, int] = field(default_factory=dict)
    skills: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Sim":
        return Sim(
            id=str(data.get("id", "")),
            name=str(data.get("name", "Unknown Sim")),
            age_stage=str(data.get("age_stage", "adult")),
            aspiration=str(data.get("aspiration", "")),
            household_id=str(data.get("household_id", "")),
            career=str(data.get("career", "")),
            career_level=int(data.get("career_level", 1)),
            needs={k: int(v) for k, v in dict(data.get("needs", {})).items()},
            skills={k: int(v) for k, v in dict(data.get("skills", {})).items()},
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "age_stage": self.age_stage,
            "aspiration": self.aspiration,
            "household_id": self.household_id,
            "career": self.career,
            "career_level": self.career_level,
            "needs": dict(self.needs),
            "skills": dict(self.skills),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class Household:
    id: str
    name: str
    funds: int
    members: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Household":
        return Household(
            id=str(data.get("id", "")),
            name=str(data.get("name", "Unknown Household")),
            funds=int(data.get("funds", 0)),
            members=[str(member) for member in data.get("members", [])],
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "funds": self.funds,
            "members": list(self.members),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class Relationship:
    sim_a: str
    sim_b: str
    score_daily: int = 0
    score_lifetime: int = 0
    flags: list[str] = field(default_factory=list)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Relationship":
        return Relationship(
            sim_a=str(data.get("sim_a", "")),
            sim_b=str(data.get("sim_b", "")),
            score_daily=int(data.get("score_daily", 0)),
            score_lifetime=int(data.get("score_lifetime", 0)),
            flags=[str(flag) for flag in data.get("flags", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sim_a": self.sim_a,
            "sim_b": self.sim_b,
            "score_daily": self.score_daily,
            "score_lifetime": self.score_lifetime,
            "flags": list(self.flags),
        }


@dataclass(slots=True)
class SaveGame:
    version: str = "0.1"
    sims: list[Sim] = field(default_factory=list)
    households: list[Household] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "SaveGame":
        return SaveGame(
            version=str(data.get("version", "0.1")),
            sims=[Sim.from_dict(item) for item in data.get("sims", [])],
            households=[Household.from_dict(item) for item in data.get("households", [])],
            relationships=[Relationship.from_dict(item) for item in data.get("relationships", [])],
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "households": [household.to_dict() for household in self.households],
            "sims": [sim.to_dict() for sim in self.sims],
            "relationships": [rel.to_dict() for rel in self.relationships],
            "metadata": dict(self.metadata),
        }

    def clone(self) -> "SaveGame":
        return SaveGame.from_dict(self.to_dict())
