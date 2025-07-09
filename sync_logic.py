import os
import sys
import hashlib
import shutil
import logging
import configparser
import subprocess
import fnmatch
from pathlib import Path
from datetime import datetime
import requests

# --- Константы ---
LOG_FILE = 'sync_log.txt'
CONFIG_FILE = 'config.ini'
HASH_ALGORITHM = hashlib.sha256
READ_BUFFER_SIZE = 65536

def setup_logging(gui_log_handler=None):
    handlers = [
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
    if gui_log_handler:
        handlers.append(gui_log_handler)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True
    )

def send_telegram_notification(message):
    config = configparser.ConfigParser()
    if not os.path.exists(CONFIG_FILE):
        logging.warning(f"Файл конфигурации {CONFIG_FILE} не найден. Уведомление не будет отправлено.")
        return
    config.read(CONFIG_FILE, encoding='utf-8')
    if not config.has_section('telegram') or not config.getboolean('telegram', 'enabled', fallback=False):
        logging.info("Отправка уведомлений в Telegram отключена в конфигурации.")
        return
    token = config.get('telegram', 'bot_token', fallback=None)
    chat_id = config.get('telegram', 'chat_id', fallback=None)
    if not token or not chat_id or token == 'YOUR_TELEGRAM_BOT_TOKEN':
        logging.warning("Токен бота или ID чата не настроены в config.ini. Уведомление не будет отправлено.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("Уведомление в Telegram успешно отправлено.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при отправке уведомления в Telegram: {e}")

def ensure_path_is_ready(path_str, net_creds=None):
    if os.path.exists(path_str):
        logging.info(f"Путь '{path_str}' доступен.")
        return True
    
    logging.warning(f"Путь '{path_str}' недоступен. Попытка анализа как сетевого пути...")
    if not path_str.startswith('\\\\'):
        logging.error(f"Путь '{path_str}' не является UNC путем и недоступен.")
        return False
    
    if not net_creds or not net_creds.get('user') or not net_creds.get('password'):
        logging.error(f"Учетные данные для пути '{path_str}' не предоставлены. Невозможно подключиться.")
        return False
        
    user = net_creds['user']
    password = net_creds['password']
    logging.info(f"Попытка подключения к '{path_str}' с пользователем '{user}'...")
    
    try:
        if sys.platform == "win32":
            command = ['net', 'use', path_str, password, f'/user:{user}', '/persistent:no']
            result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='cp866')
            logging.info(f"Команда 'net use' выполнена успешно для '{path_str}'.")
            return True
        else:
            logging.warning(f"Автоматическое подключение сетевых дисков не реализовано для {sys.platform}.")
            return False
    except subprocess.CalledProcessError as e:
        logging.error(f"Не удалось подключить сетевой диск '{path_str}'. Ошибка: {e.stderr}")
        return False
    except FileNotFoundError:
        logging.error("Команда 'net' не найдена. Убедитесь, что вы работаете на Windows.")
        return False

def calculate_file_hash(file_path):
    hasher = HASH_ALGORITHM()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(READ_BUFFER_SIZE):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (IOError, PermissionError) as e:
        logging.error(f"Не удалось прочитать файл {file_path}: {e}")
        return None

def get_files_map(directory, exclude_patterns=None):
    files_map = {}
    root_path = Path(directory)
    logging.info(f"Сканирование директории: {directory}")
    for file_path in root_path.rglob('*'):
        if file_path.is_file():
            if exclude_patterns:
                if any(fnmatch.fnmatch(file_path.name, pattern) for pattern in exclude_patterns):
                    logging.info(f"ИСКЛЮЧЕНИЕ: Файл '{file_path.name}' по шаблону.")
                    continue
            relative_path = file_path.relative_to(root_path)
            file_hash = calculate_file_hash(file_path)
            if file_hash:
                files_map[relative_path] = file_hash
    return files_map

def sync_folders(source_dir, dest_dir, no_overwrite, delete_removed, sync_empty_dirs=False, exclude_patterns=None):
    source_path = Path(source_dir)
    dest_path = Path(dest_dir)

    if not dest_path.exists():
        logging.info(f"Целевая директория не существует. Создание: {dest_dir}")
        dest_path.mkdir(parents=True, exist_ok=True)
    
    source_files = get_files_map(source_path, exclude_patterns)
    dest_files = get_files_map(dest_path, exclude_patterns)
    
    stats = {"copied": 0, "updated": 0, "skipped": 0, "deleted": 0, "errors": 0, "dirs_created": 0}

    if sync_empty_dirs:
        logging.info("Синхронизация структуры директорий...")
        for dirpath, _, _ in os.walk(source_dir):
            relative_dir = Path(dirpath).relative_to(source_path)
            dest_dir_path = dest_path / relative_dir
            if not dest_dir_path.exists():
                logging.info(f"СОЗДАНИЕ ДИРЕКТОРИИ: {relative_dir}")
                dest_dir_path.mkdir()
                stats["dirs_created"] += 1

    for rel_path, source_hash in source_files.items():
        dest_file_path = dest_path / rel_path
        if rel_path not in dest_files:
            logging.info(f"КОПИРОВАНИЕ: {rel_path}")
            try:
                dest_file_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path / rel_path, dest_file_path)
                stats["copied"] += 1
            except (IOError, PermissionError) as e:
                logging.error(f"Ошибка копирования файла {rel_path}: {e}")
                stats["errors"] += 1
        elif source_hash != dest_files[rel_path]:
            if no_overwrite:
                logging.warning(f"ПРОПУСК (перезапись отключена): {rel_path}")
                stats["skipped"] += 1
            else:
                logging.info(f"ОБНОВЛЕНИЕ: {rel_path}")
                try:
                    shutil.copy2(source_path / rel_path, dest_file_path)
                    stats["updated"] += 1
                except (IOError, PermissionError) as e:
                    logging.error(f"Ошибка обновления файла {rel_path}: {e}")
                    stats["errors"] += 1

    if delete_removed:
        for rel_path in dest_files:
            if rel_path not in source_files:
                logging.info(f"УДАЛЕНИЕ: {rel_path}")
                try:
                    (dest_path / rel_path).unlink()
                    stats["deleted"] += 1
                except (IOError, PermissionError) as e:
                    logging.error(f"Ошибка удаления файла {rel_path}: {e}")
                    stats["errors"] += 1
        for dirpath, _, _ in os.walk(dest_path, topdown=False):
            source_equivalent = source_path / Path(dirpath).relative_to(dest_path)
            if not os.path.exists(source_equivalent) and not os.listdir(dirpath):
                 logging.info(f"Удаление лишней пустой директории: {dirpath}")
                 try:
                    os.rmdir(dirpath)
                 except OSError as e:
                    logging.error(f"Ошибка удаления пустой директории {dirpath}: {e}")
    return stats

def run_sync_session(source, destination, no_overwrite, delete_removed, sync_empty_dirs=False, exclude_patterns=None, source_creds=None, dest_creds=None):
    start_time = datetime.now()
    logging.info("="*50)
    logging.info("Начало сеанса синхронизации")
    logging.info(f"Источник: {source}")
    logging.info(f"Назначение: {destination}")
    logging.info(f"Перезапись отключена: {'Да' if no_overwrite else 'Нет'}")
    logging.info(f"Удаление лишних файлов: {'Да' if delete_removed else 'Нет'}")
    logging.info(f"Синхронизация пустых папок: {'Да' if sync_empty_dirs else 'Нет'}")
    logging.info(f"Исключения: {exclude_patterns if exclude_patterns else 'Нет'}")
    logging.info("="*50)

    try:
        if not ensure_path_is_ready(source, source_creds):
            raise ConnectionError(f"Исходный путь недоступен: {source}")
        if not ensure_path_is_ready(destination, dest_creds):
            raise ConnectionError(f"Целевой путь недоступен: {destination}")

        stats = sync_folders(source, destination, no_overwrite, delete_removed, sync_empty_dirs, exclude_patterns)
        duration = datetime.now() - start_time
        summary = (
            f"✅ *Синхронизация успешно завершена!*\n\n"
            f"*Источник:* `{source}`\n*Назначение:* `{destination}`\n"
            f"Время выполнения: `{duration}`\n\n*Статистика:*\n"
            f"- Скопировано новых: *{stats['copied']}*\n- Обновлено: *{stats['updated']}*\n"
            f"- Пропущено: *{stats['skipped']}*\n- Удалено: *{stats['deleted']}*\n"
            f"- Создано директорий: *{stats.get('dirs_created', 0)}*\n"
            f"- Ошибки: *{stats['errors']}*"
        )
        logging.info("\n" + summary.replace('*', '').replace('`', ''))
        send_telegram_notification(summary)

    except Exception as e:
        duration = datetime.now() - start_time
        error_message = (
            f"❌ *ОШИБКА СИНХРОНИЗАЦИИ!*\n\n"
            f"Произошла критическая ошибка: `{e}`\n"
            f"Время выполнения до сбоя: `{duration}`\n\n"
            f"Подробности смотрите в лог-файле: `{LOG_FILE}`"
        )
        logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
        send_telegram_notification(error_message)
        raise e