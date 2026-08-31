"""Mock tool backends for Lab 1 demos."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from rag_protection_proxy.tools_gateway.backends.mcp_shim import invoke_mcp_backend
from rag_protection_proxy.tools_gateway.policy import ToolPolicyEntry


class SendEmailArgs(BaseModel):
    to: str = Field(min_length=3)
    subject: str = Field(default="", max_length=500)
    body: str = Field(default="")


class ReadFileArgs(BaseModel):
    path: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def path_not_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("path must be non-empty")
        return cleaned


class RunSqlArgs(BaseModel):
    query: str = Field(min_length=1)

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query must be non-empty")
        return cleaned


def invoke_mock_email(
    arguments: Dict[str, Any],
    entry: Optional[ToolPolicyEntry] = None,
) -> Dict[str, Any]:
    args = SendEmailArgs.model_validate(arguments)
    return {
        "status": "sent",
        "message_id": "mock-email-001",
        "to": args.to,
        "subject": args.subject,
        "body_preview": args.body[:120],
    }


def invoke_mock_files(
    arguments: Dict[str, Any],
    entry: Optional[ToolPolicyEntry] = None,
) -> Dict[str, Any]:
    args = ReadFileArgs.model_validate(arguments)
    return {
        "status": "ok",
        "path": args.path,
        "content": f"[mock file contents for {args.path}]",
        "bytes": 42,
    }


def invoke_mock_sql(
    arguments: Dict[str, Any],
    entry: Optional[ToolPolicyEntry] = None,
) -> Dict[str, Any]:
    args = RunSqlArgs.model_validate(arguments)
    return {
        "status": "ok",
        "query": args.query,
        "rows": [
            {"employee_id": "E1001", "department": "Engineering", "salary_band": "IC4"},
            {"employee_id": "E1002", "department": "HR", "salary_band": "M1"},
        ],
        "row_count": 2,
    }


BACKEND_HANDLERS = {
    "mock_email": invoke_mock_email,
    "mock_files": invoke_mock_files,
    "mock_sql": invoke_mock_sql,
    "mcp_filesystem": invoke_mcp_backend,
}

BACKEND_ARG_MODELS = {
    "mock_email": SendEmailArgs,
    "mock_files": ReadFileArgs,
    "mock_sql": RunSqlArgs,
    "mcp_filesystem": ReadFileArgs,
}
