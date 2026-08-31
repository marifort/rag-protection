"""Run red-team scenarios against a live proxy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .assertions import evaluate_scenario
from .client import RedTeamClient
from .models import Scenario, ScenarioResult
from .scenario import ScenarioLoadError, load_scenario


def run_scenario(
    client: RedTeamClient,
    scenario: Scenario,
    *,
    tenant_id: str = "default",
) -> ScenarioResult:
    ingest_results: List[dict] = []
    for doc in scenario.setup_ingest:
        ingest_results.append(
            client.ingest(
                doc.document_id,
                doc.title,
                doc.content,
                allowed_groups=doc.allowed_groups,
                tenant_id=tenant_id,
            )
        )
    query_result: Optional[dict] = None
    if scenario.attack:
        query_result = client.query(
            scenario.attack.query,
            token=scenario.attack.token,
            include_audit=True,
        )
    return evaluate_scenario(
        scenario,
        ingest_results=ingest_results,
        query_result=query_result,
    )


def run_scenarios(
    client: RedTeamClient,
    scenarios: List[Scenario],
    *,
    tenant_id: str = "default",
) -> List[ScenarioResult]:
    return [run_scenario(client, scenario, tenant_id=tenant_id) for scenario in scenarios]


def load_and_run(
    client: RedTeamClient,
    scenario_path: Path,
    *,
    tenant_id: str = "default",
) -> ScenarioResult:
    return run_scenario(client, load_scenario(scenario_path), tenant_id=tenant_id)


def write_results(out_dir: Path, results: List[ScenarioResult], audit_ndjson: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
        },
        "results": [r.to_dict() for r in results],
    }
    results_path = out_dir / "results.json"
    results_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "audit.ndjson").write_text(audit_ndjson, encoding="utf-8")
    return results_path
