import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, Toplevel
import threading
import logging
import queue
import configparser
import os

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

class SyncApp:
    def __init__(self, master):
        self.master = master
        master.title("File Synchronizer")
        master.geometry("700x550")
        self.create_menu()
        self.source_var, self.dest_var = tk.StringVar(), tk.StringVar()
        self.no_overwrite_var, self.delete_removed_var = tk.BooleanVar(), tk.BooleanVar()
        self._load_state()

        path_frame = tk.LabelFrame(master, text="Пути", padx=10, pady=10)
        path_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(path_frame, text="Источник:").grid(row=0, column=0, sticky="w")
        tk.Entry(path_frame, textvariable=self.source_var, width=60).grid(row=0, column=1, padx=5)
        tk.Button(path_frame, text="Обзор...", command=self.browse_source).grid(row=0, column=2)
        tk.Label(path_frame, text="Назначение:").grid(row=1, column=0, sticky="w")
        tk.Entry(path_frame, textvariable=self.dest_var, width=60).grid(row=1, column=1, padx=5)
        tk.Button(path_frame, text="Обзор...", command=self.browse_dest).grid(row=1, column=2)

        options_frame = tk.LabelFrame(master, text="Опции", padx=10, pady=10)
        options_frame.pack(fill="x", padx=10, pady=5)
        tk.Checkbutton(options_frame, text="Не перезаписывать измененные файлы", variable=self.no_overwrite_var).pack(anchor="w")
        tk.Checkbutton(options_frame, text="Удалять лишние файлы в назначении (ОСТОРОЖНО!)", variable=self.delete_removed_var).pack(anchor="w")
        
        self.sync_button = tk.Button(master, text="Начать синхронизацию", command=self.start_sync_thread, bg="#4CAF50", fg="white", font=("Helvetica", 12, "bold"))
        self.sync_button.pack(pady=10, ipadx=10, ipady=5)

        log_frame = tk.LabelFrame(master, text="Лог выполнения", padx=10, pady=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', wrap=tk.WORD, bg="#2b2b2b", fg="#a9b7c6")
        self.log_area.pack(fill="both", expand=True)

        self.log_queue = queue.Queue()
        sync_logic.setup_logging(QueueHandler(self.log_queue))
        self.master.after(100, self.poll_log_queue)

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
    def show_about(self): messagebox.showinfo("О программе", "File Synchronizer v1.1\n\nПрограмма для синхронизации файлов.\nРазработано с помощью Python и Tkinter.")
    def _load_state(self):
        config = configparser.ConfigParser()
        if os.path.exists(APP_STATE_FILE):
            config.read(APP_STATE_FILE, encoding='utf-8')
            self.source_var.set(config.get('Paths', 'last_source', fallback=''))
            self.dest_var.set(config.get('Paths', 'last_destination', fallback=''))
    def _save_state(self):
        config = configparser.ConfigParser()
        config['Paths'] = {'last_source': self.source_var.get(), 'last_destination': self.dest_var.get()}
        with open(APP_STATE_FILE, 'w', encoding='utf-8') as configfile: config.write(configfile)
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
    def start_sync_thread(self):
        source, dest = self.source_var.get(), self.dest_var.get()
        if not source or not dest:
            messagebox.showerror("Ошибка", "Необходимо указать исходную и целевую директории.")
            return
        self._save_state()
        self.sync_button.config(state="disabled", text="Синхронизация...")
        threading.Thread(target=self.run_sync_task, args=(source, dest, self.no_overwrite_var.get(), self.delete_removed_var.get()), daemon=True).start()
    def run_sync_task(self, source, dest, no_overwrite, delete_removed):
        try: sync_logic.run_sync_session(source, dest, no_overwrite, delete_removed)
        except Exception as e: messagebox.showerror("Критическая ошибка", f"Синхронизация прервана с ошибкой:\n\n{e}\n\nПодробности в логе.")
        finally: self.sync_button.config(state="normal", text="Начать синхронизацию")

if __name__ == "__main__":
    root = tk.Tk()
    app = SyncApp(root)
    root.mainloop()