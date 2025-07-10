import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, Toplevel
from PIL import Image, ImageTk
import threading
import logging
import queue
import configparser
import os
from pathlib import Path
import base64

import sync_logic

APP_STATE_FILE = 'app_state.ini'

class ContextMenu:
    """Контекстное меню для полей ввода."""
    def __init__(self, master):
        self.menu = tk.Menu(master, tearoff=0)
        self.menu.add_command(label="Вырезать", command=self.cut)
        self.menu.add_command(label="Копировать", command=self.copy)
        self.menu.add_command(label="Вставить", command=self.paste)
        self.widget = None

    def popup(self, event):
        self.widget = event.widget
        try:
            self.widget.focus()
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def cut(self): self.widget.event_generate("<<Cut>>")
    def copy(self): self.widget.event_generate("<<Copy>>")
    def paste(self): self.widget.event_generate("<<Paste>>")

class SettingsWindow(Toplevel):
    # ... (код этого класса не меняется) ...
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
        if not self.config.has_section('telegram'): self.config.add_section('telegram')
        self.config.set('telegram', 'bot_token', self.token_var.get())
        self.config.set('telegram', 'chat_id', self.chat_id_var.get())
        self.config.set('telegram', 'enabled', str(self.enabled_var.get()))
        with open(sync_logic.CONFIG_FILE, 'w', encoding='utf-8') as configfile: self.config.write(configfile)
        messagebox.showinfo("Сохранено", "Настройки успешно сохранены.", parent=self)
        self.destroy()

class AboutWindow(Toplevel):
    # ... (код этого класса не меняется) ...
    def __init__(self, master):
        super().__init__(master)
        self.transient(master)
        self.title("О программе")
        self.geometry("350x200") 
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
            icon_label.grid(row=0, column=0, rowspan=3, padx=(0, 15), sticky="ns")
        except Exception as e:
            logging.warning(f"Не удалось загрузить иконку assets/icon.png: {e}")
        tk.Label(main_frame, text="File Synchronizer", font=("Helvetica", 16, "bold")).grid(row=0, column=1, sticky="w")
        tk.Label(main_frame, text="Версия 1.7").grid(row=1, column=1, sticky="w")
        tk.Label(main_frame, text="Утилита для синхронизации файлов.").grid(row=2, column=1, sticky="w", pady=(5,0))
        close_button = tk.Button(self, text="Закрыть", command=self.destroy)
        close_button.pack(pady=(0, 15))

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
        self.show_net_creds_var = tk.BooleanVar()
        self.source_user_var, self.source_pass_var = tk.StringVar(), tk.StringVar()
        self.dest_user_var, self.dest_pass_var = tk.StringVar(), tk.StringVar()
        self.save_passwords_var = tk.BooleanVar()
        self.stop_event = None
        
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
        self.source_entry = tk.Entry(path_frame, textvariable=self.source_var)
        self.source_entry.grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(path_frame, text="Обзор...", command=self.browse_source).grid(row=0, column=2, padx=(0,5))
        tk.Label(path_frame, text="Назначение:").grid(row=1, column=0, sticky="w", pady=(5,5))
        self.dest_entry = tk.Entry(path_frame, textvariable=self.dest_var)
        self.dest_entry.grid(row=1, column=1, sticky="ew", padx=5)
        tk.Button(path_frame, text="Обзор...", command=self.browse_dest).grid(row=1, column=2, padx=(0,5))

        # --- СВОРАЧИВАЕМАЯ ПАНЕЛЬ СЕТЕВЫХ НАСТРОЕК ---
        self.net_frame = tk.LabelFrame(main_frame, text="Сетевые ресурсы (UNC-пути)", padx=10, pady=10)
        self.net_frame.pack(fill="x", pady=5)
        self.net_creds_check = tk.Checkbutton(self.net_frame, text="Задать учетные данные для сетевых ресурсов", variable=self.show_net_creds_var, command=self.toggle_net_creds_visibility)
        self.net_creds_check.pack(anchor="w")
        self.creds_container = tk.Frame(self.net_frame)
        self.creds_container.columnconfigure(1, weight=1)
        tk.Label(self.creds_container, text="Источник - Пользователь:").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.source_user_entry = tk.Entry(self.creds_container, textvariable=self.source_user_var)
        self.source_user_entry.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        tk.Label(self.creds_container, text="Источник - Пароль:").grid(row=1, column=0, sticky="w", padx=2, pady=2)
        self.source_pass_entry = tk.Entry(self.creds_container, textvariable=self.source_pass_var, show="*")
        self.source_pass_entry.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        tk.Label(self.creds_container, text="Назначение - Пользователь:").grid(row=2, column=0, sticky="w", padx=2, pady=2)
        self.dest_user_entry = tk.Entry(self.creds_container, textvariable=self.dest_user_var)
        self.dest_user_entry.grid(row=2, column=1, sticky="ew", padx=2, pady=2)
        tk.Label(self.creds_container, text="Назначение - Пароль:").grid(row=3, column=0, sticky="w", padx=2, pady=2)
        self.dest_pass_entry = tk.Entry(self.creds_container, textvariable=self.dest_pass_var, show="*")
        self.dest_pass_entry.grid(row=3, column=1, sticky="ew", padx=2, pady=2)
        tk.Checkbutton(self.creds_container, text="Запомнить пароли (хранятся в небезопасном виде)", variable=self.save_passwords_var).grid(row=4, column=0, columnspan=2, sticky="w", pady=(5,0))

        options_frame = tk.LabelFrame(main_frame, text="Опции", padx=10, pady=10)
        # ... (код options_frame, exclude_frame, sync_button, log_frame без изменений) ...
        options_frame.pack(fill="x", pady=5)
        tk.Checkbutton(options_frame, text="Не перезаписывать измененные файлы", variable=self.no_overwrite_var).pack(anchor="w")
        tk.Checkbutton(options_frame, text="Удалять лишние файлы в назначении (ОСТОРОЖНО!)", variable=self.delete_removed_var).pack(anchor="w")
        tk.Checkbutton(options_frame, text="Синхронизировать пустые папки", variable=self.sync_empty_dirs_var).pack(anchor="w")
        exclude_frame = tk.LabelFrame(main_frame, text="Исключения", padx=10, pady=10)
        exclude_frame.pack(fill="x", pady=5)
        tk.Label(exclude_frame, text="Исключить файлы (шаблоны через запятую):").pack(anchor="w")
        self.exclude_entry = tk.Entry(exclude_frame, textvariable=self.exclude_patterns_var)
        self.exclude_entry.pack(fill="x")
        self.sync_button = tk.Button(main_frame, text="Начать синхронизацию", command=self.start_sync_thread, bg="#4CAF50", fg="white", font=("Helvetica", 12, "bold"))
        self.sync_button.pack(pady=10, ipadx=10, ipady=5)
        log_frame = tk.LabelFrame(main_frame, text="Лог выполнения", padx=10, pady=10)
        log_frame.pack(fill="both", expand=True, pady=5)
        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', wrap=tk.WORD, bg="#2b2b2b", fg="#a9b7c6")
        self.log_area.pack(fill="both", expand=True)

        self.setup_context_menus()

    def setup_context_menus(self):
        context_menu = ContextMenu(self.master)
        widgets_with_menu = [
            self.source_entry, self.dest_entry,
            self.source_user_entry, self.source_pass_entry,
            self.dest_user_entry, self.dest_pass_entry,
            self.exclude_entry
        ]
        for widget in widgets_with_menu:
            widget.bind("<Button-3><ButtonRelease-3>", context_menu.popup)

    def toggle_net_creds_visibility(self):
        if self.show_net_creds_var.get():
            self.creds_container.pack(fill="x", pady=5)
        else:
            self.creds_container.pack_forget()

    def start_sync_thread(self):
        # ... (код start_sync_thread почти без изменений, только сборка creds)
        source, dest = self.source_var.get(), self.dest_var.get()
        if not source or not dest: messagebox.showerror("Ошибка", "Необходимо указать исходную и целевую директории."); return
        self._save_state()
        exclude_list = [p.strip() for p in self.exclude_patterns_var.get().split(',') if p.strip()]
        source_creds, dest_creds = None, None
        if self.show_net_creds_var.get():
            if self.source_user_var.get() and self.source_pass_var.get():
                source_creds = {'user': self.source_user_var.get(), 'password': self.source_pass_var.get()}
            if self.dest_user_var.get() and self.dest_pass_var.get():
                dest_creds = {'user': self.dest_user_var.get(), 'password': self.dest_pass_var.get()}
        self.stop_event = threading.Event()
        self.sync_button.config(text="Остановить", command=self.stop_sync_thread, bg="#e74c3c")
        threading.Thread(target=self.run_sync_task, args=(source, dest, self.no_overwrite_var.get(), self.delete_removed_var.get(), self.sync_empty_dirs_var.get(), exclude_list, source_creds, dest_creds, self.stop_event), daemon=True).start()

    def stop_sync_thread(self):
        if self.stop_event: logging.info("Подан сигнал на остановку синхронизации..."); self.stop_event.set(); self.sync_button.config(state="disabled", text="Остановка...")

    def run_sync_task(self, source, dest, no_overwrite, delete_removed, sync_empty_dirs, exclude_patterns, source_creds, dest_creds, stop_event):
        try:
            sync_logic.run_sync_session(source, dest, no_overwrite, delete_removed, sync_empty_dirs, exclude_patterns, source_creds, dest_creds, stop_event)
        except sync_logic.SyncCancelledError as e:
            logging.warning(f"Процесс синхронизации был корректно остановлен: {e}")
        except Exception as e:
            messagebox.showerror("Критическая ошибка", f"Синхронизация прервана с ошибкой:\n\n{e}\n\nПодробности в логе.")
        finally:
            self.sync_button.config(state="normal", text="Начать синхронизацию", command=self.start_sync_thread, bg="#4CAF50")
            self.stop_event = None

    def _load_state(self):
        config = configparser.ConfigParser()
        if os.path.exists(APP_STATE_FILE):
            config.read(APP_STATE_FILE, encoding='utf-8')
            self.source_var.set(config.get('State', 'last_source', fallback=''))
            self.dest_var.set(config.get('State', 'last_destination', fallback=''))
            self.exclude_patterns_var.set(config.get('State', 'last_exclusions', fallback='*.tmp, *.log'))
            self.sync_empty_dirs_var.set(config.getboolean('State', 'sync_empty_dirs', fallback=False))
            self.show_net_creds_var.set(config.getboolean('State', 'show_net_creds', fallback=False))
            self.save_passwords_var.set(config.getboolean('State', 'save_passwords', fallback=False))
            if self.save_passwords_var.get():
                try:
                    self.source_user_var.set(base64.b64decode(config.get('State', 's_user', '')).decode('utf-8'))
                    self.source_pass_var.set(base64.b64decode(config.get('State', 's_pass', '')).decode('utf-8'))
                    self.dest_user_var.set(base64.b64decode(config.get('State', 'd_user', '')).decode('utf-8'))
                    self.dest_pass_var.set(base64.b64decode(config.get('State', 'd_pass', '')).decode('utf-8'))
                except Exception: pass
        self.toggle_net_creds_visibility()

    def _save_state(self):
        config = configparser.ConfigParser()
        config['State'] = {
            'last_source': self.source_var.get(), 'last_destination': self.dest_var.get(),
            'last_exclusions': self.exclude_patterns_var.get(), 'sync_empty_dirs': str(self.sync_empty_dirs_var.get()),
            'show_net_creds': str(self.show_net_creds_var.get()), 'save_passwords': str(self.save_passwords_var.get())
        }
        if self.save_passwords_var.get():
            config['State']['s_user'] = base64.b64encode(self.source_user_var.get().encode('utf-8')).decode('utf-8')
            config['State']['s_pass'] = base64.b64encode(self.source_pass_var.get().encode('utf-8')).decode('utf-8')
            config['State']['d_user'] = base64.b64encode(self.dest_user_var.get().encode('utf-8')).decode('utf-8')
            config['State']['d_pass'] = base64.b64encode(self.dest_pass_var.get().encode('utf-8')).decode('utf-8')
        with open(APP_STATE_FILE, 'w', encoding='utf-8') as configfile: config.write(configfile)

    def create_menu(self):
        # ... (код create_menu, open_settings, show_about, browse, poll_log_queue без изменений) ...
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