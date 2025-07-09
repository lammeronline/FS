import argparse
import sys
import sync_logic

def main():
    parser = argparse.ArgumentParser(
        description="Синхронизация файлов между двумя директориями (локальными или сетевыми).",
        epilog=f"Лог выполнения будет сохранен в файл {sync_logic.LOG_FILE}."
    )
    parser.add_argument("source", help="Исходная директория.")
    parser.add_argument("destination", help="Целевая директория.")
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Отключить перезапись существующих файлов, даже если они отличаются."
    )
    parser.add_argument(
        "--delete-removed",
        action="store_true",
        help="Удалять из целевой директории файлы, которых нет в исходной."
    )
    args = parser.parse_args()

    sync_logic.setup_logging()

    try:
        sync_logic.run_sync_session(args.source, args.destination, args.no_overwrite, args.delete_removed)
    except Exception:
        sys.exit(1)

if __name__ == "__main__":
    main()