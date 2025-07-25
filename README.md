<p align="center">
  <img src="assets/icon.png" alt="File Synchronizer Icon" width="128"/>
</p>

<h1 align="center">File Synchronizer - Версия 3.0</h1>

<p align="center">
  Надежный и многофункциональный инструмент для однонаправленной синхронизации файлов с графическим интерфейсом и поддержкой командной строки.
  <br/>
  <br/>
  <a href="https://github.com/lammeronline/FS/actions/workflows/build.yml">
    <img alt="Build Status" src="https://github.com/lammeronline/FS/actions/workflows/build.yml/badge.svg">
  </a>
</p>

---

**File Synchronizer** — это решение для надежного резервного копирования и синхронизации данных между двумя расположениями. Программа предлагает как простой графический интерфейс (GUI) для повседневных задач, так и мощный интерфейс командной строки (CLI) для автоматизации и скриптов.

## Ключевые возможности

*   🖥️ **Два режима работы**: Интуитивный графический интерфейс (GUI) и мощный интерфейс командной строки (CLI).
*   🔄 **Импорт/Экспорт задач**: Настройте синхронизацию в GUI, экспортируйте ее в файл, а затем импортируйте на другом компьютере или используйте для автоматизации.
*   🛡️ **Надежность и безопасность**:
    *   **Транзакционное копирование**: Защищает файлы от повреждения при сбоях во время копирования.
    *   **Безопасное удаление**: Перемещает удаляемые файлы в "корзину" `.sync_trash` вместо перманентного удаления.
*   ⚡ **Оптимизация производительности**:
    *   **Гибридный режим сравнения**: Быстрая проверка по дате и размеру файла с последующей проверкой по хешу только для измененных файлов.
    *   **Параллельное сканирование**: Ускоряет вычисление хешей на многоядерных процессорах и быстрых дисках.
*   🛑 **Безопасная остановка**: Возможность в любой момент прервать процесс или безопасно закрыть приложение во время синхронизации.
*   🌐 **Поддержка сети**: Работа с сетевыми UNC-путями (`\\server\share`) с возможностью указания учетных данных.
*   🔐 **Сохранение паролей**: Опциональное безопасное (обфусцированное) сохранение паролей для сетевых ресурсов.
*   🚫 **Фильтрация и исключения**: Возможность исключать файлы и папки из синхронизации по маске (`*.log`, `cache/*`).
*   📊 **Индикатор прогресса**: Наглядное отображение общего хода выполнения синхронизации.
*   💬 **Telegram-уведомления**: Получайте отчеты об успешном завершении или ошибках прямо в Telegram.
*   📦 **Автоматическая сборка**: Проект автоматически собирается в готовый `.exe` файл с помощью GitHub Actions.

## Загрузка и Установка

Самый простой способ начать работу — скачать готовую сборку для Windows.

1.  Перейдите на вкладку **[Actions](https://github.com/lammeronline/FS/actions)** в этом репозитории.
2.  В списке слева выберите "Build Windows Executable".
3.  Нажмите на самый верхний успешный запуск в списке.
4.  Внизу страницы, в разделе **"Artifacts"**, скачайте архив `FileSynchronizer-Windows`.
5.  Распакуйте архив в удобное для вас место. Готово!

## Рабочий процесс и автоматизация

Эта программа позволяет легко автоматизировать рутинные задачи с помощью Планировщика заданий Windows или других средств.

### Шаг 1: Настройте и экспортируйте задачу

1.  **Настройте в GUI**: Откройте `FileSynchronizer_GUI.exe` и настройте все параметры (пути, опции, исключения, сетевые данные) так, как вам нужно для вашей задачи.
2.  **Экспортируйте задачу**: Перейдите в меню `Файл -> Экспорт задачи...` и сохраните вашу конфигурацию в файл, например, `daily_backup.ini`.
    > ⚠️ **Предупреждение о безопасности**: Если вы ввели пароли для сетевых ресурсов, они будут сохранены в этом файле в **открытом виде**. Убедитесь, что этот файл хранится в безопасном месте с ограниченным доступом.

### Шаг 2 (Опционально): Импортируйте задачу

Вы можете перенести этот `.ini` файл на другой компьютер и импортировать его через меню `Файл -> Импорт задачи...`, чтобы мгновенно применить все сохраненные настройки.

### Шаг 3: Автоматизируйте запуск

Создайте задачу в Планировщике заданий Windows, которая будет выполнять следующую команду:

```cmd
C:\path\to\your\app\FileSynchronizer_CLI.exe --job "C:\path\to\your\tasks\daily_backup.ini"
```

Это идеальный способ объединить удобство настройки в GUI и мощь автоматизации CLI.

<details>
<summary><strong>Подробное руководство по использованию</strong></summary>

### Графический интерфейс (GUI)
-   **Пути**: Укажите исходную и целевую папки.
-   **Сетевой путь**: Если для доступа к папке (`\\server\share`) нужны учетные данные, установите галочку "Сетевой путь" **рядом** с соответствующим полем. Появятся поля для ввода имени пользователя и пароля, а также опция "Показать пароль".
-   **Запомнить пароли**: Если вы хотите сохранить учетные данные для будущих запусков, установите галочку "Запомнить пароли".
-   **Опции**: Установите флажки для перезаписи, удаления и синхронизации пустых папок.
-   **Настройки надежности**:
    -   `Безопасное удаление`: Перемещает удаляемые файлы в скрытую папку `.sync_trash`. Рекомендуется держать включенной.
    -   `Транзакционное копирование`: Защищает файлы от повреждения при сбоях. Рекомендуется держать включенной.
-   **Исключения**: Введите шаблоны для исключения файлов через запятую.
-   **Меню "Файл"**:
    -   `Импорт/Экспорт задачи`: Загрузка и сохранение конфигураций для CLI.
    -   `Настройки`: Управление уведомлениями Telegram и параметрами производительности.
-   **Кнопка "Начать синхронизацию"**: Запускает процесс. Во время работы превращается в кнопку "Остановить".

> **Примечание о безопасности**: Сохраненные в интерфейсе пароли хранятся в обфусцированном (но не зашифрованном) виде. Используйте эту функцию на свой страх и риск на доверенных компьютерах.

### Командная строка (CLI)

-   **Синтаксис:** `FileSynchronizer_CLI.exe [source] [destination] [options]`
-   **Или с файлом задачи:** `FileSynchronizer_CLI.exe --job <path_to_job.ini>`

| Аргумент | Описание |
| :--- | :--- |
| `source`, `destination`| Исходная и целевая директории. |
| `--job` | Путь к файлу задачи `.ini` (игнорирует другие аргументы). |
| `--no-overwrite` | Не перезаписывать измененные файлы. |
| `--delete-removed`| Удалять лишние файлы в назначении. |
| `--sync-empty-dirs`| Синхронизировать пустые папки. |
| `--use-trash` | Включает безопасное удаление в корзину. |
| `--use-staging` | Включает транзакционное копирование. |
| `--exclude` | Шаблоны для исключения (e.g., `*.log` `*.tmp`). |
| `--source-user`, `--source-pass` | Учетные данные для исходного UNC-пути. |
| `--dest-user`, `--dest-pass` | Учетные данные для целевого UNC-пути. |
| `--comparison-mode`| Режим сравнения: `accurate` (по-умолчанию) или `hybrid`. |
| `--parallel` | Включает параллельное сканирование. |

</details>

<details>
<summary><strong>Установка для разработчиков</strong></summary>

1.  Клонируйте репозиторий:
    ```bash
    git clone https://github.com/lammeronline/FS.git
    cd FS
    ```
2.  Создайте и активируйте виртуальное окружение:
    ```bash
    python -m venv venv
    # Windows:
    venv\Scripts\activate
    # Linux/macOS:
    source venv/bin/activate
    ```
3.  Установите зависимости:
    ```bash
    pip install -r requirements.txt
    ```
</details>

## Лицензия

Распространяется под лицензией MIT.