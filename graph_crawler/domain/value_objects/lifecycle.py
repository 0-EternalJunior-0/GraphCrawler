"""Життєвий цикл Node - 2 етапи."""

from enum import Enum


class NodeLifecycle(str, Enum):
    """Життєвий цикл Node: URL_STAGE -> HTML_STAGE."""

    # ЕТАП 1: Створення ноди (тільки URL)
    URL_STAGE = "url_stage"

    # ЕТАП 2: Сканування (HTML доступний)
    HTML_STAGE = "html_stage"

    # Не просканована
    NOT_SCANNED = "not_scanned"


class NodeLifecycleError(Exception):
    """Помилка використання методу не на тому етапі життєвого циклу."""

    pass
