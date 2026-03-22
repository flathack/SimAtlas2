from pathlib import Path

from s2saveforge.core.parser import SaveParser


def test_parser_uses_optional_simpe_reference_catalog(tmp_path: Path) -> None:
    simpe_root = tmp_path / "SimPE-Sims2Editor" / "Data"
    simpe_root.mkdir(parents=True)
    (simpe_root / "tgi.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<tgi>
  <type value="AACE2EFB">
    <name>Sim Description</name>
    <shortname>SDSC</shortname>
  </type>
  <type value="CC364C2A">
    <name>Sim Relations</name>
    <shortname>SREL</shortname>
  </type>
</tgi>
""",
        encoding="utf-8",
    )
    (simpe_root / "hoods.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<hoods>
  <hood name="university"/>
  <hood name="downtown"/>
</hoods>
""",
        encoding="utf-8",
    )

    parser = SaveParser(str(simpe_root.parent))

    assert parser._resource_type_name(0xAACE2EFB) == "Sim Description"
    assert parser._resource_short_name(0xAACE2EFB) == "SDSC"
    assert parser._resource_type_name(0xCC364C2A) == "Sim Relations"
    assert parser._resource_short_name(0xCC364C2A) == "SREL"
    assert parser._simpe_reference is not None
    assert parser._simpe_reference.hood_kinds == ("university", "downtown")
