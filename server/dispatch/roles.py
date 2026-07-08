import json

from mcp.types import TextContent


async def handle_find_role(tools, arguments: dict) -> list[TextContent]:
    results = tools.find_role(
        arguments["name"],
        arguments.get("project_filter"),
        arguments.get("extension_filter"),
    )
    if not results:
        return [TextContent(type="text", text=f"Роль '{arguments['name']}' не найдена")]
    return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]


async def handle_list_roles(tools, arguments: dict) -> list[TextContent]:
    results = tools.list_roles(
        arguments.get("project_filter"),
        arguments.get("extension_filter"),
        arguments.get("limit", 200),
    )
    return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]


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
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


async def handle_find_roles_for_object(tools, arguments: dict) -> list[TextContent]:
    results = tools.find_roles_for_object(
        arguments["object_name"],
        project_filter=arguments.get("project_filter"),
        extension_filter=arguments.get("extension_filter"),
        merge=arguments.get("merge", False),
        right_name=arguments.get("right_name"),
        rls=arguments.get("rls"),
        max_results=arguments.get("max_results", 200),
    )
    return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]
