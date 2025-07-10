import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, scrolledtext, Toplevel
from PIL import Image, ImageTk
import threading
import logging
import queue
import configparser
import os
from pathlib import Path
import base64
import webbrowser
from tkinter import font

import sync_logic

APP_STATE_FILE = 'app_state.ini'

class QueueHandler(logging.Handler):
    """Класс для перенаправления логов в текстовое поле GUI."""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    def emit(self, record):
        self.log_queue.put(self.format(record))

class SettingsWindow(Toplevel):
    """Окно настроек с вкладками."""
    def __init__(self, master):
        super().__init__(master)
        self.transient(master)
        self.title("Настройки")
        self.geometry("420x280")
        self.resizable(False, False)
        self.grab_set()
        
        self.config = configparser.ConfigParser()
        self.config.read(sync_logic.CONFIG_FILE)
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(pady=10, padx=10, fill="both", expand=True)

        # Вкладка Telegram
        telegram_frame = tk.Frame(self.notebook, padx=10, pady=10)
        self.notebook.add(telegram_frame, text='Telegram')
        self.token_var = tk.StringVar(value=self.config.get('telegram', 'bot_token', fallback=''))
        self.chat_id_var = tk.StringVar(value=self.config.get('telegram', 'chat_id', fallback=''))
        self.enabled_var = tk.BooleanVar(value=self.config.getboolean('telegram', 'enabled', fallback=True))
        tk.Label(telegram_frame, text="Токен бота:").grid(row=0, column=0, sticky="w", pady=2)
        tk.Entry(telegram_frame, textvariable=self.token_var, width=40).grid(row=0, column=1, sticky="ew")
        tk.Label(telegram_frame, text="ID чата:").grid(row=1, column=0, sticky="w", pady=2)
        tk.Entry(telegram_frame, textvariable=self.chat_id_var, width=40).grid(row=1, column=1, sticky="ew")
        tk.Checkbutton(telegram_frame, text="Включить уведомления", variable=self.enabled_var).grid(row=2, columnspan=2, sticky="w", pady=5)
        
        # Вкладка Производительность
        perf_frame = tk.Frame(self.notebook, padx=10, pady=10)
        self.notebook.add(perf_frame, text='Производительность')
        self.comparison_mode_var = tk.StringVar(value=self.config.get('performance', 'comparison_mode', fallback='accurate'))
        self.use_parallel_var = tk.BooleanVar(value=self.config.getboolean('performance', 'use_parallel', fallback=False))
        tk.Label(perf_frame, text="Метод сравнения файлов:").pack(anchor="w")
        ttk.Radiobutton(perf_frame, text="Точный (по хешу, медленно, надежно)", variable=self.comparison_mode_var, value='accurate').pack(anchor="w", padx=10)
        ttk.Radiobutton(perf_frame, text="Гибридный (дата/размер + хеш, быстро)", variable=self.comparison_mode_var, value='hybrid').pack(anchor="w", padx=10)
        ttk.Separator(perf_frame, orient='horizontal').pack(fill='x', pady=10)
        tk.Checkbutton(perf_frame, text="Использовать параллельное сканирование\n(ускоряет на многоядерных ЦП и SSD)", variable=self.use_parallel_var, justify="left").pack(anchor="w")

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Сохранить", command=self.save_settings).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Отмена", command=self.destroy).pack(side="left", padx=5)

    def save_settings(self):
        if not self.config.has_section('telegram'): self.config.add_section('telegram')
        self.config.set('telegram', 'bot_token', self.token_var.get())
        self.config.set('telegram', 'chat_id', self.chat_id_var.get())
        self.config.set('telegram', 'enabled', str(self.enabled_var.get()))
        if not self.config.has_section('performance'): self.config.add_section('performance')
        self.config.set('performance', 'comparison_mode', self.comparison_mode_var.get())
        self.config.set('performance', 'use_parallel', str(self.use_parallel_var.get()))
        with open(sync_logic.CONFIG_FILE, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)
        messagebox.showinfo("Сохранено", "Настройки успешно сохранены.", parent=self)
        self.destroy()

class AboutWindow(Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.transient(master)
        self.title("О программе")
        self.geometry("400x300")
        self.resizable(False, False)
        self.grab_set()

        main_frame = tk.Frame(self)
        main_frame.pack(pady=15, padx=20, fill="both", expand=True)

        try:
            icon_path = Path(__file__).parent / "assets" / "icon.png"
            original_image = Image.open(icon_path)
            resized_image = original_image.resize((64, 64), Image.Resampling.LANCZOS)
            self.icon_image = ImageTk.PhotoImage(resized_image)
            icon_label = tk.Label(main_frame, image=self.icon_image)
            icon_label.grid(row=0, column=0, rowspan=6, padx=(0, 20), sticky="n")
        except Exception as e:
            logging.warning(f"Не удалось загрузить иконку assets/icon.png: {e}")

        tk.Label(main_frame, text="File Synchronizer", font=("Helvetica", 16, "bold")).grid(row=0, column=1, sticky="w")
        tk.Label(main_frame, text="Версия 2.3").grid(row=1, column=1, sticky="w")
        tk.Label(main_frame, text="Утилита для синхронизации файлов.").grid(row=2, column=1, sticky="w", pady=(5, 15))

        tk.Label(main_frame, text="Авторы:", font=("Helvetica", 10, "bold")).grid(row=3, column=1, sticky="w")
        tk.Label(main_frame, text="LammerOnline, Google AI Studio").grid(row=4, column=1, sticky="w")
        
        link_label = tk.Label(main_frame, text="Репозиторий на GitHub", fg="blue", cursor="hand2")
        link_label.grid(row=5, column=1, sticky="w", pady=(10,0))
        link_font = font.Font(link_label, link_label.cget("font"))
        link_font.configure(underline=True)
        link_label.configure(font=link_font)
        link_label.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/lammeronline/FS"))

        close_button = tk.Button(self, text="Закрыть", command=self.destroy)
        close_button.pack(pady=(0, 15))

class SyncApp:
    def __init__(self, master):
        self.master = master
        master.title("File Synchronizer"); master.minsize(700, 600); master.resizable(True, True)
        
        # Переменные
        self.source_var, self.dest_var = tk.StringVar(), tk.StringVar()
        self.no_overwrite_var, self.delete_removed_var = tk.BooleanVar(), tk.BooleanVar()
        self.sync_empty_dirs_var = tk.BooleanVar()
        self.exclude_patterns_var = tk.StringVar()
        self.source_is_network_var, self.dest_is_network_var = tk.BooleanVar(), tk.BooleanVar()
        self.source_user_var, self.source_pass_var = tk.StringVar(), tk.StringVar()
        self.dest_user_var, self.dest_pass_var = tk.StringVar(), tk.StringVar()
        self.source_show_pass_var, self.dest_show_pass_var = tk.BooleanVar(), tk.BooleanVar()
        self.save_passwords_var = tk.BooleanVar()
        self.stop_event = None
        
        # Создание интерфейса
        self.create_menu()
        self.create_widgets()
        self.create_context_menu()
        
        # Загрузка и логирование
        self._load_state()
        self.log_queue = queue.Queue()
        sync_logic.setup_logging(QueueHandler(self.log_queue))
        self.master.after(100, self.poll_log_queue)

    def create_context_menu(self):
        """Создает универсальное контекстное меню и привязывает его к классу Entry."""
        self.context_menu = tk.Menu(self.master, tearoff=0)
        self.context_menu.add_command(label="Вырезать", command=lambda: self.master.focus_get().event_generate("<<Cut>>"))
        self.context_menu.add_command(label="Копировать", command=lambda: self.master.focus_get().event_generate("<<Copy>>"))
        self.context_menu.add_command(label="Вставить", command=lambda: self.master.focus_get().event_generate("<<Paste>>"))
        self.master.bind_class("Entry", "<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        """Отображает контекстное меню."""
        widget = event.widget
        self.context_menu.tk_popup(event.x_root, event.y_root)
        
    def create_widgets(self):
        main_frame = tk.Frame(self.master); main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        path_frame = tk.LabelFrame(main_frame, text="Пути", padx=10, pady=10); path_frame.pack(fill="x")
        path_frame.columnconfigure(1, weight=1)
        tk.Label(path_frame, text="Источник:").grid(row=0, column=0, sticky="w", pady=(0,5))
        self.source_entry = tk.Entry(path_frame, textvariable=self.source_var); self.source_entry.grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(path_frame, text="Обзор...", command=self.browse_source).grid(row=0, column=2, padx=(0,5))
        tk.Checkbutton(path_frame, text="Сетевой путь", variable=self.source_is_network_var, command=self.toggle_source_creds).grid(row=0, column=3, sticky="w")
        self.source_user_label = tk.Label(path_frame, text="  Пользователь:"); self.source_user_entry = tk.Entry(path_frame, textvariable=self.source_user_var)
        self.source_pass_label = tk.Label(path_frame, text="  Пароль:"); self.source_pass_entry = tk.Entry(path_frame, textvariable=self.source_pass_var, show="*")
        self.source_show_pass_check = tk.Checkbutton(path_frame, text="Показать", variable=self.source_show_pass_var, command=self.toggle_source_pass_visibility)
        ttk.Separator(path_frame, orient='horizontal').grid(row=4, columnspan=4, sticky='ew', pady=10)
        tk.Label(path_frame, text="Назначение:").grid(row=5, column=0, sticky="w", pady=(5,5))
        self.dest_entry = tk.Entry(path_frame, textvariable=self.dest_var); self.dest_entry.grid(row=5, column=1, sticky="ew", padx=5)
        tk.Button(path_frame, text="Обзор...", command=self.browse_dest).grid(row=5, column=2, padx=(0,5))
        tk.Checkbutton(path_frame, text="Сетевой путь", variable=self.dest_is_network_var, command=self.toggle_dest_creds).grid(row=5, column=3, sticky="w")
        self.dest_user_label = tk.Label(path_frame, text="  Пользователь:"); self.dest_user_entry = tk.Entry(path_frame, textvariable=self.dest_user_var)
        self.dest_pass_label = tk.Label(path_frame, text="  Пароль:"); self.dest_pass_entry = tk.Entry(path_frame, textvariable=self.dest_pass_var, show="*")
        self.dest_show_pass_check = tk.Checkbutton(path_frame, text="Показать", variable=self.dest_show_pass_var, command=self.toggle_dest_pass_visibility)
        self.save_pass_check = tk.Checkbutton(path_frame, text="Запомнить пароли (хранятся в небезопасном виде)", variable=self.save_passwords_var)
        options_frame = tk.LabelFrame(main_frame, text="Опции", padx=10, pady=10); options_frame.pack(fill="x", pady=5)
        tk.Checkbutton(options_frame, text="Не перезаписывать измененные файлы", variable=self.no_overwrite_var).pack(anchor="w")
        tk.Checkbutton(options_frame, text="Удалять лишние файлы в назначении (ОСТОРОЖНО!)", variable=self.delete_removed_var).pack(anchor="w")
        tk.Checkbutton(options_frame, text="Синхронизировать пустые папки", variable=self.sync_empty_dirs_var).pack(anchor="w")
        exclude_frame = tk.LabelFrame(main_frame, text="Исключения", padx=10, pady=10); exclude_frame.pack(fill="x", pady=5)
        tk.Label(exclude_frame, text="Исключить файлы (шаблоны через запятую):").pack(anchor="w")
        self.exclude_entry = tk.Entry(exclude_frame, textvariable=self.exclude_patterns_var); self.exclude_entry.pack(fill="x")
        self.sync_button = tk.Button(main_frame, text="Начать синхронизацию", command=self.start_sync_thread, bg="#4CAF50", fg="white", font=("Helvetica", 12, "bold")); self.sync_button.pack(pady=10, ipadx=10, ipady=5)
        log_frame = tk.LabelFrame(main_frame, text="Лог выполнения", padx=10, pady=10); log_frame.pack(fill="both", expand=True, pady=5)
        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', wrap=tk.WORD, bg="#2b2b2b", fg="#a9b7c6"); self.log_area.pack(fill="both", expand=True)

    def create_menu(self):
        menubar = tk.Menu(self.master); self.master.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0); file_menu.add_command(label="Импорт задачи...", command=self.import_job_file); file_menu.add_command(label="Экспорт задачи...", command=self.export_job_file); file_menu.add_separator(); file_menu.add_command(label="Настройки", command=self.open_settings); file_menu.add_separator(); file_menu.add_command(label="Выход", command=self.master.quit)
        menubar.add_cascade(label="Файл", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=0); help_menu.add_command(label="О программе", command=self.show_about)
        menubar.add_cascade(label="Справка", menu=help_menu)

    def import_job_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("Job Files", "*.ini"), ("All Files", "*.*")],title="Импортировать файл задачи")
        if not filepath: return
        try:
            job_config = configparser.ConfigParser();
            if not job_config.read(filepath, encoding='utf-8'): raise FileNotFoundError("Файл пуст или не найден.")
            if 'SyncJob' not in job_config: raise configparser.NoSectionError("Файл не содержит [SyncJob].")
            job = job_config['SyncJob']; self.source_var.set(job.get('source', '')); self.dest_var.set(job.get('destination', '')); self.no_overwrite_var.set(job.getboolean('no_overwrite', False)); self.delete_removed_var.set(job.getboolean('delete_removed', False)); self.sync_empty_dirs_var.set(job.getboolean('sync_empty_dirs', False)); self.exclude_patterns_var.set(job.get('exclude', ''))
            if 'SourceNetCreds' in job_config: self.source_is_network_var.set(True); s_creds = job_config['SourceNetCreds']; self.source_user_var.set(s_creds.get('user', '')); self.source_pass_var.set(s_creds.get('password', ''))
            else: self.source_is_network_var.set(False)
            if 'DestNetCreds' in job_config: self.dest_is_network_var.set(True); d_creds = job_config['DestNetCreds']; self.dest_user_var.set(d_creds.get('user', '')); self.dest_pass_var.set(d_creds.get('password', ''))
            else: self.dest_is_network_var.set(False)
            self.toggle_source_creds(); self.toggle_dest_creds()
            messagebox.showinfo("Успешно", "Задача успешно импортирована.")
        except Exception as e: messagebox.showerror("Ошибка импорта", f"Не удалось импортировать файл задачи:\n{e}")

    def export_job_file(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".ini",filetypes=[("Job Files", "*.ini"), ("All Files", "*.*")],title="Экспортировать файл задачи")
        if not filepath: return
        job_config = configparser.ConfigParser(); job_config.add_section('SyncJob')
        job_config.set('SyncJob', 'source', self.source_var.get()); job_config.set('SyncJob', 'destination', self.dest_var.get()); job_config.set('SyncJob', 'no_overwrite', str(self.no_overwrite_var.get()).lower()); job_config.set('SyncJob', 'delete_removed', str(self.delete_removed_var.get()).lower()); job_config.set('SyncJob', 'sync_empty_dirs', str(self.sync_empty_dirs_var.get()).lower()); job_config.set('SyncJob', 'exclude', self.exclude_patterns_var.get())
        if self.source_is_network_var.get() and self.source_user_var.get(): job_config.add_section('SourceNetCreds'); job_config.set('SourceNetCreds', 'user', self.source_user_var.get()); job_config.set('SourceNetCreds', 'password', self.source_pass_var.get())
        if self.dest_is_network_var.get() and self.dest_user_var.get(): job_config.add_section('DestNetCreds'); job_config.set('DestNetCreds', 'user', self.dest_user_var.get()); job_config.set('DestNetCreds', 'password', self.dest_pass_var.get())
        try:
            with open(filepath, 'w', encoding='utf-8') as configfile: job_config.write(configfile)
            messagebox.showinfo("Успешно", f"Задача успешно экспортирована в:\n{filepath}")
        except Exception as e: messagebox.showerror("Ошибка", f"Не удалось экспортировать файл задачи:\n{e}")

    def toggle_source_creds(self):
        if self.source_is_network_var.get(): self.source_user_label.grid(row=1, column=0, sticky="e", padx=(10,0)); self.source_user_entry.grid(row=1, column=1, sticky="ew", padx=5); self.source_pass_label.grid(row=2, column=0, sticky="e", padx=(10,0)); self.source_pass_entry.grid(row=2, column=1, sticky="ew", padx=5); self.source_show_pass_check.grid(row=2, column=2, sticky="w")
        else: self.source_user_label.grid_forget(); self.source_user_entry.grid_forget(); self.source_pass_label.grid_forget(); self.source_pass_entry.grid_forget(); self.source_show_pass_check.grid_forget(); self.source_user_var.set(""); self.source_pass_var.set("")
        self.update_save_pass_visibility()
    
    def toggle_dest_creds(self):
        if self.dest_is_network_var.get(): self.dest_user_label.grid(row=6, column=0, sticky="e", padx=(10,0)); self.dest_user_entry.grid(row=6, column=1, sticky="ew", padx=5); self.dest_pass_label.grid(row=7, column=0, sticky="e", padx=(10,0)); self.dest_pass_entry.grid(row=7, column=1, sticky="ew", padx=5); self.dest_show_pass_check.grid(row=7, column=2, sticky="w")
        else: self.dest_user_label.grid_forget(); self.dest_user_entry.grid_forget(); self.dest_pass_label.grid_forget(); self.dest_pass_entry.grid_forget(); self.dest_show_pass_check.grid_forget(); self.dest_user_var.set(""); self.dest_pass_var.set("")
        self.update_save_pass_visibility()

    def update_save_pass_visibility(self):
        if self.source_is_network_var.get() or self.dest_is_network_var.get(): self.save_pass_check.grid(row=8, columnspan=4, sticky='w', pady=(10,0))
        else: self.save_pass_check.grid_forget(); self.save_passwords_var.set(False)

    def toggle_source_pass_visibility(self): self.source_pass_entry.config(show="" if self.source_show_pass_var.get() else "*")
    def toggle_dest_pass_visibility(self): self.dest_pass_entry.config(show="" if self.dest_show_pass_var.get() else "*")

    def _load_state(self):
        config = configparser.ConfigParser();
        if os.path.exists(APP_STATE_FILE):
            config.read(APP_STATE_FILE, encoding='utf-8')
            state = config['State']
            self.source_var.set(state.get('last_source', fallback='')); self.dest_var.set(state.get('last_destination', fallback=''))
            self.exclude_patterns_var.set(state.get('last_exclusions', fallback='*.tmp, *.log')); self.sync_empty_dirs_var.set(state.getboolean('sync_empty_dirs', fallback=False))
            self.source_is_network_var.set(state.getboolean('source_is_network', fallback=False)); self.dest_is_network_var.set(state.getboolean('dest_is_network', fallback=False))
            self.save_passwords_var.set(state.getboolean('save_passwords', fallback=False))
            if self.save_passwords_var.get():
                try:
                    self.source_user_var.set(base64.b64decode(state.get('s_user', '')).decode('utf-8')); self.source_pass_var.set(base64.b64decode(state.get('s_pass', '')).decode('utf-8'))
                    self.dest_user_var.set(base64.b64decode(state.get('d_user', '')).decode('utf-8')); self.dest_pass_var.set(base64.b64decode(state.get('d_pass', '')).decode('utf-8'))
                except Exception: pass
        self.toggle_source_creds(); self.toggle_dest_creds()

    def _save_state(self):
        config = configparser.ConfigParser(); config['State'] = {
            'last_source': self.source_var.get(), 'last_destination': self.dest_var.get(),
            'last_exclusions': self.exclude_patterns_var.get(), 'sync_empty_dirs': str(self.sync_empty_dirs_var.get()),
            'source_is_network': str(self.source_is_network_var.get()), 'dest_is_network': str(self.dest_is_network_var.get()),
            'save_passwords': str(self.save_passwords_var.get())}
        if self.save_passwords_var.get():
            state = config['State']
            state['s_user'] = base64.b64encode(self.source_user_var.get().encode('utf-8')).decode('utf-8'); state['s_pass'] = base64.b64encode(self.source_pass_var.get().encode('utf-8')).decode('utf-8')
            state['d_user'] = base64.b64encode(self.dest_user_var.get().encode('utf-8')).decode('utf-8'); state['d_pass'] = base64.b64encode(self.dest_pass_var.get().encode('utf-8')).decode('utf-8')
        with open(APP_STATE_FILE, 'w', encoding='utf-8') as configfile: config.write(configfile)

    def start_sync_thread(self):
        source, dest = self.source_var.get(), self.dest_var.get()
        if not source or not dest: messagebox.showerror("Ошибка", "Необходимо указать исходную и целевую директории."); return
        self._save_state(); exclude_list = [p.strip() for p in self.exclude_patterns_var.get().split(',') if p.strip()]; source_creds, dest_creds = None, None
        if self.source_is_network_var.get() and self.source_user_var.get() and self.source_pass_var.get(): source_creds = {'user': self.source_user_var.get(), 'password': self.source_pass_var.get()}
        if self.dest_is_network_var.get() and self.dest_user_var.get() and self.dest_pass_var.get(): dest_creds = {'user': self.dest_user_var.get(), 'password': self.dest_pass_var.get()}
        config = configparser.ConfigParser(); config.read(sync_logic.CONFIG_FILE)
        comparison_mode = config.get('performance', 'comparison_mode', fallback='accurate'); use_parallel = config.getboolean('performance', 'use_parallel', fallback=False)
        self.stop_event = threading.Event(); self.sync_button.config(text="Остановить", command=self.stop_sync_thread, bg="#e74c3c")
        threading.Thread(target=self.run_sync_task, args=(source, dest, self.no_overwrite_var.get(), self.delete_removed_var.get(), self.sync_empty_dirs_var.get(), exclude_list, source_creds, dest_creds, self.stop_event, comparison_mode, use_parallel), daemon=True).start()

    def stop_sync_thread(self):
        if self.stop_event: logging.info("Подан сигнал на остановку синхронизации..."); self.stop_event.set(); self.sync_button.config(state="disabled", text="Остановка...")
    
    def run_sync_task(self, source, dest, no_overwrite, delete_removed, sync_empty_dirs, exclude_patterns, source_creds, dest_creds, stop_event, comparison_mode, use_parallel):
        try: sync_logic.run_sync_session(source, dest, no_overwrite, delete_removed, sync_empty_dirs, exclude_patterns, source_creds, dest_creds, stop_event, comparison_mode, use_parallel)
        except sync_logic.SyncCancelledError as e: logging.warning(f"Процесс синхронизации был корректно остановлен: {e}")
        except Exception as e: messagebox.showerror("Критическая ошибка", f"Синхронизация прервана с ошибкой:\n\n{e}\n\nПодробности в логе.")
        finally: self.sync_button.config(state="normal", text="Начать синхронизацию", command=self.start_sync_thread, bg="#4CAF50"); self.stop_event = None
    
    def open_settings(self): SettingsWindow(self.master)
    def show_about(self): AboutWindow(self.master)
    def browse_source(self): self.source_var.set(filedialog.askdirectory() or self.source_var.get())
    def browse_dest(self): self.dest_var.set(filedialog.askdirectory() or self.dest_var.get())
    def poll_log_queue(self):
        while True:
            try: record = self.log_queue.get(block=False)
            except queue.Empty: break
            else: self.display_log(record)
        self.master.after(100, self.poll_log_queue)
    def display_log(self, record):
        self.log_area.configure(state='normal'); self.log_area.insert(tk.END, record + '\n'); self.log_area.configure(state='disabled'); self.log_area.yview(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    try:
        icon_path = Path(__file__).parent / "assets" / "icon.png"
        app_icon = tk.PhotoImage(file=icon_path)
        root.iconphoto(True, app_icon)
    except Exception as e:
        print(f"Не удалось загрузить иконку приложения assets/icon.png: {e}")
    app = SyncApp(root)
    root.mainloop()