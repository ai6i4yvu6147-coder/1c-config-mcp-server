from mcp.types import TextContent

from .common import _ambiguous_block


def _bool_ru(value):
    if value is True:
        return "да"
    if value is False:
        return "нет"
    return "—"


def _role_layer_label(item):
    if item.get('source_layer') == 'extension':
        ext = item.get('extension_name')
        return f"расширение {ext}" if ext else "расширение"
    return "основная"


def _grant_line(grant, show_db):
    line = f"    • {grant.get('target_qname')}: {grant.get('right_name')}"
    if grant.get('granted') is False:
        line += " (запрещено)"
    if show_db and grant.get('db_name'):
        line += f"  [{grant['db_name']}]"
    return line + "\n"


async def handle_find_role(tools, arguments: dict) -> list[TextContent]:
    name = arguments["name"]
    results = tools.find_role(
        name,
        arguments.get("project_filter"),
        arguments.get("extension_filter"),
    )
    if not results:
        return [TextContent(type="text", text=f"Роль '{name}' не найдена")]

    response = f"Найденные роли '{name}':\n\n"
    for project_name, project_data in results.items():
        response += f"📁 Проект: {project_name}\n"
        for db_name, roles in project_data.items():
            response += f"  └─ {db_name}:\n"
            for r in roles:
                syn = f" ({r['synonym']})" if r.get('synonym') else ""
                response += f"     • {r['role_qualified_name']}{syn}  [слой: {_role_layer_label(r)}]\n"
                if r.get('object_belonging'):
                    response += f"       Принадлежность: {r['object_belonging']}\n"
        response += "\n"
    return [TextContent(type="text", text=response)]


async def handle_list_roles(tools, arguments: dict) -> list[TextContent]:
    results = tools.list_roles(
        arguments.get("project_filter"),
        arguments.get("extension_filter"),
        arguments.get("limit", 200),
    )
    if not results:
        return [TextContent(type="text", text="Роли не найдены")]

    response = "Роли:\n\n"
    for project_name, project_data in results.items():
        response += f"📁 Проект: {project_name}\n"
        for db_name, payload in project_data.items():
            roles = payload.get('roles', [])
            total = payload.get('total_count', len(roles))
            count_note = f"{len(roles)} из {total}" if payload.get('is_truncated') else f"{len(roles)}"
            response += f"  └─ {db_name}: {count_note}\n"
            for r in roles:
                syn = f" ({r['synonym']})" if r.get('synonym') else ""
                response += f"     • {r['role_qualified_name']}{syn}\n"
            if payload.get('is_truncated'):
                response += "     … показаны не все; увеличьте limit.\n"
        response += "\n"
    return [TextContent(type="text", text=response)]


async def handle_get_role_rights(tools, arguments: dict) -> list[TextContent]:
    payload = tools.get_role_rights(
        arguments["role_name"],
        project_filter=arguments.get("project_filter"),
        extension_filter=arguments.get("extension_filter"),
        merge=arguments.get("merge", True),
        object_name=arguments.get("object_name"),
        rights=arguments.get("rights"),
        rls=arguments.get("rls"),
        depth=arguments.get("depth", "object"),
        include_restriction_text=arguments.get("include_restriction_text", False),
        max_results=arguments.get("max_results", 200),
        response_mode=arguments.get("response_mode"),
    )

    if payload.get('error') == 'not_found':
        name = payload.get('role_name', arguments.get('role_name'))
        return [TextContent(type="text", text=f"Роль '{name}' не найдена")]

    role = payload.get('role', {})
    syn = f" ({role['synonym']})" if role.get('synonym') else ""
    response = f"Права роли {role.get('qualified_name')}{syn}:\n"
    if role.get('uuid'):
        response += f"  UUID: {role['uuid']}\n"
    if role.get('object_belonging'):
        response += f"  Принадлежность: {role['object_belonging']}\n"

    merge = payload.get('merge')
    layers = payload.get('layers') or []
    response += f"  Режим: {'merge (основная + расширения)' if merge else 'один слой'}"
    if layers:
        response += f" | Слои: {', '.join(layers)}"
    response += "\n"
    show_db = bool(merge and len(layers) > 1)

    settings = payload.get('settings')
    if settings:
        response += (
            "  Настройки: "
            f"для новых объектов={_bool_ru(settings.get('set_for_new_objects'))}, "
            f"для реквизитов по умолчанию={_bool_ru(settings.get('set_for_attributes_by_default'))}, "
            f"независимые права подчинённых={_bool_ru(settings.get('independent_rights_of_child_objects'))}\n"
        )
    response += "\n"

    if payload.get('response_mode') == 'summary':
        stats = payload.get('grant_stats', {})
        prof_note = " (admin_full)" if payload.get('role_profile') == 'admin_full' else ""
        response += (
            f"  Гранты — сводка{prof_note}: всего {stats.get('total_rights', 0)} "
            f"(объектных {stats.get('object_level', 0)}, реквизитных {stats.get('field_level', 0)})\n"
        )
        if payload.get('hint'):
            response += f"  {payload['hint']}\n"
        delta = payload.get('extension_delta_grants') or []
        if delta:
            response += f"\n  Гранты расширений сверх основной ({len(delta)}):\n"
            for g in delta:
                response += _grant_line(g, True)
    else:
        grants = payload.get('grants') or []
        total = payload.get('total_count', len(grants))
        count_note = f"показаны {len(grants)} из {total}" if payload.get('is_truncated') else f"{len(grants)}"
        response += f"  Гранты ({count_note}):\n"
        for g in grants:
            response += _grant_line(g, show_db)
        if payload.get('is_truncated'):
            response += "    … показаны не все; уточните object_name/rights или увеличьте max_results.\n"

    restrictions = payload.get('access_restrictions') or []
    if restrictions:
        rtotal = payload.get('access_restrictions_total_count', len(restrictions))
        rnote = (
            f"показаны {len(restrictions)} из {rtotal}"
            if payload.get('access_restrictions_is_truncated') else f"{len(restrictions)}"
        )
        response += f"\n  Ограничения доступа RLS ({rnote}):\n"
        for r in restrictions:
            scope = f" [{r['field_scope']}]" if r.get('field_scope') else ""
            line = f"    • {r.get('object')} / {r.get('right')}{scope}"
            if show_db and r.get('db_name'):
                line += f"  [{r['db_name']}]"
            response += line + "\n"
            preview = r.get('restriction_text') or r.get('restriction_text_preview')
            if preview:
                response += f"        {preview}\n"

    templates = payload.get('restriction_templates') or []
    if templates:
        response += f"\n  Шаблоны ограничений ({len(templates)}):\n"
        for t in templates:
            response += f"    • {t.get('template_name')}\n"
            preview = t.get('condition_text') or t.get('condition_text_preview')
            if preview:
                response += f"        {preview}\n"

    return [TextContent(type="text", text=response)]


async def handle_find_roles_for_object(tools, arguments: dict) -> list[TextContent]:
    object_name = arguments["object_name"]
    merge = arguments.get("merge", False)
    results = tools.find_roles_for_object(
        object_name,
        project_filter=arguments.get("project_filter"),
        extension_filter=arguments.get("extension_filter"),
        merge=merge,
        right_name=arguments.get("right_name"),
        rls=arguments.get("rls"),
        max_results=arguments.get("max_results", 200),
        object_type=arguments.get("object_type"),
    )
    if not results:
        return [TextContent(type="text", text=f"Роли с правами на '{object_name}' не найдены")]

    if merge:
        response = f"Роли с правами на '{object_name}' (сводка по проекту):\n\n"
        for project_name, payload in results.items():
            if payload.get('error') == 'not_found':
                response += f"📁 {project_name}: объект не найден\n\n"
                continue
            target = payload.get('target', {})
            response += f"📁 Проект: {project_name} — цель {target.get('type')}.{target.get('name')}\n"
            roles = payload.get('roles', [])
            total = payload.get('total_count', len(roles))
            note = f"{len(roles)} из {total}" if payload.get('is_truncated') else f"{len(roles)}"
            response += f"  Роли ({note}):\n"
            for r in roles:
                purpose = f", {r['extension_purpose']}" if r.get('extension_purpose') else ""
                db = f"  [{r.get('db_name')}{purpose}]" if r.get('db_name') else ""
                response += f"    • {r['role_qualified_name']} — {r.get('right_name')}{db}\n"
            if payload.get('admin_roles_note'):
                response += f"  ⚠ {payload['admin_roles_note']}\n"
            response += "\n"
        return [TextContent(type="text", text=response)]

    response = f"Роли с правами на '{object_name}':\n\n"
    for project_name, project_data in results.items():
        response += f"📁 Проект: {project_name}\n"
        for db_name, payload in project_data.items():
            if payload.get('error') == 'not_found':
                response += f"  └─ {db_name}: объект не найден\n"
                continue
            if payload.get('ambiguous'):
                response += f"  └─ {db_name}:\n"
                response += _ambiguous_block(payload, indent="       ")
                continue
            target = payload.get('target', {})
            roles = payload.get('roles', [])
            total = payload.get('total_count', len(roles))
            note = f"{len(roles)} из {total}" if payload.get('is_truncated') else f"{len(roles)}"
            response += f"  └─ {db_name} — цель {target.get('type')}.{target.get('name')} — роли ({note}):\n"
            for r in roles:
                response += f"       • {r['role_qualified_name']} — {r.get('right_name')}\n"
            if payload.get('admin_roles_note'):
                response += f"       ⚠ {payload['admin_roles_note']}\n"
        response += "\n"
    return [TextContent(type="text", text=response)]
