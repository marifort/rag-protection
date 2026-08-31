# Connector fixtures (lab samples)

These JSON files simulate Google Drive documents for scheduled sync **without** live OAuth.

| File | Role |
|------|------|
| `demo_folder_hr_only.json` | Baseline share → maps to `["hr"]`. Policy job `source_id: demo-folder`. |
| `demo_folder_widened.json` | Twin with a domain permission → `["hr", "all-staff"]`. Lab widen is `cp` onto the baseline filename. |
| `demo_folder_pto.json` / `demo_folder_pto_widened.json` | Optional **second** document (`id: demo-folder-pto`) plus its own `connectors.jobs[]` row. |

**Do not set `source_revision` on these twins.** `load_drive_fixture()` then fingerprints `permissions`. A widen or restore therefore often runs as `sync_mode=full`; the **next** tick on the unchanged file is `acl_only`. That is #12 working, not a failure. Live Drive uses `modifiedTime` / `md5Checksum` instead, so a share-only change is usually ACL-only **on the same tick** as drift.

#12 **copies the source’s current groups** into the index. It does not undo a widened share.

If `demo_folder_hr_only.json` is already a copy of the widened twin, restore it (git or the DEMO_SCRIPT heredoc) before the next critical-drift take, **or** use the PTO twins for a #12 UI demo: [see #12 in the UI](../../../../ENTERPRISE.md#see-12-in-the-ui).

Full prose: [docs/ee/features/12-acl-sync.md](../../../../ENTERPRISE.md#fixture-vs-live-revision) · [see #12 in the UI](../../../../ENTERPRISE.md#see-12-in-the-ui) · [adding a second fixture](../../../../ENTERPRISE.md#adding-a-second-fixture-document).
