from mcp.types import TextContent

from shared.metadata_type_resolver import format_types_for_text
from server.tools import format_business_process_route_text

from .common import _ambiguous_block


async def handle_find_object(tools, arguments: dict) -> list[TextContent]:
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


async def handle_list_objects(tools, arguments: dict) -> list[TextContent]:
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


def _capped_header(label, items, total):
    shown = len(items)
    if total and total > shown:
        return f"  {label} (показаны {shown} из {total}):\n"
    return f"  {label} ({shown}):\n"


def _capped_footer(items, total, hint):
    shown = len(items)
    if total and total > shown:
        return f"    … ещё {total - shown}; {hint}\n"
    return ""


async def handle_get_object_structure(tools, arguments: dict) -> list[TextContent]:
    object_name = arguments["object_name"]
    project_filter = arguments.get("project_filter")
    extension_filter = arguments.get("extension_filter")
    sections = arguments.get("sections")
    max_attributes = arguments.get("max_attributes", 50)

    results = tools.get_object_structure(
        object_name, project_filter, extension_filter, sections, max_attributes,
        arguments.get("object_type"),
    )

    if not results:
        return [TextContent(type="text", text=f"Объект '{object_name}' не найден")]

    response = f"Структура объекта '{object_name}':\n\n"

    for project_name, project_data in results.items():
        response += f"Проект: {project_name}\n"
        for db_name, structure in project_data.items():
            response += f"  {db_name}:\n\n"
            if structure.get('ambiguous'):
                response += _ambiguous_block(structure, indent="  ")
                continue
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
            if structure['type'] == 'ScheduledJob':
                if structure.get('method_name'):
                    response += f"  Метод: {structure['method_name']}\n"
                if structure.get('use') is not None:
                    response += f"  Использование: {'включено' if structure['use'] else 'выключено'}\n"
                if structure.get('predefined') is not None:
                    response += f"  Предопределённое: {structure['predefined']}\n"
                if structure.get('description'):
                    response += f"  Описание: {structure['description']}\n"
                if structure.get('key'):
                    response += f"  Ключ: {structure['key']}\n"
                if structure.get('restart_count_on_failure') is not None:
                    response += f"  Перезапусков при сбое: {structure['restart_count_on_failure']}\n"
                if structure.get('restart_interval_on_failure') is not None:
                    response += f"  Интервал перезапуска (с): {structure['restart_interval_on_failure']}\n"
                response += "\n"
            if structure['type'] == 'EventSubscription':
                if structure.get('event'):
                    response += f"  Событие: {structure['event']}\n"
                if structure.get('handler'):
                    response += f"  Обработчик: {structure['handler']}\n"
                if structure.get('source_kinds'):
                    response += f"  Источник — вид целиком: {structure['source_kinds']}\n"
                sources = structure.get('sources')
                if sources:
                    total = structure.get('sources_total_count')
                    response += _capped_header("Источники", sources, total)
                    for s in sources:
                        syn = f" — {s['synonym']}" if s.get('synonym') else ""
                        response += f"    - {s['object_type']}.{s['name']}{syn}\n"
                    response += _capped_footer(sources, total, "увеличьте max_attributes")
                elif sources is not None and not structure.get('source_kinds'):
                    response += "  Источники: (не заданы)\n"
                response += "\n"
            if structure['type'] == 'DefinedType':
                if structure.get('types'):
                    response += f"  Состав типа ({len(structure['types'])}):\n"
                    for member in structure['types']:
                        response += f"    - {format_types_for_text([member])}\n"
                else:
                    response += "  Состав типа: (тип не определён)\n"
                response += "\n"
            if structure['type'] == 'Constant' and 'types' in structure:
                response += f"  Тип значения: {format_types_for_text(structure.get('types') or [])}\n\n"
            if structure.get('attributes'):
                response += _capped_header("Реквизиты", structure['attributes'], structure.get('attributes_total_count'))
                for attr in structure['attributes']:
                    std = " [стд]" if attr['is_standard'] else ""
                    title = f" — {attr['title']}" if attr.get('title') else ""
                    comment = f" — {attr['comment']}" if attr.get('comment') else ""
                    type_text = format_types_for_text(attr.get('types') or [])
                    response += f"    - {attr['name']}{std}: {type_text}{title}{comment}\n"
                response += _capped_footer(
                    structure['attributes'], structure.get('attributes_total_count'),
                    "увеличьте max_attributes или используйте find_attribute",
                )
                response += "\n"

            if structure.get('dimensions'):
                response += _capped_header("Измерения", structure['dimensions'], structure.get('dimensions_total_count'))
                for dim in structure['dimensions']:
                    title = f" — {dim['title']}" if dim.get('title') else ""
                    comment = f" — {dim['comment']}" if dim.get('comment') else ""
                    type_text = format_types_for_text(dim.get('types') or [])
                    response += f"    - {dim['name']}: {type_text}{title}{comment}\n"
                response += _capped_footer(
                    structure['dimensions'], structure.get('dimensions_total_count'), "увеличьте max_attributes",
                )
                response += "\n"

            if structure.get('resources'):
                response += _capped_header("Ресурсы", structure['resources'], structure.get('resources_total_count'))
                for res in structure['resources']:
                    title = f" — {res['title']}" if res.get('title') else ""
                    comment = f" — {res['comment']}" if res.get('comment') else ""
                    type_text = format_types_for_text(res.get('types') or [])
                    response += f"    - {res['name']}: {type_text}{title}{comment}\n"
                response += _capped_footer(
                    structure['resources'], structure.get('resources_total_count'), "увеличьте max_attributes",
                )
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
                        type_text = format_types_for_text(col.get('types') or [])
                        response += f"      - {col['name']}: {type_text}{col_title}{col_comment}\n"
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

            if structure.get('route_points') is not None:
                route_text = format_business_process_route_text(
                    structure.get('route_points', []),
                    structure.get('route_transitions', []),
                )
                if route_text:
                    response += route_text

            if structure.get('commands'):
                response += f"  Команды объекта ({len(structure['commands'])}):\n"
                for c in structure['commands']:
                    hm = " [есть модуль]" if c.get('has_module') else ""
                    syn = f" ({c['synonym']})" if c.get('synonym') else ""
                    response += f"    - {c['name']}{syn}{hm}\n"
                response += "\n"
            if structure.get('forms'):
                response += f"  Формы: {', '.join(structure['forms'])}\n"
            if structure.get('modules'):
                response += f"  Модули: {', '.join(structure['modules'])}\n"

        response += "\n"

    return [TextContent(type="text", text=response)]


async def handle_get_functional_options(tools, arguments: dict) -> list[TextContent]:
    object_name = arguments["object_name"]
    project_filter = arguments.get("project_filter")
    extension_filter = arguments.get("extension_filter")
    form_name = arguments.get("form_name")
    element_type = arguments.get("element_type")
    element_name = arguments.get("element_name")

    attribute_name = arguments.get("attribute_name")

    results = tools.get_functional_options(
        object_name, project_filter, extension_filter,
        form_name=form_name, element_type=element_type, element_name=element_name,
        attribute_name=attribute_name,
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


async def handle_find_attribute(tools, arguments: dict) -> list[TextContent]:
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
                type_text = format_types_for_text(r.get('types') or [])
                response += f"    - {r['object_type']}.{r['object_name']}: {r['attribute_name']}{section}: {type_text}{title}{belong}\n"
        response += "\n"

    return [TextContent(type="text", text=response)]
