# Project structure canons

Version: **2.1.0**

Universal standard for **any** repository. Not tied to a specific stack or domain.

Agent-cache tier paths — **English** (see `documentation.md`).

---

## Three project types

| Code | Type | When to use |
|------|------|-------------|
| **S** | Standalone | Autonomous project, no group |
| **H** | Head | Owns group shared docs, coordinates subordinates |
| **Sub** | Subordinate | In a group; local specs + sync via packets |

Every project **first** matches base **S**. H and Sub are extensions on top.

---

## Base (all types: S, H, Sub)

```
<project>/
├── README.md
├── AGENTS.md
├── CHANGELOG.md
├── .gitignore
├── src/
├── tests/
├── fixtures/               # optional
├── scripts/                # optional
└── docs/
    ├── README.md
    ├── agent-onboarding.md
    ├── architecture.md
    ├── todo.md
    └── …
```

### Do not commit (all types)

- `venv/`, `node_modules/`, `build/`, `dist/`
- Runtime configs — only `*.example.json` / `.env.example`
- `plans/`, `scratch/`
- **Group transport:** `docs/group/inbox/`, `docs/group/outbox/` — ephemeral, in `.gitignore`

---

## H extension (head project)

```
<head>/
├── …base S…
├── group.manifest.yaml
└── docs/
    └── group/
        ├── README.md
        ├── shared/              # SHARED canon (edited only here)
        ├── outbox/
        │   └── <sub-id>/        # outgoing packets (gitignored)
        └── inbox/
            └── <sub-id>/        # incoming from Sub (gitignored)
```

**Required:** `group.manifest.yaml` (`role: head`), `docs/group/README.md`, `docs/group/shared/`

---

## Sub extension (subordinate project)

```
<subordinate>/
├── …base S…
├── group.manifest.yaml          # recommended: role subordinate + path to Head
└── docs/
    └── group/
        ├── integration.md       # link to Head, local deviations, last_sync_*
        ├── inbox/               # packets from Head (gitignored)
        └── outbox/              # packets to Head (gitignored)
```

**Required:** `docs/group/integration.md`

**Do not in Sub:**

- Hold shared protocol canon — only in Head `docs/group/shared/`
- Commit sync packets to git
- Talk to other Subs directly — only via Head

---

## Required elements matrix

| Element | S | H | Sub |
|---------|:-:|:-:|:-:|
| `README.md`, `AGENTS.md`, `CHANGELOG.md` | ✅ | ✅ | ✅ |
| `docs/{README,agent-onboarding,architecture,todo}.md` | ✅ | ✅ | ✅ |
| `group.manifest.yaml` | — | ✅ | recommended |
| `docs/group/README.md` | — | ✅ | — |
| `docs/group/shared/` | — | ✅ | — |
| `docs/group/integration.md` | — | — | ✅ |
| `docs/group/inbox/`, `outbox/` in `.gitignore` | — | ✅ | ✅ |

---

## Forbidden (all types)

| Anti-pattern | Correct |
|--------------|---------|
| `readme.txt` instead of `README.md` | `README.md` |
| Long specs in root | `docs/` |
| Sync packets in git | `.gitignore` + delete after processing |
| Sub ↔ Sub directly | only via Head |
| Mirror copy of `shared/` in Sub | packets + local spec adaptation |

Templates: `../../templates/standalone/`, `head/`, `subordinate/`
