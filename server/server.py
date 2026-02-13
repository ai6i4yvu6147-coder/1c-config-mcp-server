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
            description="Поиск по коду конфигурации. Ищет во всех активных проектах и их базах/расширениях. Автоматически выбирает оптимальный метод поиска.",
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
            description="Получить код модуля объекта или модуля формы",
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
            description="Получить список процедур и функций модуля объекта или модуля формы (только сигнатуры, без тел)",
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
            description="Получить код конкретной процедуры или функции из модуля объекта или модуля формы",
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
                        "description": "Фильтр по проекту (опционально)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Фильтр по базе/расширению (опционально)"
                    }
                },
                "required": ["object_name", "procedure_name"]
            }
        ),
        Tool(
            name="find_form",
            description="Поиск форм по имени объекта и/или имени формы",
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
                        "description": "Фильтр по проекту (опционально)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Фильтр по базе/расширению (опционально)"
                    }
                }
            }
        ),
        Tool(
            name="find_form_element",
            description="Найти все формы, содержащие элемент с указанным именем",
            inputSchema={
                "type": "object",
                "properties": {
                    "element_name": {
                        "type": "string",
                        "description": "Имя элемента формы (можно частичное)"
                    },
                    "object_name": {
                        "type": "string",
                        "description": "Имя объекта для фильтрации (опционально, можно частичное)"
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
                "required": ["element_name"]
            }
        ),
        Tool(
            name="get_form_structure",
            description="Получить полную структуру формы: реквизиты, команды, элементы UI, события",
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
                        "description": "Фильтр по проекту (опционально)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Фильтр по базе/расширению (опционально)"
                    }
                },
                "required": ["object_name", "form_name"]
            }
        ),
        Tool(
            name="search_form_properties",
            description="Поиск элементов форм по свойствам (например, Visible=false, Enabled=false)",
            inputSchema={
                "type": "object",
                "properties": {
                    "property_name": {
                        "type": "string",
                        "description": "Имя свойства (например: Visible, Enabled, ReadOnly)"
                    },
                    "property_value": {
                        "type": "string",
                        "description": "Значение свойства (опционально, например: false, true)"
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
                "required": ["property_name"]
            }
        ),
        Tool(
            name="get_object_structure",
            description="Получить полную структуру метаданных объекта 1С: реквизиты, табличные части с колонками, измерения/ресурсы регистров, значения перечислений, список форм и модулей",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_name": {
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
                "required": ["object_name"]
            }
        ),
        Tool(
            name="find_attribute",
            description="Поиск реквизита по имени во всех объектах метаданных. Находит совпадения в реквизитах, измерениях и ресурсах регистров",
            inputSchema={
                "type": "object",
                "properties": {
                    "attribute_name": {
                        "type": "string",
                        "description": "Имя реквизита (можно частичное)"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Фильтр по проекту (опционально)"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Фильтр по базе/расширению (опционально)"
                    },
                    "max_results": {
                        "type": "number",
                        "description": "Максимум результатов на базу (по умолчанию 20)",
                        "default": 20
                    }
                },
                "required": ["attribute_name"]
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
        object_name = arguments.get("object_name")
        module_type = arguments.get("module_type")
        max_results = arguments.get("max_results", 10)

        results = tools.search_code(query, project_filter, extension_filter, max_results,
                                    object_name, module_type)
        
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
                    response += f"{proc['line']:4d}. {proc['type']} {proc['name']}({proc['params']}){export_mark}\n"
                
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
                    response += f"     • {form['object_type']}.{form['object_name']}.{form['form_name']}\n"
                    response += f"       Реквизитов: {form['attributes_count']}, Команд: {form['commands_count']}, Элементов: {form['items_count']}\n"
                    if form['properties']:
                        props_str = ", ".join([f"{k}={v}" for k, v in list(form['properties'].items())[:3]])
                        response += f"       Свойства: {props_str}\n"
            response += "\n"
        
        return [TextContent(type="text", text=response)]
    
    elif name == "find_form_element":
        element_name = arguments["element_name"]
        object_name = arguments.get("object_name")
        project_filter = arguments.get("project_filter")
        extension_filter = arguments.get("extension_filter")

        results = tools.find_form_element(element_name, object_name, project_filter, extension_filter)
        
        if not results:
            return [TextContent(type="text", text=f"Элемент '{element_name}' не найден в формах")]
        
        response = f"Элемент '{element_name}' найден в формах:\n\n"
        
        for project_name, project_data in results.items():
            response += f"📁 Проект: {project_name}\n"
            for db_name, elements in project_data.items():
                response += f"  └─ {db_name}:\n"
                for elem in elements:
                    response += f"     • {elem['object_name']}.{elem['form_name']}.{elem['element_name']}\n"
                    response += f"       Тип: {elem['element_type']}\n"
                    if elem['data_path']:
                        response += f"       DataPath: {elem['data_path']}\n"
                    if elem['title']:
                        response += f"       Заголовок: {elem['title']}\n"
                    if elem['properties']:
                        visible = elem['properties'].get('Visible', 'true')
                        enabled = elem['properties'].get('Enabled', 'true')
                        response += f"       Visible: {visible}, Enabled: {enabled}\n"
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
                
                # Свойства формы
                if structure['properties']:
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
                
                # Элементы UI
                if structure['items']:
                    response += f"  Элементы UI ({len(structure['items'])}):\n"
                    for item in structure['items']:
                        data_path = f" -> {item['data_path']}" if item['data_path'] else ""
                        title = f" «{item['title']}»" if item.get('title') else ""
                        props = item.get('properties', {})
                        visible = props.get('Visible', '')
                        enabled = props.get('Enabled', '')
                        vis_str = ""
                        if visible == 'false':
                            vis_str += " [скрыт]"
                        if enabled == 'false':
                            vis_str += " [недоступен]"
                        response += f"    • {item['name']} ({item['type']}){data_path}{title}{vis_str}\n"
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
                synonym = f" ({structure['synonym']})" if structure['synonym'] else ""
                response += f"  {structure['type']}: {structure['name']}{synonym}\n"
                if structure['uuid']:
                    response += f"  UUID: {structure['uuid']}\n"
                if structure['comment']:
                    response += f"  Комментарий: {structure['comment']}\n"
                response += "\n"

                if structure['attributes']:
                    response += f"  Реквизиты ({len(structure['attributes'])}):\n"
                    for attr in structure['attributes']:
                        std = " [стд]" if attr['is_standard'] else ""
                        title = f" — {attr['title']}" if attr['title'] else ""
                        response += f"    - {attr['name']}{std}: {attr['type']}{title}\n"
                    response += "\n"

                if structure['dimensions']:
                    response += f"  Измерения ({len(structure['dimensions'])}):\n"
                    for dim in structure['dimensions']:
                        title = f" — {dim['title']}" if dim['title'] else ""
                        response += f"    - {dim['name']}: {dim['type']}{title}\n"
                    response += "\n"

                if structure['resources']:
                    response += f"  Ресурсы ({len(structure['resources'])}):\n"
                    for res in structure['resources']:
                        title = f" — {res['title']}" if res['title'] else ""
                        response += f"    - {res['name']}: {res['type']}{title}\n"
                    response += "\n"

                if structure['tabular_sections']:
                    response += f"  Табличные части ({len(structure['tabular_sections'])}):\n"
                    for ts in structure['tabular_sections']:
                        ts_title = f" ({ts['title']})" if ts['title'] else ""
                        response += f"    [{ts['name']}{ts_title}]:\n"
                        for col in ts['columns']:
                            col_title = f" — {col['title']}" if col['title'] else ""
                            response += f"      - {col['name']}: {col['type']}{col_title}\n"
                    response += "\n"

                if structure['enum_values']:
                    response += f"  Значения перечисления ({len(structure['enum_values'])}):\n"
                    for ev in structure['enum_values']:
                        order = f" (порядок: {ev['enum_order']})" if ev['enum_order'] is not None else ""
                        title = f" — {ev['title']}" if ev['title'] else ""
                        response += f"    - {ev['name']}{order}{title}\n"
                    response += "\n"

                if structure['forms']:
                    response += f"  Формы: {', '.join(structure['forms'])}\n"
                if structure['modules']:
                    response += f"  Модули: {', '.join(structure['modules'])}\n"

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
                    section = f" [{r['section']}]" if r['section'] != 'Attribute' else ""
                    title = f" — {r['title']}" if r['title'] else ""
                    response += f"    - {r['object_type']}.{r['object_name']}: {r['attribute_name']}{section}: {r['attribute_type']}{title}\n"
            response += "\n"

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