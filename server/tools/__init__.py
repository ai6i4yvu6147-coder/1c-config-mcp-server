from pathlib import Path
import sys

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .base import BaseTools
from .objects import ObjectsMixin
from .code import CodeMixin, MAX_MODULES_SEARCH_CODE
from .forms import FormsMixin
from .relations import RelationsMixin
from .roles import RolesMixin
from .formatting import format_business_process_route_text


class ConfigurationTools(
    ObjectsMixin,
    CodeMixin,
    FormsMixin,
    RelationsMixin,
    RolesMixin,
    BaseTools,
):
    """Инструменты для работы с конфигурациями 1С через несколько проектов"""


__all__ = ['ConfigurationTools', 'format_business_process_route_text', 'MAX_MODULES_SEARCH_CODE']
