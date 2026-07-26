import asyncio
import json
import sys
import time
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
from shared.tool_calls_log import (
    ToolCallLogger,
    inject_correlation_properties,
    tool_calls_db_path,
    utc_now_iso,
)

_module_paths = get_paths()

# Создаем сервер
app = Server("1c-config-server")

# Создаем инструменты с правильными путями
tools = ConfigurationTools(
    projects_file=str(_module_paths.config),
    databases_dir=str(_module_paths.data_dir),
)

# Журнал вызовов инструментов (protocol v1.0.7 §3): <logsDir>/tool-calls.db
_call_logger = ToolCallLogger(tool_calls_db_path(_module_paths.logs_dir))


def _response_bytes(response: list[TextContent] | None) -> int | None:
    """Serialized response size for the journal (sum of TextContent utf-8 bytes)."""
    if not response:
        return None
    total = 0
    for item in response:
        text = getattr(item, "text", None)
        if text:
            total += len(text.encode("utf-8"))
    return total or None


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Список доступных инструментов"""
    return inject_correlation_properties(TOOL_SCHEMAS)


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Обработка вызова инструмента"""
    args = arguments or {}
    started_at = utc_now_iso()
    started_mono = time.monotonic()
    success = True
    error_code = None
    response: list[TextContent] | None = None

    try:
        if name == "set_context":
            context = _call_logger.set_context(
                task_id=args.get("task_id"),
                session_id=args.get("session_id"),
                agent=args.get("agent"),
                model=args.get("model"),
            )
            response = [TextContent(type="text", text=json.dumps({
                "success": True,
                "taskId": context["task_id"],
                "sessionId": context["session_id"],
                "agent": context["agent"],
                "model": context["model"],
            }, ensure_ascii=False))]
        elif name == "active_databases":
            response = await handle_active_databases(tools, args)
        else:
            try:
                handler = HANDLERS.get(name)
                if handler is not None:
                    response = await handler(tools, args)
                else:
                    response = [TextContent(type="text", text=f"Неизвестный инструмент: {name}")]
            except ValueError as e:
                success = False
                error_code = type(e).__name__
                response = [TextContent(type="text", text=str(e))]
        return response
    except Exception as e:
        success = False
        error_code = type(e).__name__
        raise
    finally:
        if error_code is None and sys.exc_info()[0] is not None:
            # A non-Exception BaseException (e.g. asyncio.CancelledError on a
            # client-side timeout/disconnect) skips the `except` above; without
            # this the row would be journaled as a misleading success=1.
            success = False
            error_code = sys.exc_info()[0].__name__
        _call_logger.log(
            tool=name,
            started_at=started_at,
            started_mono=started_mono,
            args=args,
            success=success,
            error_code=error_code,
            result_bytes=_response_bytes(response),
        )


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
