import os
import sys
import hashlib
import shutil
import logging
import configparser
import subprocess
import fnmatch
import concurrent.futures
from pathlib import Path
from datetime import datetime
import requests

# --- Константы ---
LOG_FILE = 'sync_log.txt'
CONFIG_FILE = 'config.ini'
HASH_ALGORITHM = hashlib.sha256
READ_BUFFER_SIZE = 65536

# --- Исключения ---
class SyncCancelledError(Exception):
    """Исключение, вызываемое, когда пользователь отменяет синхронизацию."""
    pass

# --- Функции ---
def setup_logging(gui_log_handler=None):
    handlers = [
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
    if gui_log_handler: handlers.append(gui_log_handler)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=handlers, force=True)

def send_telegram_notification(message):
    config = configparser.ConfigParser()
    if not os.path.exists(CONFIG_FILE): logging.warning(f"Файл конфигурации {CONFIG_FILE} не найден."); return
    config.read(CONFIG_FILE, encoding='utf-8')
    if not config.has_section('telegram') or not config.getboolean('telegram', 'enabled', fallback=False): logging.info("Отправка уведомлений в Telegram отключена."); return
    token = config.get('telegram', 'bot_token', fallback=None)
    chat_id = config.get('telegram', 'chat_id', fallback=None)
    if not token or not chat_id or token == 'YOUR_TELEGRAM_BOT_TOKEN': logging.warning("Токен бота или ID чата не настроены."); return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("Уведомление в Telegram успешно отправлено.")
    except requests.exceptions.RequestException as e: logging.error(f"Ошибка при отправке уведомления в Telegram: {e}")

def ensure_path_is_ready(path_str, net_creds=None):
    if os.path.exists(path_str): logging.info(f"Путь '{path_str}' доступен."); return True
    logging.warning(f"Путь '{path_str}' недоступен. Попытка анализа как сетевого пути...")
    if not path_str.startswith('\\\\'): logging.error(f"Путь '{path_str}' не является UNC путем и недоступен."); return False
    if not net_creds or not net_creds.get('user') or not net_creds.get('password'): logging.error(f"Учетные данные для пути '{path_str}' не предоставлены."); return False
    user, password = net_creds['user'], net_creds['password']
    logging.info(f"Попытка подключения к '{path_str}' с пользователем '{user}'...")
    try:
        if sys.platform == "win32":
            command = ['net', 'use', path_str, password, f'/user:{user}', '/persistent:no']
            subprocess.run(command, capture_output=True, text=True, check=True, encoding='cp866', creationflags=0x08000000) # CREATE_NO_WINDOW
            logging.info(f"Команда 'net use' выполнена успешно для '{path_str}'."); return True
        else: logging.warning(f"Автоматическое подключение не реализовано для {sys.platform}."); return False
    except (subprocess.CalledProcessError, FileNotFoundError) as e: logging.error(f"Не удалось подключить сетевой диск '{path_str}': {e}"); return False

def calculate_file_hash(file_path):
    hasher = HASH_ALGORITHM()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(READ_BUFFER_SIZE): hasher.update(chunk)
        return hasher.hexdigest()
    except (IOError, PermissionError) as e: logging.error(f"Не удалось прочитать файл {file_path}: {e}"); return None

def get_files_map(directory, exclude_patterns=None, stop_event=None, comparison_mode='accurate', use_parallel=False):
    files_map = {}
    root_path = Path(directory)
    logging.info(f"Сканирование директории: {directory} (Режим: {comparison_mode}, Параллельно: {use_parallel})")
    files_to_process = []
    for file_path in root_path.rglob('*'):
        if stop_event and stop_event.is_set(): raise SyncCancelledError("Сканирование прервано.")
        if file_path.is_file():
            if exclude_patterns and any(fnmatch.fnmatch(file_path.name, pattern) for pattern in exclude_patterns):
                logging.info(f"ИСКЛЮЧЕНИЕ: Файл '{file_path.name}' по шаблону."); continue
            try:
                stat = file_path.stat()
                files_to_process.append({'path': file_path, 'rel_path': file_path.relative_to(root_path), 'size': stat.st_size, 'mtime': stat.st_mtime})
            except FileNotFoundError: continue
    
    def process_file(file_info):
        if stop_event and stop_event.is_set(): return None
        if comparison_mode == 'hybrid': return file_info['rel_path'], (file_info['size'], file_info['mtime'], None)
        file_hash = calculate_file_hash(file_info['path'])
        return (file_info['rel_path'], file_hash) if file_hash else None

    if use_parallel:
        with concurrent.futures.ThreadPoolExecutor() as executor: results = executor.map(process_file, files_to_process)
    else:
        results = map(process_file, files_to_process)
    for result in results:
        if result: rel_path, data = result; files_map[rel_path] = data
    return files_map

def sync_folders(source_dir, dest_dir, no_overwrite, delete_removed, sync_empty_dirs=False, exclude_patterns=None, stop_event=None, comparison_mode='accurate', use_parallel=False, use_staging=False, use_trash=False, progress_callback=None):
    source_path = Path(source_dir); dest_path = Path(dest_dir)
    if not dest_path.exists(): dest_path.mkdir(parents=True, exist_ok=True)
    
    if progress_callback: progress_callback('overall', 0, 1, "Сканирование источника...")
    source_files = get_files_map(source_dir, exclude_patterns, stop_event, comparison_mode, use_parallel)
    if progress_callback: progress_callback('overall', 0, 1, "Сканирование назначения...")
    dest_files = get_files_map(dest_dir, exclude_patterns, stop_event, comparison_mode, use_parallel)
    
    stats = {"copied": 0, "updated": 0, "skipped": 0, "deleted": 0, "trashed": 0, "errors": 0, "dirs_created": 0}

    trash_dir = None
    if use_trash and delete_removed:
        trash_dir = dest_path / ".sync_trash" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        trash_dir.mkdir(parents=True, exist_ok=True)

    if sync_empty_dirs:
        for dirpath, _, _ in os.walk(source_dir):
            if stop_event and stop_event.is_set(): raise SyncCancelledError("Прервано на этапе синхронизации папок.")
            relative_dir = Path(dirpath).relative_to(source_path); dest_dir_path = dest_path / relative_dir
            if not dest_dir_path.exists(): logging.info(f"СОЗДАНИЕ ДИРЕКТОРИИ: {relative_dir}"); dest_dir_path.mkdir(); stats["dirs_created"] += 1

    total_files = len(source_files)
    for i, (rel_path, source_data) in enumerate(source_files.items()):
        if stop_event and stop_event.is_set(): raise SyncCancelledError("Прервано на этапе копирования файлов.")
        if progress_callback: progress_callback('overall', i + 1, total_files, f"Проверка: {rel_path}")

        dest_file_path = dest_path / rel_path; needs_update = False; reason = ""
        if rel_path not in dest_files: needs_update = True; reason = "КОПИРОВАНИЕ (новый)"
        else:
            dest_data = dest_files[rel_path]
            if comparison_mode == 'hybrid':
                source_size, source_mtime, _ = source_data; dest_size, dest_mtime, _ = dest_data
                if source_size != dest_size or int(source_mtime) != int(dest_mtime):
                    source_hash = calculate_file_hash(source_path / rel_path)
                    if stop_event and stop_event.is_set(): raise SyncCancelledError("Прервано на этапе хеширования.")
                    dest_hash = calculate_file_hash(dest_path / rel_path)
                    if source_hash != dest_hash: needs_update = True; reason = "ОБНОВЛЕНИЕ (изменен)"
            elif source_data != dest_data: needs_update = True; reason = "ОБНОВЛЕНИЕ (изменен)"
        
        if needs_update:
            if no_overwrite and rel_path in dest_files: logging.warning(f"ПРОПУСК (перезапись отключена): {rel_path}"); stats["skipped"] += 1
            else:
                logging.info(f"{reason}: {rel_path}")
                try:
                    target_path = dest_file_path.with_suffix(dest_file_path.suffix + '.tmp') if use_staging else dest_file_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path / rel_path, target_path)
                    if use_staging: os.rename(target_path, dest_file_path)
                    if "ОБНОВЛЕНИЕ" in reason: stats["updated"] += 1
                    else: stats["copied"] += 1
                except Exception as e: logging.error(f"Ошибка операции с файлом {rel_path}: {e}"); stats["errors"] += 1

    if delete_removed:
        files_to_delete = [p for p in dest_files if p not in source_files]
        total_delete = len(files_to_delete)
        for i, rel_path in enumerate(files_to_delete):
            if stop_event and stop_event.is_set(): raise SyncCancelledError("Прервано на этапе удаления файлов.")
            if progress_callback: progress_callback('overall', i + 1, total_delete, f"Удаление/Перемещение: {rel_path}")
            if use_trash:
                logging.info(f"В КОРЗИНУ: {rel_path}")
                try:
                    trash_file_path = trash_dir / rel_path
                    trash_file_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dest_path / rel_path), str(trash_file_path)); stats["trashed"] += 1
                except Exception as e: logging.error(f"Ошибка перемещения в корзину файла {rel_path}: {e}"); stats["errors"] += 1
            else:
                logging.info(f"УДАЛЕНИЕ: {rel_path}")
                try: (dest_path / rel_path).unlink(); stats["deleted"] += 1
                except Exception as e: logging.error(f"Ошибка удаления файла {rel_path}: {e}"); stats["errors"] += 1
        for dirpath, _, _ in os.walk(dest_path, topdown=False):
            relative_dir = Path(dirpath).relative_to(dest_path)
            source_equivalent = source_path / relative_dir
            if not source_equivalent.exists() and not os.listdir(dirpath):
                if str(relative_dir) != '.':
                    try: logging.info(f"Удаление пустой директории: {dirpath}"); os.rmdir(dirpath)
                    except OSError as e: logging.error(f"Ошибка удаления пустой директории {dirpath}: {e}")
    return stats

def run_sync_session(source, destination, no_overwrite, delete_removed, sync_empty_dirs=False, exclude_patterns=None, source_creds=None, dest_creds=None, stop_event=None, comparison_mode='accurate', use_parallel=False, use_staging=False, use_trash=False, progress_callback=None):
    start_time = datetime.now()
    logging.info("="*50); logging.info("Начало сеанса синхронизации"); logging.info(f"Источник: {source}"); logging.info(f"Назначение: {destination}")
    logging.info(f"Перезапись отключена: {'Да' if no_overwrite else 'Нет'}"); logging.info(f"Удаление лишних файлов: {'Да' if delete_removed else 'Нет'}")
    logging.info(f"Синхронизация пустых папок: {'Да' if sync_empty_dirs else 'Нет'}"); logging.info(f"Исключения: {exclude_patterns if exclude_patterns else 'Нет'}")
    logging.info(f"Режим сравнения: {comparison_mode}"); logging.info(f"Параллельное сканирование: {'Да' if use_parallel else 'Нет'}")
    logging.info(f"Безопасное удаление: {'Да' if use_trash else 'Нет'}"); logging.info(f"Транзакционное копирование: {'Да' if use_staging else 'Нет'}"); logging.info("="*50)
    try:
        if not ensure_path_is_ready(source, source_creds): raise ConnectionError(f"Исходный путь недоступен: {source}")
        if not ensure_path_is_ready(destination, dest_creds): raise ConnectionError(f"Целевой путь недоступен: {destination}")
        stats = sync_folders(source, destination, no_overwrite, delete_removed, sync_empty_dirs, exclude_patterns, stop_event, comparison_mode, use_parallel, use_staging, use_trash, progress_callback)
        duration = datetime.now() - start_time
        summary = (f"✅ *Синхронизация успешно завершена!*\n\n*Источник:* `{source}`\n*Назначение:* `{destination}`\n"
                   f"Время выполнения: `{duration}`\n\n*Статистика:*\n- Скопировано новых: *{stats['copied']}*\n- Обновлено: *{stats['updated']}*\n"
                   f"- Пропущено: *{stats['skipped']}*\n- Удалено (навсегда): *{stats['deleted']}*\n- Удалено (в корзину): *{stats['trashed']}*\n"
                   f"- Создано директорий: *{stats.get('dirs_created', 0)}*\n- Ошибки: *{stats['errors']}*")
        logging.info("\n" + summary.replace('*', '').replace('`', '')); send_telegram_notification(summary)
    except SyncCancelledError as e:
        duration = datetime.now() - start_time
        cancel_message = f"🟡 *Синхронизация прервана пользователем!*\n\nПроцесс был остановлен после `{duration}`.\nСообщение: `{e}`"
        logging.warning(cancel_message.replace('*', '').replace('`', '')); send_telegram_notification(cancel_message)
        raise e
    except Exception as e:
        duration = datetime.now() - start_time
        error_message = (f"❌ *ОШИБКА СИНХРОНИЗАЦИИ!*\n\nПроизошла критическая ошибка: `{e}`\n"
                         f"Время выполнения до сбоя: `{duration}`\n\nПодробности смотрите в лог-файле: `{LOG_FILE}`")
        logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True); send_telegram_notification(error_message)
        raise e