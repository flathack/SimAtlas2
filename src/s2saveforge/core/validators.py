from __future__ import annotations

from dataclasses import dataclass

from s2saveforge.core.models import SaveGame


@dataclass(slots=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    entity_id: str = ""


def validate_savegame(savegame: SaveGame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

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
