import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import sys
from pathlib import Path
import threading

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from admin_tool.db_manager import DatabaseManager


class AdminApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Администратор баз 1С-MCP")
        self.root.geometry("600x500")
        
        self.db_dir = Path("databases")
        self.db_dir.mkdir(exist_ok=True)
        
        self._create_widgets()
        self._load_databases()
    
    def _create_widgets(self):
        """Создает элементы интерфейса"""
        
        # Заголовок
        title_label = tk.Label(
            self.root, 
            text="Администратор баз 1С-MCP", 
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=20)
        
        # Список баз данных
        list_frame = tk.Frame(self.root)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        tk.Label(list_frame, text="Список баз данных:", font=("Arial", 12)).pack(anchor=tk.W)
        
        # Listbox с прокруткой
        scroll = tk.Scrollbar(list_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.db_listbox = tk.Listbox(list_frame, yscrollcommand=scroll.set, height=10)
        self.db_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=self.db_listbox.yview)
        
        # Кнопки - первый ряд
        button_frame1 = tk.Frame(self.root)
        button_frame1.pack(pady=5)

        tk.Button(
            button_frame1, 
            text="Создать новую БД", 
            command=self.create_database,
            width=20,
            bg="#4CAF50",
            fg="white"
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            button_frame1, 
            text="Сделать активной", 
            command=self.set_active_database,
            width=20,
            bg="#2196F3",
            fg="white"
        ).pack(side=tk.LEFT, padx=5)

        # Кнопки - второй ряд
        button_frame2 = tk.Frame(self.root)
        button_frame2.pack(pady=5)

        tk.Button(
            button_frame2, 
            text="Показать статистику", 
            command=self.show_statistics,
            width=20
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            button_frame2, 
            text="Удалить", 
            command=self.delete_database,
            width=20,
            bg="#f44336",
            fg="white"
        ).pack(side=tk.LEFT, padx=5)
    
    def _load_databases(self):
        """Загружает список баз данных"""
        self.db_listbox.delete(0, tk.END)
        
        db_files = list(self.db_dir.glob("*.db"))
        active_db = self._get_active_database()
        
        if not db_files:
            self.db_listbox.insert(tk.END, "(нет баз данных)")
        else:
            for db_file in sorted(db_files):
                db_name = db_file.stem
                display_name = f"★ {db_name}" if db_name == active_db else f"  {db_name}"
                self.db_listbox.insert(tk.END, display_name)

    def _get_active_database(self):
        """Получить имя активной БД из config.json"""
        config_path = Path("Server/config.json")
        if not config_path.exists():
            return None
        
        try:
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            active_path = config.get('active_database', '')
            # Извлекаем имя файла без пути и расширения
            if active_path:
                return Path(active_path).stem
        except:
            return None
        
        return None
    
    def create_database(self):
        """Открывает окно создания новой БД"""
        CreateDatabaseWindow(self.root, self)

    def set_active_database(self):
        """Устанавливает выбранную БД как активную"""
        selection = self.db_listbox.curselection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите базу данных")
            return
        
        db_display = self.db_listbox.get(selection[0])
        if db_display == "(нет баз данных)":
            return
        
        # Убираем звёздочку и пробелы
        db_name = db_display.replace("★", "").strip()
        
        # Обновляем config.json
        config_path = Path("Server/config.json")
        
        try:
            import json
            
            config = {
                "active_database": f"databases/{db_name}.db"
            }
            
            # Создаём папку Server если не существует
            config_path.parent.mkdir(exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # Обновляем список
            self._load_databases()
            
            messagebox.showinfo("Успех", f"База данных '{db_name}' установлена как активная.\n\nПерезапустите Claude Desktop для применения изменений.")
        
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обновить конфигурацию:\n{str(e)}")
    
    def show_statistics(self):
        """Показывает статистику выбранной БД"""
        selection = self.db_listbox.curselection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите базу данных")
            return
        
        db_name = self.db_listbox.get(selection[0])
        if db_name == "(нет баз данных)":
            return
        
        db_path = self.db_dir / f"{db_name}.db"
        
        try:
            db = DatabaseManager(db_path)
            db.connect()
            stats = db.get_statistics()
            db.close()
            
            # Формируем сообщение
            msg = f"База данных: {db_name}\n\n"
            msg += f"Всего объектов: {stats['total_objects']}\n"
            msg += f"Всего модулей: {stats['total_modules']}\n\n"
            msg += "По типам:\n"
            for obj_type, count in sorted(stats['by_type'].items()):
                msg += f"  {obj_type}: {count}\n"
            
            messagebox.showinfo("Статистика", msg)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать БД:\n{str(e)}")
    
    def delete_database(self):
        """Удаляет выбранную БД"""
        selection = self.db_listbox.curselection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите базу данных")
            return
        
        db_name = self.db_listbox.get(selection[0])
        if db_name == "(нет баз данных)":
            return
        
        if messagebox.askyesno("Подтверждение", f"Удалить базу данных '{db_name}'?"):
            db_path = self.db_dir / f"{db_name}.db"
            db_path.unlink()
            self._load_databases()
            messagebox.showinfo("Успех", "База данных удалена")


class CreateDatabaseWindow:
    """Окно создания новой базы данных"""
    
    def __init__(self, parent, main_app):
        self.main_app = main_app
        self.window = tk.Toplevel(parent)
        self.window.title("Создание базы данных")
        self.window.geometry("500x300")
        self.window.grab_set()
        
        self.xml_path = None
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Создает элементы окна"""
        
        # Название БД
        tk.Label(self.window, text="Название базы данных:", font=("Arial", 10)).pack(anchor=tk.W, padx=20, pady=(20, 5))
        self.name_entry = tk.Entry(self.window, width=50)
        self.name_entry.pack(padx=20, pady=5)
        
        # Выбор XML файла
        tk.Label(self.window, text="XML файл конфигурации:", font=("Arial", 10)).pack(anchor=tk.W, padx=20, pady=(10, 5))
        
        xml_frame = tk.Frame(self.window)
        xml_frame.pack(padx=20, pady=5, fill=tk.X)
        
        self.xml_label = tk.Label(xml_frame, text="(не выбран)", fg="gray")
        self.xml_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Button(xml_frame, text="Обзор...", command=self.browse_xml, width=10).pack(side=tk.RIGHT)
        
        # Прогресс-бар
        self.progress_frame = tk.Frame(self.window)
        self.progress_frame.pack(padx=20, pady=20, fill=tk.X)
        
        self.progress = ttk.Progressbar(self.progress_frame, mode='determinate')
        self.progress.pack(fill=tk.X)
        
        self.progress_label = tk.Label(self.progress_frame, text="")
        self.progress_label.pack()
        
        # Кнопки
        button_frame = tk.Frame(self.window)
        button_frame.pack(pady=10)
        
        self.create_button = tk.Button(button_frame, text="Создать", command=self.create, width=15, bg="#4CAF50", fg="white")
        self.create_button.pack(side=tk.LEFT, padx=5)
        
        tk.Button(button_frame, text="Отмена", command=self.window.destroy, width=15).pack(side=tk.LEFT, padx=5)
    
    def browse_xml(self):
        """Выбор XML файла"""
        filename = filedialog.askopenfilename(
            title="Выберите Configuration.xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
        )
        
        if filename:
            self.xml_path = Path(filename)
            self.xml_label.config(text=self.xml_path.name, fg="black")
            
            # Автозаполнение названия
            if not self.name_entry.get():
                self.name_entry.insert(0, self.xml_path.parent.name)
    
    def create(self):
        """Создание базы данных"""
        db_name = self.name_entry.get().strip()
        
        if not db_name:
            messagebox.showwarning("Предупреждение", "Введите название базы данных")
            return
        
        if not self.xml_path:
            messagebox.showwarning("Предупреждение", "Выберите XML файл")
            return
        
        db_path = self.main_app.db_dir / f"{db_name}.db"
        
        if db_path.exists():
            if not messagebox.askyesno("Подтверждение", f"База '{db_name}' уже существует. Перезаписать?"):
                return
            db_path.unlink()
        
        # Отключаем кнопку
        self.create_button.config(state=tk.DISABLED)
        
        # Запускаем создание в отдельном потоке
        thread = threading.Thread(target=self._create_database_thread, args=(db_path,))
        thread.start()
    
    def _create_database_thread(self, db_path):
        """Создание БД в отдельном потоке"""
        try:
            db = DatabaseManager(db_path)
            db.connect()
            
            def progress_callback(current, total, message):
                self.progress['value'] = current
                self.progress_label.config(text=message)
                self.window.update_idletasks()
            
            db.create_database(str(self.xml_path), progress_callback)
            db.close()
            
            # Обновляем список в главном окне
            self.main_app._load_databases()
            
            messagebox.showinfo("Успех", "База данных создана успешно!")
            self.window.destroy()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать БД:\n{str(e)}")
            self.create_button.config(state=tk.NORMAL)


def main():
    root = tk.Tk()
    app = AdminApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()