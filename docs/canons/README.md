# Project structure canons

Universal standards for **all** repositories.

## Reading order

1. `project-structure.md` — S / H / Sub, base layout
2. `documentation.md` — docs hierarchy, language tiers
3. `normalize-governance.md` — agent-first normalize
4. `normalize-merge.md` — merge with existing repo
5. `group-sync.md` — hub sync (Head ↔ Sub)
6. `dev-pipeline.md` — subagent workflow (product repos)
7. `model-selection.md` — subagent model tiers (reference)

## Versioning

| Version | Date | Change |
|---------|------|--------|
| 2.0.0 | 2026-06-29 | Universal S / H / Sub model |
| 2.1.0 | 2026-06-29 | Packet sync inbox/outbox |
| 2.2.0 | 2026-06-30 | Agent-first normalize; protocol states; 2 subagents |
| 2.3.0 | 2026-07-01 | Skills sync/sync-base; operator handoff; `normalize.deprecations.yaml` |
| 2.4.0 | 2026-07-02 | Agent-cache tier English; language migration on re-normalize |
| 2.5.0 | 2026-07-02 | Hub sync model (`GROUP-HUB.md`); `agent-map.md` entry; dev pipeline agents |
| 2.5.1 | 2026-07-04 | `group-sync.md` 2.5.1: explicit Sub write-surface boundary at Head; delivery-notice thread for Sub-completed work |
| 2.6.0 | 2026-07-12 | Drop protocol epochs, `dispute_round` registry field, and the `protocol-ref`/`exports` snapshot mechanism; Sub reads `shared/` at `head.path` directly; `protocol-snapshot.py` removed |

## Artifacts

| Artifact | Path |
|----------|------|
| Templates | `../../templates/` |
| Initiators | `../../initiators/` |
| Checklist | `../../normalize.bundle.yaml` |
| Deprecations | `../../normalize.deprecations.yaml` |
| Check | `../../scripts/project-doctor.py` |
| Status | `../../scripts/sync-status.py` |
