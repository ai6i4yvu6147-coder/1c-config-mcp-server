from mcp.types import TextContent

from shared.metadata_type_resolver import format_types_for_text

from .common import _form_item_command_suffix


async def handle_find_form(tools, arguments: dict) -> list[TextContent]:
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


async def handle_find_form_element(tools, arguments: dict) -> list[TextContent]:
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


async def handle_get_form_structure(tools, arguments: dict) -> list[TextContent]:
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
                    type_text = format_types_for_text(attr.get('types') or [])
                    response += f"    • {attr['name']}{main_mark}: {type_text}\n"
                    for col in attr.get('columns') or []:
                        col_type_text = format_types_for_text(col.get('types') or [])
                        table_ctx = f" [{col['table']}]" if col.get('table') else ""
                        response += f"      - {col['name']}{table_ctx}: {col_type_text}\n"
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
                    cmd_sfx = _form_item_command_suffix(item)
                    response += f"{indent}• {item['name']} ({item['type']}){data_path}{title}{vis_str}{cmd_sfx}\n"
                response += "\n"

    return [TextContent(type="text", text=response)]


async def handle_search_form_properties(tools, arguments: dict) -> list[TextContent]:
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
