# Shared documentation (CE + EE)

Single source for concepts that apply to both editions. **Does not** duplicate CE/EE boundary claims — see [editions/README.md](../../ENTERPRISE.md) for tiering.

| Document | Purpose |
|----------|---------|
| [architecture.md](architecture.md) | **Canonical** system architecture, pipeline, threat model |
| [ce/security/PIPELINE_LAYERS_AND_THREAT_MAINTENANCE.md](../ce/security/PIPELINE_LAYERS_AND_THREAT_MAINTENANCE.md) | Four-layer firewall sketch vs this pipeline; threat-maintenance process |
| [edition/README.md](../ce/README.md) | Directory-level CE / EE / shared / internal map + `check_tree.py` |
| [PRODUCTION_ARCHITECTURE.md](PRODUCTION_ARCHITECTURE.md) | Production topology: HTTP :8090, TLS at ingress, HA honesty |
| [PRODUCTION_SCENARIOS.md](PRODUCTION_SCENARIOS.md) | When HTTPS is required; when HA is in or out of scope |
| [PRODUCT_OWNERSHIP_GUIDE.md](PRODUCT_OWNERSHIP_GUIDE.md) | End-to-end ownership handoff (master routing) |
| [OWNERSHIP_HANDOFF_CHECKLIST.md](OWNERSHIP_HANDOFF_CHECKLIST.md) | Sign-off checklist + evidence |
| [FEATURE_CATALOG_INDEX.md](FEATURE_CATALOG_INDEX.md) | Long-form catalog jump table (#1–#31) |
| [FEATURE_ID_ALIASES.md](FEATURE_ID_ALIASES.md) | Lab/A → `#N` aliases |
| [compliance/](../ce/README.md) | Trust artifacts (SOC readiness, data handling, security FAQ) |

**Day-to-day features:** [INDEX.md](../INDEX.md) · **Pipeline controls:** [ce/security/](../ce/security/README.md)
