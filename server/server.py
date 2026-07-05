import asyncio
import sys
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.tools import ConfigurationTools
from server.tool_schemas import TOOL_SCHEMAS
from server.dispatch import HANDLERS, handle_active_databases
from shared.runtime_paths import get_paths

_module_paths = get_paths()

# Создаем сервер
app = Server("1c-config-server")

# Создаем инструменты с правильными путями
tools = ConfigurationTools(
    projects_file=str(_module_paths.config),
    databases_dir=str(_module_paths.data_dir),
)


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Список доступных инструментов"""
    return TOOL_SCHEMAS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Обработка вызова инструмента"""

    if name == "active_databases":
        return await handle_active_databases(tools, arguments)

    try:
        handler = HANDLERS.get(name)
        if handler is not None:
            return await handler(tools, arguments)
        return [TextContent(type="text", text=f"Неизвестный инструмент: {name}")]
    except ValueError as e:
        return [TextContent(type="text", text=str(e))]


async def main():
    """Запуск сервера через stdio"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
