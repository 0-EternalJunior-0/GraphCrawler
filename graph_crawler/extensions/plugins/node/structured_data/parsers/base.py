"""Базовий протокол для парсерів мікророзмітки."""

from typing import Any, Dict, List, Protocol, Union, runtime_checkable

from graph_crawler.extensions.plugins.node.structured_data.options import StructuredDataOptions


@runtime_checkable
class BaseParser(Protocol):
    """
    Протокол для парсерів мікророзмітки.

    Консистентно з IDriver, IStorage protocols в domain/interfaces.
    runtime_checkable для isinstance() перевірок.
    """

    @property
    def name(self) -> str:
        """Унікальне ім'я парсера."""
        ...

    def parse(
        self, source: Union[str, Any], options: StructuredDataOptions
    ) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        Парсить джерело.

        Args:
            source: HTML string або parser adapter
            options: Налаштування

        Returns:
            List[Dict] для JSON-LD/Microdata
            Dict[str, str] для OG/Twitter

        Raises:
            ParserError: При помилці парсингу
        """
        ...

    def can_parse(self, source: Union[str, Any]) -> bool:
        """Перевіряє чи може парсити джерело."""
        ...
