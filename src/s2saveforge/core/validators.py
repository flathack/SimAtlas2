from __future__ import annotations

from dataclasses import dataclass
from collections import Counter

from s2saveforge.core.models import SaveGame


@dataclass(slots=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    entity_id: str = ""


def summarize_issues(issues: list[ValidationIssue]) -> dict[str, int]:
    counts = Counter(issue.severity for issue in issues)
    return {
        "error": counts.get("error", 0),
        "warning": counts.get("warning", 0),
        "info": counts.get("info", 0),
        "total": len(issues),
    }


def group_issues_by_entity(issues: list[ValidationIssue]) -> dict[str, list[ValidationIssue]]:
    grouped: dict[str, list[ValidationIssue]] = {}
    for issue in issues:
        entity_id = issue.entity_id or "_global"
        grouped.setdefault(entity_id, []).append(issue)
    return grouped


def validate_savegame(savegame: SaveGame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    metadata = savegame.metadata

    if metadata.get("source_kind") == "folder_preview":
        if not metadata.get("neighborhood_manager_exists", False):
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="PREVIEW_MISSING_NEIGHBORHOOD_MANAGER",
                    message="NeighborhoodManager.package is missing from the Neighborhoods folder.",
                )
            )

    sim_ids = {sim.id for sim in savegame.sims}
    household_ids = {household.id for household in savegame.households}

    if len(sim_ids) != len(savegame.sims):
        issues.append(
            ValidationIssue(
                severity="error",
                code="SIM_DUPLICATE_ID",
                message="At least one Sim ID is duplicated.",
            )
        )

    if len(household_ids) != len(savegame.households):
        issues.append(
            ValidationIssue(
                severity="error",
                code="HOUSEHOLD_DUPLICATE_ID",
                message="At least one Household ID is duplicated.",
            )
        )

    for sim in savegame.sims:
        if sim.household_id and sim.household_id not in household_ids:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="SIM_UNKNOWN_HOUSEHOLD",
                    message=f"Sim references unknown household '{sim.household_id}'.",
                    entity_id=sim.id,
                )
            )

        if not 1 <= sim.career_level <= 10:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="SIM_CAREER_LEVEL_RANGE",
                    message="Career level is outside common range 1..10.",
                    entity_id=sim.id,
                )
            )

        for skill_name, value in sim.skills.items():
            if not 0 <= value <= 10:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="SIM_SKILL_RANGE",
                        message=f"Skill '{skill_name}' outside allowed range 0..10.",
                        entity_id=sim.id,
                    )
                )

        for need_name, value in sim.needs.items():
            if not 0 <= value <= 100:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="SIM_NEED_RANGE",
                        message=f"Need '{need_name}' outside allowed range 0..100.",
                        entity_id=sim.id,
                    )
                )

    for household in savegame.households:
        household_meta = household.metadata
        if household_meta.get("kind") == "neighborhood_preview":
            if not household_meta.get("main_package_exists", False):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="PREVIEW_MISSING_MAIN_PACKAGE",
                        message="Neighborhood main package is missing.",
                        entity_id=household.id,
                    )
                )
            if not household_meta.get("characters_dir_exists", False):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="PREVIEW_MISSING_CHARACTERS_DIR",
                        message="Characters directory is missing.",
                        entity_id=household.id,
                    )
                )
            if not household_meta.get("lots_dir_exists", False):
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="PREVIEW_MISSING_LOTS_DIR",
                        message="Lots directory is missing.",
                        entity_id=household.id,
                    )
                )
            if household_meta.get("character_count", 0) == 0:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="PREVIEW_NO_CHARACTER_PACKAGES",
                        message="No character packages were found for this neighborhood preview.",
                        entity_id=household.id,
                    )
                )
            if household_meta.get("lot_count", 0) == 0:
                issues.append(
                    ValidationIssue(
                        severity="info",
                        code="PREVIEW_NO_LOT_PACKAGES",
                        message="No lot packages were found for this neighborhood preview.",
                        entity_id=household.id,
                    )
                )

        if household.funds < 0:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="HOUSEHOLD_NEGATIVE_FUNDS",
                    message="Household funds are negative.",
                    entity_id=household.id,
                )
            )

        for member in household.members:
            if member not in sim_ids:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="HOUSEHOLD_UNKNOWN_MEMBER",
                        message=f"Household references unknown Sim '{member}'.",
                        entity_id=household.id,
                    )
                )

    for rel in savegame.relationships:
        if rel.sim_a not in sim_ids or rel.sim_b not in sim_ids:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="RELATIONSHIP_UNKNOWN_SIM",
                    message="Relationship references unknown Sim IDs.",
                    entity_id=f"{rel.sim_a}->{rel.sim_b}",
                )
            )

        if not -100 <= rel.score_daily <= 100:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="RELATIONSHIP_DAILY_RANGE",
                    message="Daily relationship score outside typical range -100..100.",
                    entity_id=f"{rel.sim_a}->{rel.sim_b}",
                )
            )

        if not -100 <= rel.score_lifetime <= 100:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="RELATIONSHIP_LIFETIME_RANGE",
                    message="Lifetime relationship score outside typical range -100..100.",
                    entity_id=f"{rel.sim_a}->{rel.sim_b}",
                )
            )

    return issues
