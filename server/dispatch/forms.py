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


def _format_item_overview_line(item, attribute_names):
    depth = item.get('depth', 0)
    indent = "    " + "  " * depth
    props = item.get('overview_properties') or {}
    prop_parts = []
    for key, val in props.items():
        if key == 'CommandName':
            continue
        if key == 'DataPath' and val in attribute_names:
            prop_parts.append(f"{key}={val} (→ attribute {val})")
        else:
            prop_parts.append(f"{key}={val}")
    props_str = (' ' + ' '.join(prop_parts)) if prop_parts else ''
    vis_str = ''
    if props.get('Visible', '').lower() == 'false':
        vis_str += " [скрыт]"
    if props.get('Enabled', '').lower() == 'false':
        vis_str += " [недоступен]"
    cmd_sfx = _form_item_command_suffix(item)
    line = f"{indent}• {item['name']} ({item['type']}){props_str}{vis_str}{cmd_sfx}\n"
    if item.get('child_count'):
        line += f"{indent}  columns: {item['child_count']} — get_form_item(element_name=\"{item['name']}\")\n"
    return line


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
            if structure.get('properties'):
                response += "  Свойства формы:\n"
                for key, value in structure['properties'].items():
                    response += f"    • {key}: {value}\n"
                response += "\n"

            if structure['events']:
                response += "  События формы:\n"
                for event in structure['events']:
                    call_type = f" ({event['call_type']})" if event['call_type'] else ""
                    response += f"    • {event['event_name']}{call_type} -> {event['handler']}\n"
                response += "\n"

            attr_names = set(structure.get('attribute_names') or [])
            if structure['attributes']:
                response += "  Реквизиты:\n"
                for attr in structure['attributes']:
                    main_mark = " [Основной]" if attr['is_main'] else ""
                    type_text = format_types_for_text(attr.get('types') or [])
                    response += f"    • {attr['name']}{main_mark}: {type_text}\n"
                    for hint in attr.get('hints') or []:
                        response += f"      {hint}\n"
                response += "\n"

            if structure['commands']:
                response += "  Команды:\n"
                for cmd in structure['commands']:
                    shortcut = f" [{cmd['shortcut']}]" if cmd['shortcut'] else ""
                    response += f"    • {cmd['name']}{shortcut}: {cmd['action']}\n"
                response += "\n"

            if structure['items']:
                response += f"  Элементы UI ({len(structure['items'])}):\n"
                for item in structure['items']:
                    response += _format_item_overview_line(item, attr_names)
                response += "\n"

    return [TextContent(type="text", text=response)]


async def handle_get_form_attribute(tools, arguments: dict) -> list[TextContent]:
    object_name = arguments["object_name"]
    form_name = arguments["form_name"]
    attribute_name = arguments["attribute_name"]
    project_filter = arguments.get("project_filter")
    extension_filter = arguments.get("extension_filter")
    column_name = arguments.get("column_name")

    results = tools.get_form_attribute(
        object_name, form_name, attribute_name, project_filter, extension_filter, column_name,
    )

    if not results:
        target = f"{attribute_name}" + (f".{column_name}" if column_name else "")
        return [TextContent(type="text", text=f"Реквизит '{target}' не найден в форме '{object_name}.{form_name}'")]

    response = ""
    for project_name, project_data in results.items():
        for db_name, data in project_data.items():
            response += f"📁 {project_name} / {db_name}\n"
            if column_name:
                response += f"Колонка/поле {column_name} реквизита {attribute_name}:\n\n"
                if data.get('types'):
                    response += f"  types: {format_types_for_text(data['types'])}\n"
                for prop in data.get('properties') or []:
                    response += f"  {prop['path']}: {prop['value']}\n"
                for fo in data.get('functional_options') or []:
                    response += f"  ФО: {fo['name']}\n"
            else:
                main_mark = " [Основной]" if data.get('is_main') else ""
                response += f"Реквизит {data['name']}{main_mark}\n"
                if data.get('title'):
                    response += f"  title: {data['title']}\n"
                response += f"  types: {format_types_for_text(data.get('types') or [])}\n\n"
                for prop in data.get('properties') or []:
                    response += f"  {prop['path']}: {prop['value']}\n"
                if data.get('columns'):
                    response += "\n  Columns:\n"
                    for col in data['columns']:
                        if col.get('types'):
                            ct = format_types_for_text(col['types'])
                            table_ctx = f" [{col['table']}]" if col.get('table') else ""
                            response += f"    • {col['name']}{table_ctx}: {ct}\n"
                        else:
                            dp = col.get('dataPath') or col.get('field') or col.get('name')
                            response += f"    • dataPath={dp}\n"
            response += "\n"

    return [TextContent(type="text", text=response)]


async def handle_get_form_item(tools, arguments: dict) -> list[TextContent]:
    object_name = arguments["object_name"]
    form_name = arguments["form_name"]
    element_name = arguments["element_name"]
    project_filter = arguments.get("project_filter")
    extension_filter = arguments.get("extension_filter")
    column_name = arguments.get("column_name")

    results = tools.get_form_item(
        object_name, form_name, element_name, project_filter, extension_filter, column_name,
    )

    if not results:
        target = element_name + (f".{column_name}" if column_name else "")
        return [TextContent(type="text", text=f"Элемент '{target}' не найден в форме '{object_name}.{form_name}'")]

    response = ""
    for project_name, project_data in results.items():
        for db_name, data in project_data.items():
            response += f"📁 {project_name} / {db_name}\n"
            label = data['name']
            if column_name:
                response += f"Колонка UI {label} (родитель: {data.get('parent_name')}):\n\n"
            else:
                response += f"Элемент {label} ({data['item_type']}):\n\n"
            for prop in data.get('properties') or []:
                response += f"  {prop['path']}: {prop['value']}\n"
            if data.get('events'):
                response += "\n  События:\n"
                for ev in data['events']:
                    response += f"    • {ev['event_name']} -> {ev['handler']}\n"
            if data.get('columns'):
                response += "\n  Columns:\n"
                for col in data['columns']:
                    dp = f" -> {col['dataPath']}" if col.get('dataPath') else ""
                    response += f"    • {col['name']} ({col['item_type']}){dp}\n"
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
                if elem.get('data_path'):
                    response += f"       DataPath: {elem['data_path']}\n"
        response += "\n"

    return [TextContent(type="text", text=response)]
