import sys
from pathlib import Path
import json
import asyncio

# Добавляем корневую папку в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.types import Tool, TextContent
from tools import ConfigurationTools

# Загружаем конфигурацию
# Для упакованного exe используем путь относительно exe-файла
if getattr(sys, 'frozen', False):
    # Запущено из exe
    application_path = Path(sys.executable).parent
else:
    # Запущено из Python
    application_path = Path(__file__).parent

config_path = application_path / 'config.json'
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

# Создаем сервер
app = Server("1c-config-server")

# Путь к БД - поднимаемся на уровень выше для portable структуры
if getattr(sys, 'frozen', False):
    # Для exe: Portable/Server -> Portable
    portable_root = application_path.parent
    db_path = portable_root / config['active_database']
else:
    # Для разработки: server/ -> project_root/
    project_root = application_path.parent
    db_path = project_root / config['active_database']

# Инициализируем инструменты
tools = ConfigurationTools(db_path)
tools.connect()


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Список доступных инструментов"""
    return [
        Tool(
            name="search_code",
            description="Поиск текста в коде модулей конфигурации 1С. Используйте ключевые слова для поиска процедур, функций, переменных.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Строка поиска (например: 'РегистрыСведений.Регистр1' или 'Функция ПолучитьДанные')"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Максимальное количество результатов (по умолчанию 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="find_object",
            description="Найти объект метаданных по имени (справочник, документ, регистр и т.д.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Имя объекта (например: 'Номенклатура', 'ФТ_Бюджетирование')"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="list_objects",
            description="Получить список объектов метаданных",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_type": {
                        "type": "string",
                        "description": "Тип объекта: Catalog, Document, CommonModule, InformationRegister, AccumulationRegister, Report и т.д. (опционально)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Максимум результатов (по умолчанию 50)",
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
                    }
                },
                "required": ["object_name"]
            }
        ),
        Tool(
            name="get_module_procedures",
            description="Получить список процедур и функций модуля (только сигнатуры, без тел). Полезно для обзора модуля.",
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
                    }
                },
                "required": ["object_name", "procedure_name"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Вызов инструмента"""
    
    if name == "search_code":
        query = arguments["query"]
        max_results = arguments.get("max_results", 10)
        
        results = tools.search_code(query, max_results)
        
        if not results:
            return [TextContent(type="text", text=f"Ничего не найдено по запросу '{query}'")]
        
        response = f"Найдено {len(results)} результатов по запросу '{query}':\n\n"
        for i, result in enumerate(results, 1):
            response += f"{i}. {result['object']} ({result['module']})\n"
            response += f"   {result['snippet']}\n\n"
        
        return [TextContent(type="text", text=response)]
    
    elif name == "find_object":
        name_query = arguments["name"]
        obj = tools.find_object(name_query)
        
        if not obj:
            return [TextContent(type="text", text=f"Объект '{name_query}' не найден")]
        
        response = f"Объект: {obj['name']}\n"
        response += f"Тип: {obj['type']}\n"
        response += f"Синоним: {obj['synonym']}\n"
        response += f"UUID: {obj['uuid']}\n"
        
        if obj['modules']:
            response += "\nМодули:\n"
            for mod in obj['modules']:
                response += f"  - {mod['type']} (~{mod['lines']} строк)\n"
        
        return [TextContent(type="text", text=response)]
    
    elif name == "list_objects":
        object_type = arguments.get("object_type")
        limit = arguments.get("limit", 50)
        
        objects = tools.list_objects(object_type, limit)
        
        if not objects:
            return [TextContent(type="text", text="Объекты не найдены")]
        
        response = f"Найдено объектов: {len(objects)}\n\n"
        
        current_type = None
        for obj in objects:
            if obj['type'] != current_type:
                current_type = obj['type']
                response += f"\n{current_type}:\n"
            
            synonym = f" ({obj['synonym']})" if obj['synonym'] else ""
            response += f"  - {obj['name']}{synonym}\n"
        
        return [TextContent(type="text", text=response)]
    
    elif name == "get_module_code":
        object_name = arguments["object_name"]
        module_type = arguments.get("module_type", "Module")
        
        code = tools.get_module_code(object_name, module_type)
        
        if not code:
            return [TextContent(type="text", text=f"Модуль '{module_type}' объекта '{object_name}' не найден")]
        
        return [TextContent(type="text", text=f"Код модуля {object_name}.{module_type}:\n\n{code}")]
    
    elif name == "get_module_procedures":
        object_name = arguments["object_name"]
        module_type = arguments.get("module_type", "Module")
        
        procedures = tools.get_module_procedures(object_name, module_type)
        
        if procedures is None:
            return [TextContent(type="text", text=f"Модуль '{module_type}' объекта '{object_name}' не найден")]
        
        if not procedures:
            return [TextContent(type="text", text=f"В модуле {object_name}.{module_type} не найдено процедур и функций")]
        
        response = f"Процедуры и функции в модуле {object_name}.{module_type}:\n\n"
        
        for proc in procedures:
            export_mark = " [Экспорт]" if proc['export'] else ""
            response += f"{proc['line']:4d}. {proc['type']} {proc['name']}({proc['params']}){export_mark}\n"
        
        return [TextContent(type="text", text=response)]
    
    elif name == "get_procedure_code":
        object_name = arguments["object_name"]
        procedure_name = arguments["procedure_name"]
        module_type = arguments.get("module_type", "Module")
        
        code = tools.get_procedure_code(object_name, procedure_name, module_type)
        
        if not code:
            return [TextContent(type="text", text=f"Процедура/функция '{procedure_name}' не найдена в модуле {object_name}.{module_type}")]
        
        return [TextContent(type="text", text=f"Код процедуры {procedure_name} из {object_name}.{module_type}:\n\n{code}")]
    
    else:
        return [TextContent(type="text", text=f"Неизвестный инструмент: {name}")]


async def main():
    """Запуск сервера"""
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())