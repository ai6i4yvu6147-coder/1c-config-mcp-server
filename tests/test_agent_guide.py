"""Agent guide contract (Head `docs/agent-guide-contract.md` §9).

The coverage test below is the point of the whole mechanism: it is what turns "the guide stays in
sync with the project" from a hope into an invariant that breaks the build.
"""

from pathlib import Path

import pytest

from server.dispatch import HANDLERS
from server.tool_schemas import TOOL_SCHEMAS
from shared import agent_guide

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def guide_text() -> str:
    return agent_guide.load_guide()


def registered_tool_names() -> set[str]:
    """Every tool this server advertises — schemas are the contract the agent actually sees."""
    names = {tool.name for tool in TOOL_SCHEMAS}
    # Handlers must not drift from schemas either; active_databases/set_context/guide are
    # dispatched in server.py outside HANDLERS.
    assert set(HANDLERS) - names == set(), "есть обработчик без схемы инструмента"
    return names


def test_guide_ships_and_is_not_empty(guide_text):
    assert agent_guide.guide_path().is_file()
    assert len(guide_text.strip()) > 500


def test_guide_structure_is_valid(guide_text):
    assert agent_guide.validate(guide_text) == []


def test_tool_map_covers_every_registered_tool_exactly(guide_text):
    documented = set(agent_guide.tool_names_in_map(guide_text))
    registered = registered_tool_names()

    missing = registered - documented
    extra = documented - registered
    assert not missing, f"инструменты без строки в карте справки: {sorted(missing)}"
    assert not extra, f"в карте справки описаны несуществующие инструменты: {sorted(extra)}"


def test_tool_map_has_no_duplicate_entries(guide_text):
    listed = agent_guide.tool_names_in_map(guide_text)
    assert len(listed) == len(set(listed)), "дубли в карте инструментов"


def test_overview_lists_sections_and_how_to_open_them(guide_text):
    overview = agent_guide.render(None, text=guide_text)
    ids = [s.id for s in agent_guide.parse_sections(guide_text)]
    for section_id in ids:
        assert f"`{section_id}`" in overview
    assert "section" in overview
    # The menu is a pointer, not the whole guide.
    assert len(overview) < len(guide_text)


def test_section_render_returns_that_section(guide_text):
    body = agent_guide.render("tools", text=guide_text)
    assert body.startswith("## ")
    assert "`active_databases`" in body
    assert "{#" not in body, "якоря не должны попадать в выдачу"


def test_render_all_returns_whole_file(guide_text):
    body = agent_guide.render("all", text=guide_text)
    assert body.strip().startswith("# ")
    assert "{#" not in body
    for section in agent_guide.parse_sections(guide_text):
        assert f"## {section.title}" in body


def test_unknown_section_lists_valid_ids(guide_text):
    with pytest.raises(agent_guide.GuideSectionError) as exc:
        agent_guide.render("нет-такого", text=guide_text)
    message = str(exc.value)
    assert "tools" in message and "all" in message


def test_frozen_build_reads_the_bundled_copy(monkeypatch, tmp_path):
    bundled = tmp_path / "docs"
    bundled.mkdir()
    (bundled / "agent-guide.md").write_text("# stub\n", encoding="utf-8")

    monkeypatch.setattr(agent_guide.sys, "frozen", True, raising=False)
    monkeypatch.setattr(agent_guide.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert agent_guide.guide_path() == tmp_path / "docs" / "agent-guide.md"
    assert agent_guide.load_guide().strip() == "# stub"


def test_guide_version_is_stable_and_content_addressed(guide_text):
    assert agent_guide.guide_version(guide_text) == agent_guide.guide_version(guide_text)
    assert agent_guide.guide_version(guide_text).startswith("sha256:")
    assert agent_guide.guide_version(guide_text) != agent_guide.guide_version(guide_text + " ")


@pytest.mark.parametrize("spec_name", ["1c-config-server.spec", "1c-config-cli.spec"])
def test_spec_ships_agent_guide(spec_name):
    """PyInstaller regenerates (overwrites) a same-named .spec when built from CLI flags
    (--name ...) instead of `pyinstaller X.spec` — that is exactly how this datas entry
    vanished before. Guards the tracked .spec regardless of how a future build creates it.
    """
    spec_text = (REPO_ROOT / spec_name).read_text(encoding="utf-8")
    assert "docs/agent-guide.md" in spec_text, (
        f"{spec_name}: docs/agent-guide.md missing from datas — frozen build will not ship the guide"
    )


def test_cli_envelope_carries_module_identity_and_same_markdown(guide_text):
    payload = agent_guide.envelope(
        "tools",
        module="1c-config-mcp",
        module_type="config-mcp",
        module_version="1.0.0",
    )
    assert payload["module"] == "1c-config-mcp"
    assert payload["section"] == "tools"
    assert payload["markdown"] == agent_guide.render("tools", text=guide_text)
    assert {s["id"] for s in payload["sections"]} == {
        s.id for s in agent_guide.parse_sections(guide_text)
    }
