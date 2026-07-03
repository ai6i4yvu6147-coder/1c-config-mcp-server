# Project structure canons

Version: **2.5.0**

Universal standard for **any** repository. Not tied to a specific stack or domain.

Agent-cache tier paths — **English** (see `documentation.md`).

---

## Three project types

| Code | Type | When to use |
|------|------|-------------|
| **S** | Standalone | Autonomous project, no group |
| **H** | Head | Owns group shared canon + `GROUP-HUB.md`, coordinates subordinates |
| **Sub** | Subordinate | In a group; local specs + hub access via `head.path` |

Every project **first** matches base **S**. H and Sub are extensions on top.

---

## Base (all types: S, H, Sub)

```
<project>/
├── README.md
├── AGENTS.md               # pointer → docs/agent-map.md
├── CHANGELOG.md
├── .gitignore
├── src/
├── tests/
├── fixtures/               # optional
├── scripts/                # optional
└── docs/
    ├── README.md
    ├── agent-map.md        # agent entry point (~80 lines)
    ├── architecture.md
    ├── todo.md             # includes ## Hub pending (H/Sub)
    ├── canons/             # reference; not a default session read
    └── …
```

`docs/agent-map.md` is the session entry: directory map, delegation rules, sync triggers, test command. Full canons are read on normalize or dispute, not every session.

### Do not commit (all types)

- `venv/`, `node_modules/`, `build/`, `dist/`
- Runtime configs — only `*.example.json` / `.env.example`
- `plans/`, `scratch/`, `.tasks/` (subagent handoff artifacts)
- `docs/group/exports/` (ephemeral sync snapshots)
- `.cursor/settings.local.json` and Cursor runtime state (personal)

**Commit** the materialized `.cursor/agents/` and `.cursor/skills/` — they are agent-cache tier and travel with the repo, so `git`-ignoring `.cursor/*` wholesale is wrong. Ignore only the personal/runtime pieces above.

---

## H extension (head project)

```
<head>/
├── …base S…
├── GROUP-HUB.md            # group sync state, committed (NOT agent-cache tier)
├── group.manifest.yaml     # role: head + subordinate paths
└── docs/
    └── group/
        ├── README.md       # sub registry mirror
        ├── shared/         # SHARED canon (edited only here)
        ├── exports/        # snapshot staging per sub (ephemeral, gitignored)
        └── archive/
            └── <sub-id>/   # closed-thread summaries
```

`docs/group/exports/<sub-id>/` holds protocol/review snapshots the hub thread points to; the Sub reads them via `head.path` and installs into its own `protocol-ref/`.

**Required:** `GROUP-HUB.md`, `group.manifest.yaml` (`role: head`), `docs/group/README.md`, `docs/group/shared/`

---

## Sub extension (subordinate project)

```
<subordinate>/
├── …base S…
├── group.manifest.yaml     # role: subordinate + head.path (required for hub access)
└── docs/
    └── group/
        ├── integration.md  # link to Head, local deviations, protocol state
        └── protocol-ref/
            └── epoch<N>/   # stable snapshot, in git
```

**Required:** `docs/group/integration.md`

The Sub reads/writes the hub at `<head.path>/GROUP-HUB.md` in its own `sub_id` sections only. It never holds a copy of `shared/` or talks to other Subs directly.

---

## Required elements matrix

| Element | S | H | Sub |
|---------|:-:|:-:|:-:|
| `README.md`, `AGENTS.md`, `CHANGELOG.md` | ✅ | ✅ | ✅ |
| `docs/{README,agent-map,architecture,todo}.md` | ✅ | ✅ | ✅ |
| `group.manifest.yaml` | — | ✅ | ✅ (head.path) |
| `GROUP-HUB.md` | — | ✅ | — |
| `docs/group/README.md`, `docs/group/shared/` | — | ✅ | — |
| `docs/group/integration.md` | — | — | ✅ |

---

## Forbidden (all types)

| Anti-pattern | Correct |
|--------------|---------|
| `readme.txt` instead of `README.md` | `README.md` |
| Long specs in root | `docs/` |
| Inbox/outbox packet dirs | `GROUP-HUB.md` threads |
| Inlining contracts in the hub | pointers by path + commit |
| Sub ↔ Sub directly | only via Head |
| Mirror copy of `shared/` in Sub | `protocol-ref/` snapshot + local adaptation |
| Full canons in the default session path | `docs/agent-map.md` entry |

Templates: `../../templates/standalone/`, `head/`, `subordinate/`
