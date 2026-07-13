import os
import re
from logging.handlers import TimedRotatingFileHandler


class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Меняем дефисы на точки в стандартном суффиксе (для MIDNIGHT это будет "%Y.%m.%d")
        self.suffix = "%Y.%m.%d"
        # Перекомпилируем регулярное выражение для корректной работы getFilesToDelete()
        self.extMatch = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")

    def rotation_filename(self, default_name):
        """
        Переносит суффикс даты ДО расширения .log
        default_name приходит в формате: /path/to/logs/info.log.2026.07.02
        """
        # Выделяем путь к базовому файлу и суффикс даты
        base_filename = self.baseFilename  # /path/to/logs/info.log
        base, ext = os.path.splitext(
            base_filename
        )  # (/path/to/logs/info, .log)

        # Получаем часть с датой, которая была добавлена в конец
        # Она находится после 'info.log.'
        date_suffix = default_name[len(base_filename) + 1 :]

        # Формируем красивое имя: /path/to/logs/info.2026.07.02.log
        return f"{base}.{date_suffix}{ext}"

    def dest_filename(self, default_name):
        """
        Этот метод необходим для совместимости со старыми версиями Python,
        чтобы getFilesToDelete правильно определял файлы к удалению.
        """
        return self.rotation_filename(default_name)
