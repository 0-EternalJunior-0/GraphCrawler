"""Базовий інтерфейс для HTML Tree адаптерів.

TreeElement тепер використовує функціональний підхід через callbacks
замість зберігання посилання на adapter. Це покращує ізоляцію шарів.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional

# Type aliases для callbacks (функціональний підхід)
TextExtractor = Callable[[Any], str]
AttributeExtractor = Callable[[Any, str], Optional[str]]
ElementFinder = Callable[[Any, str], Optional["TreeElement"]]
ElementsFinder = Callable[[Any, str], List["TreeElement"]]


class TreeElement:
    """
    Легка обгортка для елемента HTML дерева.

    Замість зберігання посилання на adapter, TreeElement тепер приймає
    функції-callbacks для операцій. Це забезпечує:
    - Кращу ізоляцію (Element не знає про Adapter)
    - Легше тестування (можна передати mock функції)
    - Зменшення coupling

    Використовує __slots__ для мінімального overhead (8-16 bytes).
    Надає єдиний API для роботи з елементами незалежно від парсера.

    Design: Функціональний підхід з callbacks замість tight coupling.

    Attributes:
        _element: Оригінальний елемент від парсера (BS/lxml/Scrapy)
        _text_fn: Функція для отримання тексту
        _attr_fn: Функція для отримання атрибутів
        _find_fn: Функція для пошуку одного елемента
        _find_all_fn: Функція для пошуку всіх елементів

    Example:
        >>> # Створення через adapter (рекомендовано)
        >>> elem = adapter.find('a')
        >>> elem.text()
        'Some text'
        >>> elem.get_attribute('href')
        '/page1'
    """

    __slots__ = ("_element", "_text_fn", "_attr_fn", "_find_fn", "_find_all_fn")

    def __init__(
        self,
        element: Any,
        text_fn: TextExtractor,
        attr_fn: AttributeExtractor,
        find_fn: ElementFinder,
        find_all_fn: ElementsFinder,
    ):
        """
        Ініціалізує TreeElement з функціональними callbacks.

        Args:
            element: Оригінальний елемент (BeautifulSoup Tag, lxml Element, Scrapy Selector)
            text_fn: Функція для отримання тексту елемента
            attr_fn: Функція для отримання атрибута елемента
            find_fn: Функція для пошуку одного дочірнього елемента
            find_all_fn: Функція для пошуку всіх дочірніх елементів
        """
        self._element = element
        self._text_fn = text_fn
        self._attr_fn = attr_fn
        self._find_fn = find_fn
        self._find_all_fn = find_all_fn

    @classmethod
    def from_adapter(cls, element: Any, adapter: "BaseTreeAdapter") -> "TreeElement":
        """
        Фабричний метод для створення TreeElement через adapter.

        Це рекомендований спосіб створення TreeElement - adapter передає
        свої методи як callbacks.

        Args:
            element: Оригінальний елемент
            adapter: BaseTreeAdapter instance

        Returns:
            TreeElement з прив'язаними callbacks
        """
        return cls(
            element=element,
            text_fn=adapter._get_element_text,
            attr_fn=adapter._get_element_attribute,
            find_fn=lambda el, sel: adapter._find_in_element(el, sel),
            find_all_fn=lambda el, sel: adapter._find_all_in_element(el, sel),
        )

    def text(self) -> str:
        """
        Повертає текст елемента (без HTML тегів).

        Returns:
            Текстовий контент елемента

        Example:
            >>> elem.text()
            'Click here'
        """
        return self._text_fn(self._element)

    def get_attribute(self, name: str) -> Optional[str]:
        """
        Повертає атрибут елемента.

        Args:
            name: Назва атрибута (href, src, class, id, etc)

        Returns:
            Значення атрибута або None

        Example:
            >>> elem.get_attribute('href')
            '/page1'
        """
        return self._attr_fn(self._element, name)

    def find(self, selector: str) -> Optional["TreeElement"]:
        """
        Знаходить перший дочірній елемент.

        Args:
            selector: CSS селектор

        Returns:
            TreeElement або None

        Example:
            >>> elem.find('a')
            <TreeElement ...>
        """
        return self._find_fn(self._element, selector)

    def find_all(self, selector: str) -> List["TreeElement"]:
        """
        Знаходить всі дочірні елементи.

        Args:
            selector: CSS селектор

        Returns:
            Список TreeElement

        Example:
            >>> elem.find_all('a')
            [<TreeElement ...>, <TreeElement ...>]
        """
        return self._find_all_fn(self._element, selector)

    @property
    def raw(self) -> Any:
        """
        Повертає оригінальний елемент парсера.

        Для advanced use cases коли потрібен прямий доступ до BS/lxml/Scrapy API.

        Returns:
            Оригінальний елемент (BeautifulSoup Tag / lxml Element / Scrapy Selector)

        Example:
            >>> elem.raw
            <Tag: a href="/page">
        """
        return self._element


class BaseTreeAdapter(ABC):
    """
    Абстрактний базовий клас для адаптерів HTML дерева.

    Адаптує різні HTML парсери (BeautifulSoup, lxml, Scrapy) до єдиного API.
    Plugins працюють з цим API і не залежать від конкретного парсера.

    Design Pattern: Adapter Pattern

    Переваги:
    - Єдиний API для всіх парсерів
    - Plugins не прив'язані до конкретної бібліотеки
    - Легко додати новий парсер
    - Можливість оптимізації під конкретні задачі

    Example:
        >>> adapter = TreeAdapterFactory.create('beautifulsoup')
        >>> adapter.parse('<html><title>Test</title></html>')
        >>> element = adapter.find('title')
        >>> element.text()
        'Test'
    """

    @abstractmethod
    def parse(self, html: str) -> Any:
        """
        Парсить HTML в дерево.

        Args:
            html: HTML string для парсингу

        Returns:
            Tree об'єкт (тип залежить від адаптера).
            BeautifulSoup: BeautifulSoup об'єкт
            lxml: HtmlElement
            Scrapy: Selector

        Raises:
            Exception: Якщо HTML не вдалося розпарсити

        Example:
            >>> adapter = BeautifulSoupAdapter()
            >>> tree = adapter.parse('<html><body>Hello</body></html>')
        """
        pass

    @abstractmethod
    def find(self, selector: str) -> Optional[TreeElement]:
        """
        Знаходить перший елемент за CSS селектором.

        Args:
            selector: CSS селектор (наприклад, 'div.content', 'a[href]', 'title')

        Returns:
            TreeElement або None якщо елемент не знайдено

        Example:
            >>> adapter = BeautifulSoupAdapter()
            >>> adapter.parse('<html><title>Test</title></html>')
            >>> elem = adapter.find('title')
            >>> elem.text()
            'Test'
        """
        pass

    @abstractmethod
    def find_all(self, selector: str) -> List[TreeElement]:
        """
        Знаходить всі елементи за CSS селектором.

        Args:
            selector: CSS селектор

        Returns:
            Список TreeElement (може бути порожнім)

        Example:
            >>> adapter = BeautifulSoupAdapter()
            >>> adapter.parse('<html><a href="/1">L1</a><a href="/2">L2</a></html>')
            >>> links = adapter.find_all('a')
            >>> len(links)
            2
            >>> links[0].get_attribute('href')
            '/1'
        """
        pass

    @abstractmethod
    def css(self, selector: str) -> List[TreeElement]:
        """
        CSS селектор (alias для find_all для Scrapy-подібного API).

        Args:
            selector: CSS селектор

        Returns:
            Список TreeElement

        Example:
            >>> adapter.css('a[href]')
            [<TreeElement ...>, ...]
        """
        pass

    @abstractmethod
    def xpath(self, query: str) -> List[TreeElement]:
        """
        XPath запит (якщо підтримується парсером).

        Args:
            query: XPath вираз (наприклад, '//div[@class="content"]//p')

        Returns:
            Список TreeElement

        Note:
            BeautifulSoup не підтримує XPath - поверне порожній список.
            lxml та Scrapy підтримують повністю.

        Example:
            >>> adapter.xpath('//title/text()')
            [<TreeElement ...>]
        """
        pass

    @property
    @abstractmethod
    def text(self) -> str:
        """
        Повертає весь текст без HTML тегів.

        Returns:
            Текст всього документа

        Example:
            >>> adapter.parse('<html><body><p>Hello</p><p>World</p></body></html>')
            >>> adapter.text
            'Hello World'
        """
        pass

    @property
    @abstractmethod
    def tree(self) -> Any:
        """
        Повертає оригінальне дерево парсера.

        Для advanced use cases.

        Returns:
            BeautifulSoup / lxml.HtmlElement / scrapy.Selector

        Example:
            >>> adapter.parse('<html>...</html>')
            >>> raw_tree = adapter.tree
            >>> type(raw_tree)
            <class 'bs4.BeautifulSoup'>
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Повертає назву адаптера.

        Returns:
            Назва адаптера (наприклад, 'beautifulsoup', 'lxml', 'scrapy')

        Example:
            >>> adapter.name
            'beautifulsoup-html.parser'
        """
        pass

    # Protected методи для TreeElement (делегування)

    @abstractmethod
    def _get_element_text(self, element: Any) -> str:
        """Повертає текст конкретного елемента."""
        pass

    @abstractmethod
    def _get_element_attribute(self, element: Any, name: str) -> Optional[str]:
        """Повертає атрибут конкретного елемента."""
        pass

    @abstractmethod
    def _find_in_element(self, element: Any, selector: str) -> Optional[TreeElement]:
        """Знаходить дочірній елемент."""
        pass

    @abstractmethod
    def _find_all_in_element(self, element: Any, selector: str) -> List[TreeElement]:
        """Знаходить всі дочірні елементи."""
        pass


# =====================================
# ISP: Interface Segregation Principle
# =====================================
# Ці Protocol інтерфейси визначають мінімальний контракт для кожної
# відповідальності. BaseTreeAdapter реалізує всі ці інтерфейси,
# але клієнт може залежати тільки від того, що йому потрібно.
# Приклад використання:
# >>> def extract_links(searcher: ITreeSearcher) -> List[str]:
# ...     links = searcher.find_all('a')
# ...     return [link.get_attribute('href') for link in links]

from typing import Protocol, runtime_checkable


@runtime_checkable
class ITreeParser(Protocol):
    """
    Інтерфейс для парсингу HTML в дерево.


    Відповідальність: Парсинг HTML рядка в дерево елементів.

    Використовується коли потрібна тільки функціональність парсингу
    без пошуку чи навігації.

    Example:
        >>> def parse_html(parser: ITreeParser, html: str):
        ...     return parser.parse(html)
        >>>
        >>> adapter = BeautifulSoupAdapter()
        >>> tree = parse_html(adapter, '<html>...</html>')
    """

    def parse(self, html: str) -> Any:
        """Парсить HTML в дерево."""
        ...


@runtime_checkable
class ITreeSearcher(Protocol):
    """
    Інтерфейс для пошуку елементів в дереві.


    Відповідальність: Пошук елементів за селекторами (CSS, XPath).

    Використовується коли потрібна тільки функціональність пошуку.

    Example:
        >>> def extract_links(searcher: ITreeSearcher) -> List[str]:
        ...     links = searcher.find_all('a[href]')
        ...     return [link.get_attribute('href') for link in links if link]
        >>>
        >>> adapter = BeautifulSoupAdapter()
        >>> adapter.parse(html)
        >>> urls = extract_links(adapter)
    """

    def find(self, selector: str) -> Optional[TreeElement]:
        """Знаходить перший елемент за селектором."""
        ...

    def find_all(self, selector: str) -> List[TreeElement]:
        """Знаходить всі елементи за селектором."""
        ...

    def css(self, selector: str) -> List[TreeElement]:
        """CSS селектор (alias для find_all)."""
        ...

    def xpath(self, query: str) -> List[TreeElement]:
        """XPath запит (якщо підтримується)."""
        ...


@runtime_checkable
class ITreeNavigator(Protocol):
    """
    Інтерфейс для навігації та отримання даних з дерева.


    Відповідальність: Отримання тексту, атрибутів, доступ до дерева.

    Використовується коли потрібен доступ до тексту документа.

    Example:
        >>> def get_page_text(navigator: ITreeNavigator) -> str:
        ...     return navigator.text
        >>>
        >>> adapter = BeautifulSoupAdapter()
        >>> adapter.parse(html)
        >>> text = get_page_text(adapter)
    """

    @property
    def text(self) -> str:
        """Повертає весь текст без HTML тегів."""
        ...

    @property
    def tree(self) -> Any:
        """Повертає оригінальне дерево парсера."""
        ...

    @property
    def name(self) -> str:
        """Повертає назву адаптера."""
        ...


@runtime_checkable
class ITreeSerializer(Protocol):
    """
    Інтерфейс для серіалізації дерева.


    Відповідальність: Конвертація дерева в різні формати.

    Примітка: Цей інтерфейс визначений для майбутнього розширення.
    Поточні адаптери можуть не реалізовувати його повністю.

    Example:
        >>> def export_html(serializer: ITreeSerializer, tree) -> str:
        ...     return serializer.to_string(tree)
    """

    def to_string(self, tree: Any) -> str:
        """Конвертує дерево в HTML рядок."""
        ...


# =====================================
# Composite Interface
# =====================================


@runtime_checkable
class ITreeAdapter(ITreeParser, ITreeSearcher, ITreeNavigator, Protocol):
    """
    Повний інтерфейс для HTML Tree Adapter.

    Об'єднує всі ISP інтерфейси:
    - ITreeParser - парсинг HTML
    - ITreeSearcher - пошук елементів
    - ITreeNavigator - навігація та доступ до даних

    BaseTreeAdapter реалізує цей інтерфейс.

    Example:
        >>> def process_html(adapter: ITreeAdapter, html: str):
        ...     adapter.parse(html)
        ...     title = adapter.find('title')
        ...     return title.text() if title else adapter.text[:100]
    """

    pass


# Export all interfaces
__all__ = [
    "TreeElement",
    "BaseTreeAdapter",
    "ITreeParser",
    "ITreeSearcher",
    "ITreeNavigator",
    "ITreeSerializer",
    "ITreeAdapter",
]
