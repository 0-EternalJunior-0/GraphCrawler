"""Pydantic моделі для типізації даних.

Цей модуль містить всі Pydantic моделі для заміни Dict[str, Any].
Забезпечує type safety та валідацію даних.
"""

import re
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from graph_crawler.domain.entities.node import Node

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContentType(str, Enum):
    """
    Тип контенту сторінки (Value Object).

    Examples:
        >>> # Фільтрація HTML сторінок
        >>> html_nodes = [n for n in graph if n.content_type == ContentType.HTML]
    """

    # Невідомий тип (ще не визначено або не вдалося)
    UNKNOWN = "unknown"

    # Текстові формати
    HTML = "html"  # text/html
    JSON = "json"  # application/json
    XML = "xml"  # text/xml, application/xml
    TEXT = "text"  # text/plain
    CSS = "css"  # text/css
    JAVASCRIPT = "javascript"  # application/javascript, text/javascript

    # Медіа формати
    IMAGE = "image"  # image/*
    VIDEO = "video"  # video/*
    AUDIO = "audio"  # audio/*

    # Документи
    PDF = "pdf"  # application/pdf
    DOC = "doc"  # application/msword, application/vnd.openxmlformats-officedocument.*

    # Бінарні та архіви
    BINARY = "binary"  # application/octet-stream та інші бінарні
    ARCHIVE = "archive"  # application/zip, application/x-rar тощо

    # Спеціальні стани
    EMPTY = "empty"  # HTTP 200 але body пустий
    ERROR = "error"  # Помилка завантаження (4xx, 5xx, timeout)
    REDIRECT = "redirect"  # HTTP 3xx без body (чистий redirect)

    @classmethod
    def from_content_type_header(cls, content_type: Optional[str]) -> "ContentType":
        """
        Визначає ContentType з HTTP Content-Type header.

        Args:
            content_type: Значення Content-Type header (напр. "text/html; charset=utf-8")

        Returns:
            ContentType enum value

        Examples:
            >>> ContentType.from_content_type_header("text/html; charset=utf-8")
            <ContentType.HTML: 'html'>

            >>> ContentType.from_content_type_header("application/json")
            <ContentType.JSON: 'json'>

            >>> ContentType.from_content_type_header(None)
            <ContentType.UNKNOWN: 'unknown'>
        """
        if not content_type:
            return cls.UNKNOWN

        # Конвертуємо Cython об'єкти в string (проблема з selectolax в Python 3.14)
        # Cython об'єкти можуть не мати методів string, тому явно конвертуємо
        try:
            if isinstance(content_type, str):
                content_type_str = content_type
            else:
                content_type_str = str(content_type)
        except Exception:
            return cls.UNKNOWN

        # Нормалізуємо: lowercase, видаляємо параметри (charset тощо)
        ct = content_type_str.lower().split(";")[0].strip()

        # HTML
        if "text/html" in ct or "application/xhtml" in ct:
            return cls.HTML

        # JSON
        if "application/json" in ct or ct.endswith("+json"):
            return cls.JSON

        # XML (включаючи sitemap, RSS, Atom)
        if "xml" in ct:
            return cls.XML

        # Plain text
        if ct == "text/plain":
            return cls.TEXT

        # CSS
        if ct == "text/css":
            return cls.CSS

        # JavaScript
        if "javascript" in ct:
            return cls.JAVASCRIPT

        # Images
        if ct.startswith("image/"):
            return cls.IMAGE

        # Video
        if ct.startswith("video/"):
            return cls.VIDEO

        # Audio
        if ct.startswith("audio/"):
            return cls.AUDIO

        # PDF
        if ct == "application/pdf":
            return cls.PDF

        # Documents (Word, Excel, etc.)
        if "msword" in ct or "officedocument" in ct or "opendocument" in ct:
            return cls.DOC

        # Archives
        if any(x in ct for x in ["zip", "rar", "tar", "gzip", "7z", "bzip", "compressed"]):
            return cls.ARCHIVE

        # Binary/octet-stream
        if ct == "application/octet-stream":
            return cls.BINARY

        # Fallback для невідомих application/* типів
        if ct.startswith("application/"):
            return cls.BINARY

        return cls.UNKNOWN

    @classmethod
    def from_url(cls, url: str) -> "ContentType":
        """
        Визначає ContentType з URL extension (fallback метод).

        Використовується коли Content-Type header недоступний або невизначений.

        Args:
            url: URL для аналізу

        Returns:
            ContentType enum value або UNKNOWN

        Examples:
            >>> ContentType.from_url("https://example.com/data.json")
            <ContentType.JSON: 'json'>

            >>> ContentType.from_url("https://example.com/image.png")
            <ContentType.IMAGE: 'image'>
        """
        from urllib.parse import urlparse

        try:
            path = urlparse(url).path.lower()
        except Exception:
            return cls.UNKNOWN

        # HTML
        if path.endswith((".html", ".htm", ".xhtml")):
            return cls.HTML

        # JSON
        if path.endswith(".json"):
            return cls.JSON

        # XML (sitemap, RSS, feeds)
        if path.endswith((".xml", ".rss", ".atom")):
            return cls.XML

        # Text
        if path.endswith(".txt"):
            return cls.TEXT

        # CSS
        if path.endswith(".css"):
            return cls.CSS

        # JavaScript
        if path.endswith((".js", ".mjs")):
            return cls.JAVASCRIPT

        # Images
        if path.endswith(
            (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff")
        ):
            return cls.IMAGE

        # Video
        if path.endswith((".mp4", ".webm", ".avi", ".mov", ".mkv", ".flv")):
            return cls.VIDEO

        # Audio
        if path.endswith((".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a")):
            return cls.AUDIO

        # PDF
        if path.endswith(".pdf"):
            return cls.PDF

        # Documents
        if path.endswith((".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt")):
            return cls.DOC

        # Archives
        if path.endswith((".zip", ".rar", ".tar", ".gz", ".7z", ".bz2")):
            return cls.ARCHIVE

        return cls.UNKNOWN

    def is_text_based(self) -> bool:
        """
        Перевіряє чи це текстовий контент який можна парсити.

        Returns:
            True для HTML, JSON, XML, TEXT, CSS, JAVASCRIPT
        """
        return self in (
            ContentType.HTML,
            ContentType.JSON,
            ContentType.XML,
            ContentType.TEXT,
            ContentType.CSS,
            ContentType.JAVASCRIPT,
        )

    def is_media(self) -> bool:
        """
        Перевіряє чи це медіа контент.

        Returns:
            True для IMAGE, VIDEO, AUDIO
        """
        return self in (ContentType.IMAGE, ContentType.VIDEO, ContentType.AUDIO)

    def is_scannable(self) -> bool:
        """
        Перевіряє чи варто сканувати цей тип на посилання.

        Returns:
            True для HTML, XML (sitemap може містити URLs)
        """
        return self in (ContentType.HTML, ContentType.XML)

    @classmethod
    def detect(
        cls,
        content_type_header: Optional[str] = None,
        url: Optional[str] = None,
        content: Optional[str] = None,
        status_code: Optional[int] = None,
        has_error: bool = False,
    ) -> "ContentType":
        """
        Комплексна детекція типу контенту (Domain Logic).

        Args:
            content_type_header: Значення HTTP Content-Type header
            url: URL для fallback детекції по розширенню
            content: Контент сторінки для евристичної детекції
            status_code: HTTP статус код
            has_error: Чи була помилка при завантаженні
        Returns:
            ContentType enum value
        Examples:
            >>> # Детекція з header
            >>> ContentType.detect(content_type_header="text/html; charset=utf-8")
            <ContentType.HTML: 'html'>
        """
        # 1. Помилка завантаження
        if has_error:
            return cls.ERROR

        # 2. HTTP error статуси (4xx, 5xx)
        if status_code is not None and status_code >= 400:
            return cls.ERROR

        # 3. Пустий контент (status 200 але body пустий)
        if content is not None and len(content.strip()) == 0:
            return cls.EMPTY

        # 4. Визначаємо з Content-Type header (primary)
        if content_type_header:
            detected = cls.from_content_type_header(content_type_header)
            if detected != cls.UNKNOWN:
                return detected

        # 5. Fallback на URL extension
        if url:
            detected_from_url = cls.from_url(url)
            if detected_from_url != cls.UNKNOWN:
                return detected_from_url

        # 6. Евристика по контенту
        if content:
            content_lower = content.strip().lower()

            # HTML/XML евристика
            if content_lower.startswith(("<!doctype", "<html", "<head", "<body", "<?xml")):
                # Розрізняємо XML та HTML
                if "<?xml" in content_lower and "<html" not in content_lower[:500]:
                    return cls.XML
                return cls.HTML

            # JSON евристика
            if content.strip().startswith(("{", "[")):
                return cls.JSON

        # 7. Не вдалося визначити
        return cls.UNKNOWN


class EdgeCreationStrategy(str, Enum):
    """
    Стратегії створення edges в графі.

    Examples:
        >>> # Мінімальний граф (дерево): edges == nodes - 1
        >>> strategy = EdgeCreationStrategy.NEW_ONLY
    """

    ALL = "all"
    NEW_ONLY = "new_only"
    MAX_IN_DEGREE = "max_in_degree"
    SAME_DEPTH_ONLY = "same_depth_only"
    DEEPER_ONLY = "deeper_only"
    FIRST_ENCOUNTER_ONLY = "first_encounter_only"


class FetchResponse(BaseModel):
    """Відповідь від драйвера після завантаження сторінки.

    Замінює Dict[str, Any] для type safety.
    """

    url: str
    html: Optional[str] = None
    status_code: Optional[int] = None
    headers: dict[str, str] = Field(default_factory=dict)
    error: Optional[str] = None

    # Redirect information (заповнюється всіма драйверами)
    final_url: Optional[str] = None
    redirect_chain: list[str] = Field(default_factory=list)

    # Partial content flag (для timeout з частковим HTML)
    is_partial: bool = False

    @property
    def is_success(self) -> bool:
        """Перевіряє чи запит був успішним (повний контент, без помилок)."""
        return self.error is None and self.html is not None and not self.is_partial

    @property
    def has_content(self) -> bool:
        """Перевіряє чи є HTML контент (включаючи partial)."""
        return self.html is not None

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


class DomainFilterConfig(BaseModel):
    """Конфігурація фільтра доменів.

    Замінює Dict[str, Any] для type safety.
    Examples:
        >>> # Спеціальні патерни
        >>> config = DomainFilterConfig(
        ...     base_domain="company.com",
        ...     allowed_domains=["domain+subdomains"]  # DEFAULT
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
        from graph_crawler.domain.value_objects.domain_patterns import (
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
    scanned_nodes: int = Field(default=0, ge=0, description="Кількість просканованих вузлів")
    unscanned_nodes: int = Field(default=0, ge=0, description="Кількість непросканованих вузлів")
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
    removed_nodes_count: int = Field(..., ge=0, description="Кількість видалених вузлів")
    common_nodes_count: int = Field(..., ge=0, description="Кількість спільних вузлів")

    # Списки вузлів (для доступу через API)
    new_nodes: list[Any] = Field(default_factory=list, description="Список нових вузлів")
    removed_nodes: list[Any] = Field(default_factory=list, description="Список видалених вузлів")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # Для Node об'єктів
        frozen=False,
    )


class URLRule(BaseModel):
    r"""
    Правило для контролю URL (Smart Scheduling).

    Examples:
        >>> # Сканувати work.ua але не йти далі (перебиває фільтри)
        >>> URLRule(
        ...     pattern=r'work\.ua',
        ...     should_scan=True,  # Дозволити (навіть якщо заблокований фільтром)
        ...     should_follow_links=False  # Не йти далі
        ... )
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


class RuleScope(str, Enum):
    """
    Область застосування правила для SmartURLRule.

    Визначає, до якої частини URL застосовується патерн.
    """

    FULL_URL = "full_url"  # Весь URL (як звичайний URLRule)
    DOMAIN = "domain"  # Тільки домен (epam.com)
    SUBDOMAIN = "subdomain"  # Субдомен (careers.epam.com)
    PATH = "path"  # Шлях після домену (/jobs, /careers)
    QUERY = "query"  # Query параметри (?country=UA)


class SmartURLRule(BaseModel):
    r"""
    Розумне правило для контролю URL з автоматичним парсингом компонентів.

    Examples:
        >>> # Пріоритет субдомену careers.epam.com
        >>> SmartURLRule(
        ...     pattern=r'careers\.epam\.com',
        ...     scope=RuleScope.SUBDOMAIN,
        ...     priority=7,
        ...     should_scan=True
        ... )
    """

    pattern: str = Field(..., description="Regex патерн або точний текст", min_length=1)

    scope: RuleScope = Field(default=RuleScope.FULL_URL, description="Область застосування патерну")

    is_regex: bool = Field(
        default=True, description="True = regex патерн, False = точний текст для порівняння"
    )

    priority: int = Field(
        default=5, ge=1, le=10, description="Пріоритет обробки (1=низький, 10=високий)"
    )

    should_scan: Optional[bool] = Field(
        default=None, description="Чи сканувати сторінку. True/False перебиває фільтри!"
    )

    should_follow_links: Optional[bool] = Field(
        default=None, description="Чи обробляти посилання. True/False перебиває фільтри!"
    )

    create_edge: Optional[bool] = Field(default=None, description="Чи створювати edge на цей URL")

    # Кешований скомпільований regex
    _compiled_pattern: Optional[re.Pattern] = None

    model_config = ConfigDict(frozen=False, arbitrary_types_allowed=True)

    def _get_compiled_pattern(self) -> Optional[re.Pattern]:
        """Повертає скомпільований regex (з кешуванням)."""
        if not self.is_regex:
            return None
        if self._compiled_pattern is None:
            try:
                self._compiled_pattern = re.compile(self.pattern)
            except re.error:
                return None
        return self._compiled_pattern

    def _extract_url_part(self, url: str) -> str:
        """
        Витягує потрібну частину URL згідно scope.

        Args:
            url: Повний URL

        Returns:
            Частина URL для матчингу
        """
        from urllib.parse import urlparse

        parsed = urlparse(url)

        if self.scope == RuleScope.FULL_URL:
            return url

        elif self.scope == RuleScope.DOMAIN:
            # Базовий домен без субдоменів (epam.com з careers.epam.com)
            host = parsed.netloc.replace("www.", "").split(":")[0]
            parts = host.split(".")
            # Беремо останні 2 частини (або всі якщо менше)
            if len(parts) >= 2:
                return ".".join(parts[-2:])
            return host

        elif self.scope == RuleScope.SUBDOMAIN:
            # Повний хост з субдоменами (careers.epam.com)
            return parsed.netloc.replace("www.", "").split(":")[0]

        elif self.scope == RuleScope.PATH:
            # Шлях без query (/jobs, /careers/ua)
            return parsed.path or "/"

        elif self.scope == RuleScope.QUERY:
            # Query string (country=UA&utm_source=google)
            return parsed.query or ""

        return url

    def matches(self, url: str) -> bool:
        """
        Перевіряє чи URL відповідає правилу.

        Args:
            url: URL для перевірки

        Returns:
            True якщо URL матчить правило

        Example:
            >>> rule = SmartURLRule(pattern=r'^/jobs/?', scope=RuleScope.PATH)
            >>> rule.matches('https://careers.epam.com/jobs')  # True
            >>> rule.matches('https://jobs.epam.com/')  # False (це субдомен!)
        """
        url_part = self._extract_url_part(url)

        if self.is_regex:
            compiled = self._get_compiled_pattern()
            if compiled:
                return bool(compiled.search(url_part))
            return False
        else:
            # Точний матч
            return self.pattern in url_part

    def apply_to_node(self, node: "Node") -> None:
        """
        Застосовує правило до ноди.

        Args:
            node: Нода для модифікації
        """
        if self.should_scan is not None:
            node.should_scan = self.should_scan
        if self.should_follow_links is not None:
            node.can_create_edges = self.should_follow_links

    def to_url_rule(self) -> "URLRule":
        """
        Конвертує SmartURLRule в звичайний URLRule.

        Корисно для backwards compatibility з існуючим кодом.

        Note: Втрачається інформація про scope - патерн застосовується до всього URL.

        Returns:
            Еквівалентний URLRule
        """
        return URLRule(
            pattern=self.pattern,
            priority=self.priority,
            should_scan=self.should_scan,
            should_follow_links=self.should_follow_links,
            create_edge=self.create_edge,
        )

    def __repr__(self):
        parts = [f"pattern={self.pattern!r}", f"scope={self.scope.value}"]
        if not self.is_regex:
            parts.append("is_regex=False")
        if self.priority != 5:
            parts.append(f"priority={self.priority}")
        if self.should_scan is not None:
            parts.append(f"should_scan={self.should_scan}")
        if self.should_follow_links is not None:
            parts.append(f"should_follow_links={self.should_follow_links}")
        if self.create_edge is not None:
            parts.append(f"create_edge={self.create_edge}")
        return f"SmartURLRule({', '.join(parts)})"


def build_smart_rules(
    target_url: str,
    subdomain_priority: int = 6,
    path_patterns: Optional[list[tuple[str, int]]] = None,
    blocked_domains: Optional[list[str]] = None,
) -> list[SmartURLRule]:
    """
    Хелпер для побудови набору SmartURLRule правил.

    Args:
        target_url: Цільовий URL (напр. https://careers.epam.com/ua/jobs)
        subdomain_priority: Пріоритет для субдомену (default=6)
        path_patterns: Список кортежів (pattern, priority) для шляхів
        blocked_domains: Список доменів для блокування
    Returns:
        Список SmartURLRule правил
    """
    from urllib.parse import urlparse

    rules: list[SmartURLRule] = []
    parsed = urlparse(target_url)
    host = parsed.netloc.replace("www.", "").split(":")[0]
    host_parts = host.split(".")

    # 1. Blocked domains - найвищий пріоритет
    if blocked_domains:
        for domain in blocked_domains:
            rules.append(
                SmartURLRule(
                    pattern=domain,
                    scope=RuleScope.DOMAIN,
                    is_regex=False,
                    priority=10,
                    should_scan=False,
                    should_follow_links=False,
                )
            )

    # 2. Базовий домен
    if len(host_parts) >= 2:
        base_domain = ".".join(host_parts[-2:])
        rules.append(
            SmartURLRule(
                pattern=base_domain,
                scope=RuleScope.DOMAIN,
                is_regex=False,
                priority=5,
                should_scan=True,
                should_follow_links=True,
            )
        )

    # 3. Субдомен (якщо є)
    if len(host_parts) > 2 or (len(host_parts) == 2 and host != ".".join(host_parts[-2:])):
        rules.append(
            SmartURLRule(
                pattern=host,
                scope=RuleScope.SUBDOMAIN,
                is_regex=False,
                priority=subdomain_priority,
                should_scan=True,
                should_follow_links=True,
            )
        )

    # 4. Path patterns
    if path_patterns:
        for pattern, priority in path_patterns:
            rules.append(
                SmartURLRule(
                    pattern=pattern,
                    scope=RuleScope.PATH,
                    is_regex=True,
                    priority=priority,
                    should_scan=True,
                    should_follow_links=True,
                )
            )

    # Сортуємо за пріоритетом (вищий першим)
    rules.sort(key=lambda r: r.priority, reverse=True)

    return rules


class EdgeRule(BaseModel):
    r"""
    Правило для контролю створення edges (Iteration 4 Team 2).

    Examples:
        >>> # Не створювати edges якщо різниця глибини > 2
        >>> EdgeRule(max_depth_diff=2, action='skip')
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

        Логіка:
        - source_pattern/target_pattern: правило застосовується якщо URL матчить патерн
        - max_depth_diff: правило застосовується якщо різниця глибини > max_depth_diff
          (це "violation rule" - спрацьовує коли умова порушена)

        Args:
            source_url: URL source node
            target_url: URL target node
            source_depth: Глибина source node
            target_depth: Глибина target node

        Returns:
            bool: True якщо правило застосовується, False інакше
        """
        # Перевірка source_pattern (якщо вказано - URL має матчити)
        if self.source_pattern:
            if not re.match(self.source_pattern, source_url):
                return False

        # Перевірка target_pattern (якщо вказано - URL має матчити)
        if self.target_pattern:
            if not re.match(self.target_pattern, target_url):
                return False

        # Перевірка max_depth_diff (violation rule - спрацьовує коли перевищено)
        # Якщо max_depth_diff=2 і action='skip', то правило має застосуватись
        # коли depth_diff > 2, щоб edge був skipped
        if self.max_depth_diff is not None:
            depth_diff = abs(target_depth - source_depth)
            # Правило застосовується ТІЛЬКИ якщо ліміт перевищено
            if depth_diff <= self.max_depth_diff:
                return False

        # Всі умови пройдені - правило застосовується
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


# Union type для підтримки обох типів правил
# URLRule - проста зворотня сумісність (regex по всьому URL)
# SmartURLRule - розумні правила з scope (domain/path/query)
from typing import Union

Rule = Union[URLRule, SmartURLRule]
__all__ = [
    "ContentType",
    "EdgeCreationStrategy",
    "FetchResponse",
    "DomainFilterConfig",
    "PathFilterConfig",
    "PageMetadata",
    "GraphMetadata",
    "GraphStats",
    "GraphComparisonResult",
    "URLRule",
    "SmartURLRule",
    "RuleScope",
    "Rule",
    "EdgeRule",
    "build_smart_rules",
]
