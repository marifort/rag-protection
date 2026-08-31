"""Load scenario YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import yaml

from .models import AttackSpec, ExpectSpec, IngestSpec, Scenario


class ScenarioLoadError(Exception):
    """Invalid scenario file."""


def _require_mapping(raw: object, path: Path) -> dict:
    if not isinstance(raw, dict):
        raise ScenarioLoadError(f"{path}: expected mapping at root")
    return raw


def load_scenario(path: Path) -> Scenario:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    data = _require_mapping(raw, path)
    scenario_id = str(data.get("id") or path.stem)
    title = str(data.get("title") or scenario_id)
    owasp = data.get("owasp")
    setup = data.get("setup") or {}
    ingest_rows = setup.get("ingest") or []
    setup_ingest: List[IngestSpec] = []
    for row in ingest_rows:
        if not isinstance(row, dict):
            continue
        setup_ingest.append(
            IngestSpec(
                document_id=str(row["document_id"]),
                title=str(row.get("title") or row["document_id"]),
                content=str(row.get("content") or ""),
                allowed_groups=[str(g) for g in (row.get("allowed_groups") or ["all-staff"])],
            )
        )
    attack_raw = data.get("attack")
    attack: Optional[AttackSpec] = None
    if isinstance(attack_raw, dict):
        attack = AttackSpec(
            token=str(attack_raw["token"]),
            query=str(attack_raw["query"]),
        )
    expect_raw = data.get("expect")
    expect: Optional[ExpectSpec] = None
    if isinstance(expect_raw, dict):
        expect = ExpectSpec(
            decision=str(expect_raw["decision"]),
            control=expect_raw.get("control"),
            not_in_answer=[str(v) for v in (expect_raw.get("not_in_answer") or [])],
        )
    return Scenario(
        id=scenario_id,
        title=title,
        owasp=str(owasp) if owasp else None,
        setup_ingest=setup_ingest,
        attack=attack,
        expect=expect,
        uses_sample_corpus=bool(data.get("uses_sample_corpus")),
        exploitability=float(data.get("exploitability", 0.7)),
        sensitivity=float(data.get("sensitivity", 0.7)),
    )


def list_scenarios(directory: Path) -> List[Path]:
    return sorted(directory.glob("*.yaml"))
