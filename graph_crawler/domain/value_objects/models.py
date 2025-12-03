"""Pydantic моделі для типізації даних.

Цей модуль містить всі Pydantic моделі для заміни Dict[str, Any].
Забезпечує type safety та валідацію даних.
"""

import re
import warnings
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ==================== EDGE CREATION STRATEGIES ====================


class EdgeCreationStrategy(str, Enum):
    """
    Стратегії створення edges в графі.

    Дозволяє контролювати які edges створюються для економії пам'яті
    та зменшення noise в графі (популярні сторінки як header/footer).

    Значення:
        ALL: Створювати всі edges (default поведінка).
             Кожне посилання = edge. Може бути багато edges на одну ноду.

        NEW_ONLY: Edge створюється ТІЛЬКИ коли нода знайдена ВПЕРШЕ.
             Кожна нода має рівно 1 incoming edge (від того хто знайшов першим).
             Результат: edges == nodes (мінус root).
             Ідеально для побудови дерева без дублікатів.

        MAX_IN_DEGREE: Не створювати edge якщо target має >= N incoming edges.
             Захист від "популярних" сторінок (header/footer посилання).

        SAME_DEPTH_ONLY: Edges тільки між нодами на одному рівні глибини.
             Горизонтальні зв'язки (siblings).

        DEEPER_ONLY: Edges тільки на глибші рівні (source.depth < target.depth).
             Без посилань назад на батьківські сторінки.

        FIRST_ENCOUNTER_ONLY: Тільки перший edge на кожен URL.
             Схоже на NEW_ONLY, але дозволяє edge якщо нода вже існує
             але ще не має incoming edges.

    Порівняння NEW_ONLY vs FIRST_ENCOUNTER_ONLY:
        - NEW_ONLY: edge тільки якщо нода створена В ЦЕЙ МОМЕНТ
        - FIRST_ENCOUNTER_ONLY: edge якщо нода не має жодного incoming edge

        Різниця: якщо нода була створена раніше (через scheduler) але ще не
        має edges, FIRST_ENCOUNTER_ONLY створить edge, NEW_ONLY - ні.

    Examples:
        >>> # Мінімальний граф (дерево): edges == nodes - 1
        >>> strategy = EdgeCreationStrategy.NEW_ONLY

        >>> # Не створювати edges на популярні сторінки (header/footer)
        >>> strategy = EdgeCreationStrategy.MAX_IN_DEGREE

        >>> # Тільки вперед (не повертатись на батьківські сторінки)
        >>> strategy = EdgeCreationStrategy.DEEPER_ONLY
    """

    ALL = "all"
    NEW_ONLY = "new_only"
    MAX_IN_DEGREE = "max_in_degree"
    SAME_DEPTH_ONLY = "same_depth_only"
    DEEPER_ONLY = "deeper_only"
    FIRST_ENCOUNTER_ONLY = "first_encounter_only"


# ==================== DRIVER MODELS ====================


class FetchResponse(BaseModel):
    """Відповідь від драйвера після завантаження сторінки.

    Замінює Dict[str, Any] для type safety.

    Атрибути:
        url: Оригінальний URL запиту
        html: HTML контент (або None при помилці)
        status_code: HTTP статус код (або None при помилці)
        headers: HTTP заголовки
        error: Повідомлення про помилку (або None при успіху)
        final_url: Фінальний URL після редіректів (або None якщо редіректів не було)
        redirect_chain: Список проміжних URL редіректів (порожній якщо редіректів не було)

    Examples:
        >>> response = FetchResponse(
        ...     url="https://example.com",
        ...     html="<html>...</html>",
        ...     status_code=200,
        ...     headers={"content-type": "text/html"},
        ...     error=None
        ... )
        >>> if response.error:
        ...     print(f"Error: {response.error}")
        >>> else:
        ...     print(f"Success: {response.status_code}")

        >>> # Приклад з редіректом
        >>> response = FetchResponse(
        ...     url="https://example.com/old-page",
        ...     html="<html>...</html>",
        ...     status_code=200,
        ...     final_url="https://example.com/new-page",
        ...     redirect_chain=["https://example.com/old-page", "https://example.com/intermediate"]
        ... )
        >>> if response.is_redirect:
        ...     print(f"Redirected: {response.url} -> {response.final_url}")
    """

    url: str
    html: Optional[str] = None
    status_code: Optional[int] = None
    headers: dict[str, str] = Field(default_factory=dict)
    error: Optional[str] = None

    # Redirect information (заповнюється всіма драйверами)
    final_url: Optional[str] = None
    redirect_chain: list[str] = Field(default_factory=list)

    @property
    def is_success(self) -> bool:
        """Перевіряє чи запит був успішним."""
        return self.error is None and self.html is not None

    @property
    def is_ok(self) -> bool:
        """Перевіряє чи HTTP статус код 2xx."""
        return self.status_code is not None and 200 <= self.status_code < 300

    @property
    def is_redirect(self) -> bool:
        """
        Перевіряє чи був HTTP редірект.

        Returns:
            True якщо final_url відрізняється від original url

        Examples:
            >>> response = FetchResponse(url="http://old.com", final_url="http://new.com")
            >>> response.is_redirect
            True

            >>> response = FetchResponse(url="http://example.com", final_url=None)
            >>> response.is_redirect
            False
        """
        return self.final_url is not None and self.final_url != self.url

    model_config = ConfigDict(frozen=False)


# ==================== FILTER MODELS ====================


class DomainFilterConfig(BaseModel):
    """Конфігурація фільтра доменів.

    Замінює Dict[str, Any] для type safety.

    allowed_domains підтримує спеціальні патерни:
      * '*' або AllowedDomains.ALL - куди завгодно
      * 'domain' - тільки основний домен
      * 'subdomains' - тільки субдомени
      * 'domain+subdomains' - домен + субдомени (DEFAULT)

    Атрибути:
        base_domain: Базовий домен для порівняння
        allowed_domains: Список дозволених доменів + спеціальні патерни
        blocked_domains: Список заблокованих доменів

    Examples:
        >>> # Спеціальні патерни
        >>> config = DomainFilterConfig(
        ...     base_domain="company.com",
        ...     allowed_domains=["domain+subdomains"]  # DEFAULT
        ... )

        >>> # Wildcard режим
        >>> config = DomainFilterConfig(
        ...     base_domain="company.com",
        ...     allowed_domains=["*"]
        ... )

        >>> # Комбінація патернів + конкретних доменів
        >>> config = DomainFilterConfig(
        ...     base_domain="company.com",
        ...     allowed_domains=["domain+subdomains", "partner.com"]
        ... )
    """

    base_domain: str
    allowed_domains: list[str] = Field(
        default_factory=lambda: ["domain+subdomains"],
        description="Дозволені домени + спеціальні патерни ('*', 'domain', 'subdomains', 'domain+subdomains')",
    )
    blocked_domains: list[str] = Field(default_factory=list)

    def is_wildcard_allowed(self) -> bool:
        """
        Перевіряє чи дозволено сканувати куди завгодно.

        Returns:
            True якщо '*' в allowed_domains

        Example:
            >>> config = DomainFilterConfig(
            ...     base_domain="company.com",
            ...     allowed_domains=["*"]
            ... )
            >>> config.is_wildcard_allowed()
            True
        """
        return "*" in self.allowed_domains

    def has_special_patterns(self) -> bool:
        """
        Перевіряє чи є спеціальні патерни в allowed_domains.

        Returns:
            True якщо є хоча б один спеціальний патерн

        Example:
            >>> config = DomainFilterConfig(
            ...     base_domain="company.com",
            ...     allowed_domains=["domain+subdomains", "partner.com"]
            ... )
            >>> config.has_special_patterns()
            True
        """
        from graph_crawler.application.use_cases.crawling.filters.domain_patterns import (
            AllowedDomains,
        )

        special_patterns = AllowedDomains.get_special_patterns()
        return any(domain in special_patterns for domain in self.allowed_domains)

    model_config = ConfigDict(frozen=False)


class PathFilterConfig(BaseModel):
    """Конфігурація фільтра шляхів URL.

    Замінює Dict[str, Any] для type safety.

    Атрибути:
        excluded_patterns: Список regex патернів для виключення
        included_patterns: Список regex патернів для включення

    Examples:
        >>> config = PathFilterConfig(
        ...     excluded_patterns=[r'/admin/.*', r'/api/.*'],
        ...     included_patterns=[r'/products/.*']
        ... )
    """

    excluded_patterns: list[str] = Field(default_factory=list)
    included_patterns: list[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=False)


# ==================== METADATA MODELS ====================


class PageMetadata(BaseModel):
    """Метадані сторінки.

    Опціональна модель для структурованих метаданих.

    Атрибути:
        title: Заголовок сторінки
        description: Опис сторінки
        keywords: Ключові слова
        h1: Перший H1 заголовок
        author: Автор (якщо вказано)
        language: Мова контенту
        canonical: Canonical URL
    """

    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    h1: Optional[str] = None
    author: Optional[str] = None
    language: Optional[str] = None
    canonical: Optional[str] = None

    model_config = ConfigDict(frozen=False)


# ==================== GRAPH STORAGE MODELS ====================


class GraphMetadata(BaseModel):
    """
    Модель для метаданих збереженого графа.

    Використовується для зберігання інформації про граф без завантаження самого графа.
    Замінює словник для типізації та валідації.

    Атрибути:
        name: Базове ім'я графа (без дати)
        full_name: Повне ім'я графа з датою
        description: Опис графа
        created_at: Дата та час створення (ISO format)
        stats: Статистика графа (GraphStats модель)
        metadata: Додаткові метадані від користувача
    """

    name: str = Field(..., description="Базове ім'я графа (без дати)")
    full_name: str = Field(..., description="Повне ім'я графа з датою")
    description: str = Field(default="", description="Опис графа")
    created_at: str = Field(..., description="Дата та час створення (ISO format)")

    # Статистика графа (тепер GraphStats модель)
    stats: "GraphStats" = Field(
        default_factory=lambda: GraphStats(), description="Статистика графа"
    )

    # Додаткові метадані від користувача
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Додаткові метадані від користувача"
    )

    model_config = ConfigDict(frozen=False)


class GraphStats(BaseModel):
    """
    Модель для статистики графа.

    Замінює Dict[str, int] для type safety.

    Атрибути:
        total_nodes: Загальна кількість вузлів
        scanned_nodes: Кількість просканованих вузлів
        unscanned_nodes: Кількість непросканованих вузлів
        total_edges: Загальна кількість ребер
    """

    total_nodes: int = Field(default=0, ge=0, description="Загальна кількість вузлів")
    scanned_nodes: int = Field(
        default=0, ge=0, description="Кількість просканованих вузлів"
    )
    unscanned_nodes: int = Field(
        default=0, ge=0, description="Кількість непросканованих вузлів"
    )
    total_edges: int = Field(default=0, ge=0, description="Загальна кількість ребер")

    model_config = ConfigDict(frozen=False)


class GraphComparisonResult(BaseModel):
    """
    Модель для результатів порівняння двох графів.

    Типізований результат порівняння замість словника.
    Використовується методом client.compare_graphs().

    Атрибути:
        old_graph: Ім'я старого графа
        new_graph: Ім'я нового графа
        old_stats: Статистика старого графа (GraphStats модель)
        new_stats: Статистика нового графа (GraphStats модель)
        new_nodes_count: Кількість нових вузлів
        removed_nodes_count: Кількість видалених вузлів
        common_nodes_count: Кількість спільних вузлів
        new_nodes: Список нових вузлів
        removed_nodes: Список видалених вузлів
    """

    old_graph: str = Field(..., description="Ім'я старого графа")
    new_graph: str = Field(..., description="Ім'я нового графа")

    # Статистика графів (тепер GraphStats моделі)
    old_stats: "GraphStats" = Field(..., description="Статистика старого графа")
    new_stats: "GraphStats" = Field(..., description="Статистика нового графа")

    # Підрахунки змін
    new_nodes_count: int = Field(..., ge=0, description="Кількість нових вузлів")
    removed_nodes_count: int = Field(
        ..., ge=0, description="Кількість видалених вузлів"
    )
    common_nodes_count: int = Field(..., ge=0, description="Кількість спільних вузлів")

    # Списки вузлів (для доступу через API)
    new_nodes: list[Any] = Field(
        default_factory=list, description="Список нових вузлів"
    )
    removed_nodes: list[Any] = Field(
        default_factory=list, description="Список видалених вузлів"
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # Для Node об'єктів
        frozen=False,
    )


# ==================== URL RULE MODELS ====================


class URLRule(BaseModel):
    r"""
    Правило для контролю URL (Smart Scheduling).

    Об'єднує фільтрацію, пріоритизацію та контроль поведінки в одній моделі.

    should_scan/should_follow_links мають ВИЩИЙ ПРІОРИТЕТ за allowed_domains.
    URLRule перевіряється ПЕРШИМ у LinkProcessor (перед фільтрами).

    Атрибути:
        pattern: Regex патерн для URL (обов'язковий)
        should_scan: Чи сканувати сторінку (перебиває фільтри!)
        should_follow_links: Чи обробляти посилання (перебиває фільтри!)
        priority: Пріоритет обробки 1-10 (1=низький, 10=високий, default=5)
        create_edge: Чи створювати edge на цей URL

    Examples:
        >>> # Сканувати work.ua але не йти далі (перебиває фільтри)
        >>> URLRule(
        ...     pattern=r'work\.ua',
        ...     should_scan=True,  # Дозволити (навіть якщо заблокований фільтром)
        ...     should_follow_links=False  # Не йти далі
        ... )

        >>> # Виключити /app/ (навіть якщо в allowed_domains)
        >>> URLRule(pattern=r'/app/', should_scan=False)

        >>> # Високий пріоритет для products
        >>> URLRule(pattern=r"/products/", priority=10)

        >>> # Не сканувати PDF файли
        >>> URLRule(pattern=r".*\.pdf$", should_scan=False)
    """

    pattern: str = Field(..., description="Regex патерн для URL", min_length=1)

    priority: int = Field(
        default=5, ge=1, le=10, description="Пріоритет обробки (1=низький, 10=високий)"
    )

    should_scan: Optional[bool] = Field(
        default=None,
        description=(
            "Чи сканувати сторінку (завантажувати HTML). "
            "True/False перебиває фільтри! None = використати фільтри"
        ),
    )

    should_follow_links: Optional[bool] = Field(
        default=None,
        description=(
            "Чи обробляти посилання (can_create_edges). "
            "True/False перебиває фільтри! None = використати фільтри"
        ),
    )

    create_edge: Optional[bool] = Field(
        default=None,
        description=(
            "Чи створювати edge на цей URL. "
            "True/False перебиває default поведінку! None = використати default стратегію"
        ),
    )

    def apply_to_node(self, node: "Node") -> None:
        """
        Застосовує правило до ноди (Tell, Don't Ask принцип).

        Замість того щоб scheduler питав значення з rule і встановлював їх в node,
        правило саме модифікує node.

        Args:
            node: Нода для модифікації

        Example:
            >>> rule = URLRule(pattern=r"/archive/", should_scan=True, should_follow_links=False)
            >>> rule.apply_to_node(node)
            >>> # node.should_scan = True, node.can_create_edges = False
        """

        # Застосовуємо should_scan
        if self.should_scan is not None:
            node.should_scan = self.should_scan

        # Застосовуємо should_follow_links (can_create_edges)
        if self.should_follow_links is not None:
            node.can_create_edges = self.should_follow_links

    model_config = ConfigDict(frozen=False)

    def __repr__(self):
        parts = [f"pattern={self.pattern!r}"]
        if self.priority != 5:
            parts.append(f"priority={self.priority}")
        if self.should_scan is not None:
            parts.append(f"should_scan={self.should_scan}")
        if self.should_follow_links is not None:
            parts.append(f"should_follow_links={self.should_follow_links}")
        if self.create_edge is not None:
            parts.append(f"create_edge={self.create_edge}")
        return f"URLRule({', '.join(parts)})"


class EdgeRule(BaseModel):
    r"""
    Правило для контролю створення edges (Iteration 4 Team 2).

    Дозволяє задавати складні умови для того, які edges створювати або пропускати.
    Перевіряється після фільтрації URL але перед створенням edge в LinkProcessor.

    Атрибути:
        source_pattern: Regex патерн для source node URL (опціонально)
        target_pattern: Regex патерн для target node URL (опціонально)
        max_depth_diff: Максимальна різниця в depth між source та target (опціонально)
        action: Дія - 'create' або 'skip' (обов'язковий)

    Examples:
        >>> # Не створювати edges якщо різниця глибини > 2
        >>> EdgeRule(max_depth_diff=2, action='skip')

        >>> # Не створювати edges з blog на products
        >>> EdgeRule(
        ...     source_pattern=r'.*/blog/.*',
        ...     target_pattern=r'.*/products/.*',
        ...     action='skip'
        ... )

        >>> # Створювати edges тільки в межах розділів
        >>> EdgeRule(
        ...     source_pattern=r'.*/docs/.*',
        ...     target_pattern=r'.*/docs/.*',
        ...     action='create'
        ... )

        >>> # Не створювати edges назад на головну сторінку
        >>> EdgeRule(
        ...     target_pattern=r'^https://site\.com/$',
        ...     action='skip'
        ... )
    """

    source_pattern: Optional[str] = Field(
        default=None, description="Regex патерн для source node URL (None = будь-який)"
    )

    target_pattern: Optional[str] = Field(
        default=None, description="Regex патерн для target node URL (None = будь-який)"
    )

    max_depth_diff: Optional[int] = Field(
        default=None,
        ge=0,
        description="Максимальна різниця в depth між source та target (None = без обмежень)",
    )

    action: str = Field(
        ..., description="Дія: 'create' (створити edge) або 'skip' (пропустити edge)"
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Валідація action - має бути 'create' або 'skip'."""
        if v not in ("create", "skip"):
            raise ValueError(f"action must be 'create' or 'skip', got: {v}")
        return v

    def matches(
        self, source_url: str, target_url: str, source_depth: int, target_depth: int
    ) -> bool:
        """
        Перевіряє чи правило застосовується до даної пари URLs.

        Args:
            source_url: URL source node
            target_url: URL target node
            source_depth: Глибина source node
            target_depth: Глибина target node

        Returns:
            bool: True якщо правило застосовується, False інакше
        """
        # Перевірка source_pattern
        if self.source_pattern:
            if not re.match(self.source_pattern, source_url):
                return False

        # Перевірка target_pattern
        if self.target_pattern:
            if not re.match(self.target_pattern, target_url):
                return False

        # Перевірка max_depth_diff
        if self.max_depth_diff is not None:
            depth_diff = abs(target_depth - source_depth)
            if depth_diff > self.max_depth_diff:
                return False

        # Всі умови пройдені
        return True

    def should_create_edge(
        self, source_url: str, target_url: str, source_depth: int, target_depth: int
    ) -> Optional[bool]:
        """
        Визначає чи треба створювати edge.

        Args:
            source_url: URL source node
            target_url: URL target node
            source_depth: Глибина source node
            target_depth: Глибина target node

        Returns:
            Optional[bool]:
                - True якщо правило каже створити edge
                - False якщо правило каже пропустити edge
                - None якщо правило не застосовується

        Example:
            >>> rule = EdgeRule(target_pattern=r'.*/login.*', action='skip')
            >>> rule.should_create_edge(
            ...     'https://site.com/page',
            ...     'https://site.com/login',
            ...     1, 2
            ... )
            False
        """
        if not self.matches(source_url, target_url, source_depth, target_depth):
            return None

        return self.action == "create"

    model_config = ConfigDict(frozen=False)

    def __repr__(self):
        parts = []
        if self.source_pattern:
            parts.append(f"source_pattern={self.source_pattern!r}")
        if self.target_pattern:
            parts.append(f"target_pattern={self.target_pattern!r}")
        if self.max_depth_diff is not None:
            parts.append(f"max_depth_diff={self.max_depth_diff}")
        parts.append(f"action={self.action!r}")
        return f"EdgeRule({', '.join(parts)})"


# ==================== EXPORT ====================

__all__ = [
    "EdgeCreationStrategy",
    "FetchResponse",
    "DomainFilterConfig",
    "PathFilterConfig",
    "PageMetadata",
    "GraphMetadata",
    "GraphStats",
    "GraphComparisonResult",
    "URLRule",
    "EdgeRule",
]
