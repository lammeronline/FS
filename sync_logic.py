import os
import sys
import hashlib
import shutil
import logging
import configparser
from pathlib import Path
from datetime import datetime
import requests

# --- Константы ---
LOG_FILE = 'sync_log.txt'
CONFIG_FILE = 'config.ini'
HASH_ALGORITHM = hashlib.sha256
READ_BUFFER_SIZE = 65536  # 64kb

def setup_logging(gui_log_handler=None):
    """
    Настраивает логирование. Может принимать кастомный обработчик для вывода в GUI.
    """
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
        force=True # Для возможности перенастройки
    )

def send_telegram_notification(message):
    """Отправляет сообщение в Telegram, если настроено."""
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

def calculate_file_hash(file_path):
    """Вычисляет хеш-сумму файла."""
    hasher = HASH_ALGORITHM()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(READ_BUFFER_SIZE):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (IOError, PermissionError) as e:
        logging.error(f"Не удалось прочитать файл {file_path}: {e}")
        return None

def get_files_map(directory):
    """Создает словарь {относительный_путь: хеш} для всех файлов в директории."""
    files_map = {}
    root_path = Path(directory)
    if not root_path.is_dir():
        logging.error(f"Директория не найдена: {directory}")
        return None
    logging.info(f"Сканирование директории: {directory}")
    for file_path in root_path.rglob('*'):
        if file_path.is_file():
            relative_path = file_path.relative_to(root_path)
            file_hash = calculate_file_hash(file_path)
            if file_hash:
                files_map[relative_path] = file_hash
    return files_map

def sync_folders(source_dir, dest_dir, no_overwrite, delete_removed):
    """Синхронизирует файлы из исходной директории в целевую."""
    source_path = Path(source_dir)
    dest_path = Path(dest_dir)

    if not source_path.is_dir():
        raise FileNotFoundError(f"Исходная директория не найдена: {source_dir}")

    if not dest_path.exists():
        logging.info(f"Целевая директория не существует. Создание: {dest_dir}")
        dest_path.mkdir(parents=True, exist_ok=True)
    elif not dest_path.is_dir():
        raise NotADirectoryError(f"Целевой путь не является директорией: {dest_dir}")

    source_files = get_files_map(source_path)
    dest_files = get_files_map(dest_path)
    
    stats = {"copied": 0, "updated": 0, "skipped": 0, "deleted": 0, "errors": 0}

    # 1. Копирование и обновление файлов
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

    # 2. Удаление лишних файлов
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
            if not os.listdir(dirpath):
                logging.info(f"Удаление пустой директории: {dirpath}")
                os.rmdir(dirpath)
    return stats

def run_sync_session(source, destination, no_overwrite, delete_removed):
    """Главная функция-обертка для запуска сессии синхронизации."""
    start_time = datetime.now()
    logging.info("="*50)
    logging.info("Начало сеанса синхронизации")
    logging.info(f"Источник: {source}")
    logging.info(f"Назначение: {destination}")
    logging.info(f"Перезапись отключена: {'Да' if no_overwrite else 'Нет'}")
    logging.info(f"Удаление лишних файлов: {'Да' if delete_removed else 'Нет'}")
    logging.info("="*50)

    try:
        stats = sync_folders(source, destination, no_overwrite, delete_removed)
        duration = datetime.now() - start_time
        summary = (
            f"✅ *Синхронизация успешно завершена!*\n\n"
            f"*Источник:* `{source}`\n*Назначение:* `{destination}`\n"
            f"Время выполнения: `{duration}`\n\n*Статистика:*\n"
            f"- Скопировано новых: *{stats['copied']}*\n- Обновлено: *{stats['updated']}*\n"
            f"- Пропущено: *{stats['skipped']}*\n- Удалено: *{stats['deleted']}*\n"
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
        raise e # Поднимаем исключение дальше