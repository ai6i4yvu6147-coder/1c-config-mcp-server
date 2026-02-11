import asyncio
import json
import sys
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.tools import ConfigurationTools

# Определяем корневую папку проекта
if getattr(sys, 'frozen', False):
    # Запущено из exe: Portable/Server/1c-config-server.exe -> Portable/
    application_path = Path(sys.executable).parent
    project_root = application_path.parent
else:
    # Запущено из Python: project_root/server/server.py -> project_root/
    application_path = Path(__file__).parent
    project_root = application_path.parent

# Создаем сервер
app = Server("1c-config-server")

# Создаем инструменты с правильными путями
tools = ConfigurationTools(
    projects_file=str(project_root / "projects.json"),
    databases_dir=str(project_root / "databases")
)


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Список доступных инструментов"""
    return [
        Tool(
            name="search_code",
            description="Поиск по коду конфигурации. Ищет во всех активных проектах и их базах/расширениях.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (опционально). Например: 'ТГ'"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Фильтр по базе/расширению (опционально). Например: 'РАСШ1_Бюджет'"
                    },
                    "max_results": {
                        "type": "number",
                        "description": "Максимум результатов на базу (по умолчанию 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="find_object",
            description="Найти объект метаданных по имени во всех активных проектах",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Имя объекта (можно частичное)"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (опционально)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Фильтр по базе/расширению (опционально)"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="list_objects",
            description="Получить список объектов метаданных из всех активных проектов",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_type": {
                        "type": "string",
                        "description": "Тип объекта (опционально): CommonModule, Catalog, Document и т.д."
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (опционально)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Фильтр по базе/расширению (опционально)"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Максимум объектов на базу (по умолчанию 50)",
                        "default": 50
                    }
                }
            }
        ),
        Tool(
            name="get_module_code",
            description="Получить код модуля объекта",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_name": {
                        "type": "string",
                        "description": "Имя объекта"
                    },
                    "module_type": {
                        "type": "string",
                        "description": "Тип модуля: Module, ManagerModule, ObjectModule (по умолчанию Module)",
                        "default": "Module"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (опционально)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Фильтр по базе/расширению (опционально)"
                    }
                },
                "required": ["object_name"]
            }
        ),
        Tool(
            name="get_module_procedures",
            description="Получить список процедур и функций модуля (только сигнатуры, без тел)",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_name": {
                        "type": "string",
                        "description": "Имя объекта"
                    },
                    "module_type": {
                        "type": "string",
                        "description": "Тип модуля: Module, ManagerModule, ObjectModule (по умолчанию Module)",
                        "default": "Module"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (опционально)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Фильтр по базе/расширению (опционально)"
                    }
                },
                "required": ["object_name"]
            }
        ),
        Tool(
            name="get_procedure_code",
            description="Получить код конкретной процедуры или функции из модуля",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_name": {
                        "type": "string",
                        "description": "Имя объекта"
                    },
                    "procedure_name": {
                        "type": "string",
                        "description": "Имя процедуры или функции"
                    },
                    "module_type": {
                        "type": "string",
                        "description": "Тип модуля: Module, ManagerModule, ObjectModule (по умолчанию Module)",
                        "default": "Module"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (опционально)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Фильтр по базе/расширению (опционально)"
                    }
                },
                "required": ["object_name", "procedure_name"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Обработка вызова инструмента"""
    
    if name == "search_code":
        query = arguments["query"]
        project_filter = arguments.get("project_filter")
        extension_filter = arguments.get("extension_filter")
        max_results = arguments.get("max_results", 10)
        
        results = tools.search_code(query, project_filter, extension_filter, max_results)
        
        if not results:
            return [TextContent(type="text", text=f"Ничего не найдено по запросу '{query}'")]
        
        response = f"Результаты поиска '{query}':\n\n"
        
        for project_name, project_data in results.items():
            response += f"📁 Проект: {project_name}\n"
            for db_name, db_results in project_data.items():
                response += f"  └─ {db_name}: {len(db_results)} результат(ов)\n"
                for r in db_results:
                    response += f"     • {r['object_type']}.{r['object_name']}.{r['module_type']}\n"
                    response += f"       {r['snippet']}\n"
            response += "\n"
        
        return [TextContent(type="text", text=response)]
    
    elif name == "find_object":
        obj_name = arguments["name"]
        project_filter = arguments.get("project_filter")
        extension_filter = arguments.get("extension_filter")
        
        results = tools.find_object(obj_name, project_filter, extension_filter)
        
        if not results:
            return [TextContent(type="text", text=f"Объект '{obj_name}' не найден")]
        
        response = f"Найденные объекты '{obj_name}':\n\n"
        
        for project_name, project_data in results.items():
            response += f"📁 Проект: {project_name}\n"
            for db_name, db_results in project_data.items():
                response += f"  └─ {db_name}:\n"
                for obj in db_results:
                    response += f"     • {obj['type']}.{obj['name']}\n"
                    if obj['synonym']:
                        response += f"       Синоним: {obj['synonym']}\n"
                    if obj['modules']:
                        response += f"       Модули: {', '.join(obj['modules'])}\n"
            response += "\n"
        
        return [TextContent(type="text", text=response)]
    
    elif name == "list_objects":
        object_type = arguments.get("object_type")
        project_filter = arguments.get("project_filter")
        extension_filter = arguments.get("extension_filter")
        limit = arguments.get("limit", 50)
        
        results = tools.list_objects(object_type, project_filter, extension_filter, limit)
        
        if not results:
            return [TextContent(type="text", text="Объекты не найдены")]
        
        response = "Объекты метаданных:\n\n"
        
        for project_name, project_data in results.items():
            response += f"📁 Проект: {project_name}\n"
            for db_name, db_results in project_data.items():
                response += f"  └─ {db_name}:\n"
                for obj_type, objects in sorted(db_results.items()):
                    response += f"     {obj_type} ({len(objects)}):\n"
                    for obj_name in objects[:10]:  # Первые 10
                        response += f"       - {obj_name}\n"
                    if len(objects) > 10:
                        response += f"       ... еще {len(objects) - 10}\n"
            response += "\n"
        
        return [TextContent(type="text", text=response)]
    
    elif name == "get_module_code":
        object_name = arguments["object_name"]
        module_type = arguments.get("module_type", "Module")
        project_filter = arguments.get("project_filter")
        extension_filter = arguments.get("extension_filter")
        
        results = tools.get_module_code(object_name, module_type, project_filter, extension_filter)
        
        if not results:
            return [TextContent(type="text", text=f"Модуль '{module_type}' объекта '{object_name}' не найден")]
        
        response = ""
        
        for project_name, project_data in results.items():
            for db_name, code in project_data.items():
                response += f"📁 {project_name} / {db_name}\n"
                response += f"Код модуля {object_name}.{module_type}:\n\n"
                response += code + "\n\n"
        
        return [TextContent(type="text", text=response)]
    
    elif name == "get_module_procedures":
        object_name = arguments["object_name"]
        module_type = arguments.get("module_type", "Module")
        project_filter = arguments.get("project_filter")
        extension_filter = arguments.get("extension_filter")
        
        results = tools.get_module_procedures(object_name, module_type, project_filter, extension_filter)
        
        if not results:
            return [TextContent(type="text", text=f"Модуль '{module_type}' объекта '{object_name}' не найден")]
        
        response = ""
        
        for project_name, project_data in results.items():
            for db_name, procedures in project_data.items():
                response += f"📁 {project_name} / {db_name}\n"
                response += f"Процедуры и функции в {object_name}.{module_type}:\n\n"
                
                for proc in procedures:
                    export_mark = " [Экспорт]" if proc['export'] else ""
                    response += f"{proc['line']:4d}. {proc['type']} {proc['name']}({proc['params']}){export_mark}\n"
                
                response += "\n"
        
        return [TextContent(type="text", text=response)]
    
    elif name == "get_procedure_code":
        object_name = arguments["object_name"]
        procedure_name = arguments["procedure_name"]
        module_type = arguments.get("module_type", "Module")
        project_filter = arguments.get("project_filter")
        extension_filter = arguments.get("extension_filter")
        
        results = tools.get_procedure_code(object_name, procedure_name, module_type, project_filter, extension_filter)
        
        if not results:
            return [TextContent(type="text", text=f"Процедура '{procedure_name}' не найдена в модуле {object_name}.{module_type}")]
        
        response = ""
        
        for project_name, project_data in results.items():
            for db_name, code in project_data.items():
                response += f"📁 {project_name} / {db_name}\n"
                response += f"Код процедуры {procedure_name} из {object_name}.{module_type}:\n\n"
                response += code + "\n\n"
        
        return [TextContent(type="text", text=response)]
    
    else:
        return [TextContent(type="text", text=f"Неизвестный инструмент: {name}")]


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