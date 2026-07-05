from mcp.types import TextContent


async def handle_search_code(tools, arguments: dict) -> list[TextContent]:
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
                loc = f"{r['object_type']}.{r['object_name']}.{r['module_type']}"
                if r['module_type'] == 'CommandModule' and r.get('command_name'):
                    loc = f"{r['object_type']}.{r['object_name']}.CommandModule.{r['command_name']}"
                response += f"     • {loc}\n"
                response += f"       {r.get('procedure_display', '')}\n"
                id_line = f"       object_name={r['object_name']!r}, module_type={r['module_type']!r}"
                if r.get('form_name'):
                    id_line += f", form_name={r['form_name']!r}"
                if r.get('command_name'):
                    id_line += f", command_name={r['command_name']!r}"
                response += id_line + "\n"
                response += f"       {r['snippet']}\n"
        response += "\n"

    return [TextContent(type="text", text=response)]


async def handle_get_module_code(tools, arguments: dict) -> list[TextContent]:
    object_name = arguments["object_name"]
    module_type = arguments.get("module_type", "Module")
    form_name = arguments.get("form_name")
    command_name = arguments.get("command_name")
    project_filter = arguments.get("project_filter")
    extension_filter = arguments.get("extension_filter")

    results = tools.get_module_code(
        object_name, module_type, form_name, command_name, project_filter, extension_filter
    )

    if not results:
        return [TextContent(type="text", text=f"Модуль '{module_type}' объекта '{object_name}' не найден")]

    response = ""
    mod_label = module_type
    if module_type == 'CommandModule' and (command_name or '').strip():
        mod_label = f"CommandModule.{command_name.strip()}"
    elif module_type == 'CommandModule':
        mod_label = "CommandModule (общая команда)"

    for project_name, project_data in results.items():
        for db_name, code in project_data.items():
            response += f"📁 {project_name} / {db_name}\n"
            response += f"Код модуля {object_name}.{mod_label}:\n\n"
            response += code + "\n\n"

    return [TextContent(type="text", text=response)]


async def handle_get_module_procedures(tools, arguments: dict) -> list[TextContent]:
    object_name = arguments["object_name"]
    module_type = arguments.get("module_type", "Module")
    form_name = arguments.get("form_name")
    command_name = arguments.get("command_name")
    project_filter = arguments.get("project_filter")
    extension_filter = arguments.get("extension_filter")

    results = tools.get_module_procedures(
        object_name, module_type, form_name, command_name, project_filter, extension_filter
    )

    if not results:
        return [TextContent(type="text", text=f"Модуль '{module_type}' объекта '{object_name}' не найден")]

    response = ""
    mod_label = module_type
    if module_type == 'CommandModule' and (command_name or '').strip():
        mod_label = f"CommandModule.{command_name.strip()}"
    elif module_type == 'CommandModule':
        mod_label = "CommandModule (общая команда)"

    for project_name, project_data in results.items():
        for db_name, procedures in project_data.items():
            response += f"📁 {project_name} / {db_name}\n"
            response += f"Процедуры и функции в {object_name}.{mod_label}:\n\n"

            for proc in procedures:
                export_mark = " [Экспорт]" if proc['export'] else ""
                ctx = f" [{proc['execution_context']}]" if proc.get('execution_context') else ""
                sj_mark = " [регл. задание]" if proc.get('used_in_scheduled_job') else ""
                response += f"{proc['line']:4d}. {proc['type']} {proc['name']}({proc['params']}){export_mark}{ctx}{sj_mark}\n"
                if proc.get('comment'):
                    for comment_line in proc['comment'].split('\n'):
                        response += f"      {comment_line}\n"

            response += "\n"

    return [TextContent(type="text", text=response)]


async def handle_get_procedure_code(tools, arguments: dict) -> list[TextContent]:
    object_name = arguments["object_name"]
    procedure_name = arguments["procedure_name"]
    module_type = arguments.get("module_type", "Module")
    form_name = arguments.get("form_name")
    command_name = arguments.get("command_name")
    project_filter = arguments.get("project_filter")
    extension_filter = arguments.get("extension_filter")

    results = tools.get_procedure_code(
        object_name, procedure_name, module_type, form_name, command_name, project_filter, extension_filter
    )

    if not results:
        return [TextContent(type="text", text=f"Процедура '{procedure_name}' не найдена в модуле {object_name}.{module_type}")]

    response = ""
    mod_label = module_type
    if module_type == 'CommandModule' and (command_name or '').strip():
        mod_label = f"CommandModule.{command_name.strip()}"
    elif module_type == 'CommandModule':
        mod_label = "CommandModule (общая команда)"

    for project_name, project_data in results.items():
        for db_name, code in project_data.items():
            response += f"📁 {project_name} / {db_name}\n"
            response += f"Код процедуры {procedure_name} из {object_name}.{mod_label}:\n\n"
            response += code + "\n\n"

    return [TextContent(type="text", text=response)]
