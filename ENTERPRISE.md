# Enterprise Edition

**Marifort Gate** is open core — two packages, wired at runtime via `register_enterprise()`:

| Edition | License | Package | Get it |
|---------|---------|---------|--------|
| **Community Edition (CE)** | [MIT](LICENSE) | `rag-protection-proxy` | **This repository** — guardrail pipeline, ACL at retrieval, OIDC, CE operator console, Docker/Helm |
| **Enterprise Edition (EE)** | Commercial subscription | `rag-protection-enterprise` | Separate private package — live connectors, pgvector, compliance packs, premium operator UX, support SLA |

This public tree **does not contain EE source**. CE installs and runs standalone. `GET /health` → `enterprise_installed: false` until the commercial wheel is installed.

## Community Edition includes

- Four-guardrail pipeline (ACL, DLP, injection, citation)
- SQLite, Qdrant, and hybrid retrieval with ACL metadata filters
- OIDC/JWKS (Okta, Azure AD) and demo bearer tokens
- Operator console (Overview, Query Lab, Documents & Ingest, Tool Gateway, Audit Log)
- Docker Compose, Helm chart, smoke tests, architecture documentation

## Enterprise Edition adds

- Live connectors (Google Drive OAuth, scheduled sync) and SCIM onboarding
- Postgres pgvector backend and production scale options
- Compliance artifact pack, audit retention, export scrub, rate limits
- Premium operator UX (policy forms, audit analytics, pattern lab, CHALLENGE queue)
- Enterprise support, SLA, DPA, and professional implementation

Optional Compose overlay `compose.ee.yml` documents how an EE image is built **when** you have the commercial checkout. It is not required for CE.

## Contact

**Vendor:** Marifort Systems Inc., Ontario, Canada

- Email: [support@marifort.com](mailto:support@marifort.com)

**Copyright:** © 2024-2026 Marifort Systems Inc. Community Edition is MIT; Enterprise Edition is proprietary.
