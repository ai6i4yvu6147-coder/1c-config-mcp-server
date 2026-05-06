import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import sys
from pathlib import Path
import threading

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from admin_tool.db_manager import DatabaseManager
from shared.project_manager import ProjectManager
from shared.xml_parser import get_configuration_name, get_configuration_type
from shared.indexer_version import INDEXER_VERSION


class AdminAppV2:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Администратор баз 1С-MCP v2 — формат индекса v{INDEXER_VERSION}")
        self.root.geometry("1000x600")
        
        self.db_dir = Path("databases")
        self.db_dir.mkdir(exist_ok=True)
        
        self.pm = ProjectManager()
        
        self._create_widgets()
        self._load_projects()
    
    def _create_widgets(self):
        """Создает элементы интерфейса"""
        
        # Заголовок
        title_label = tk.Label(
            self.root, 
            text="Администратор баз 1С-MCP v2", 
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=20)
        
        # Дерево проектов
        tree_frame = tk.Frame(self.root)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        tk.Label(tree_frame, text="Проекты и базы данных:", font=("Arial", 12)).pack(anchor=tk.W)
        
        # Scrollbar
        scrollbar = tk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # TreeView
        self.tree = ttk.Treeview(tree_frame, yscrollcommand=scrollbar.set, height=15)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.tree.yview)
        self.tree.tag_configure("outdated", foreground="#b00000")
        self.tree.tag_configure("newer_than_app", foreground="#a06000")
        
        # Колонки
        self.tree["columns"] = ("type", "file", "status")
        self.tree.column("#0", width=320, minwidth=200)
        self.tree.column("type", width=90, minwidth=70)
        self.tree.column("file", width=240, minwidth=120)
        self.tree.column("status", width=280, minwidth=180)
        
        self.tree.heading("#0", text="Название", anchor=tk.W)
        self.tree.heading("type", text="Тип", anchor=tk.W)
        self.tree.heading("file", text="Файл БД", anchor=tk.W)
        self.tree.heading("status", text="Состояние", anchor=tk.W)
        
        # Привязка двойного клика для активации
        self.tree.bind("<Double-1>", self._on_double_click)
        
        # Кнопки управления проектами
        project_buttons = tk.Frame(self.root)
        project_buttons.pack(pady=5)
        
        tk.Button(
            project_buttons,
            text="➕ Создать проект",
            command=self.create_project,
            width=20,
            bg="#4CAF50",
            fg="white"
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            project_buttons,
            text="➕ Добавить базу/расширение",
            command=self.add_database,
            width=25,
            bg="#2196F3",
            fg="white"
        ).pack(side=tk.LEFT, padx=5)
        
        # Кнопки действий
        action_buttons = tk.Frame(self.root)
        action_buttons.pack(pady=5)
        
        tk.Button(
            action_buttons,
            text="🔄 Обновить базу",
            command=self.update_database,
            width=20
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            action_buttons,
            text="📊 Статистика",
            command=self.show_statistics,
            width=20
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            action_buttons,
            text="🗑 Удалить",
            command=self.delete_item,
            width=20,
            bg="#f44336",
            fg="white"
        ).pack(side=tk.LEFT, padx=5)
    
    def _load_projects(self):
        """Загружает проекты и базы в дерево"""
        # Очищаем дерево
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Загружаем проекты
        projects = self.pm.get_all_projects()
        
        if not projects:
            self.tree.insert("", "end", text="(нет проектов)", values=("", "", ""))
            return
        
        for project in projects:
            # Добавляем проект
            active_mark = "☑" if project["active"] else "☐"
            project_text = f"{active_mark} {project['name']}"
            
            project_item = self.tree.insert(
                "", "end", 
                text=project_text,
                values=("Проект", "", ""),
                tags=("project", project["id"])
            )
            
            # Добавляем базы данных
            for db in project["databases"]:
                db_icon = "📁" if db["type"] == "base" else "📦"
                db_text = f"{db_icon} {db['name']}"
                db_path = self.db_dir / db["db_file"]
                ver = DatabaseManager.read_db_version(db_path)
                if ver is None:
                    status = "Нет файла"
                    db_tags = ("database", project["id"], db["id"], "outdated")
                elif ver == 0:
                    status = "Устарела (без версии) → пересобрать"
                    db_tags = ("database", project["id"], db["id"], "outdated")
                elif ver < INDEXER_VERSION:
                    status = f"Устарела (v{ver} < v{INDEXER_VERSION})"
                    db_tags = ("database", project["id"], db["id"], "outdated")
                elif ver == INDEXER_VERSION:
                    status = f"OK v{INDEXER_VERSION}"
                    db_tags = ("database", project["id"], db["id"])
                else:
                    status = f"Новее ПО (v{ver} > v{INDEXER_VERSION}) → обновите сервер"
                    db_tags = ("database", project["id"], db["id"], "newer_than_app")
                
                self.tree.insert(
                    project_item, "end",
                    text=db_text,
                    values=(db["type"], db["db_file"], status),
                    tags=db_tags
                )
    
    def _on_double_click(self, event):
        """Обработка двойного клика - переключение активности проекта"""
        item = self.tree.selection()[0]
        tags = self.tree.item(item, "tags")
        
        if tags and tags[0] == "project":
            project_id = tags[1]
            project = self.pm.get_project(project_id)
            
            # Переключаем активность
            new_active = not project["active"]
            self.pm.set_project_active(project_id, new_active)
            
            # Обновляем отображение
            self._load_projects()
    
    def create_project(self):
        """Создание нового проекта"""
        CreateProjectWindow(self.root, self)
    
    def add_database(self):
        """Добавление базы в проект"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите проект")
            return
        
        item = selection[0]
        tags = self.tree.item(item, "tags")
        
        # Определяем project_id
        if tags[0] == "project":
            project_id = tags[1]
        elif tags[0] == "database":
            project_id = tags[1]
        else:
            messagebox.showwarning("Предупреждение", "Выберите проект или базу в проекте")
            return
        
        project = self.pm.get_project(project_id)
        AddDatabaseWindow(self.root, self, project)
    
    def update_database(self):
        """Обновление базы данных"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите базу данных")
            return
        
        item = selection[0]
        tags = self.tree.item(item, "tags")
        
        if not tags or tags[0] != "database":
            messagebox.showwarning("Предупреждение", "Выберите базу данных (не проект)")
            return
        
        project_id = tags[1]
        db_id = tags[2]
        
        project = self.pm.get_project(project_id)
        db = next((d for d in project["databases"] if d["id"] == db_id), None)
        
        if not db:
            return
        
        # Проверяем, есть ли сохранённый путь
        source_xml = self.pm.get_source_xml(project_id, db_id)
        
        if source_xml and Path(source_xml).exists():
            # Есть сохранённый путь - показываем диалог выбора
            QuickUpdateDialog(self.root, self, project, db, source_xml)
        else:
            # Нет пути или файл не существует - открываем окно выбора
            if source_xml:
                messagebox.showinfo("Информация", 
                    f"Сохранённый файл не найден:\n{source_xml}\n\nВыберите новый файл.")
            UpdateDatabaseWindow(self.root, self, project, db)
    
    def show_statistics(self):
        """Показать статистику базы"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите базу данных")
            return
        
        item = selection[0]
        tags = self.tree.item(item, "tags")
        
        if not tags or tags[0] != "database":
            messagebox.showwarning("Предупреждение", "Выберите базу данных")
            return
        
        project_id = tags[1]
        db_id = tags[2]
        
        project = self.pm.get_project(project_id)
        db = next((d for d in project["databases"] if d["id"] == db_id), None)
        
        if not db:
            return
        
        db_path = self.db_dir / db["db_file"]
        
        if not db_path.exists():
            messagebox.showerror("Ошибка", f"Файл базы не найден: {db['db_file']}")
            return
        
        try:
            db_manager = DatabaseManager(db_path)
            db_manager.connect()
            stats = db_manager.get_statistics()
            db_manager.close()
            
            msg = f"База данных: {db['name']}\n"
            msg += f"Проект: {project['name']}\n"
            msg += f"Тип: {'Основная' if db['type'] == 'base' else 'Расширение'}\n\n"
            msg += f"Всего объектов: {stats['total_objects']}\n"
            msg += f"Всего модулей: {stats['total_modules']}\n\n"
            msg += "По типам:\n"
            for obj_type, count in sorted(stats['by_type'].items()):
                msg += f"  {obj_type}: {count}\n"
            
            messagebox.showinfo("Статистика", msg)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать БД:\n{str(e)}")
    
    def delete_item(self):
        """Удаление проекта или базы"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите проект или базу")
            return
        
        item = selection[0]
        tags = self.tree.item(item, "tags")
        
        if not tags:
            return
        
        if tags[0] == "project":
            project_id = tags[1]
            project = self.pm.get_project(project_id)
            
            if not messagebox.askyesno("Подтверждение", 
                f"Удалить проект '{project['name']}' и все его базы?"):
                return
            
            # Удаляем файлы баз
            for db in project["databases"]:
                db_path = self.db_dir / db["db_file"]
                if db_path.exists():
                    db_path.unlink()
            
            self.pm.delete_project(project_id)
            self._load_projects()
            messagebox.showinfo("Успех", "Проект удален")
        
        elif tags[0] == "database":
            project_id = tags[1]
            db_id = tags[2]
            
            project = self.pm.get_project(project_id)
            db = next((d for d in project["databases"] if d["id"] == db_id), None)
            
            if not db:
                return
            
            if not messagebox.askyesno("Подтверждение", 
                f"Удалить базу '{db['name']}'?"):
                return
            
            # Удаляем файл
            db_path = self.db_dir / db["db_file"]
            if db_path.exists():
                db_path.unlink()
            
            self.pm.delete_database(project_id, db_id)
            self._load_projects()
            messagebox.showinfo("Успех", "База данных удалена")


class CreateProjectWindow:
    """Окно создания проекта"""
    
    def __init__(self, parent, main_app):
        self.main_app = main_app
        self.window = tk.Toplevel(parent)
        self.window.title("Создание проекта")
        self.window.geometry("400x150")
        self.window.grab_set()
        
        tk.Label(self.window, text="Название проекта:", font=("Arial", 10)).pack(anchor=tk.W, padx=20, pady=(20, 5))
        self.name_entry = tk.Entry(self.window, width=40)
        self.name_entry.pack(padx=20, pady=5)
        self.name_entry.focus()
        
        button_frame = tk.Frame(self.window)
        button_frame.pack(pady=20)
        
        tk.Button(button_frame, text="Создать", command=self.create, width=15, bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Отмена", command=self.window.destroy, width=15).pack(side=tk.LEFT, padx=5)
    
    def create(self):
        name = self.name_entry.get().strip()
        
        if not name:
            messagebox.showwarning("Предупреждение", "Введите название проекта")
            return
        
        try:
            self.main_app.pm.create_project(name)
            self.main_app._load_projects()
            messagebox.showinfo("Успех", f"Проект '{name}' создан")
            self.window.destroy()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать проект:\n{str(e)}")


class AddDatabaseWindow:
    """Окно добавления базы/расширения"""
    
    def __init__(self, parent, main_app, project):
        self.main_app = main_app
        self.project = project
        self.window = tk.Toplevel(parent)
        self.window.title("Добавление базы данных")
        self.window.geometry("550x350")
        self.window.grab_set()
        
        self.xml_path = None
        
        self._create_widgets()
    
    def _create_widgets(self):
        tk.Label(self.window, text=f"Проект: {self.project['name']}", font=("Arial", 12, "bold")).pack(pady=10)
        
        tk.Label(self.window, text="Название базы/расширения:", font=("Arial", 10)).pack(anchor=tk.W, padx=20, pady=(10, 5))
        self.name_entry = tk.Entry(self.window, width=50)
        self.name_entry.pack(padx=20, pady=5)
        
        tk.Label(self.window, text="Тип:", font=("Arial", 10)).pack(anchor=tk.W, padx=20, pady=(10, 5))
        self.type_var = tk.StringVar(value="base")
        type_frame = tk.Frame(self.window)
        type_frame.pack(padx=20, pady=5, anchor=tk.W)
        tk.Radiobutton(type_frame, text="Основная конфигурация", variable=self.type_var, value="base").pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(type_frame, text="Расширение", variable=self.type_var, value="extension").pack(side=tk.LEFT, padx=10)
        
        tk.Label(self.window, text="XML файл конфигурации:", font=("Arial", 10)).pack(anchor=tk.W, padx=20, pady=(10, 5))
        xml_frame = tk.Frame(self.window)
        xml_frame.pack(padx=20, pady=5, fill=tk.X)
        
        self.xml_label = tk.Label(xml_frame, text="(не выбран)", fg="gray")
        self.xml_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Button(xml_frame, text="Обзор...", command=self.browse_xml, width=10).pack(side=tk.RIGHT)
        
        button_frame = tk.Frame(self.window)
        button_frame.pack(pady=20)
        
        self.create_button = tk.Button(button_frame, text="Добавить", command=self.add, width=15, bg="#4CAF50", fg="white")
        self.create_button.pack(side=tk.LEFT, padx=5)
        
        tk.Button(button_frame, text="Отмена", command=self.window.destroy, width=15).pack(side=tk.LEFT, padx=5)
    
    def browse_xml(self):
        filename = filedialog.askopenfilename(
            title="Выберите Configuration.xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
        )
        
        if filename:
            self.xml_path = Path(filename)
            self.xml_label.config(text=self.xml_path.name, fg="black")
            name = get_configuration_name(self.xml_path)
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, name or self.xml_path.parent.name)
            cfg_type = get_configuration_type(self.xml_path)
            self.type_var.set(cfg_type)
    
    def add(self):
        name = self.name_entry.get().strip()
        db_type = self.type_var.get()
        
        if not name:
            messagebox.showwarning("Предупреждение", "Введите название")
            return
        
        if not self.xml_path:
            messagebox.showwarning("Предупреждение", "Выберите XML файл")
            return
        
        # Генерируем имя файла БД
        safe_project_name = "".join(c for c in self.project['name'] if c.isalnum() or c in (' ', '_')).strip()
        safe_db_name = "".join(c for c in name if c.isalnum() or c in (' ', '_')).strip()
        db_filename = f"{safe_project_name}_{safe_db_name}.db".replace(" ", "_")
        
        db_path = self.main_app.db_dir / db_filename
        
        if db_path.exists():
            if not messagebox.askyesno("Подтверждение", f"База '{db_filename}' уже существует. Перезаписать?"):
                return
            db_path.unlink()
        
        self.create_button.config(state=tk.DISABLED)
        
        thread = threading.Thread(target=self._create_database_thread, args=(name, db_type, db_filename, db_path))
        thread.start()
    
    def _create_database_thread(self, name, db_type, db_filename, db_path):
        try:
            db_manager = DatabaseManager(db_path)
            db_manager.connect()
            
            success = db_manager.create_database(str(self.xml_path))
            db_manager.close()
            
            if success:
                db_id = self.main_app.pm.add_database(self.project["id"], name, db_type, db_filename)
                self.main_app.pm.update_source_xml(self.project["id"], db_id, str(self.xml_path))
                self.main_app._load_projects()
                
                messagebox.showinfo("Успех", "База данных создана успешно!")
                self.window.destroy()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать БД:\n{str(e)}")
            self.create_button.config(state=tk.NORMAL)

class QuickUpdateDialog:
    """Диалог быстрого обновления"""
    
    def __init__(self, parent, main_app, project, database, source_xml):
        self.main_app = main_app
        self.project = project
        self.database = database
        self.source_xml = source_xml
        
        self.window = tk.Toplevel(parent)
        self.window.title("Обновить базу данных")
        self.window.geometry("600x250")
        self.window.grab_set()
        
        self._create_widgets()
    
    def _create_widgets(self):
        tk.Label(
            self.window, 
            text=f"База: {self.database['name']}", 
            font=("Arial", 12, "bold")
        ).pack(pady=10)
        
        tk.Label(
            self.window,
            text="Обновить из сохранённого источника?",
            font=("Arial", 10)
        ).pack(pady=5)
        
        # Путь к файлу
        path_frame = tk.Frame(self.window, bg="#f0f0f0", relief=tk.SUNKEN, borderwidth=1)
        path_frame.pack(padx=20, pady=10, fill=tk.X)
        
        tk.Label(
            path_frame,
            text=self.source_xml,
            font=("Arial", 9),
            bg="#f0f0f0",
            anchor=tk.W,
            wraplength=550
        ).pack(padx=10, pady=10)
        
        # Проверка существования
        if Path(self.source_xml).exists():
            status_text = "✓ Файл найден"
            status_color = "green"
            quick_enabled = True
        else:
            status_text = "✗ Файл не найден"
            status_color = "red"
            quick_enabled = False
        
        tk.Label(
            self.window,
            text=status_text,
            font=("Arial", 9),
            fg=status_color
        ).pack(pady=5)
        
        # Кнопки
        button_frame = tk.Frame(self.window)
        button_frame.pack(pady=20)
        
        self.quick_button = tk.Button(
            button_frame,
            text="⚡ Да, обновить",
            command=self.quick_update,
            width=20,
            bg="#4CAF50",
            fg="white",
            state=tk.NORMAL if quick_enabled else tk.DISABLED
        )
        self.quick_button.pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="📁 Выбрать другой файл",
            command=self.choose_other,
            width=20,
            bg="#2196F3",
            fg="white"
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="Отмена",
            command=self.window.destroy,
            width=15
        ).pack(side=tk.LEFT, padx=5)
    
    def quick_update(self):
        """Быстрое обновление из сохранённого файла"""
        if not messagebox.askyesno("Подтверждение",
            f"Перезаписать базу данных '{self.database['name']}'?\nСтарые данные будут удалены."):
            return
        
        self.quick_button.config(state=tk.DISABLED)
        
        db_path = self.main_app.db_dir / self.database["db_file"]
        
        if db_path.exists():
            db_path.unlink()
        
        thread = threading.Thread(
            target=self._update_database_thread,
            args=(db_path, self.source_xml)
        )
        thread.start()
    
    def choose_other(self):
        """Выбрать другой файл"""
        self.window.destroy()
        UpdateDatabaseWindow(self.main_app.root, self.main_app, self.project, self.database)
    
    def _update_database_thread(self, db_path, xml_path):
        try:
            db_manager = DatabaseManager(db_path)
            db_manager.connect()
            
            success = db_manager.create_database(xml_path)
            db_manager.close()
            
            if success:
                messagebox.showinfo("Успех", "База данных обновлена успешно!")
                self.window.destroy()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обновить БД:\n{str(e)}")
            self.quick_button.config(state=tk.NORMAL)

class UpdateDatabaseWindow:
    """Окно обновления базы данных"""
    
    def __init__(self, parent, main_app, project, database):
        self.main_app = main_app
        self.project = project
        self.database = database
        self.window = tk.Toplevel(parent)
        self.window.title("Обновление базы данных")
        self.window.geometry("550x250")
        self.window.grab_set()
        
        self.xml_path = None
        
        self._create_widgets()
    
    def _create_widgets(self):
        tk.Label(self.window, text=f"Проект: {self.project['name']}", font=("Arial", 12, "bold")).pack(pady=10)
        tk.Label(self.window, text=f"База: {self.database['name']}", font=("Arial", 11)).pack(pady=5)
        
        tk.Label(self.window, text="Выберите новый XML файл конфигурации:", font=("Arial", 10)).pack(anchor=tk.W, padx=20, pady=(20, 5))
        
        xml_frame = tk.Frame(self.window)
        xml_frame.pack(padx=20, pady=5, fill=tk.X)
        
        self.xml_label = tk.Label(xml_frame, text="(не выбран)", fg="gray")
        self.xml_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Button(xml_frame, text="Обзор...", command=self.browse_xml, width=10).pack(side=tk.RIGHT)
        
        button_frame = tk.Frame(self.window)
        button_frame.pack(pady=20)
        
        self.update_button = tk.Button(button_frame, text="Обновить", command=self.update, width=15, bg="#2196F3", fg="white")
        self.update_button.pack(side=tk.LEFT, padx=5)
        
        tk.Button(button_frame, text="Отмена", command=self.window.destroy, width=15).pack(side=tk.LEFT, padx=5)
    
    def browse_xml(self):
        filename = filedialog.askopenfilename(
            title="Выберите Configuration.xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
        )
        
        if filename:
            self.xml_path = Path(filename)
            self.xml_label.config(text=self.xml_path.name, fg="black")
    
    def update(self):
        if not self.xml_path:
            messagebox.showwarning("Предупреждение", "Выберите XML файл")
            return
        
        if not messagebox.askyesno("Подтверждение", 
            f"Перезаписать базу данных '{self.database['name']}'?\nСтарые данные будут удалены."):
            return
        
        db_path = self.main_app.db_dir / self.database["db_file"]
        
        if db_path.exists():
            db_path.unlink()
        
        self.update_button.config(state=tk.DISABLED)
        
        thread = threading.Thread(target=self._update_database_thread, args=(db_path,))
        thread.start()
    
    def _update_database_thread(self, db_path):
        try:
            db_manager = DatabaseManager(db_path)
            db_manager.connect()
            
            success = db_manager.create_database(str(self.xml_path))
            db_manager.close()
            
            if success:
                self.main_app.pm.update_source_xml(
                    self.project["id"],
                    self.database["id"],
                    str(self.xml_path)
                )
                messagebox.showinfo("Успех", "База данных обновлена успешно!")
                self.window.destroy()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обновить БД:\n{str(e)}")
            self.update_button.config(state=tk.NORMAL)


def main():
    root = tk.Tk()
    app = AdminAppV2(root)
    root.mainloop()


if __name__ == "__main__":
    main()