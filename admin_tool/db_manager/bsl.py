import re


def _strip_bsl_comment_line(line):
    """Снимает префикс // с строки документирующего комментария BSL."""
    stripped = line.strip()
    if stripped.startswith('//'):
        text = stripped[2:]
        if text.startswith(' '):
            text = text[1:]
        return text
    return stripped


def _paren_depth(line):
    """Баланс круглых скобок в строке без её хвостового //-комментария.

    Комментарий срезается, чтобы `// (см. ниже` не ломал поиск конца многострочной
    сигнатуры; по той же причине баланс, а не «есть ли в строке )» — иначе объявление
    вида `Процедура Х(П = Новый Массив(),` не подхватывал ни один из шаблонов.
    """
    idx = line.find('//')
    code_part = line if idx < 0 else line[:idx]
    return code_part.count('(') - code_part.count(')')


def _parse_module_procedures(code):
    """
    Парсит код модуля 1С, возвращает список процедур/функций для таблицы module_procedures.
    Каждый элемент: name, proc_type, start_line, end_line, params, is_export, comment,
    execution_context, extension_call_type.
    start_line — первая строка для среза (включая //-комментарии и &-директивы над процедурой); 1-based.
    comment — многострочный текст документирующих //-строк над процедурой (без префикса //).
    execution_context и extension_call_type определяются по &-строкам в префиксе.
    Поддерживаются многострочные объявления (закрывающая скобка ) и Экспорт на следующих строках).
    """
    lines = code.split('\n')
    # Хвост строки объявления: 1С допускает и точку с запятой после сигнатуры, и //-комментарий
    # (в общих модулях ЕРП — 350 объявлений с комментарием и 205 с `;`). Требование `$` сразу
    # после `)`/`Экспорт` выбрасывало такую процедуру из индекса целиком: основной шаблон её
    # не брал, а фолбэк многострочной сигнатуры отсеивал строку по наличию `)`.
    pattern = re.compile(
        r'^\s*(Процедура|Функция)\s+([А-Яа-яA-Za-z0-9_]+)\s*\((.*?)\)\s*(Экспорт)?\s*;?\s*(?://.*)?$',
        re.IGNORECASE
    )
    # Начало объявления без требования закрывающей ) на той же строке (для многострочных сигнатур)
    start_only_pattern = re.compile(
        r'^\s*(Процедура|Функция)\s+([А-Яа-яA-Za-z0-9_]+)\s*\(',
        re.IGNORECASE
    )
    directive_pattern = re.compile(
        r'^\s*&(НаКлиентеНаСервереБезКонтекста|НаСервереБезКонтекста|НаКлиенте|НаСервере|'
        r'AtClientAtServerNoContext|AtServerNoContext|AtClient|AtServer)\s*$',
        re.IGNORECASE
    )
    # Аннотации расширений: с параметром &Перед("ИмяПроцедуры") или без (форма модуля)
    extension_patterns = [
        (re.compile(r'^\s*&ИзменениеИКонтроль\s*(\([^)]*\))?\s*$', re.IGNORECASE), 'ChangeAndControl'),
        (re.compile(r'^\s*&Вместо\s*(\([^)]*\))?\s*$', re.IGNORECASE), 'Instead'),
        (re.compile(r'^\s*&После\s*(\([^)]*\))?\s*$', re.IGNORECASE), 'After'),
        (re.compile(r'^\s*&Перед\s*(\([^)]*\))?\s*$', re.IGNORECASE), 'Before'),
    ]
    # Trailing // comments after КонецФункции/КонецПроцедуры are common in 1C codebases and must not
    # prevent boundary detection (e.g. "КонецФункции // ИмяФункции()").
    # Начало строки — не единственная позиция закрывающего ключевого слова: в живом коде оно
    # встречается приклеенным к предыдущему оператору («КонецЦикла;\tКонецПроцедуры»,
    # «Возврат Х;КонецФункции» — 34 места в ЕРП). Пропущенная граница стоит дорого вдвойне:
    # предыдущая процедура получает end_line следующей (get_procedure_code склеивает две), а
    # следующая теряется целиком. Разрешаем позицию после `;` — то есть после конца оператора,
    # но не внутри строки или комментария.
    end_pattern = re.compile(
        r'(?:^|;)\s*(КонецФункции|КонецПроцедуры|EndFunction|EndProcedure)\b(?:\s*//.*)?\s*$',
        re.IGNORECASE,
    )

    def directive_to_context(line):
        """Возвращает директиву как есть (без нормализации)."""
        if not line:
            return None
        stripped = line.strip()
        m = re.match(r'^&([А-Яа-яA-Za-z]+)', stripped)
        if m and directive_pattern.match(stripped):
            return m.group(1)
        return None

    def line_to_extension_call_type(stripped):
        for pat, value in extension_patterns:
            if pat.match(stripped):
                return value
        return None

    def collect_procedure_prefix_above(proc_line_index):
        """Собирает //-комментарии и &-директивы непосредственно над объявлением процедуры."""
        indices = []
        j = proc_line_index - 1
        while j >= 0:
            stripped = lines[j].strip()
            if stripped.startswith('//'):
                indices.append(j)
                j -= 1
            elif stripped.startswith('&') and len(stripped) > 1:
                indices.append(j)
                j -= 1
            elif stripped == '':
                break
            else:
                break
        indices.reverse()
        comment_indices = [idx for idx in indices if lines[idx].strip().startswith('//')]
        directive_indices = [idx for idx in indices if lines[idx].strip().startswith('&')]
        return comment_indices, directive_indices, indices

    def prefix_info(proc_line_index, default_start_line):
        comment_indices, directive_indices, all_indices = collect_procedure_prefix_above(proc_line_index)
        execution_context = None
        extension_call_type = None
        for idx in reversed(directive_indices):
            stripped = lines[idx].strip()
            if execution_context is None:
                execution_context = directive_to_context(stripped)
            if extension_call_type is None:
                extension_call_type = line_to_extension_call_type(stripped)
        start_line = (all_indices[0] + 1) if all_indices else default_start_line
        comment = (
            '\n'.join(_strip_bsl_comment_line(lines[idx]) for idx in comment_indices)
            if comment_indices else ''
        )
        return start_line, comment, execution_context, extension_call_type

    result = []
    i = 0
    while i < len(lines):
        match = pattern.match(lines[i])
        if match:
            line_num = i + 1
            proc_type = match.group(1)
            name = match.group(2)
            params = (match.group(3) or '').strip() or '(без параметров)'
            is_export = bool(match.group(4))
            start_line, comment, execution_context, extension_call_type = prefix_info(i, line_num)
            end_line = None
            for j in range(i + 1, len(lines)):
                if end_pattern.search(lines[j]):
                    end_line = j + 1
                    break
            result.append({
                'name': name,
                'proc_type': proc_type,
                'start_line': start_line,
                'end_line': end_line,
                'params': params,
                'is_export': 1 if is_export else 0,
                'comment': comment,
                'execution_context': execution_context,
                'extension_call_type': extension_call_type,
            })
            if end_line is not None:
                i = end_line
            else:
                i = len(lines)
        else:
            start_match = start_only_pattern.match(lines[i])
            depth = _paren_depth(lines[i]) if start_match else 0
            if start_match and depth > 0:
                # Многострочное объявление: читаем до строки, закрывающей сигнатуру
                proc_type = start_match.group(1)
                name = start_match.group(2)
                j = i
                while j + 1 < len(lines) and depth > 0:
                    j += 1
                    depth += _paren_depth(lines[j])
                if depth > 0:
                    i += 1
                    continue
                closing_line = lines[j]
                is_export = bool(re.search(r'\bЭкспорт\b', closing_line, re.IGNORECASE))
                params = '(многострочные)'
                start_line, comment, execution_context, extension_call_type = prefix_info(i, i + 1)
                end_line = None
                for k in range(j + 1, len(lines)):
                    if end_pattern.search(lines[k]):
                        end_line = k + 1
                        break
                result.append({
                    'name': name,
                    'proc_type': proc_type,
                    'start_line': start_line,
                    'end_line': end_line,
                    'params': params,
                    'is_export': 1 if is_export else 0,
                    'comment': comment,
                    'execution_context': execution_context,
                    'extension_call_type': extension_call_type,
                })
                if end_line is not None:
                    i = end_line
                else:
                    i = len(lines)
            else:
                i += 1
    return result
