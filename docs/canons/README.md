# Project structure canons

Universal standards for **all** repositories.

## Reading order

1. `project-structure.md` — S / H / Sub, base layout
2. `documentation.md` — docs hierarchy, language tiers
3. `normalize-governance.md` — agent-first normalize
4. `normalize-merge.md` — merge with existing repo
5. `group-sync.md` — packet sync, protocol reconcile

## Versioning

| Version | Date | Change |
|---------|------|--------|
| 2.0.0 | 2026-06-29 | Universal S / H / Sub model |
| 2.1.0 | 2026-06-29 | Packet sync inbox/outbox |
| 2.2.0 | 2026-06-30 | Agent-first normalize; protocol states; 2 subagents |
| 2.3.0 | 2026-07-01 | Skills sync/sync-base; operator handoff; `normalize.deprecations.yaml` |
| 2.4.0 | 2026-07-02 | Agent-cache tier English; language migration on re-normalize |

## Artifacts

| Artifact | Path |
|----------|------|
| Templates | `../../templates/` |
| Initiators | `../../initiators/` |
| Checklist | `../../normalize.bundle.yaml` |
| Deprecations | `../../normalize.deprecations.yaml` |
| Check | `../../scripts/project-doctor.py` |
| Snapshot / status | `../../scripts/protocol-snapshot.py`, `../../scripts/sync-status.py` |

## Artifacts in this repository

| Artifact | Path |
|----------|------|
| Group manifest | `group.manifest.yaml` |
| Sub integration | `docs/group/integration.md` |
| Normalize record | `docs/normalize-record.md` |
| Structure check | `scripts/project-doctor.py` |
| Sync status | `scripts/sync-status.py` |
| Skills / agents | `.cursor/skills/` (4), `.cursor/agents/` (1: doc-librarian) |

Canon version for this repo: **2.4.0** (`group.manifest.yaml`). Templates and initiators remain in Workspace improve — not copied into the product repository.
