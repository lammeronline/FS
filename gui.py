import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import logging
import queue

import sync_logic

class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))

class SyncApp:
    def __init__(self, master):
        self.master = master
        master.title("File Synchronizer")
        master.geometry("700x500")

        self.source_var = tk.StringVar()
        self.dest_var = tk.StringVar()
        self.no_overwrite_var = tk.BooleanVar()
        self.delete_removed_var = tk.BooleanVar()
        
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
        queue_handler = QueueHandler(self.log_queue)
        sync_logic.setup_logging(queue_handler)
        
        self.master.after(100, self.poll_log_queue)

    def browse_source(self):
        directory = filedialog.askdirectory()
        if directory:
            self.source_var.set(directory)

    def browse_dest(self):
        directory = filedialog.askdirectory()
        if directory:
            self.dest_var.set(directory)

    def poll_log_queue(self):
        while True:
            try:
                record = self.log_queue.get(block=False)
            except queue.Empty:
                break
            else:
                self.display_log(record)
        self.master.after(100, self.poll_log_queue)

    def display_log(self, record):
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, record + '\n')
        self.log_area.configure(state='disabled')
        self.log_area.yview(tk.END)

    def start_sync_thread(self):
        source = self.source_var.get()
        dest = self.dest_var.get()
        if not source or not dest:
            messagebox.showerror("Ошибка", "Необходимо указать исходную и целевую директории.")
            return

        self.sync_button.config(state="disabled", text="Синхронизация...")
        
        self.sync_thread = threading.Thread(
            target=self.run_sync_task,
            args=(source, dest, self.no_overwrite_var.get(), self.delete_removed_var.get()),
            daemon=True
        )
        self.sync_thread.start()

    def run_sync_task(self, source, dest, no_overwrite, delete_removed):
        try:
            sync_logic.run_sync_session(source, dest, no_overwrite, delete_removed)
        except Exception as e:
            messagebox.showerror("Критическая ошибка", f"Синхронизация прервана с ошибкой:\n\n{e}\n\nПодробности в логе.")
        finally:
            self.sync_button.config(state="normal", text="Начать синхронизацию")

if __name__ == "__main__":
    root = tk.Tk()
    app = SyncApp(root)
    root.mainloop()