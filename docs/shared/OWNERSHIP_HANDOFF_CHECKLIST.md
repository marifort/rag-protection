# Product Ownership Handoff Checklist

**Audience:** Internal product owner, successor developer/architect, Security, Product  
**Purpose:** Evidence-based sign-off for transferring engineering and architecture ownership of Community Edition (CE) and, when licensed and available, Enterprise Edition (EE)  
**Companion guides:** [Product Ownership Guide](PRODUCT_OWNERSHIP_GUIDE.md) · [CE Developer Guide](../ce/guide/DEVELOPER_GUIDE.md) · [EE Developer Guide](../../ENTERPRISE.md)

Use a dated handoff folder, ticket, or internal evidence workspace for outputs. Record links, commit SHAs, CI run URLs, screenshots, and redacted logs; do **not** paste tokens, keys, customer data, private package contents, or other secrets into this document or the evidence record.

Mark an item complete only when its pass condition is met. An EE item may be **N/A** only when the EE repository/package, license, entitlement, or target environment is unavailable or the feature is explicitly Planned/Optional. Record the precise reason, approver, and a follow-up owner/date; lack of familiarity is not an N/A reason.

**Handoff record**

| Field | Value |
|---|---|
| Scope / editions | `CE` / `CE + EE` / other: |
| Owner | |
| Successor | |
| Target handoff date | |
| Evidence workspace | |
| CE commit / release | |
| EE commit / release or N/A reason | |
| Open risks / exceptions | |

## 1. Access and prerequisites

| Done | Checklist item | Evidence / command | Pass condition |
|---|---|---|---|
| [ ] | Confirm least-privilege access to the CE repository and protected branches. | `gh repo view <ce-owner>/<ce-repo>`; `gh api repos/<ce-owner>/<ce-repo>/branches/main/protection` or repository-settings screenshot. | Successor can clone, create a branch/PR, and view protection rules; direct production bypass is not required. |
| [ ] | Confirm EE repository access when licensed and in scope. | `gh repo view <ee-owner>/<ee-repo>`; record repository URL and access approval, not credentials. | Successor can read the private repository and its release/pinning instructions, or item is N/A with license/access reason and approver. |
| [ ] | Confirm CI, artifact, container-registry, deployment, monitoring, and incident-system roles. | Links to access-group membership and a read-only visit to one recent run/artifact/dashboard/incident queue. | Every in-scope system has a named access group, successor access is verified, and no shared personal account is required. |
| [ ] | Confirm private package delivery ownership without copying package credentials. | Redacted package-source configuration; `python -m pip config debug` with URLs/usernames/tokens removed; link to secret-manager entry by name only. | Successor can identify package source, publishing owner, consumer flow, and rotation contact; no secret value appears in evidence. |
| [ ] | Establish a clean local toolchain. | `python3 --version`; `node --version`; `npm --version`; `docker version`; `gh auth status` with account details redacted as needed. | Versions satisfy the developer guides and all tools run without exposing credentials. |
| [ ] | Verify repository hygiene before exercises. | `git status --short`; `git remote -v`; `git branch --show-current`. | Intended checkout/branch/remotes are clear; pre-existing changes are identified and not overwritten. |
| [ ] | Review secret handling and rotation ownership. | Link to secret-management runbook and rotation schedule; `git ls-files | rg '(^|/)(\.env|credentials|secrets?)(\.|/|$)'` reviewed manually. | Secrets are supplied through approved stores/environment injection, tracked files contain samples/placeholders only, and rotation has a named owner. |

## 2. Architecture teach-back

| Done | Checklist item | Evidence / command | Pass condition |
|---|---|---|---|
| [ ] | Explain the request path from identity through ACL-filtered retrieval, four guardrails, response, and audit. | Successor-created diagram/notes cross-checked against [CE Architecture](../../ENTERPRISE.md) and the [Product Ownership Guide](PRODUCT_OWNERSHIP_GUIDE.md). | Owner can challenge any stage and successor correctly identifies fail-closed boundaries, data stores, and audit outputs. |
| [ ] | Explain CE/EE packaging and registration seams. | Teach-back references `register_enterprise()`, `enterprise_installed`, `CE_PIN`, Tier 1/2/3 routes, and lazy-loaded `ee-ui.js`; run `pytest rag-protection-proxy/tests/test_ce_ee_seams.py -q`. | Successor explains why CE remains independently runnable, why absent EE routes return 404, and how EE extends rather than forks the CE trust pipeline; seam tests pass. |
| [ ] | Explain storage-specific ACL enforcement. | Trace one query in code/tests for SQLite and Qdrant; cite [CE Design](../../ENTERPRISE.md). | Successor distinguishes SQLite application-side filtering before scoring from Qdrant in-query filtering and identifies the regression tests. |
| [ ] | Identify authority boundaries and change impact. | Successor maps runtime/seam, build/deploy, readiness, functional specification, feature catalog, and commercial claims to their canonical documents. | For three sample conflicts, successor selects the correct authority and names documents that must be updated together. |
| [ ] | Walk through one failure mode end to end. | Redacted trace/log for a blocked injection, ACL denial, DLP finding, or citation failure. | Successor locates decision, block reason, audit event, operator surface, and relevant test without relying on the outgoing owner. |

## 3. Local CE proof

| Done | Checklist item | Evidence / command | Pass condition |
|---|---|---|---|
| [ ] | Build and install CE in a CE-only environment. | `bash tools/build_ce.sh --install --typecheck --test`; save command output and commit SHA. | Command exits 0 and the evidence identifies the source commit and tool versions. |
| [ ] | Prove EE is not accidentally registered. | `python -c "from rag_protection_proxy.app import app; assert not getattr(app.state, 'enterprise_registered', False)"`. | Assertion exits 0 in the CE-only environment. |
| [ ] | Run CE unit and seam tests. | `bash tools/workflow_validate_commit.sh ce`; if unavailable, record equivalent `pytest` and console test commands from the [CE Developer Guide](../ce/guide/DEVELOPER_GUIDE.md). | Required CE validation exits 0; any documented exclusions have owner and due date. |
| [ ] | Start and smoke the CE stack. | `bash tools/docker_start.sh --smoke`; capture health, smoke summary, and `bash tools/docker_stop.sh` result. | Health is ready, Tier 1 smoke passes, and the stack shuts down cleanly. |
| [ ] | Prove the CE-only edition boundary. | With the CE service running, probe one Tier 1 endpoint and one Tier 2 endpoint using placeholder environment variables such as `${ADMIN_TOKEN}`; save only status codes. | Tier 1 behaves as documented and the absent Tier 2 route returns 404, not a misleading enabled/forbidden response. |
| [ ] | Demonstrate the CE console. | Screenshot or short recording of the four documented CE workspaces at the tested commit. | Overview, Query Lab, Tool Gateway, and Audit Log are present; no EE-only workspace is represented as CE. |

## 4. Local EE proof when package is available

| Done | Checklist item | Evidence / command | Pass condition |
|---|---|---|---|
| [ ] | Record EE availability before testing. | `test -d "${EE_ROOT:-rag-protection-enterprise}" && printf 'EE checkout present\n'`; link license/package access approval. | EE checkout/package is available and authorized, or item is N/A with reason, approver, and reassessment date. |
| [ ] | Install CE + EE through the supported path. | `bash tools/dev_install_ee.sh`; do not record package tokens or private artifact contents. | Install exits 0 and both package names are visible in a redacted `python -m pip list` excerpt. |
| [ ] | Build the complete UI. | `bash tools/build_ee.sh --with-ce --typecheck`; use exact supported flags from the [EE Developer Guide](../../ENTERPRISE.md) if they differ. | CE shell and EE bundle build successfully at recorded commits. |
| [ ] | Prove EE registration and route semantics. | `python -c "from rag_protection_proxy.app import app; assert getattr(app.state, 'enterprise_registered', False)"`; authenticated/unauthenticated Tier 2 probes using `${ADMIN_TOKEN}`. | Registration assertion passes; existing protected EE route rejects unauthenticated access and succeeds for an authorized role. |
| [ ] | Validate EE against its pinned CE. | `bash tools/workflow_validate_commit.sh ee`; record `cat "$EE_ROOT/CE_PIN"` and resolved CE tag/commit. | Validation exits 0 against `CE_PIN`, and the pin resolves to an immutable CE release artifact. |
| [ ] | Demonstrate one shipped EE workflow and one entitlement denial. | Redacted API/UI evidence for a shipped Tier 2/3 workflow plus a request lacking a required entitlement. | Authorized shipped workflow succeeds; an existing unentitled route returns 403; Planned features are not presented as live. |

## 5. Security invariant proof

| Done | Checklist item | Evidence / command | Pass condition |
|---|---|---|---|
| [ ] | Prove ACL enforcement and anti-bypass behavior. | `pytest rag-protection-proxy/tests/test_rag_protection.py rag-protection-proxy/tests/test_vector_store.py -q`. | Tests pass and evidence includes at least one allowed and one denied identity/group case. |
| [ ] | Prove CE/EE route and package isolation. | `pytest rag-protection-proxy/tests/test_ce_ee_seams.py -q`. | Tests pass, including CE-only Tier 2/3 absence and helpful optional-package failure behavior. |
| [ ] | Prove injection, DLP, citation, and URL/egress controls. | `pytest rag-protection-proxy/tests/test_injection_policy.py rag-protection-proxy/tests/test_rag_protection.py rag-protection-proxy/tests/test_url_threat.py -q`. | Tests pass; successor can identify each control's allow/block/challenge outcome and audit signal. |
| [ ] | Prove canary and extraction defenses. | `pytest rag-protection-proxy/tests/test_canary.py rag-protection-proxy/tests/test_extraction.py -q`. | Tests pass and successor explains trigger, response, and operational follow-up. |
| [ ] | Prove tamper-evident audit behavior. | `pytest rag-protection-proxy/tests/test_audit_integrity.py -q`; optionally capture a redacted `/admin/audit/integrity/verify` response. | Valid chain verifies and a tampered fixture fails verification as designed. |
| [ ] | Confirm logs/evidence do not leak sensitive values. | Review captured handoff artifacts with the repository's secret scanner or approved organizational scanner; record tool/version and result. | No credentials, raw tokens, customer data, or prohibited private package contents are present. |

## 6. Configuration and data lifecycle proof

| Done | Checklist item | Evidence / command | Pass condition |
|---|---|---|---|
| [ ] | Identify effective policy sources and precedence. | Record redacted values of relevant path environment variables; compare `config/policy.yaml` with persisted `data/policy.yaml` where applicable. | Successor can state which policy/ACL files each local and deployed mode actually reads and avoids confusing clean seed with persisted data. |
| [ ] | Prove policy validation and reload. | Run the documented policy validator/scanner, then `POST /admin/reload-policy` using `${ADMIN_TOKEN}`; capture status and redacted audit evidence. | Valid change reloads without redeploy, invalid configuration is rejected, and no secret appears in command history/evidence. |
| [ ] | Prove backup and restore when the EE policy-admin route is available. | Use a non-sensitive test knob, list backups, restore the selected test backup, and query audit events; use `${ADMIN_TOKEN}` and retain only redacted requests/results. | Original value is restored, pre-change/current backups are preserved as documented, and `policy_changed`/`policy_restored` evidence exists; otherwise N/A with EE reason. |
| [ ] | Walk through document ingest-to-delete lifecycle. | Ingest a synthetic document, inspect metadata/quarantine state, query with allowed and denied identities, delete it, and save redacted IDs/statuses. | ACL metadata survives ingest, denied identity cannot retrieve content, quarantine behavior matches risk, and deletion removes it from supported query paths. |
| [ ] | Explain audit, vector, policy-backup, and generated-artifact retention. | Link deployment-specific retention/backup schedule and execute a read-only inventory command approved for that environment. | Each data class has owner, location, retention, backup, restore, and deletion procedure; unsupported guarantees are explicitly listed. |
| [ ] | Prove a disposable restore/migration path. | Restore a sanitized fixture or snapshot into an isolated environment and run `rag-scan`/documented validation. | Restored data is readable, ACL metadata is intact, scanner has no release-blocking finding, and production data is untouched. |

## 7. Test and CI ownership

| Done | Checklist item | Evidence / command | Pass condition |
|---|---|---|---|
| [ ] | Map CI workflows to required branch checks. | `gh workflow list`; `gh api repos/<owner>/<repo>/branches/main/protection`; link the test-to-capability map. | Every required check has a purpose, maintainer, expected duration, and escalation path. |
| [ ] | Reproduce CE CI locally. | `bash tools/workflow_validate_commit.sh ce`. | Local gate exits 0 at the same commit as a successful CE CI run, or any environment-only difference is documented and approved. |
| [ ] | Reproduce EE and seam CI when in scope. | `bash tools/workflow_validate_commit.sh ee`; `bash tools/workflow_validate_commit.sh seam --help` followed by an approved non-publishing/dry-run phase. | EE pinned validation passes and successor explains seam ordering; otherwise N/A under the EE rule. |
| [ ] | Triage a known or injected test failure. | Pair on a reversible failing assertion/fixture in a scratch branch; save issue/PR discussion and successful rerun. | Successor identifies owning layer, fixes or correctly routes the failure, and restores a green branch without disabling the check. |
| [ ] | Accept flaky-test and dependency-update ownership. | Link current flaky-test register and dependency/security alert queues; record review cadence. | Queues have named owner, severity SLA, and no unexplained ignored required check. |

## 8. Release pairing and promotion dry run

| Done | Checklist item | Evidence / command | Pass condition |
|---|---|---|---|
| [ ] | Select a known non-production release pair. | Record CE tag, resolved CE commit, EE tag, and `CE_PIN`; `git rev-parse <ce-tag>^{commit}` and `cat "$EE_ROOT/CE_PIN"`. | Tags/pin resolve, versions are compatible, and immutable source SHAs are recorded. |
| [ ] | Rehearse CE-internal, EE-internal, and seam classification. | For three sample changes, run `bash tools/workflow_validate_commit.sh <ce|ee|seam> --help` and write the chosen workflow/reason. | Successor chooses the correct path and identifies when `CE_PIN` must remain unchanged or advance. |
| [ ] | Dry-run promotion ordering without publishing. | Produce a command transcript from [Dev Workflow Quick Reference](../ce/README.md): CE PR/merge → CE validation/tag candidate → EE `CE_PIN` update/validation → EE release candidate. | Owner confirms ordering, version pair, required approvals, and stop points; no tag, package, image, or deployment is published. |
| [ ] | Verify package/image provenance for the selected pair. | Inspect checksums, signatures/attestations, build-run URL, and source SHA using approved registry/package read commands. | Every releasable artifact traces to reviewed source and a successful required CI run. |

## 9. Deployment and rollback drill

| Done | Checklist item | Evidence / command | Pass condition |
|---|---|---|---|
| [ ] | Deploy the selected pair to an isolated local/staging target. | Use the deployment-specific runbook; for local Compose, `bash tools/docker_start.sh --smoke`. | Deployment becomes healthy and smoke/security checks pass at the recorded versions. |
| [ ] | Exercise configuration rollback. | Apply a harmless test change through the supported path, then restore the prior version/backup; capture redacted status and audit evidence. | Effective configuration returns to the baseline and security checks remain green. |
| [ ] | Exercise application rollback. | Roll back to the previous known-good immutable artifact with the environment runbook; record before/after health and version. | Previous version is healthy within the stated recovery objective and no unsupported destructive migration is required. |
| [ ] | Verify post-rollback integrity. | Run smoke, ACL denial, audit integrity, and one representative query after rollback. | All checks pass and the evidence identifies any data written during the failed version. |
| [ ] | Confirm stop/abort authority. | Link change-management record naming deploy lead, rollback caller, Security contact, and Product communicator. | Successor knows who can stop promotion and can initiate rollback without the outgoing owner. |

## 10. Incident response tabletop

| Done | Checklist item | Evidence / command | Pass condition |
|---|---|---|---|
| [ ] | Tabletop an ACL data-exposure scenario. | Timed scenario notes covering alert, containment, evidence preservation, impacted identities/documents, rollback, and notification decision. | Team identifies a decision owner, preserves audit integrity, stops exposure, and produces an initial scope statement within the agreed target. |
| [ ] | Tabletop a prompt-injection/canary event. | Use synthetic events from tests or SIEM samples; record alert route and investigation queries with sensitive fields removed. | Successor distinguishes malicious corpus behavior from model/output failure and identifies quarantine/remediation steps. |
| [ ] | Tabletop compromised package/dependency or signing identity. | Scenario notes reference artifact provenance, credential rotation, release revocation, and customer/deployment impact. | Team can block promotion, identify affected versions, rotate/revoke through approved owners, and select a clean rebuild source. |
| [ ] | Complete the incident handoff. | Link incident template populated with severity, timeline, commander, Security/Product contacts, evidence locations, and follow-ups. | Security accepts the tabletop record and every action has an owner and due date. |

## 11. Feature-change exercise

| Done | Checklist item | Evidence / command | Pass condition |
|---|---|---|---|
| [ ] | Implement a small, reversible feature or policy behavior change in a scratch branch. | Link branch/PR; include tests, threat/edition impact, and exact validation commands. | Change is scoped, reviewable, preserves security invariants, and does not couple CE to the private EE package. |
| [ ] | Classify edition and route impact. | Update the PR description with Tier 1/2/3, CE/EE seam, entitlement, compatibility, and migration assessment. | Reviewers agree on edition ownership and whether a CE tag/`CE_PIN` change is required. |
| [ ] | Prove behavior and negative cases. | Run targeted tests plus the correct CE/EE/seam workflow; attach sanitized output. | Positive behavior, authorization denial, invalid input, and regression path all pass. |
| [ ] | Identify documentation and claim updates before merge. | PR checklist links affected functional specification, design/admin/user/demo guide, feature catalog, readiness, and release notes—or explains why each is unaffected. | Product and engineering reviewers can trace behavior to accurate docs and no maturity label is silently upgraded. |

## 12. Documentation governance

| Done | Checklist item | Evidence / command | Pass condition |
|---|---|---|---|
| [ ] | Apply the documentation authority hierarchy. | Resolve a sample contradiction using [Edition Guides README](README.md) and record the selected canonical source. | Runtime/build evidence wins over stale summaries and the correction plan names all synchronized documents. |
| [ ] | Validate links and status vocabulary. | Run the repository's documented Markdown/link validation, or record a manual link check for changed pages; search changed docs for `Planned`, `Deferred`, `Commercial`, `Partial`, and `Shipped`. | Links resolve, maturity terms match the edition functional specifications/readiness source, and Planned/Deferred is never phrased as available. |
| [ ] | Preserve edition-specific instructions. | Review changed CE docs for Tier 2/3 click paths and changed EE docs for duplicated/forked CE baseline. | CE docs point to EE for EE-only operations; EE docs remain additive and accurately gated. |
| [ ] | Establish routine doc review ownership. | Link review calendar/issue with owners for architecture, functional specs, catalogs, runbooks, and claim surfaces. | Each document family has a named maintainer and trigger events for mandatory updates. |

## 13. Commercial and claim safety

| Done | Checklist item | Evidence / command | Pass condition |
|---|---|---|---|
| [ ] | Reconcile product claims with readiness. | Compare three representative claims against [Capability Readiness](../../ENTERPRISE.md), edition functional specs, and live/test evidence. | Status and limitations agree across sources; private-EE evidence is labeled appropriately when not reproduced locally. |
| [ ] | Demonstrate safe Planned/Optional handling. | Review one roadmap feature and one optional/entitled feature in demo or proposal text. | Planned is explicitly roadmap/not available; optional/entitled is not implied to be included or enabled. |
| [ ] | Review compliance language. | Security/Product review of Evidence Pack, SOC 2, EU AI Act, HIPAA/PCI/GDPR, and related statements. | Language says the product supports controls/evidence where accurate and does not claim certification, legal compliance, or conformity. |
| [ ] | Review support and legal boundaries. | Link current approved SLA/DPA/licensing sources and identify commercial owner. | Runtime capability is not conflated with contractual service, and successor knows who approves exceptions. |
| [ ] | Approve a claim correction drill. | Successor rewrites an intentionally overstated sample and links supporting evidence. | Product and Security accept the corrected wording and its maturity/edition qualifiers. |

## 14. 30/60/90-day milestones

| Done | Due | Milestone | Evidence / command | Pass condition |
|---|---|---|---|---|
| [ ] | Day 30 | Operate CE independently. | Successor leads one CE triage, change, green CI run, and local/staging smoke; link issue/PR/run. | No outgoing-owner intervention is needed for routine CE development or rollback. |
| [ ] | Day 30 | Close access and knowledge gaps. | Review this checklist's exceptions/N/A register and access tickets. | All critical access is granted or has an accepted contingency; unresolved high-risk gaps have executive owners/dates. |
| [ ] | Day 60 | Own an edition/seam release exercise. | Successor leads a real approved release or a complete non-publishing promotion rehearsal with `CE_PIN` evidence when EE is in scope. | Required reviewers approve provenance, compatibility, rollout, and rollback evidence; EE may be N/A under the stated rule. |
| [ ] | Day 60 | Lead a security/incident review. | Link one tabletop or real incident review and completed follow-ups. | Security accepts containment/evidence handling and no critical action is ownerless. |
| [ ] | Day 90 | Deliver a production-representative change. | Link design, threat/edition assessment, tests, docs, release, and post-deploy verification. | Change meets acceptance criteria, preserves invariants, and has no unresolved release-blocking regression. |
| [ ] | Day 90 | Re-baseline ownership risks and roadmap. | Updated risk register, architecture debt list, test/CI health, documentation freshness, and next-quarter priorities. | Product, Security, and successor agree on priorities, owners, and measurable outcomes. |

## 15. Exceptions and N/A register

Use this register for every incomplete or N/A item, especially EE. Do not use N/A to bypass a required CE/security control.

| Checklist item | Status (`Exception` / `N/A`) | Reason and scope | Compensating evidence/control | Owner | Approver | Review / due date |
|---|---|---|---|---|---|---|
| | | | | | | |
| | | | | | | |

## 16. Final sign-off

Sign only after reviewing the evidence workspace, open exceptions, and 30/60/90-day commitments. A signature accepts the transfer within the recorded scope; it does not waive unresolved risks.

| Role | Name | Decision (`Approve` / `Approve with exceptions` / `Reject`) | Date (UTC) | Evidence links / approved exceptions |
|---|---|---|---|---|
| Owner | | | | |
| Successor | | | | |
| Security | | | | |
| Product | | | | |

**Transfer effective date:**  
**Next formal ownership review:**  
**Outgoing owner escalation window (if any):**  
