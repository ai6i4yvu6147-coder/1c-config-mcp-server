from .common import handle_active_databases
from .code import (
    handle_search_code,
    handle_get_module_code,
    handle_get_module_procedures,
    handle_get_procedure_code,
)
from .objects import (
    handle_find_object,
    handle_list_objects,
    handle_get_object_structure,
    handle_get_functional_options,
    handle_find_attribute,
)
from .forms import (
    handle_find_form,
    handle_find_form_element,
    handle_get_form_structure,
    handle_get_form_attribute,
    handle_get_form_item,
    handle_search_form_properties,
)
from .relations import handle_find_referencing_objects
from .roles import (
    handle_find_role,
    handle_list_roles,
    handle_get_role_rights,
    handle_find_roles_for_object,
)
from .dcs import handle_get_dcs_schema

# Tool name -> async handler(tools, arguments) -> list[TextContent].
# active_databases is dispatched separately in server.py (outside the ValueError try/except).
HANDLERS = {
    "search_code": handle_search_code,
    "find_object": handle_find_object,
    "list_objects": handle_list_objects,
    "get_module_code": handle_get_module_code,
    "get_module_procedures": handle_get_module_procedures,
    "get_procedure_code": handle_get_procedure_code,
    "find_form": handle_find_form,
    "find_form_element": handle_find_form_element,
    "get_form_structure": handle_get_form_structure,
    "get_form_attribute": handle_get_form_attribute,
    "get_form_item": handle_get_form_item,
    "search_form_properties": handle_search_form_properties,
    "get_object_structure": handle_get_object_structure,
    "find_referencing_objects": handle_find_referencing_objects,
    "get_functional_options": handle_get_functional_options,
    "find_attribute": handle_find_attribute,
    "find_role": handle_find_role,
    "list_roles": handle_list_roles,
    "get_role_rights": handle_get_role_rights,
    "find_roles_for_object": handle_find_roles_for_object,
    "get_dcs_schema": handle_get_dcs_schema,
}

__all__ = ['HANDLERS', 'handle_active_databases']
