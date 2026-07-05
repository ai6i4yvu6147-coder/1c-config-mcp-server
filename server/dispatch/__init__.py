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
    handle_search_form_properties,
)
from .relations import handle_find_referencing_objects

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
    "search_form_properties": handle_search_form_properties,
    "get_object_structure": handle_get_object_structure,
    "find_referencing_objects": handle_find_referencing_objects,
    "get_functional_options": handle_get_functional_options,
    "find_attribute": handle_find_attribute,
}

__all__ = ['HANDLERS', 'handle_active_databases']
