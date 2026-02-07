"""Базовий клас для ребра графу (посилання між сторінками) - Pydantic модель."""

import uuid
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class Edge(BaseModel):
    """
    Базовий клас для ребра графу (посилання між сторінками) - Pydantic модель.

    Ребро представляє зв'язок між двома вузлами (сторінками).

    Використання Pydantic:
    - Автоматична валідація полів
    - Type safety
    - Автоматична серіалізація/десеріалізація
    - Підтримка кастомних підкласів

    Атрибути:
        source_node_id: ID вузла-джерела
        target_node_id: ID цільового вузла
        edge_id: Унікальний ідентифікатор ребра
        metadata: Додаткові метадані про посилання

    Приклад:
        >>> edge = Edge(source_node_id="node1", target_node_id="node2")
        >>> edge.add_metadata("anchor_text", "Click here")
        >>> data = edge.model_dump()  # Серіалізація
        >>> restored = Edge.model_validate(data)  # Десеріалізація
    """

    # Pydantic fields
    source_node_id: str
    target_node_id: str
    edge_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Pydantic configuration
    model_config = ConfigDict(
        validate_assignment=True,  # Валідація при присвоєнні
    )

    def add_metadata(self, key: str, value: Any):
        """
        Додає метадані до ребра.

        Args:
            key: Ключ метаданих
            value: Значення
        """
        self.metadata[key] = value

    def get_meta_value(self, key: str, default: Any = None) -> Any:
        """
        Отримати значення з metadata за ключем (Law of Demeter wrapper).

        Args:
            key: Ключ метаданих
            default: Значення за замовчуванням

        Returns:
            Значення метаданих або default
        """
        return self.metadata.get(key, default)

    def set_redirect_info(
        self, original_url: str, final_url: str, redirect_chain: list[str]
    ):
        """
        Зберігає інформацію про HTTP редірект в metadata.

        Використовується коли посилання веде на URL який редірить на інший URL.
        Edge буде вести з source на final_url, але metadata міститиме original_url.

        Args:
            original_url: Оригінальний URL посилання (який редірить)
            final_url: Фінальний URL після всіх редіректів
            redirect_chain: Список проміжних URL редіректів

        Examples:
            >>> edge = Edge(source_node_id="page1", target_node_id="page2")
            >>> edge.set_redirect_info(
            ...     original_url="https://example.com/old",
            ...     final_url="https://example.com/new",
            ...     redirect_chain=["https://example.com/old", "https://example.com/temp"]
            ... )
            >>> edge.is_redirect()
            True
            >>> edge.get_original_url()
            'https://example.com/old'
        """
        self.add_metadata("was_redirect", True)
        self.add_metadata("original_url", original_url)
        self.add_metadata("final_url", final_url)
        self.add_metadata("redirect_chain", redirect_chain)

    def is_redirect(self) -> bool:
        """
        Перевіряє чи edge представляє HTTP редірект.

        Returns:
            True якщо edge створений для посилання яке редірить

        Examples:
            >>> edge = Edge(source_node_id="page1", target_node_id="page2")
            >>> edge.set_redirect_info("http://old.com", "http://new.com", [])
            >>> edge.is_redirect()
            True
        """
        return self.get_meta_value("was_redirect", False)

    def get_original_url(self) -> Optional[str]:
        """
        Отримує оригінальний URL посилання (до редіректу).

        Returns:
            Оригінальний URL або None якщо це не редірект

        Examples:
            >>> edge = Edge(source_node_id="page1", target_node_id="page2")
            >>> edge.set_redirect_info("http://old.com", "http://new.com", [])
            >>> edge.get_original_url()
            'http://old.com'
        """
        return self.get_meta_value("original_url")

    def get_redirect_chain(self) -> list[str]:
        """
        Отримує ланцюжок проміжних редіректів.

        Returns:
            Список проміжних URL або порожній список

        Examples:
            >>> edge = Edge(source_node_id="page1", target_node_id="page2")
            >>> edge.set_redirect_info(
            ...     "http://old.com",
            ...     "http://new.com",
            ...     ["http://old.com", "http://temp.com"]
            ... )
            >>> edge.get_redirect_chain()
            ['http://old.com', 'http://temp.com']
        """
        return self.get_meta_value("redirect_chain", [])

    def __repr__(self):
        redirect_marker = " [REDIRECT]" if self.is_redirect() else ""
        return f"Edge(from={self.source_node_id[:8]}... to={self.target_node_id[:8]}...{redirect_marker})"
