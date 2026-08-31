"""Scan context: loads policy/ACL/sample docs using the runtime loaders."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import _bootstrap

_bootstrap.ensure_proxy_importable()

# Imported after bootstrap so the runtime loaders are guaranteed importable.
from rag_protection_proxy.config import (  # noqa: E402
    ACLPolicy,
    Policy,
    PolicyValidationError,
    load_acl_policy,
    load_policy,
)


class ConfigLoadError(Exception):
    """Raised when a policy/ACL file cannot be parsed or validated (exit code 2)."""


@dataclass
class ScanContext:
    """Everything a check needs. Loaded files are validated via runtime loaders."""

    env: str = "dev"
    policy_path: Optional[Path] = None
    acl_path: Optional[Path] = None
    sample_docs_path: Optional[Path] = None
    qdrant_url: Optional[str] = None

    policy: Optional[Policy] = None
    acl: Optional[ACLPolicy] = None
    sample_docs: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_prod(self) -> bool:
        return self.env.lower() in {"prod", "production"}


def build_context(
    *,
    env: str = "dev",
    policy_path: Optional[str] = None,
    acl_path: Optional[str] = None,
    sample_docs_path: Optional[str] = None,
    qdrant_url: Optional[str] = None,
) -> ScanContext:
    """Load and validate inputs. Raises ConfigLoadError on invalid YAML/policy."""
    ctx = ScanContext(
        env=env,
        policy_path=Path(policy_path) if policy_path else None,
        acl_path=Path(acl_path) if acl_path else None,
        sample_docs_path=Path(sample_docs_path) if sample_docs_path else None,
        qdrant_url=qdrant_url,
    )

    if policy_path:
        if not ctx.policy_path.exists():
            raise ConfigLoadError(f"policy file not found: {policy_path}")
        try:
            ctx.policy = load_policy(str(policy_path))
        except (PolicyValidationError, ValueError) as exc:
            raise ConfigLoadError(f"invalid policy ({policy_path}): {exc}") from exc

    if acl_path:
        if not ctx.acl_path.exists():
            raise ConfigLoadError(f"acl file not found: {acl_path}")
        try:
            ctx.acl = load_acl_policy(str(acl_path))
        except (PolicyValidationError, ValueError) as exc:
            raise ConfigLoadError(f"invalid acl policy ({acl_path}): {exc}") from exc

    if sample_docs_path:
        if not ctx.sample_docs_path.exists():
            raise ConfigLoadError(f"sample docs not found: {sample_docs_path}")
        try:
            raw = json.loads(ctx.sample_docs_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigLoadError(f"invalid sample docs JSON ({sample_docs_path}): {exc}") from exc
        if not isinstance(raw, list):
            raise ConfigLoadError("sample docs must be a JSON array of documents")
        ctx.sample_docs = [d for d in raw if isinstance(d, dict)]

    return ctx
