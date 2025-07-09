import argparse
import sys
import configparser
import sync_logic

def main():
    parser = argparse.ArgumentParser(
        description="Синхронизация файлов. Можно использовать либо прямые аргументы, либо файл задачи.",
        epilog=f"Лог выполнения будет сохранен в файл {sync_logic.LOG_FILE}."
    )
    parser.add_argument("source", nargs='?', default=None, help="Исходная директория.")
    parser.add_argument("destination", nargs='?', default=None, help="Целевая директория.")
    parser.add_argument("--job", help="Путь к файлу задачи (.ini) с настройками синхронизации.")
    parser.add_argument("--no-overwrite", action="store_true", help="Отключить перезапись.")
    parser.add_argument("--delete-removed", action="store_true", help="Удалять лишние файлы.")
    parser.add_argument("--sync-empty-dirs", action="store_true", help="Синхронизировать пустые директории.")
    parser.add_argument("--exclude", nargs='+', help="Список шаблонов для исключения файлов (например, *.log *.tmp).")
    
    args = parser.parse_args()
    sync_logic.setup_logging()

    if args.job:
        config = configparser.ConfigParser()
        try:
            if not config.read(args.job, encoding='utf-8'):
                raise FileNotFoundError(f"Файл задачи не найден: {args.job}")
            
            job_section = config['SyncJob']
            source = job_section['source']
            destination = job_section['destination']
            no_overwrite = job_section.getboolean('no_overwrite', fallback=args.no_overwrite)
            delete_removed = job_section.getboolean('delete_removed', fallback=args.delete_removed)
            sync_empty_dirs = job_section.getboolean('sync_empty_dirs', fallback=args.sync_empty_dirs)
            
            exclude_str = job_section.get('exclude', fallback='')
            exclude_patterns = [p.strip() for p in exclude_str.split(',') if p.strip()]
            if args.exclude:
                exclude_patterns = args.exclude
            
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
        source_creds, dest_creds = None, None
    else:
        parser.error("Необходимо указать либо 'source' и 'destination', либо опцию '--job'.")

    try:
        sync_logic.run_sync_session(source, destination, no_overwrite, delete_removed, sync_empty_dirs, exclude_patterns, source_creds, dest_creds)
    except Exception:
        sys.exit(1)

if __name__ == "__main__":
    main()