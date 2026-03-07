"""Винятки для StructuredData плагіна."""


class StructuredDataError(Exception):
    """Базова помилка для Structured Data плагіна."""
    pass


class ParserError(StructuredDataError):
    """Помилка парсингу мікророзмітки."""

    def __init__(self, parser_name: str, message: str):
        self.parser_name = parser_name
        self.message = message
        super().__init__(f"{parser_name}: {message}")
