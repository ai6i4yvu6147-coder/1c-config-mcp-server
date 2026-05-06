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
            name="active_databases",
            description=(
                "Список проектов и список баз данных. Получить список проектов, перечень проектов, какие проекты доступны, доступные базы. "
                "Узнать какой project_filter указать для search_code, find_object, get_module_code, get_procedure_code. "
                "Первый шаг при работе с конфигурацией 1С: с чего начать, начало работы. Возвращает имена проектов и имён баз (основная конфигурация и расширения). "
                "Без вызова этого инструмента нельзя узнать допустимые значения project_filter. Вызывайте перед search_code и другими инструментами. "
                "Передавайте возвращённые имена в project_filter и extension_filter без изменений (точное совпадение)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "placeholder": {
                        "type": "string",
                        "description": "Не используется; параметр опционален. Вызовите инструмент без аргументов для получения списка проектов и баз."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="search_code",
            description="Поиск по коду конфигурации. project_filter обязателен; extension_filter опционален. Используйте active_databases для списка проектов и баз.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (обязательно). Например: 'ТГ'"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                    },
                    "object_name": {
                        "type": "string",
                        "description": "Фильтр по имени объекта (опционально, можно частичное). Например: 'ФТ_Конвертации'"
                    },
                    "module_type": {
                        "type": "string",
                        "description": "Фильтр по типу модуля (опционально): Module, ManagerModule, ObjectModule, FormModule"
                    },
                    "max_results": {
                        "type": "number",
                        "description": "Максимум результатов на базу (по умолчанию 10)",
                        "default": 10
                    }
                },
                "required": ["query", "project_filter"]
            }
        ),
        Tool(
            name="find_object",
            description="Найти объект метаданных по имени. project_filter обязателен. Для расширений в ответе возвращается object_belonging (Own/Adopted).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Имя объекта (можно частичное)"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (обязательно)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                    }
                },
                "required": ["name", "project_filter"]
            }
        ),
        Tool(
            name="list_objects",
            description="Список объектов метаданных. project_filter обязателен. Для расширений в ответе — object_belonging (Own/Adopted). В ответе по каждой базе: total_count, returned_count, is_truncated; при is_truncated: true увеличьте limit или сообщите пользователю о неполном списке.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_type": {
                        "type": "string",
                        "description": "Тип объекта (опционально): CommonModule, Catalog, Document и т.д."
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (обязательно)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                    },
                    "limit": {
                        "type": "number",
                        "description": "Максимум объектов на базу (по умолчанию 50)",
                        "default": 50
                    }
                },
                "required": ["project_filter"]
            }
        ),
        Tool(
            name="get_module_code",
            description="Получить код модуля объекта или модуля формы. project_filter обязателен.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_name": {
                        "type": "string",
                        "description": "Имя объекта"
                    },
                    "module_type": {
                        "type": "string",
                        "description": "Тип модуля: Module, ManagerModule, ObjectModule, FormModule (по умолчанию Module)",
                        "default": "Module"
                    },
                    "form_name": {
                        "type": "string",
                        "description": "Имя формы (обязательно для module_type='FormModule')"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (обязательно)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                    }
                },
                "required": ["object_name", "project_filter"]
            }
        ),
        Tool(
            name="get_module_procedures",
            description="Получить список процедур и функций модуля (сигнатуры и контекст выполнения Клиент/Сервер). project_filter обязателен.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_name": {
                        "type": "string",
                        "description": "Имя объекта"
                    },
                    "module_type": {
                        "type": "string",
                        "description": "Тип модуля: Module, ManagerModule, ObjectModule, FormModule (по умолчанию Module)",
                        "default": "Module"
                    },
                    "form_name": {
                        "type": "string",
                        "description": "Имя формы (обязательно для module_type='FormModule')"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (обязательно)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                    }
                },
                "required": ["object_name", "project_filter"]
            }
        ),
        Tool(
            name="get_procedure_code",
            description="Получить код конкретной процедуры или функции (включая директиву &НаКлиенте/&НаСервере). project_filter обязателен.",
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
                        "description": "Тип модуля: Module, ManagerModule, ObjectModule, FormModule (по умолчанию Module)",
                        "default": "Module"
                    },
                    "form_name": {
                        "type": "string",
                        "description": "Имя формы (обязательно для module_type='FormModule')"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (обязательно)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                    }
                },
                "required": ["object_name", "procedure_name", "project_filter"]
            }
        ),
        Tool(
            name="find_form",
            description="Поиск форм по имени объекта и/или формы. project_filter обязателен. В ответе: form_kind (List/Choice/Element), для расширений — object_belonging.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_name": {
                        "type": "string",
                        "description": "Имя объекта (опционально, можно частичное)"
                    },
                    "form_name": {
                        "type": "string",
                        "description": "Имя формы (опционально, можно частичное)"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (обязательно)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                    }
                },
                "required": ["project_filter"]
            }
        ),
        Tool(
            name="find_form_element",
            description="Найти формы по элементу: по имени элемента (element_name) или по связи с данными — ПутьКДанным (data_path). project_filter обязателен. В ответе: visible, enabled, data_path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "element_name": {
                        "type": "string",
                        "description": "Имя элемента формы (можно частичное). Задайте его или data_path."
                    },
                    "data_path": {
                        "type": "string",
                        "description": "Путь к данным (реквизит): поиск по полю DataPath/ПутьКДанным (можно частичное). Задайте его или element_name."
                    },
                    "object_name": {
                        "type": "string",
                        "description": "Имя объекта для фильтрации (опционально, можно частичное)"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (обязательно)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                    }
                },
                "required": ["project_filter"]
            }
        ),
        Tool(
            name="get_form_structure",
            description="Полная структура формы: реквизиты, команды, элементы UI (visible, enabled), события. project_filter обязателен. form_kind и object_belonging для расширений.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_name": {
                        "type": "string",
                        "description": "Имя объекта"
                    },
                    "form_name": {
                        "type": "string",
                        "description": "Имя формы"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (обязательно)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                    }
                },
                "required": ["object_name", "form_name", "project_filter"]
            }
        ),
        Tool(
            name="search_form_properties",
            description="Поиск элементов форм по свойствам Visible и Enabled. Поддерживаются только эти два свойства. project_filter обязателен.",
            inputSchema={
                "type": "object",
                "properties": {
                    "property_name": {
                        "type": "string",
                        "description": "Имя свойства: только Visible или Enabled"
                    },
                    "property_value": {
                        "type": "string",
                        "description": "Значение (опционально): true, false, 1, 0"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (обязательно)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                    }
                },
                "required": ["property_name", "project_filter"]
            }
        ),
        Tool(
            name="get_object_structure",
            description="Полная структура метаданных объекта 1С. project_filter обязателен. Для расширений в ответе — object_belonging (Own/Adopted).",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_name": {
                        "type": "string",
                        "description": "Имя объекта (можно частичное)"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (обязательно)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                    }
                },
                "required": ["object_name", "project_filter"]
            }
        ),
        Tool(
            name="get_functional_options",
            description="Функциональные опции для объекта или элемента формы. Вызывать при вопросах: почему объект/документ недоступен; почему поле/кнопка на форме не отображается. Один tool: только object_name — в каких ФО задействован объект; object_name + form_name + element_type + element_name — от каких ФО зависит элемент формы. project_filter обязателен.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_name": {
                        "type": "string",
                        "description": "Имя объекта (документ, справочник и т.д.) — обязательно."
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (обязательно)."
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Точное имя базы из active_databases (опционально)."
                    },
                    "form_name": {
                        "type": "string",
                        "description": "Имя формы — для запроса по элементу формы (вместе с element_type и element_name)."
                    },
                    "element_type": {
                        "type": "string",
                        "description": "FormAttribute | FormCommand | FormItem — для элемента формы."
                    },
                    "element_name": {
                        "type": "string",
                        "description": "Имя реквизита/команды/элемента формы."
                    }
                },
                "required": ["object_name", "project_filter"]
            }
        ),
        Tool(
            name="find_attribute",
            description="Поиск реквизита по имени. project_filter обязателен. Для расширений в ответе — object_belonging (Own/Adopted).",
            inputSchema={
                "type": "object",
                "properties": {
                    "attribute_name": {
                        "type": "string",
                        "description": "Имя реквизита (можно частичное)"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (обязательно)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Точное имя базы из ответа active_databases (опционально). Передавайте имя без изменений."
                    },
                    "max_results": {
                        "type": "number",
                        "description": "Максимум результатов на базу (по умолчанию 20)",
                        "default": 20
                    }
                },
                "required": ["attribute_name", "project_filter"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Обработка вызова инструмента"""
    
    if name == "active_databases":
        results = tools.list_active_databases()
        lines = []
        for proj in results.get("projects", []):
            lines.append(f"Проект: {proj['name']}")
            for db in proj.get("databases", []):
                suffix = " [!] устарела" if db.get("is_outdated") else ""
                lines.append(f"  — {db['name']} ({db['type']}){suffix}")
            lines.append("")
        return [TextContent(type="text", text="Активные проекты и базы:\n\n" + "\n".join(lines) if lines else "Нет активных проектов.")]

    try:
        if name == "search_code":
            query = arguments["query"]
            project_filter = arguments.get("project_filter")
            extension_filter = arguments.get("extension_filter")
            object_name = arguments.get("object_name")
            module_type = arguments.get("module_type")
            max_results = arguments.get("max_results", 10)

            results = tools.search_code(query, project_filter, extension_filter, max_results,
                                        object_name, module_type)
            
            if isinstance(results, dict) and results.get("_empty") and results.get("diagnostics"):
                d = results["diagnostics"]
                msg = (f"По запросу '{query}' ничего не найдено. "
                       f"Проект: {d.get('project_filter', '?')}, просмотрено баз: {d.get('num_databases', 0)}, совпадений: 0. "
                       "Используйте active_databases для проверки имён проектов и баз.")
                return [TextContent(type="text", text=msg)]
            if not results:
                return [TextContent(type="text", text=f"Ничего не найдено по запросу '{query}'")]
            
            response = f"Результаты поиска '{query}':\n\n"
            
            for project_name, project_data in results.items():
                response += f"📁 Проект: {project_name}\n"
                for db_name, db_results in project_data.items():
                    response += f"  └─ {db_name}: {len(db_results)} результат(ов)\n"
                    for r in db_results:
                        response += f"     • {r['object_type']}.{r['object_name']}.{r['module_type']}\n"
                        response += f"       {r.get('procedure_display', '')}\n"
                        id_line = f"       object_name={r['object_name']!r}, module_type={r['module_type']!r}"
                        if r.get('form_name'):
                            id_line += f", form_name={r['form_name']!r}"
                        response += id_line + "\n"
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
                        if obj.get('object_belonging'):
                            response += f"       Принадлежность: {obj['object_belonging']}\n"
                        if obj['synonym']:
                            response += f"       Синоним: {obj['synonym']}\n"
                        if obj['modules']:
                            response += f"       Модули: {', '.join(obj['modules'])}\n"
                        if obj.get('forms'):
                            response += f"       Формы: {', '.join(obj['forms'])}\n"
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
                    by_type = db_results.get('by_type', db_results)
                    response += f"  └─ {db_name}:\n"
                    total_count = db_results.get('total_count')
                    returned_count = db_results.get('returned_count')
                    is_truncated = db_results.get('is_truncated', db_results.get('truncated', False))
                    if total_count is not None and returned_count is not None:
                        response += f"     total_count: {total_count}\n"
                        response += f"     returned_count: {returned_count}\n"
                        response += f"     is_truncated: {str(is_truncated).lower()}\n"
                    if is_truncated:
                        response += "     При is_truncated: true увеличьте limit или сообщите пользователю о неполном списке.\n"
                    for obj_type, objects in sorted(by_type.items()):
                        response += f"     {obj_type} ({len(objects)}):\n"
                        for obj_entry in objects[:10]:
                            name = obj_entry['name'] if isinstance(obj_entry, dict) else obj_entry
                            belong = f" [{obj_entry.get('object_belonging')}]" if isinstance(obj_entry, dict) and obj_entry.get('object_belonging') else ""
                            response += f"       - {name}{belong}\n"
                        if len(objects) > 10:
                            response += f"       ... еще {len(objects) - 10}\n"
                response += "\n"
        
            return [TextContent(type="text", text=response)]
    
        elif name == "get_module_code":
            object_name = arguments["object_name"]
            module_type = arguments.get("module_type", "Module")
            form_name = arguments.get("form_name")
            project_filter = arguments.get("project_filter")
            extension_filter = arguments.get("extension_filter")
        
            results = tools.get_module_code(object_name, module_type, form_name, project_filter, extension_filter)
        
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
            form_name = arguments.get("form_name")
            project_filter = arguments.get("project_filter")
            extension_filter = arguments.get("extension_filter")
        
            results = tools.get_module_procedures(object_name, module_type, form_name, project_filter, extension_filter)
        
            if not results:
                return [TextContent(type="text", text=f"Модуль '{module_type}' объекта '{object_name}' не найден")]
        
            response = ""
        
            for project_name, project_data in results.items():
                for db_name, procedures in project_data.items():
                    response += f"📁 {project_name} / {db_name}\n"
                    response += f"Процедуры и функции в {object_name}.{module_type}:\n\n"
                
                    for proc in procedures:
                        export_mark = " [Экспорт]" if proc['export'] else ""
                        ctx = f" [{proc['execution_context']}]" if proc.get('execution_context') else ""
                        response += f"{proc['line']:4d}. {proc['type']} {proc['name']}({proc['params']}){export_mark}{ctx}\n"
                
                    response += "\n"
        
            return [TextContent(type="text", text=response)]
    
        elif name == "get_procedure_code":
            object_name = arguments["object_name"]
            procedure_name = arguments["procedure_name"]
            module_type = arguments.get("module_type", "Module")
            form_name = arguments.get("form_name")
            project_filter = arguments.get("project_filter")
            extension_filter = arguments.get("extension_filter")
        
            results = tools.get_procedure_code(object_name, procedure_name, module_type, form_name, project_filter, extension_filter)
        
            if not results:
                return [TextContent(type="text", text=f"Процедура '{procedure_name}' не найдена в модуле {object_name}.{module_type}")]
        
            response = ""
        
            for project_name, project_data in results.items():
                for db_name, code in project_data.items():
                    response += f"📁 {project_name} / {db_name}\n"
                    response += f"Код процедуры {procedure_name} из {object_name}.{module_type}:\n\n"
                    response += code + "\n\n"
        
            return [TextContent(type="text", text=response)]
    
        elif name == "find_form":
            object_name = arguments.get("object_name")
            form_name = arguments.get("form_name")
            project_filter = arguments.get("project_filter")
            extension_filter = arguments.get("extension_filter")
        
            results = tools.find_form(object_name, form_name, project_filter, extension_filter)
        
            if not results:
                return [TextContent(type="text", text="Формы не найдены")]
        
            response = "Найденные формы:\n\n"
        
            for project_name, project_data in results.items():
                response += f"📁 Проект: {project_name}\n"
                for db_name, forms in project_data.items():
                    response += f"  └─ {db_name}:\n"
                    for form in forms:
                        kind = f" ({form['form_kind']})" if form.get('form_kind') else ""
                        response += f"     • {form['object_type']}.{form['object_name']}.{form['form_name']}{kind}\n"
                        if form.get('object_belonging'):
                            response += f"       Принадлежность: {form['object_belonging']}\n"
                        response += f"       Реквизитов: {form['attributes_count']}, Команд: {form['commands_count']}, Элементов: {form['items_count']}\n"
                        if form.get('properties'):
                            props_str = ", ".join([f"{k}={v}" for k, v in list(form['properties'].items())[:3]])
                            response += f"       Свойства: {props_str}\n"
                response += "\n"
        
            return [TextContent(type="text", text=response)]
    
        elif name == "find_form_element":
            element_name = arguments.get("element_name")
            data_path = arguments.get("data_path")
            object_name = arguments.get("object_name")
            project_filter = arguments.get("project_filter")
            extension_filter = arguments.get("extension_filter")
            if not element_name and not data_path:
                return [TextContent(type="text", text="Укажите element_name и/или data_path для поиска элемента формы.")]

            results = tools.find_form_element(element_name=element_name, data_path=data_path, object_name=object_name, project_filter=project_filter, extension_filter=extension_filter)
        
            if not results:
                search_desc = element_name or data_path
                return [TextContent(type="text", text=f"Элемент/путь к данным '{search_desc}' не найден в формах")]
        
            search_desc = " или ".join(filter(None, [element_name and f"имя: {element_name}", data_path and f"data_path: {data_path}"]))
            response = f"Найдено по критерию ({search_desc}):\n\n"
        
            for project_name, project_data in results.items():
                response += f"📁 Проект: {project_name}\n"
                for db_name, elements in project_data.items():
                    response += f"  └─ {db_name}:\n"
                    for elem in elements:
                        response += f"     • {elem['object_name']}.{elem['form_name']}.{elem['element_name']}\n"
                        response += f"       Тип: {elem['element_type']}\n"
                        if elem.get('data_path'):
                            response += f"       DataPath: {elem['data_path']}\n"
                        if elem.get('title'):
                            response += f"       Заголовок: {elem['title']}\n"
                        if elem.get('object_belonging'):
                            response += f"       Принадлежность: {elem['object_belonging']}\n"
                        v, e = elem.get('visible'), elem.get('enabled')
                        if v is not None or e is not None:
                            response += f"       Visible: {v}, Enabled: {e}\n"
                response += "\n"
        
            return [TextContent(type="text", text=response)]
    
        elif name == "get_form_structure":
            object_name = arguments["object_name"]
            form_name = arguments["form_name"]
            project_filter = arguments.get("project_filter")
            extension_filter = arguments.get("extension_filter")
        
            results = tools.get_form_structure(object_name, form_name, project_filter, extension_filter)
        
            if not results:
                return [TextContent(type="text", text=f"Форма '{object_name}.{form_name}' не найдена")]
        
            response = f"Структура формы {object_name}.{form_name}:\n\n"
        
            for project_name, project_data in results.items():
                response += f"📁 Проект: {project_name}\n"
                for db_name, structure in project_data.items():
                    response += f"  └─ {db_name}:\n\n"
                    if structure.get('form_kind'):
                        response += f"  Тип формы: {structure['form_kind']}\n"
                    if structure.get('object_belonging'):
                        response += f"  Принадлежность: {structure['object_belonging']}\n\n"
                    # Свойства формы
                    if structure.get('properties'):
                        response += "  Свойства формы:\n"
                        for key, value in structure['properties'].items():
                            response += f"    • {key}: {value}\n"
                        response += "\n"
                
                    # События
                    if structure['events']:
                        response += "  События формы:\n"
                        for event in structure['events']:
                            call_type = f" ({event['call_type']})" if event['call_type'] else ""
                            response += f"    • {event['event_name']}{call_type} -> {event['handler']}\n"
                        response += "\n"
                
                    # Реквизиты
                    if structure['attributes']:
                        response += "  Реквизиты:\n"
                        for attr in structure['attributes']:
                            main_mark = " [Основной]" if attr['is_main'] else ""
                            response += f"    • {attr['name']}{main_mark}: {attr['type']}\n"
                            if attr.get('query_text'):
                                response += f"      QueryText: {attr['query_text'][:100]}...\n"
                        response += "\n"
                
                    # Команды
                    if structure['commands']:
                        response += "  Команды:\n"
                        for cmd in structure['commands']:
                            shortcut = f" [{cmd['shortcut']}]" if cmd['shortcut'] else ""
                            response += f"    • {cmd['name']}{shortcut}: {cmd['action']}\n"
                        response += "\n"
                
                    # Элементы UI (с иерархией по depth)
                    if structure['items']:
                        response += f"  Элементы UI ({len(structure['items'])}):\n"
                        for item in structure['items']:
                            depth = item.get('depth', 0)
                            indent = "    " + "  " * depth
                            data_path = f" -> {item['data_path']}" if item.get('data_path') else ""
                            title = f" «{item['title']}»" if item.get('title') else ""
                            v, e = item.get('visible'), item.get('enabled')
                            vis_str = ""
                            if v == 0:
                                vis_str += " [скрыт]"
                            if e == 0:
                                vis_str += " [недоступен]"
                            response += f"{indent}• {item['name']} ({item['type']}){data_path}{title}{vis_str}\n"
                        response += "\n"
        
            return [TextContent(type="text", text=response)]
    
        elif name == "search_form_properties":
            property_name = arguments["property_name"]
            property_value = arguments.get("property_value")
            project_filter = arguments.get("project_filter")
            extension_filter = arguments.get("extension_filter")
        
            results = tools.search_form_properties(property_name, property_value, project_filter, extension_filter)
        
            if not results:
                value_text = f"={property_value}" if property_value else ""
                return [TextContent(type="text", text=f"Элементы со свойством '{property_name}{value_text}' не найдены")]
        
            value_text = f"={property_value}" if property_value else ""
            response = f"Элементы со свойством '{property_name}{value_text}':\n\n"
        
            for project_name, project_data in results.items():
                response += f"📁 Проект: {project_name}\n"
                for db_name, elements in project_data.items():
                    response += f"  └─ {db_name}: {len(elements)} элемент(ов)\n"
                    for elem in elements:
                        response += f"     • {elem['object_name']}.{elem['form_name']}.{elem['element_name']}\n"
                        response += f"       Тип: {elem['element_type']}, {property_name}: {elem['property_value']}\n"
                        if elem['data_path']:
                            response += f"       DataPath: {elem['data_path']}\n"
                response += "\n"
        
            return [TextContent(type="text", text=response)]
    
        elif name == "get_object_structure":
            object_name = arguments["object_name"]
            project_filter = arguments.get("project_filter")
            extension_filter = arguments.get("extension_filter")

            results = tools.get_object_structure(object_name, project_filter, extension_filter)

            if not results:
                return [TextContent(type="text", text=f"Объект '{object_name}' не найден")]

            response = f"Структура объекта '{object_name}':\n\n"

            for project_name, project_data in results.items():
                response += f"Проект: {project_name}\n"
                for db_name, structure in project_data.items():
                    response += f"  {db_name}:\n\n"
                    synonym = f" ({structure['synonym']})" if structure.get('synonym') else ""
                    response += f"  {structure['type']}: {structure['name']}{synonym}\n"
                    if structure.get('object_belonging'):
                        response += f"  Принадлежность: {structure['object_belonging']}\n"
                    if structure.get('uuid'):
                        response += f"  UUID: {structure['uuid']}\n"
                    if structure.get('comment'):
                        response += f"  Комментарий: {structure['comment']}\n"
                    response += "\n"

                    if structure['type'] == 'FunctionalOption':
                        if structure.get('location_constant'):
                            response += f"  Константа хранения: {structure['location_constant']}\n"
                        if structure.get('privileged_get_mode') is not None:
                            response += f"  Привилегированное получение: {structure['privileged_get_mode']}\n"
                        if structure.get('content_refs'):
                            response += f"  Привязка к объектам: {len(structure['content_refs'])} объект(ов)\n"
                        if structure.get('used_in'):
                            response += f"  Используется в ({len(structure['used_in'])}):\n"
                            for u in structure['used_in']:
                                response += f"    - {u['owner_object']}.{u['form_name']} / {u['element_type']} {u['element_name'] or '(уровень формы)'}\n"
                        response += "\n"
                    if structure.get('attributes'):
                        response += f"  Реквизиты ({len(structure['attributes'])}):\n"
                        for attr in structure['attributes']:
                            std = " [стд]" if attr['is_standard'] else ""
                            title = f" — {attr['title']}" if attr.get('title') else ""
                            comment = f" — {attr['comment']}" if attr.get('comment') else ""
                            response += f"    - {attr['name']}{std}: {attr['type']}{title}{comment}\n"
                        response += "\n"

                    if structure.get('dimensions'):
                        response += f"  Измерения ({len(structure['dimensions'])}):\n"
                        for dim in structure['dimensions']:
                            title = f" — {dim['title']}" if dim.get('title') else ""
                            comment = f" — {dim['comment']}" if dim.get('comment') else ""
                            response += f"    - {dim['name']}: {dim['type']}{title}{comment}\n"
                        response += "\n"

                    if structure.get('resources'):
                        response += f"  Ресурсы ({len(structure['resources'])}):\n"
                        for res in structure['resources']:
                            title = f" — {res['title']}" if res.get('title') else ""
                            comment = f" — {res['comment']}" if res.get('comment') else ""
                            response += f"    - {res['name']}: {res['type']}{title}{comment}\n"
                        response += "\n"

                    if structure.get('tabular_sections'):
                        response += f"  Табличные части ({len(structure['tabular_sections'])}):\n"
                        for ts in structure['tabular_sections']:
                            ts_title = f" ({ts['title']})" if ts.get('title') else ""
                            ts_comment = f" — {ts['comment']}" if ts.get('comment') else ""
                            response += f"    [{ts['name']}{ts_title}{ts_comment}]:\n"
                            for col in ts['columns']:
                                col_title = f" — {col.get('title')}" if col.get('title') else ""
                                col_comment = f" — {col['comment']}" if col.get('comment') else ""
                                response += f"      - {col['name']}: {col['type']}{col_title}{col_comment}\n"
                        response += "\n"

                    if structure.get('enum_values'):
                        response += f"  Значения перечисления ({len(structure['enum_values'])}):\n"
                        for ev in structure['enum_values']:
                            order = f" (порядок: {ev['enum_order']})" if ev.get('enum_order') is not None else ""
                            title = f" — {ev['title']}" if ev.get('title') else ""
                            comment = f" — {ev['comment']}" if ev.get('comment') else ""
                            belong = f" [{ev['object_belonging']}]" if ev.get('object_belonging') else ""
                            response += f"    - {ev['name']}{order}{title}{comment}{belong}\n"
                        response += "\n"

                    if structure.get('forms'):
                        response += f"  Формы: {', '.join(structure['forms'])}\n"
                    if structure.get('modules'):
                        response += f"  Модули: {', '.join(structure['modules'])}\n"

                response += "\n"

            return [TextContent(type="text", text=response)]

        elif name == "get_functional_options":
            object_name = arguments["object_name"]
            project_filter = arguments.get("project_filter")
            extension_filter = arguments.get("extension_filter")
            form_name = arguments.get("form_name")
            element_type = arguments.get("element_type")
            element_name = arguments.get("element_name")

            results = tools.get_functional_options(
                object_name, project_filter, extension_filter,
                form_name=form_name, element_type=element_type, element_name=element_name
            )

            if not results:
                return [TextContent(type="text", text="Объект или элемент не найдены, либо привязок к функциональным опциям нет.")]

            if form_name and element_type and element_name:
                title = f"Функциональные опции элемента формы {object_name}.{form_name} / {element_type} '{element_name}':"
            else:
                title = f"Функциональные опции объекта {object_name}:"

            response = title + "\n\n"
            for project_name, project_data in results.items():
                response += f"Проект: {project_name}\n"
                for db_name, options in project_data.items():
                    response += f"  {db_name}: {len(options)} ФО\n"
                    for opt in options:
                        syn = f" ({opt['synonym']})" if opt.get('synonym') else ""
                        detail = ""
                        if opt.get('content_ref_type') and opt['content_ref_type'] != 'Object':
                            detail = f" — {opt['content_ref_type']}"
                            if opt.get('element_name'):
                                detail += f".{opt['element_name']}"
                            if opt.get('tabular_section_name'):
                                detail += f" ТЧ {opt['tabular_section_name']}"
                        response += f"    - {opt['name']}{syn}{detail}\n"
                response += "\n"
            return [TextContent(type="text", text=response)]

        elif name == "find_attribute":
            attribute_name = arguments["attribute_name"]
            project_filter = arguments.get("project_filter")
            extension_filter = arguments.get("extension_filter")
            max_results = arguments.get("max_results", 20)

            results = tools.find_attribute(attribute_name, project_filter, extension_filter, max_results)

            if not results:
                return [TextContent(type="text", text=f"Реквизит '{attribute_name}' не найден ни в одном объекте")]

            response = f"Реквизит '{attribute_name}' найден в:\n\n"

            for project_name, project_data in results.items():
                response += f"Проект: {project_name}\n"
                for db_name, db_results in project_data.items():
                    response += f"  {db_name}: {len(db_results)} совпадение(ий)\n"
                    for r in db_results:
                        section = f" [{r['section']}]" if r.get('section') != 'Attribute' else ""
                        title = f" — {r['title']}" if r.get('title') else ""
                        belong = f" [{r['object_belonging']}]" if r.get('object_belonging') else ""
                        response += f"    - {r['object_type']}.{r['object_name']}: {r['attribute_name']}{section}: {r['attribute_type']}{title}{belong}\n"
                response += "\n"

            return [TextContent(type="text", text=response)]

        else:
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
