import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, Toplevel
import threading
import logging
import queue
import configparser
import os
from pathlib import Path

import sync_logic

APP_STATE_FILE = 'app_state.ini'

class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    def emit(self, record):
        self.log_queue.put(self.format(record))

class SettingsWindow(Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.transient(master)
        self.title("Настройки")
        self.geometry("400x150")
        self.resizable(False, False)
        self.grab_set()

        self.config = configparser.ConfigParser()
        self.config.read(sync_logic.CONFIG_FILE)

        self.token_var = tk.StringVar(value=self.config.get('telegram', 'bot_token', fallback=''))
        self.chat_id_var = tk.StringVar(value=self.config.get('telegram', 'chat_id', fallback=''))
        self.enabled_var = tk.BooleanVar(value=self.config.getboolean('telegram', 'enabled', fallback=True))
        
        frame = tk.Frame(self, padx=10, pady=10)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Токен бота:").grid(row=0, column=0, sticky="w", pady=2)
        tk.Entry(frame, textvariable=self.token_var, width=40).grid(row=0, column=1, sticky="ew")
        
        tk.Label(frame, text="ID чата:").grid(row=1, column=0, sticky="w", pady=2)
        tk.Entry(frame, textvariable=self.chat_id_var, width=40).grid(row=1, column=1, sticky="ew")
        
        tk.Checkbutton(frame, text="Включить уведомления", variable=self.enabled_var).grid(row=2, columnspan=2, sticky="w", pady=5)
        
        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=3, columnspan=2, pady=10)
        
        tk.Button(btn_frame, text="Сохранить", command=self.save_settings).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Отмена", command=self.destroy).pack(side="left", padx=5)

    def save_settings(self):
        if not self.config.has_section('telegram'):
            self.config.add_section('telegram')
        self.config.set('telegram', 'bot_token', self.token_var.get())
        self.config.set('telegram', 'chat_id', self.chat_id_var.get())
        self.config.set('telegram', 'enabled', str(self.enabled_var.get()))
        with open(sync_logic.CONFIG_FILE, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)
        messagebox.showinfo("Сохранено", "Настройки успешно сохранены.", parent=self)
        self.destroy()

class AboutWindow(Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.transient(master)
        self.title("О программе")
        self.geometry("350x250")
        self.resizable(False, False)
        self.grab_set()

        try:
            # Путь должен быть относительным, PyInstaller найдет его в сборке.
            icon_path = Path(__file__).parent / "assets" / "icon.png"
            self.icon_image = tk.PhotoImage(file=icon_path)
            icon_label = tk.Label(self, image=self.icon_image)
            icon_label.pack(pady=10)
        except tk.TclError:
            logging.warning("Не удалось загрузить иконку assets/icon.png. Убедитесь, что файл существует.")

        tk.Label(self, text="File Synchronizer", font=("Helvetica", 16, "bold")).pack()
        tk.Label(self, text="Версия 1.5").pack()
        tk.Label(self, text="Утилита для синхронизации файлов.").pack(pady=5)
        
        tk.Button(self, text="Закрыть", command=self.destroy).pack(pady=15)

class SyncApp:
    def __init__(self, master):
        self.master = master
        master.title("File Synchronizer")
        master.minsize(700, 600)
        master.resizable(True, True)
        
        self.create_menu()
        
        self.source_var, self.dest_var = tk.StringVar(), tk.StringVar()
        self.no_overwrite_var, self.delete_removed_var = tk.BooleanVar(), tk.BooleanVar()
        self.sync_empty_dirs_var = tk.BooleanVar()
        self.exclude_patterns_var = tk.StringVar()
        self.source_is_network_var, self.dest_is_network_var = tk.BooleanVar(), tk.BooleanVar()
        self.source_user_var, self.source_pass_var = tk.StringVar(), tk.StringVar()
        self.dest_user_var, self.dest_pass_var = tk.StringVar(), tk.StringVar()
        
        self.create_widgets()
        self._load_state()

        self.log_queue = queue.Queue()
        sync_logic.setup_logging(QueueHandler(self.log_queue))
        self.master.after(100, self.poll_log_queue)

    def create_widgets(self):
        main_frame = tk.Frame(self.master)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        path_frame = tk.LabelFrame(main_frame, text="Пути", padx=10, pady=10)
        path_frame.pack(fill="x")
        path_frame.columnconfigure(1, weight=1)
        tk.Label(path_frame, text="Источник:").grid(row=0, column=0, sticky="w", pady=(0,5))
        tk.Entry(path_frame, textvariable=self.source_var).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(path_frame, text="Обзор...", command=self.browse_source).grid(row=0, column=2, padx=(0,5))
        tk.Checkbutton(path_frame, text="Сетевой путь", variable=self.source_is_network_var, command=self.toggle_creds_visibility).grid(row=0, column=3, sticky="w")
        self.source_user_label = tk.Label(path_frame, text="  Пользователь:")
        self.source_user_entry = tk.Entry(path_frame, textvariable=self.source_user_var)
        self.source_pass_label = tk.Label(path_frame, text="  Пароль:")
        self.source_pass_entry = tk.Entry(path_frame, textvariable=self.source_pass_var, show="*")
        tk.Label(path_frame, text="Назначение:").grid(row=3, column=0, sticky="w", pady=(10,5))
        tk.Entry(path_frame, textvariable=self.dest_var).grid(row=3, column=1, sticky="ew", padx=5)
        tk.Button(path_frame, text="Обзор...", command=self.browse_dest).grid(row=3, column=2, padx=(0,5))
        tk.Checkbutton(path_frame, text="Сетевой путь", variable=self.dest_is_network_var, command=self.toggle_creds_visibility).grid(row=3, column=3, sticky="w")
        self.dest_user_label = tk.Label(path_frame, text="  Пользователь:")
        self.dest_user_entry = tk.Entry(path_frame, textvariable=self.dest_user_var)
        self.dest_pass_label = tk.Label(path_frame, text="  Пароль:")
        self.dest_pass_entry = tk.Entry(path_frame, textvariable=self.dest_pass_var, show="*")
        options_frame = tk.LabelFrame(main_frame, text="Опции", padx=10, pady=10)
        options_frame.pack(fill="x", pady=5)
        tk.Checkbutton(options_frame, text="Не перезаписывать измененные файлы", variable=self.no_overwrite_var).pack(anchor="w")
        tk.Checkbutton(options_frame, text="Удалять лишние файлы в назначении (ОСТОРОЖНО!)", variable=self.delete_removed_var).pack(anchor="w")
        tk.Checkbutton(options_frame, text="Синхронизировать пустые папки", variable=self.sync_empty_dirs_var).pack(anchor="w")
        exclude_frame = tk.LabelFrame(main_frame, text="Исключения", padx=10, pady=10)
        exclude_frame.pack(fill="x", pady=5)
        tk.Label(exclude_frame, text="Исключить файлы (шаблоны через запятую):").pack(anchor="w")
        tk.Entry(exclude_frame, textvariable=self.exclude_patterns_var).pack(fill="x")
        self.sync_button = tk.Button(main_frame, text="Начать синхронизацию", command=self.start_sync_thread, bg="#4CAF50", fg="white", font=("Helvetica", 12, "bold"))
        self.sync_button.pack(pady=10, ipadx=10, ipady=5)
        log_frame = tk.LabelFrame(main_frame, text="Лог выполнения", padx=10, pady=10)
        log_frame.pack(fill="both", expand=True, pady=5)
        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', wrap=tk.WORD, bg="#2b2b2b", fg="#a9b7c6")
        self.log_area.pack(fill="both", expand=True)

    def toggle_creds_visibility(self):
        if self.source_is_network_var.get():
            self.source_user_label.grid(row=1, column=0, sticky="e", padx=(10,0))
            self.source_user_entry.grid(row=1, column=1, sticky="ew", padx=5)
            self.source_pass_label.grid(row=2, column=0, sticky="e", padx=(10,0))
            self.source_pass_entry.grid(row=2, column=1, sticky="ew", padx=5)
        else:
            self.source_user_label.grid_forget()
            self.source_user_entry.grid_forget()
            self.source_pass_label.grid_forget()
            self.source_pass_entry.grid_forget()
            self.source_user_var.set("")
            self.source_pass_var.set("")
        if self.dest_is_network_var.get():
            self.dest_user_label.grid(row=4, column=0, sticky="e", padx=(10,0))
            self.dest_user_entry.grid(row=4, column=1, sticky="ew", padx=5)
            self.dest_pass_label.grid(row=5, column=0, sticky="e", padx=(10,0))
            self.dest_pass_entry.grid(row=5, column=1, sticky="ew", padx=5)
        else:
            self.dest_user_label.grid_forget()
            self.dest_user_entry.grid_forget()
            self.dest_pass_label.grid_forget()
            self.dest_pass_entry.grid_forget()
            self.dest_user_var.set("")
            self.dest_pass_var.set("")

    def start_sync_thread(self):
        source, dest = self.source_var.get(), self.dest_var.get()
        if not source or not dest:
            messagebox.showerror("Ошибка", "Необходимо указать исходную и целевую директории.")
            return
        self._save_state()
        exclude_str = self.exclude_patterns_var.get()
        exclude_list = [p.strip() for p in exclude_str.split(',') if p.strip()]
        source_creds = {'user': self.source_user_var.get(), 'password': self.source_pass_var.get()} if self.source_is_network_var.get() else None
        dest_creds = {'user': self.dest_user_var.get(), 'password': self.dest_pass_var.get()} if self.dest_is_network_var.get() else None
        self.sync_button.config(state="disabled", text="Синхронизация...")
        threading.Thread(target=self.run_sync_task, args=(source, dest, self.no_overwrite_var.get(), self.delete_removed_var.get(), self.sync_empty_dirs_var.get(), exclude_list, source_creds, dest_creds), daemon=True).start()

    def _load_state(self):
        config = configparser.ConfigParser()
        if os.path.exists(APP_STATE_FILE):
            config.read(APP_STATE_FILE, encoding='utf-8')
            self.source_var.set(config.get('Paths', 'last_source', fallback=''))
            self.dest_var.set(config.get('Paths', 'last_destination', fallback=''))
            self.exclude_patterns_var.set(config.get('Options', 'last_exclusions', fallback='*.tmp, *.log'))
            self.sync_empty_dirs_var.set(config.getboolean('Options', 'sync_empty_dirs', fallback=False))
            self.source_is_network_var.set(config.getboolean('Options', 'source_is_network', fallback=False))
            self.dest_is_network_var.set(config.getboolean('Options', 'dest_is_network', fallback=False))
        self.toggle_creds_visibility()

    def _save_state(self):
        config = configparser.ConfigParser()
        config['Paths'] = {'last_source': self.source_var.get(), 'last_destination': self.dest_var.get()}
        config['Options'] = {'last_exclusions': self.exclude_patterns_var.get(), 'sync_empty_dirs': str(self.sync_empty_dirs_var.get()),'source_is_network': str(self.source_is_network_var.get()),'dest_is_network': str(self.dest_is_network_var.get())}
        with open(APP_STATE_FILE, 'w', encoding='utf-8') as configfile: config.write(configfile)

    def create_menu(self):
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Настройки", command=self.open_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.master.quit)
        menubar.add_cascade(label="Файл", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="О программе", command=self.show_about)
        menubar.add_cascade(label="Справка", menu=help_menu)

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
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, record + '\n')
        self.log_area.configure(state='disabled')
        self.log_area.yview(tk.END)
    def run_sync_task(self, source, dest, no_overwrite, delete_removed, sync_empty_dirs, exclude_patterns, source_creds, dest_creds):
        try: sync_logic.run_sync_session(source, dest, no_overwrite, delete_removed, sync_empty_dirs, exclude_patterns, source_creds, dest_creds)
        except Exception as e: messagebox.showerror("Критическая ошибка", f"Синхронизация прервана с ошибкой:\n\n{e}\n\nПодробности в логе.")
        finally: self.sync_button.config(state="normal", text="Начать синхронизацию")

if __name__ == "__main__":
    root = tk.Tk()
    # Установка иконки для главного окна
    try:
        icon_path = Path(__file__).parent / "assets" / "icon.png"
        app_icon = tk.PhotoImage(file=icon_path)
        root.iconphoto(True, app_icon)
    except tk.TclError:
        print("Не удалось загрузить иконку приложения assets/icon.png")

    app = SyncApp(root)
    root.mainloop()