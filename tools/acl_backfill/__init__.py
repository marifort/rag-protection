"""acl-backfill — Vector ACL backfill / migration utility (A4, consulting tool).

One-shot CLI that maps source permissions → ``allowed_groups`` and patches
existing vector payloads **without re-embedding**. Reuses the shipped
``connectors/acl_mapping`` semantics so backfilled corpora stay drift-ready
for Lab 4 / ACL sync (#12).

Service SKU companion to the ACL mapping workshop — not a product entitlement.
"""

from __future__ import annotations

__version__ = "0.1.0"
