"""Базовий клас для ребра графу (посилання між сторінками) - Pydantic модель.

Економія: ~500-700 bytes на edge при використанні LightEdge замість Edge.
При 100k edges: ~50-70 MB економії RAM.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field



@dataclass(slots=True)
class LightEdge:
    """
    
    Використовує __slots__ для економії ~100 bytes per object.
    Зберігає мінімум даних для відновлення Edge при потребі.
    
    Особливості:
    - source_id та target_id як strings (не UUID об'єкти)
    - anchor_hash замість full anchor_text string (~50-200 bytes економія)
    - link_type_bits як бітова маска замість List[str] (~50 bytes економія)
    
    Бітові флаги для link_type:
    - INTERNAL = 1   (internal link)
    - EXTERNAL = 2   (external link) 
    - DEEPER = 4     (deeper depth)
    - SHALLOWER = 8  (shallower depth)
    - SAME_DEPTH = 16 (same depth)
    - NOFOLLOW = 32  (rel=nofollow)
    - SPONSORED = 64 (rel=sponsored)
    - UGC = 128      (rel=ugc)
    
    Розмір в RAM: ~80-120 bytes (замість ~500-1000 bytes для Edge)
    
    Example:
        >>> light_edge = LightEdge(
        ...     source_id="abc123",
        ...     target_id="def456", 
        ...     anchor_hash=hash("Click here"),
        ...     link_type_bits=LightEdge.INTERNAL | LightEdge.DEEPER
        ... )
        >>> # Перевірка типу посилання
        >>> if light_edge.is_internal():
        ...     print("Internal link")
    """
    source_id: str
    target_id: str
    anchor_hash: int = 0  # hash(anchor_text) замість full string
    link_type_bits: int = 0  # Бітова маска замість List[str]
    
    # Бітові флаги для link_type
    INTERNAL = 1
    EXTERNAL = 2
    DEEPER = 4
    SHALLOWER = 8
    SAME_DEPTH = 16
    NOFOLLOW = 32
    SPONSORED = 64
    UGC = 128
    
    # Redirect flag
    WAS_REDIRECT = 256
    
    def is_internal(self) -> bool:
        """Чи є посилання internal."""
        return bool(self.link_type_bits & self.INTERNAL)
    
    def is_external(self) -> bool:
        """Чи є посилання external."""
        return bool(self.link_type_bits & self.EXTERNAL)
    
    def is_deeper(self) -> bool:
        """Чи є посилання на глибший рівень."""
        return bool(self.link_type_bits & self.DEEPER)
    
    def is_nofollow(self) -> bool:
        """Чи має посилання rel=nofollow."""
        return bool(self.link_type_bits & self.NOFOLLOW)
    
    def is_redirect(self) -> bool:
        """Чи представляє edge HTTP редірект."""
        return bool(self.link_type_bits & self.WAS_REDIRECT)
    
    @classmethod
    def from_edge(cls, edge: 'Edge') -> 'LightEdge':
        """
        Конвертує Edge в LightEdge.
        
        Args:
            edge: Edge об'єкт для конвертації
            
        Returns:
            LightEdge з мінімальними даними
        """
        # Обчислюємо anchor_hash
        anchor_text = edge.get_meta_value("anchor_text", "")
        anchor_hash = hash(anchor_text) if anchor_text else 0
        
        # Конвертуємо link_type list в бітову маску
        link_type_bits = 0
        link_types = edge.get_meta_value("link_type", [])
        
        type_map = {
            "internal": cls.INTERNAL,
            "external": cls.EXTERNAL,
            "deeper": cls.DEEPER,
            "shallower": cls.SHALLOWER,
            "same_depth": cls.SAME_DEPTH,
            "nofollow": cls.NOFOLLOW,
            "sponsored": cls.SPONSORED,
            "ugc": cls.UGC,
        }
        
        for lt in link_types:
            lt_lower = lt.lower() if isinstance(lt, str) else str(lt).lower()
            if lt_lower in type_map:
                link_type_bits |= type_map[lt_lower]
        
        # Redirect flag
        if edge.is_redirect():
            link_type_bits |= cls.WAS_REDIRECT
        
        return cls(
            source_id=edge.source_node_id,
            target_id=edge.target_node_id,
            anchor_hash=anchor_hash,
            link_type_bits=link_type_bits,
        )
    
    def to_tuple(self) -> tuple:
        """
        Конвертує в tuple для efficient storage.
        
        Returns:
            Tuple (source_id, target_id, anchor_hash, link_type_bits)
        """
        return (self.source_id, self.target_id, self.anchor_hash, self.link_type_bits)
    
    @classmethod
    def from_tuple(cls, data: tuple) -> 'LightEdge':
        """
        Створює LightEdge з tuple.
        
        Args:
            data: Tuple (source_id, target_id, anchor_hash, link_type_bits)
            
        Returns:
            LightEdge об'єкт
        """
        return cls(
            source_id=data[0],
            target_id=data[1],
            anchor_hash=data[2] if len(data) > 2 else 0,
            link_type_bits=data[3] if len(data) > 3 else 0,
        )


# ============ ORIGINAL EDGE CLASS ============


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
    
    def to_light_edge(self) -> 'LightEdge':
        """
        
        Returns:
            LightEdge з мінімальними даними
        """
        return LightEdge.from_edge(self)

    def __repr__(self):
        redirect_marker = " [REDIRECT]" if self.is_redirect() else ""
        return f"Edge(from={self.source_node_id[:8]}... to={self.target_node_id[:8]}...{redirect_marker})"


__all__ = ['Edge', 'LightEdge']
