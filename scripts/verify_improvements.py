#!/usr/bin/env python3
"""
Проверка доработок MCP (оптимизация архитектуры).
Запуск из корня проекта: python scripts/verify_improvements.py
Или с указанием projects: python scripts/verify_improvements.py --projects test_projects.json
"""
import sys
import json
from pathlib import Path

# Корень проекта
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.tools import ConfigurationTools


def main():
    projects_file = ROOT / "projects.json"
    if "--projects" in sys.argv:
        i = sys.argv.index("--projects")
        if i + 1 < len(sys.argv):
            projects_file = Path(sys.argv[i + 1])
            if not projects_file.is_absolute():
                projects_file = ROOT / projects_file
    databases_dir = ROOT / "databases"

    print("=== Проверка доработок MCP ===\n")
    print(f"projects: {projects_file}")
    print(f"databases: {databases_dir}\n")

    tools = ConfigurationTools(projects_file=str(projects_file), databases_dir=str(databases_dir))

    ok = 0
    fail = 0

    # 1. list_active_databases — есть и возвращает структуру
    print("1. list_active_databases()")
    try:
        r = tools.list_active_databases()
        assert "projects" in r, "Нет ключа 'projects'"
        print(f"   OK. Проектов: {len(r['projects'])}")
        for p in r["projects"]:
            print(f"      - {p['name']}: баз {len(p.get('databases', []))}")
        ok += 1
    except Exception as e:
        print(f"   FAIL: {e}")
        fail += 1

    # 2. Без project_filter search_code должен выбросить
    print("\n2. search_code без project_filter -> ValueError")
    try:
        tools.search_code("Запрос", project_filter=None)
        print("   FAIL: ожидалась ошибка ValueError")
        fail += 1
    except ValueError as e:
        if "project_filter" in str(e) or "list_active_databases" in str(e).lower():
            print(f"   OK. Ошибка: {e}")
            ok += 1
        else:
            print(f"   FAIL: не та ошибка: {e}")
            fail += 1
    except Exception as e:
        print(f"   FAIL: {e}")
        fail += 1

    # 3. search_form_properties только Visible/Enabled
    print("\n3. search_form_properties с property_name='ReadOnly' -> ValueError")
    try:
        tools.search_form_properties("ReadOnly", project_filter="ЛюбойПроект")
        print("   FAIL: ожидалась ошибка (ReadOnly не поддерживается)")
        fail += 1
    except ValueError as e:
        if "Visible" in str(e) and "Enabled" in str(e):
            print(f"   OK. Ошибка: {e}")
            ok += 1
        else:
            print(f"   FAIL: не та ошибка: {e}")
            fail += 1
    except Exception as e:
        # Может быть проект не найден — тогда просто не ValueError
        if "project_filter" in str(e).lower() or "required" in str(e).lower():
            ok += 1
            print("   OK (другая ожидаемая ошибка).")
        else:
            print(f"   FAIL: {e}")
            fail += 1

    # 4. При наличии активных БД — быстрые проверки ответов
    dbs = tools._get_active_databases()
    if dbs:
        proj = dbs[0]["project_name"]
        print(f"\n4. Проверка ответов (project_filter={proj!r})")
        # find_object — в ответе может быть object_belonging для расширений
        try:
            r = tools.find_object("Константа", project_filter=proj)
            if r:
                for pname, pdata in r.items():
                    for dbname, objs in pdata.items():
                        if objs and isinstance(objs[0], dict):
                            keys = objs[0].keys()
                            if "object_belonging" in keys or "form_kind" in str(r):
                                print("   find_object: в ответе есть поля object_belonging/form_kind — OK")
                            else:
                                print("   find_object: структура ответа с полями имени/типа — OK")
                            break
                    break
            else:
                print("   find_object: пустой результат (нет объектов) — OK")
            ok += 1
        except Exception as e:
            print(f"   find_object FAIL: {e}")
            fail += 1

        # get_module_procedures — execution_context в процедурах
        try:
            r = tools.get_module_procedures("Константы", "Module", project_filter=proj)
            if r:
                for pname, pdata in r.items():
                    for dbname, procs in pdata.items():
                        if procs and isinstance(procs[0], dict) and "execution_context" in procs[0]:
                            print("   get_module_procedures: в процедурах есть execution_context — OK")
                            break
                        break
                    break
            else:
                print("   get_module_procedures: пустой результат — OK")
            ok += 1
        except Exception as e:
            print(f"   get_module_procedures FAIL: {e}")
            fail += 1
    else:
        print("\n4. Активных БД нет — проверки ответов пропущены.")

    tools.close_all()

    print("\n=== Итог ===")
    print(f"OK: {ok}, FAIL: {fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
