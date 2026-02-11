import json
from pathlib import Path
import uuid
import sys
from typing import List, Dict, Optional


class ProjectManager:
    """Управление проектами конфигураций"""
    
    def __init__(self, projects_file=None, databases_dir=None):
        """
        Args:
            projects_file: Путь к projects.json (если None - автоопределение)
            databases_dir: Путь к папке databases (если None - автоопределение)
        """
        # Автоопределение путей если не указаны
        if projects_file is None or databases_dir is None:
            if getattr(sys, 'frozen', False):
                # Portable: exe в подпапке, поднимаемся на уровень выше
                app_path = Path(sys.executable).parent
                root = app_path.parent
            else:
                # Разработка: текущая папка - это корень
                root = Path.cwd()
            
            if projects_file is None:
                projects_file = root / "projects.json"
            if databases_dir is None:
                databases_dir = root / "databases"
        
        self.projects_file = Path(projects_file)
        self.databases_dir = Path(databases_dir)
        self.databases_dir.mkdir(exist_ok=True)
        self.projects = self._load_projects()
    
    def _load_projects(self) -> Dict:
        """Загрузка проектов из JSON"""
        if not self.projects_file.exists():
            return {"projects": []}
        
        try:
            with open(self.projects_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"projects": []}
    
    def _save_projects(self):
        """Сохранение проектов в JSON"""
        with open(self.projects_file, 'w', encoding='utf-8') as f:
            json.dump(self.projects, f, indent=2, ensure_ascii=False)
    
    def create_project(self, name: str) -> str:
        """
        Создать новый проект
        
        Returns:
            project_id
        """
        project_id = str(uuid.uuid4())
        
        project = {
            "id": project_id,
            "name": name,
            "active": False,
            "databases": []
        }
        
        self.projects["projects"].append(project)
        self._save_projects()
        
        return project_id
    
    def add_database(self, project_id: str, name: str, db_type: str, db_file: str) -> str:
        """
        Добавить базу данных в проект
        
        Args:
            project_id: ID проекта
            name: Название базы (например, "Бухгалтерия 3.0")
            db_type: "base" или "extension"
            db_file: Имя файла БД (например, "ТГ_Бухгалтерия.db")
        
        Returns:
            database_id
        """
        project = self._find_project(project_id)
        if not project:
            raise ValueError(f"Проект {project_id} не найден")
        
        db_id = str(uuid.uuid4())
        
        database = {
            "id": db_id,
            "name": name,
            "type": db_type,
            "db_file": db_file
        }
        
        project["databases"].append(database)
        self._save_projects()
        
        return db_id
    
    def set_project_active(self, project_id: str, active: bool):
        """Активировать/деактивировать проект"""
        project = self._find_project(project_id)
        if project:
            project["active"] = active
            self._save_projects()
    
    def delete_project(self, project_id: str):
        """Удалить проект"""
        self.projects["projects"] = [
            p for p in self.projects["projects"] 
            if p["id"] != project_id
        ]
        self._save_projects()
    
    def delete_database(self, project_id: str, db_id: str):
        """Удалить базу данных из проекта"""
        project = self._find_project(project_id)
        if project:
            project["databases"] = [
                db for db in project["databases"] 
                if db["id"] != db_id
            ]
            self._save_projects()
    
    def update_database_file(self, project_id: str, db_id: str, new_db_file: str):
        """Обновить файл базы данных"""
        project = self._find_project(project_id)
        if project:
            db = self._find_database(project, db_id)
            if db:
                db["db_file"] = new_db_file
                self._save_projects()

    def update_source_xml(self, project_id: str, db_id: str, source_xml: str):
        """Обновить путь к исходному XML"""
        project = self._find_project(project_id)
        if project:
            db = self._find_database(project, db_id)
            if db:
                db["source_xml"] = source_xml
                self._save_projects()

    def get_source_xml(self, project_id: str, db_id: str) -> Optional[str]:
        """Получить сохранённый путь к XML"""
        project = self._find_project(project_id)
        if project:
            db = self._find_database(project, db_id)
            if db:
                return db.get("source_xml")
        return None
    
    def get_all_projects(self) -> List[Dict]:
        """Получить все проекты"""
        return self.projects["projects"]
    
    def get_active_projects(self) -> List[Dict]:
        """Получить активные проекты"""
        return [p for p in self.projects["projects"] if p["active"]]
    
    def get_project(self, project_id: str) -> Optional[Dict]:
        """Получить проект по ID"""
        return self._find_project(project_id)
    
    def get_active_databases(self) -> List[Dict]:
        """
        Получить все БД из активных проектов
        
        Returns:
            [{"project_name": "ТГ", "db_name": "Бухгалтерия", "db_file": "...", ...}, ...]
        """
        result = []
        for project in self.get_active_projects():
            for db in project["databases"]:
                result.append({
                    "project_id": project["id"],
                    "project_name": project["name"],
                    "db_id": db["id"],
                    "db_name": db["name"],
                    "db_type": db["type"],
                    "db_file": db["db_file"],
                    "db_path": str(self.databases_dir / db["db_file"])
                })
        return result
    
    def _find_project(self, project_id: str) -> Optional[Dict]:
        """Найти проект по ID"""
        for project in self.projects["projects"]:
            if project["id"] == project_id:
                return project
        return None
    
    def _find_database(self, project: Dict, db_id: str) -> Optional[Dict]:
        """Найти базу в проекте"""
        for db in project["databases"]:
            if db["id"] == db_id:
                return db
        return None


# Тестовая функция
def test_project_manager():
    """Тест работы ProjectManager"""
    pm = ProjectManager("test_projects.json", "test_databases")
    
    # Создаем проект
    proj_id = pm.create_project("Тестовый проект")
    print(f"Создан проект: {proj_id}")
    
    # Добавляем базу
    db_id = pm.add_database(proj_id, "Бухгалтерия 3.0", "base", "test_buh.db")
    print(f"Добавлена база: {db_id}")
    
    # Активируем
    pm.set_project_active(proj_id, True)
    
    # Проверяем
    active = pm.get_active_databases()
    print(f"Активные БД: {active}")
    
    print("Тест пройден!")


if __name__ == "__main__":
    test_project_manager()