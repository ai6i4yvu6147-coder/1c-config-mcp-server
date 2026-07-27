"""Agent guide: the server's own manual, shipped inside the portable build.

Contract: Head ``docs/agent-guide-contract.md`` (agent guide v1). The source of truth is
``docs/agent-guide.md`` in this repository — it travels into the portable via the PyInstaller
``datas`` entry ``('docs/agent-guide.md', 'docs')``, so editing the server and editing its
manual is one change in one commit.

Two consumers, one text:

* the MCP tool ``guide`` returns **markdown** (an LLM reads it as-is, no JSON escaping);
* the CLI command ``guide`` returns the same markdown inside a JSON envelope for the Hub.

This module is uniform across all Subs (like ``tool_calls_log.py`` / ``security.py``). The only
line that differs per repository is ``_DEV_ROOT`` — see the comment there.
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

GUIDE_RELATIVE_PATH = Path("docs") / "agent-guide.md"

# Repository root in development. ``shared/agent_guide.py`` → parents[1] is the repo root.
# Under a ``src/<package>/`` layout (data-mcp, knowledge-rag) this is ``parents[2]``.
_DEV_ROOT = Path(__file__).resolve().parents[1]

#: Section id that must hold the tool map (contract §3.3).
TOOL_MAP_SECTION_ID = "tools"

#: ``## Заголовок {#anchor}`` — the anchor is explicit so the id survives a heading rewording.
_SECTION_RE = re.compile(r"^##\s+(?P<title>.+?)\s*\{#(?P<id>[a-z0-9-]+)\}\s*$")
_ANCHOR_RE = re.compile(r"\s*\{#[a-z0-9-]+\}\s*$")
_TOOL_BULLET_RE = re.compile(r"^-\s+`(?P<name>[a-z][a-z0-9_]*)`\s+—")


class GuideError(RuntimeError):
    """Guide file missing or malformed."""


class GuideSectionError(ValueError):
    """Unknown section id requested."""


@dataclass(frozen=True)
class GuideSection:
    id: str
    title: str
    body: str  # heading line (anchor stripped) + section text


def guide_path() -> Path:
    """Where the guide lives now: inside the frozen bundle, or in the repo during development."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", None)
        if base:
            return Path(base) / GUIDE_RELATIVE_PATH
        return Path(sys.executable).resolve().parent / GUIDE_RELATIVE_PATH
    return _DEV_ROOT / GUIDE_RELATIVE_PATH


def load_guide() -> str:
    """Raw guide text (UTF-8). Raises :class:`GuideError` when the file did not ship."""
    path = guide_path()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        # In a frozen build the realistic cause is a missing PyInstaller `datas` entry — name it,
        # so the fix is one line in the spec instead of an investigation.
        hint = (" Добавьте ('docs/agent-guide.md', 'docs') в datas спеки сборки."
                if getattr(sys, "frozen", False) else "")
        raise GuideError(f"Справка для агента не найдена: {path}.{hint}") from exc
    return raw.decode("utf-8-sig").replace("\r\n", "\n")


def guide_version(text: Optional[str] = None) -> str:
    """``sha256:`` + first 12 hex chars — enough to spot a guide that differs between PCs."""
    body = load_guide() if text is None else text
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:12]}"


def guide_title(text: str) -> str:
    for line in text.split("\n"):
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def parse_sections(text: str) -> List[GuideSection]:
    """Split on ``## `` headings carrying an explicit ``{#id}`` anchor."""
    sections: List[GuideSection] = []
    current_id: Optional[str] = None
    current_title = ""
    buffer: List[str] = []

    def flush() -> None:
        if current_id is not None:
            sections.append(
                GuideSection(
                    id=current_id,
                    title=current_title,
                    body="\n".join(buffer).strip("\n"),
                )
            )

    for line in text.split("\n"):
        match = _SECTION_RE.match(line)
        if match:
            flush()
            current_id = match.group("id")
            current_title = match.group("title").strip()
            buffer = [f"## {current_title}"]
        elif current_id is not None:
            buffer.append(line)

    flush()
    return sections


def intro_text(text: str) -> str:
    """Everything between the H1 and the first section heading."""
    lines: List[str] = []
    seen_h1 = False
    for line in text.split("\n"):
        if line.startswith("# ") and not seen_h1:
            seen_h1 = True
            continue
        if _SECTION_RE.match(line):
            break
        if seen_h1:
            lines.append(line)
    return "\n".join(lines).strip("\n")


def strip_anchors(text: str) -> str:
    return "\n".join(_ANCHOR_RE.sub("", line) if line.startswith("#") else line
                     for line in text.split("\n"))


def tool_names_in_map(text: str) -> List[str]:
    """Tool names listed in the ``{#tools}`` section — the set a test compares to the registry."""
    for section in parse_sections(text):
        if section.id == TOOL_MAP_SECTION_ID:
            return [m.group("name")
                    for m in (_TOOL_BULLET_RE.match(line) for line in section.body.split("\n"))
                    if m]
    return []


def render(section: Optional[str] = None, *, text: Optional[str] = None) -> str:
    """The markdown the ``guide`` tool returns.

    ``None`` — title, intro and the section menu; ``"all"`` — the whole file; otherwise the one
    section. An unknown id raises :class:`GuideSectionError` listing what is valid.
    """
    body = load_guide() if text is None else text
    sections = parse_sections(body)

    if section is None or not str(section).strip():
        menu = "\n".join(f"- `{s.id}` — {s.title}" for s in sections)
        parts = [f"# {guide_title(body)}", intro_text(body)]
        if menu:
            parts.append(
                "## Разделы справки\n\n"
                "Открыть раздел: `guide` с параметром `section` (например `section=\"" +
                sections[0].id + "\"`); весь текст сразу — `section=\"all\"`.\n\n" + menu
            )
        return strip_anchors("\n\n".join(p for p in parts if p).strip() + "\n")

    wanted = str(section).strip().lower()
    if wanted == "all":
        return strip_anchors(body.strip() + "\n")

    for s in sections:
        if s.id == wanted:
            return strip_anchors(s.body.strip() + "\n")

    valid = ", ".join(s.id for s in sections)
    raise GuideSectionError(
        f"Неизвестный раздел справки: '{section}'. Допустимо: {valid}, all "
        "(или вызовите guide без параметров — вернётся меню)."
    )


def envelope(
    section: Optional[str] = None,
    *,
    module: str,
    module_type: str,
    module_version: str,
) -> Dict[str, Any]:
    """The JSON the CLI ``guide`` command prints — same markdown, plus module identity."""
    body = load_guide()
    return {
        "module": module,
        "moduleType": module_type,
        "moduleVersion": module_version,
        "guideVersion": guide_version(body),
        "title": guide_title(body),
        "section": section,
        "sections": [{"id": s.id, "title": s.title} for s in parse_sections(body)],
        "markdown": render(section, text=body),
    }


def validate(text: str) -> List[str]:
    """Structural problems with the guide file (contract §3). Empty list = valid."""
    problems: List[str] = []
    lines = text.split("\n")

    h1 = [line for line in lines if line.startswith("# ")]
    if len(h1) != 1:
        problems.append(f"ожидался ровно один заголовок '# ', найдено {len(h1)}")
    elif not lines or not lines[0].startswith("# "):
        problems.append("заголовок '# ' должен быть первой строкой файла")

    seen: Dict[str, int] = {}
    for number, line in enumerate(lines, start=1):
        if not line.startswith("## "):
            continue
        match = _SECTION_RE.match(line)
        if not match:
            problems.append(f"строка {number}: у заголовка нет якоря вида {{#id}}: {line.strip()}")
            continue
        anchor = match.group("id")
        if anchor in seen:
            problems.append(f"строка {number}: якорь #{anchor} уже использован (строка {seen[anchor]})")
        seen[anchor] = number

    if TOOL_MAP_SECTION_ID not in seen:
        problems.append(f"нет секции карты инструментов {{#{TOOL_MAP_SECTION_ID}}}")
    elif not tool_names_in_map(text):
        problems.append(
            f"секция {{#{TOOL_MAP_SECTION_ID}}} не содержит пунктов вида '- `имя_тула` — описание'"
        )

    return problems
