import argparse
import sys
import configparser
import sync_logic

def main():
    parser = argparse.ArgumentParser(
        description="Синхронизация файлов. Можно использовать либо прямые аргументы, либо файл задачи.",
        epilog=f"Лог выполнения будет сохранен в файл {sync_logic.LOG_FILE}."
    )
    # Основные аргументы
    parser.add_argument("source", nargs='?', default=None, help="Исходная директория.")
    parser.add_argument("destination", nargs='?', default=None, help="Целевая директория.")
    parser.add_argument("--job", help="Путь к файлу задачи (.ini).")
    
    # Опции синхронизации
    parser.add_argument("--no-overwrite", action="store_true", help="Отключить перезапись.")
    parser.add_argument("--delete-removed", action="store_true", help="Удалять лишние файлы.")
    parser.add_argument("--sync-empty-dirs", action="store_true", help="Синхронизировать пустые директории.")
    parser.add_argument("--exclude", nargs='+', help="Список шаблонов для исключения файлов (например, *.log *.tmp).")

    # Опции надежности
    parser.add_argument("--use-staging", action="store_true", help="Использовать транзакционное копирование (надежнее).")
    parser.add_argument("--use-trash", action="store_true", help="Использовать безопасное удаление (в корзину).")
    
    # Опции производительности
    parser.add_argument("--comparison-mode", choices=['accurate', 'hybrid'], default=None, help="Режим сравнения файлов: accurate или hybrid.")
    parser.add_argument("--parallel", action="store_true", help="Использовать параллельное сканирование.")

    # Сетевые опции
    parser.add_argument("--source-user", help="Имя пользователя для исходного сетевого ресурса.")
    parser.add_argument("--source-pass", help="Пароль для исходного сетевого ресурса. ВНИМАНИЕ: будет виден в истории команд!")
    parser.add_argument("--dest-user", help="Имя пользователя для целевого сетевого ресурса.")
    parser.add_argument("--dest-pass", help="Пароль для целевого сетевого ресурса. ВНИМАНИЕ: будет виден в истории команд!")

    args = parser.parse_args()
    sync_logic.setup_logging()

    if args.job:
        config = configparser.ConfigParser()
        try:
            if not config.read(args.job, encoding='utf-8'):
                raise FileNotFoundError(f"Файл задачи не найден: {args.job}")
            
            job = config['SyncJob']
            source = job.get('source')
            destination = job.get('destination')
            no_overwrite = job.getboolean('no_overwrite', fallback=args.no_overwrite)
            delete_removed = job.getboolean('delete_removed', fallback=args.delete_removed)
            sync_empty_dirs = job.getboolean('sync_empty_dirs', fallback=args.sync_empty_dirs)
            
            exclude_str = job.get('exclude', '')
            exclude_patterns = [p.strip() for p in exclude_str.split(',') if p.strip()] if exclude_str else (args.exclude or [])
            
            comparison_mode = job.get('comparison_mode', fallback=args.comparison_mode or 'accurate')
            use_parallel = job.getboolean('use_parallel', fallback=args.parallel)
            use_staging = job.getboolean('use_staging', fallback=args.use_staging)
            use_trash = job.getboolean('use_trash', fallback=args.use_trash)
            
            source_creds = dict(config.items('SourceNetCreds')) if config.has_section('SourceNetCreds') else None
            dest_creds = dict(config.items('DestNetCreds')) if config.has_section('DestNetCreds') else None
        except (configparser.Error, KeyError, FileNotFoundError) as e:
            print(f"Ошибка чтения файла задачи '{args.job}': {e}", file=sys.stderr)
            sys.exit(1)
            
    elif args.source and args.destination:
        source = args.source
        destination = args.destination
        no_overwrite = args.no_overwrite
        delete_removed = args.delete_removed
        sync_empty_dirs = args.sync_empty_dirs
        exclude_patterns = args.exclude
        comparison_mode = args.comparison_mode or 'accurate'
        use_parallel = args.parallel
        use_staging = args.use_staging
        use_trash = args.use_trash
        source_creds = {'user': args.source_user, 'password': args.source_pass} if args.source_user and args.source_pass else None
        dest_creds = {'user': args.dest_user, 'password': args.dest_pass} if args.dest_user and args.dest_pass else None
    else:
        parser.error("Необходимо указать 'source' и 'destination', либо опцию '--job'.")

    try:
        sync_logic.run_sync_session(
            source, destination, no_overwrite, delete_removed, sync_empty_dirs, 
            exclude_patterns, source_creds, dest_creds, None, 
            comparison_mode, use_parallel, use_staging, use_trash
        )
    except Exception as e:
        # Теперь мы печатаем ошибку в консоль перед выходом!
        print(f"\nКРИТИЧЕСКАЯ ОШИБКА: {e}", file=sys.stderr)
        print("Синхронизация прервана. Подробности смотрите в лог-файле.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()