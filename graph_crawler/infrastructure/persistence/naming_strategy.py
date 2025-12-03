"""Strategy Pattern для іменування графів (Repository Pattern SRP)."""

import re
from datetime import datetime
from pathlib import Path
from typing import List


class GraphNamingStrategy:
    """
    Відповідає тільки за іменування графів.

        Repository Pattern порушував SRP - містив логіку збереження/завантаження
        ТА логіку іменування файлів. Тепер це розділено:
        - GraphRepository - збереження/завантаження даних
        - GraphNamingStrategy - формування імен файлів

        Це покращує:
        - Тестованість (можна тестувати іменування окремо)
        - Гнучкість (можна змінити схему іменування без зміни репозиторію)
        - Читабельність (кожен клас має одну відповідальність)

        Підтримувані схеми іменування:
        - timestamp: name_2025-01-15_14-30-00
        - date_only: name_2025-01-15
        - uuid: name_a1b2c3d4

        Example:
            >>> strategy = GraphNamingStrategy()
            >>> full_name = strategy.generate_name('mysite_scan')
            'mysite_scan_2025-01-15_14-30-00'
            >>>
            >>> base_name = strategy.extract_base_name('mysite_scan_2025-01-15_14-30-00')
            'mysite_scan'
    """

    def __init__(self, scheme: str = "timestamp"):
        """
        Ініціалізує naming strategy.

        Args:
            scheme: Схема іменування ('timestamp', 'date_only', 'uuid')
        """
        self.scheme = scheme

    def generate_name(self, base_name: str) -> str:
        """
        Генерує повне ім'я графа з унікальним суфіксом.

        Args:
            base_name: Базове ім'я графа (без суфікса)

        Returns:
            Повне ім'я графа з суфіксом

        Example:
            >>> strategy = GraphNamingStrategy('timestamp')
            >>> strategy.generate_name('mysite')
            'mysite_2025-01-15_14-30-00'
        """
        if self.scheme == "timestamp":
            suffix = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            return f"{base_name}_{suffix}"
        elif self.scheme == "date_only":
            suffix = datetime.now().strftime("%Y-%m-%d")
            return f"{base_name}_{suffix}"
        elif self.scheme == "uuid":
            import uuid

            suffix = str(uuid.uuid4())[:8]
            return f"{base_name}_{suffix}"
        else:
            raise ValueError(f"Unknown naming scheme: {self.scheme}")

    def extract_base_name(self, full_name: str) -> str:
        """
        Витягує базове ім'я з повного імені (видаляє timestamp/uuid).

        Args:
            full_name: Повне ім'я графа

        Returns:
            Базове ім'я графа

        Example:
            >>> strategy = GraphNamingStrategy()
            >>> strategy.extract_base_name('mysite_2025-01-15_14-30-00')
            'mysite'
            >>> strategy.extract_base_name('mysite_scan_2025-01-15')
            'mysite_scan'
        """
        # Патерни для різних схем
        patterns = [
            r"_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$",  # timestamp: _2025-01-15_14-30-00
            r"_\d{4}-\d{2}-\d{2}$",  # date_only: _2025-01-15
            r"_[0-9a-f]{8}$",  # uuid: _a1b2c3d4
        ]

        for pattern in patterns:
            match = re.search(pattern, full_name)
            if match:
                return full_name[: match.start()]

        # Якщо не знайдено суфікс, повертаємо як є
        return full_name

    def find_versions(self, base_name: str, files: List[Path]) -> List[str]:
        """
        Знаходить всі версії графа з заданим базовим ім'ям.

        Args:
            base_name: Базове ім'я графа
            files: Список файлів для пошуку

        Returns:
            Список повних імен (сортовані по даті, найновіші першими)

        Example:
            >>> files = [Path('mysite_2025-01-15.json'), Path('mysite_2025-01-20.json')]
            >>> strategy = GraphNamingStrategy()
            >>> strategy.find_versions('mysite', files)
            ['mysite_2025-01-20', 'mysite_2025-01-15']
        """
        versions = []
        for file in files:
            file_name = file.stem  # Без розширення
            extracted_base = self.extract_base_name(file_name)
            if extracted_base == base_name:
                versions.append(file_name)

        # Сортуємо в зворотному порядку (найновіші першими)
        versions.sort(reverse=True)
        return versions

    def get_latest_version(self, base_name: str, files: List[Path]) -> str:
        """
        Повертає найновішу версію графа.

        Args:
            base_name: Базове ім'я графа
            files: Список файлів

        Returns:
            Повне ім'я найновішої версії або base_name якщо не знайдено

        Example:
            >>> files = [Path('mysite_2025-01-15.json'), Path('mysite_2025-01-20.json')]
            >>> strategy = GraphNamingStrategy()
            >>> strategy.get_latest_version('mysite', files)
            'mysite_2025-01-20'
        """
        versions = self.find_versions(base_name, files)
        return versions[0] if versions else base_name

    def format_graph_filename(self, full_name: str) -> str:
        """
        Форматує ім'я файла графа.

        Args:
            full_name: Повне ім'я графа

        Returns:
            Ім'я файла з розширенням

        Example:
            >>> strategy = GraphNamingStrategy()
            >>> strategy.format_graph_filename('mysite_2025-01-15')
            'mysite_2025-01-15.json'
        """
        return f"{full_name}.json"

    def format_metadata_filename(self, full_name: str) -> str:
        """
        Форматує ім'я файла метаданих.

        Args:
            full_name: Повне ім'я графа

        Returns:
            Ім'я файла метаданих

        Example:
            >>> strategy = GraphNamingStrategy()
            >>> strategy.format_metadata_filename('mysite_2025-01-15')
            'mysite_2025-01-15.meta.json'
        """
        return f"{full_name}.meta.json"
