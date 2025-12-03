"""
Менеджер графу для управління вузлами та ребрами.

Складні операції винесено в окремі класи:
- GraphOperations - арифметичні операції та операції теорії графів
- GraphStatistics - статистика та аналіз графа
"""

import logging
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple, Union

from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.edge_analysis import EdgeAnalysis
from graph_crawler.domain.entities.graph_operations import GraphOperations
from graph_crawler.domain.entities.graph_statistics import GraphStatistics
from graph_crawler.domain.entities.node import Node

logger = logging.getLogger(__name__)


class Graph:
    """
    Менеджер графу - базові CRUD операції та Python API.

        Відповідальність: управління вузлами та ребрами, базові операції з графом.
        Складні операції делеговані спеціалізованим класам:
        - GraphOperations - арифметичні операції (+, -, &, |, ^, порівняння)
        - GraphStatistics - статистика та аналіз (degree, neighbors, connectivity)

        Підтримує операції:
        - CRUD: add_node(), add_edge(), get_node_by_url(), get_node_by_id()
        - Колекційні: len(), iter(), in, [] (доступ до елементів)
        - Арифметичні: +, -, &, |, ^ (делеговані GraphOperations)
        - Порівняння: ==, !=, <, <=, >, >= (делеговані GraphOperations)

        Атрибути:
            nodes: Словник вузлів {node_id: Node}
            edges: Список ребер
            url_to_node: Мапа URL -> Node для швидкого пошуку
            default_merge_strategy: Дефолтна стратегія для операцій union (+, |)

        Examples:
            >>> g1 = Graph()
            >>> g2 = Graph()
            >>> g3 = g1 + g2  # Об'єднання графів (делеговано GraphOperations)
            >>> stats = g1.get_stats()  # Статистика (делеговано GraphStatistics)
            >>> len(g1)  # Кількість вузлів
            >>> for node in g1:  # Ітерація
            >>>     print(node.url)
            >>>
            >>> # Налаштування merge strategy через DI або вручну
            >>> g1 = Graph(default_merge_strategy='merge')
            >>> g3 = g1 + g2  # Використає 'merge' стратегію
    """

    def __init__(self, default_merge_strategy: Optional[str] = None):
        """
        Ініціалізує новий граф.

        Args:
            default_merge_strategy: Дефолтна стратегія для union операцій.
                Доступні: 'first', 'last', 'merge', 'newest', 'oldest', 'custom'.
                За замовчуванням: 'last' (якщо None, використовується 'last').
        """
        # Приватні поля для інкапсуляції
        self._nodes: Dict[str, Node] = {}
        self._edges: List[Edge] = []
        self._url_to_node: Dict[str, Node] = {}
        # Якщо None - використовуємо дефолт 'last'
        self._default_merge_strategy: str = default_merge_strategy or "last"

        # Edge index для O(1) lookup замість O(n)
        # Зберігає (source_node_id, target_node_id) пари для швидкої перевірки наявності edge
        self._edge_index: Set[tuple] = set()

        # Adjacency List для O(1) get_neighbors()
        # Замість O(E) проходу через всі edges, маємо O(1) lookup
        # _adjacency_list_out: source_id -> {target_ids}
        # _adjacency_list_in: target_id -> {source_ids}
        from collections import defaultdict

        self._adjacency_list_out: Dict[str, Set[str]] = defaultdict(set)
        self._adjacency_list_in: Dict[str, Set[str]] = defaultdict(set)

    # Read-only properties для безпечного доступу
    @property
    def nodes(self) -> Dict[str, Node]:
        """Read-only доступ до вузлів. Модифікація тільки через add_node()."""
        return self._nodes

    @property
    def edges(self) -> List[Edge]:
        """Read-only доступ до ребер. Модифікація тільки через add_edge()."""
        return self._edges

    @property
    def url_to_node(self) -> Dict[str, Node]:
        """Read-only доступ до URL мапи. Автоматично синхронізується з nodes."""
        return self._url_to_node

    @property
    def default_merge_strategy(self) -> str:
        """Повертає дефолтну стратегію merge для цього графа."""
        return self._default_merge_strategy
    
    @default_merge_strategy.setter
    def default_merge_strategy(self, value: str) -> None:
        """Встановлює дефолтну стратегію merge для цього графа."""
        valid_strategies = ['first', 'last', 'merge', 'newest', 'oldest', 'custom']
        if value not in valid_strategies:
            raise ValueError(
                f"Invalid merge strategy: {value}. "
                f"Valid: {valid_strategies}"
            )
        self._default_merge_strategy = value
    
    def _get_effective_merge_strategy(self) -> tuple:
        """
        Отримує ефективну стратегію merge з урахуванням контексту.
        
        ПРІОРИТЕТ (від вищого до нижчого):
        1. Локальний MergeContext (with with_merge_strategy('...'))
        2. default_merge_strategy графа self
        3. Глобальний DependencyRegistry default
        
        Returns:
            Tuple (strategy_name, custom_merge_fn)
        """
        try:
            # Спробуємо отримати з MergeContext (якщо є)
            from graph_crawler.application.context.merge_context import (
                MergeContextManager,
            )
            
            context = MergeContextManager.current()
            if context:
                # Є локальний контекст - використовуємо його
                return context.strategy, context.custom_merge_fn
        except ImportError:
            # Модуль context ще не доступний - використовуємо дефолт графа
            pass
        
        # Fallback до default_merge_strategy графа
        return self._default_merge_strategy, None

    def add_node(self, node: Node, overwrite: bool = False) -> Node:
        """
        Додає вузол до графу.

        Args:
            node: Вузол для додавання
            overwrite: Якщо True - перезаписує існуючий вузол з тим самим URL

        Returns:
            Доданий або існуючий вузол
        """
        if node.url in self._url_to_node:
            existing = self._url_to_node[node.url]
            if overwrite:
                # Перезаписуємо існуючий вузол
                logger.debug(f"Node overwritten: {node.url}")
                self._nodes[existing.node_id] = node
                self._url_to_node[node.url] = node
                return node
            else:
                # Повертаємо існуючий вузол
                return existing

        self._nodes[node.node_id] = node
        self._url_to_node[node.url] = node
        return node

    def get_node_by_url(self, url: str) -> Optional[Node]:
        """Отримує вузол за URL."""
        return self._url_to_node.get(url)

    def get_node_by_id(self, node_id: str) -> Optional[Node]:
        """Отримує вузол за ID."""
        return self._nodes.get(node_id)

    def add_edge(self, edge: Edge) -> Edge:
        """
        Додає ребро до графу.

        Args:
            edge: Ребро для додавання

        Returns:
            Додане ребро
        """
        self._edges.append(edge)
        # Оновлюємо edge index для O(1) lookup
        self._edge_index.add((edge.source_node_id, edge.target_node_id))
        # Оновлюємо adjacency lists
        self._adjacency_list_out[edge.source_node_id].add(edge.target_node_id)
        self._adjacency_list_in[edge.target_node_id].add(edge.source_node_id)
        return edge

    def has_edge(self, source_node_id: str, target_node_id: str) -> bool:
        """
        Перевіряє наявність ребра за O(1) замість O(n).

                Args:
                    source_node_id: ID вузла-джерела
                    target_node_id: ID цільового вузла

                Returns:
                    True якщо ребро існує

                Example:
                    >>> graph.has_edge('node1', 'node2')
        """
        return (source_node_id, target_node_id) in self._edge_index

    def remove_node(self, node_id: str) -> bool:
        """
        Видаляє вузол з графу за node_id.

        Також видаляє всі ребра пов'язані з цим вузлом.

        Args:
            node_id: ID вузла для видалення

        Returns:
            True якщо вузол був видалений, False якщо не знайдено

        Example:
            >>> graph.remove_node('node-123')
        """
        node = self._nodes.get(node_id)
        if not node:
            return False

        # Видаляємо вузол
        del self._nodes[node_id]
        del self._url_to_node[node.url]

        # Видаляємо ребра та оновлюємо edge_index + adjacency lists одночасно
        edges_to_keep = []
        for edge in self._edges:
            if edge.source_node_id == node_id or edge.target_node_id == node_id:
                # Видаляємо з edge_index
                self._edge_index.discard((edge.source_node_id, edge.target_node_id))
                # Видаляємо з adjacency lists
                self._adjacency_list_out[edge.source_node_id].discard(
                    edge.target_node_id
                )
                self._adjacency_list_in[edge.target_node_id].discard(
                    edge.source_node_id
                )
            else:
                edges_to_keep.append(edge)

        self._edges = edges_to_keep

        # Видаляємо порожні записи з adjacency lists
        if node_id in self._adjacency_list_out:
            del self._adjacency_list_out[node_id]
        if node_id in self._adjacency_list_in:
            del self._adjacency_list_in[node_id]

        logger.debug(f"Node removed: {node.url} (id={node_id})")
        return True

    def handle_redirect(
        self, original_node: Node, final_url: str, redirect_chain: list[str] = None
    ) -> Optional[Node]:
        """
        Обробляє HTTP редірект - переспрямовує граф на реальний URL.

        Коли сторінка /page1 редірить на /404:
        1. Знаходимо або створюємо вузол для final_url (/404)
        2. Переспрямовуємо всі incoming edges з original_node на final_url
        3. В metadata кожного edge додаємо redirect info
        4. Видаляємо original_node з графу (якщо final вже існує)

        ВАЖЛИВО: Граф завжди відображає РЕАЛЬНИЙ стан сайту!
        Якщо є 500 сторінок що редірять на /404 - буде 1 вузол /404 з 500 edges.

        Args:
            original_node: Вузол який редірить (буде видалений якщо final існує)
            final_url: Фінальний URL після редіректу
            redirect_chain: Список проміжних URL редіректів (optional)

        Returns:
            Node: Вузол для final_url (новий або існуючий)
            None: Якщо original_node не в графі

        Examples:
            >>> # /page1 редірить на /404
            >>> original = graph.get_node_by_url("/page1")
            >>> final_node = graph.handle_redirect(original, "/404")
            >>> # Тепер всі edges що вели на /page1 ведуть на /404
            >>> # з metadata: was_redirect=True, original_url="/page1"

            >>> # 500 сторінок редірять на /login
            >>> for page in broken_pages:
            ...     graph.handle_redirect(page, "/login")
            >>> # Результат: 1 вузол /login з 500 incoming edges
        """
        if not original_node or original_node.node_id not in self._nodes:
            logger.warning(f"Cannot handle redirect: original_node not in graph")
            return None

        original_url = original_node.url
        redirect_chain = redirect_chain or []

        # Якщо final_url == original_url - це не редірект
        if final_url == original_url:
            logger.debug(f"No redirect: {original_url} -> {final_url}")
            return original_node

        logger.info(f"Handling redirect: {original_url} -> {final_url}")

        # Крок 1: Знаходимо або створюємо вузол для final_url
        final_node = self.get_node_by_url(final_url)

        if final_node:
            # Final вузол вже існує - переспрямовуємо edges і видаляємо original
            logger.debug(f"Final node exists: {final_url}, redirecting edges")

            # Переспрямовуємо incoming edges з original на final
            self._redirect_incoming_edges(
                original_node=original_node,
                final_node=final_node,
                original_url=original_url,
                redirect_chain=redirect_chain,
            )

            # Видаляємо original_node з графу
            # (outgoing edges теж видаляються, що правильно - вони з редірект-сторінки)
            self.remove_node(original_node.node_id)

            return final_node
        else:
            # Final вузол НЕ існує - перетворюємо original на final
            logger.debug(
                f"Final node doesn't exist, transforming original: {original_url} -> {final_url}"
            )

            # Оновлюємо URL оригінального вузла
            del self._url_to_node[original_url]
            original_node.url = final_url
            self._url_to_node[final_url] = original_node

            # Додаємо redirect info в metadata вузла
            original_node.metadata["was_redirected_from"] = original_url
            original_node.metadata["redirect_chain"] = redirect_chain

            # Оновлюємо metadata всіх incoming edges
            for edge in self._edges:
                if edge.target_node_id == original_node.node_id:
                    edge.set_redirect_info(
                        original_url=original_url,
                        final_url=final_url,
                        redirect_chain=redirect_chain,
                    )

            return original_node

    def _redirect_incoming_edges(
        self,
        original_node: Node,
        final_node: Node,
        original_url: str,
        redirect_chain: list[str],
    ) -> int:
        """
        Переспрямовує всі incoming edges з original_node на final_node.

        Внутрішній метод для handle_redirect().

        Args:
            original_node: Вузол з якого переспрямовуємо
            final_node: Вузол на який переспрямовуємо
            original_url: Оригінальний URL (для metadata)
            redirect_chain: Ланцюжок редіректів (для metadata)

        Returns:
            Кількість переспрямованих edges
        """
        redirected_count = 0
        original_id = original_node.node_id
        final_id = final_node.node_id

        for edge in self._edges:
            if edge.target_node_id == original_id:
                # Оновлюємо target на final
                old_target = edge.target_node_id
                edge.target_node_id = final_id

                # Оновлюємо edge_index
                self._edge_index.discard((edge.source_node_id, old_target))
                self._edge_index.add((edge.source_node_id, final_id))

                # Оновлюємо adjacency lists
                self._adjacency_list_in[old_target].discard(edge.source_node_id)
                self._adjacency_list_in[final_id].add(edge.source_node_id)
                self._adjacency_list_out[edge.source_node_id].discard(old_target)
                self._adjacency_list_out[edge.source_node_id].add(final_id)

                # Додаємо redirect info в metadata
                edge.set_redirect_info(
                    original_url=original_url,
                    final_url=final_node.url,
                    redirect_chain=redirect_chain,
                )

                redirected_count += 1
                logger.debug(
                    f"Redirected edge: {edge.source_node_id[:8]}... -> {final_node.url}"
                )

        if redirected_count > 0:
            logger.info(
                f"Redirected {redirected_count} edges from {original_url} to {final_node.url}"
            )

        return redirected_count

    # ==================== Delegation to GraphStatistics ====================

    def get_unscanned_nodes(self) -> List[Node]:
        """
        Повертає список непросканованих вузлів.
        Делеговано GraphStatistics.

        Returns:
            Список вузлів зі scanned=False
        """
        return GraphStatistics.get_unscanned_nodes(self)

    def get_nodes_by_depth(self, depth: int) -> List[Node]:
        """
        Повертає всі вузли на певній глибині.
        Делеговано GraphStatistics.
        """
        return GraphStatistics.get_nodes_by_depth(self, depth)

    def get_stats(self) -> Dict[str, int]:
        """
        Повертає статистику графу.
        Делеговано GraphStatistics.

        Returns:
            Словник зі статистикою
        """
        return GraphStatistics.get_stats(self)

    def to_dict(self) -> Dict[str, Any]:
        """
        Серіалізує весь граф у словник.

        Використовує Pydantic model_dump() для автоматичної серіалізації
        всіх полів (включаючи кастомні поля в підкласах Node/Edge).

         ВАЖЛИВО про url_to_node мапу:
        - url_to_node НЕ серіалізується (це допоміжна структура)
        - При десеріалізації мапа відновлюється автоматично через add_node()
        - Не потрібно зберігати url_to_node окремо
        - Мапа завжди синхронізована з nodes словником
        """
        return {
            "nodes": [node.model_dump() for node in self._nodes.values()],
            "edges": [edge.model_dump() for edge in self._edges],
        }

    def clear(self):
        """Очищає граф."""
        self._nodes.clear()
        self._edges.clear()
        self._url_to_node.clear()
        # Очищаємо edge_index
        self._edge_index.clear()
        # Очищаємо adjacency lists
        self._adjacency_list_out.clear()
        self._adjacency_list_in.clear()

    def __repr__(self):
        stats = self.get_stats()
        return f"Graph(nodes={stats['total_nodes']}, edges={stats['total_edges']}, scanned={stats['scanned_nodes']})"

    # ==================== Python API: Колекційні операції ====================

    def __len__(self) -> int:
        """
        Повертає кількість вузлів у графі.

        Returns:
            Кількість вузлів

        Example:
            >>> graph = Graph()
            >>> len(graph)
            0
        """
        return len(self._nodes)

    def __iter__(self) -> Iterator[Node]:
        """
        Дозволяє ітерацію по вузлах графу.

        Yields:
            Node об'єкти

        Example:
            >>> for node in graph:
            >>>     print(node.url)
        """
        return iter(self._nodes.values())

    def __contains__(self, item: Union[str, Node]) -> bool:
        """
        Перевіряє наявність вузла в графі.

        Args:
            item: URL (str) або Node об'єкт

        Returns:
            True якщо вузол присутній у графі

        Example:
            >>> 'https://example.com' in graph
            >>> node in graph
        """
        if isinstance(item, str):
            # Перевіряємо за URL
            return item in self._url_to_node
        elif isinstance(item, Node):
            # Перевіряємо за node_id
            return item.node_id in self._nodes
        return False

    def __getitem__(self, key: Union[str, int]) -> Node:
        """
        Доступ до вузла за URL або індексом.

        Args:
            key: URL (str) або індекс (int)

        Returns:
            Node об'єкт

        Raises:
            KeyError: Якщо вузол не знайдено
            IndexError: Якщо індекс за межами

        Example:
            >>> node = graph['https://example.com']
            >>> node = graph[0]
        """
        if isinstance(key, str):
            # Доступ за URL
            node = self._url_to_node.get(key)
            if node is None:
                raise KeyError(f"Node with URL '{key}' not found")
            return node
        elif isinstance(key, int):
            # Доступ за індексом
            nodes_list = list(self._nodes.values())
            if key < 0 or key >= len(nodes_list):
                raise IndexError(f"Index {key} out of range")
            return nodes_list[key]
        else:
            raise TypeError(f"Key must be str or int, not {type(key)}")

    # ==================== Python API: Арифметичні операції ====================

    def __add__(self, other: "Graph") -> "Graph":
        """
        Об'єднання двох графів (union).
        Делеговано GraphOperations.union().

        ПРІОРИТЕТ СТРАТЕГІЇ (від вищого до нижчого):
        1. Локальний MergeContext (with with_merge_strategy('...'))
        2. default_merge_strategy графа self
        3. Глобальний DependencyRegistry default

        Args:
            other: Інший граф для об'єднання

        Returns:
            Новий граф (union)

        Example:
            >>> g1 = Graph(default_merge_strategy='merge')
            >>> g2 = Graph()
            >>> g3 = g1 + g2  # Використає 'merge' стратегію з g1
            >>>
            >>> # Або через контекст
            >>> from graph_crawler.application.context import with_merge_strategy
            >>> with with_merge_strategy('newest'):
            ...     g3 = g1 + g2  # Використає 'newest'
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot add Graph and {type(other)}")
        
        # Отримуємо стратегію з контексту або з графа
        strategy, custom_fn = self._get_effective_merge_strategy()
        
        return GraphOperations.union(
            self, other, 
            merge_strategy=strategy,
            custom_merge_fn=custom_fn,
        )

    def __sub__(self, other: "Graph") -> "Graph":
        """
        Різниця двох графів (difference).
        Делеговано GraphOperations.difference().

        Args:
            other: Граф для віднімання

        Returns:
            Новий граф (різниця)

        Example:
            >>> g3 = g1 - g2
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot subtract {type(other)} from Graph")
        return GraphOperations.difference(self, other)

    def __and__(self, other: "Graph") -> "Graph":
        """
        Перетин двох графів (intersection).
        Делеговано GraphOperations.intersection().

        Args:
            other: Інший граф

        Returns:
            Новий граф (перетин)

        Example:
            >>> g3 = g1 & g2
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot intersect Graph and {type(other)}")
        return GraphOperations.intersection(self, other)

    def __or__(self, other: "Graph") -> "Graph":
        """
        Об'єднання графів (альтернатива __add__).
        Делеговано GraphOperations.union().

        ПРІОРИТЕТ СТРАТЕГІЇ (від вищого до нижчого):
        1. Локальний MergeContext (with with_merge_strategy('...'))
        2. default_merge_strategy графа self
        3. Глобальний DependencyRegistry default

        Args:
            other: Інший граф

        Returns:
            Новий граф (union)

        Example:
            >>> g1 = Graph(default_merge_strategy='merge')
            >>> g2 = Graph()
            >>> g3 = g1 | g2  # Використає 'merge' стратегію з g1
            >>>
            >>> # Або через контекст
            >>> from graph_crawler.application.context import with_merge_strategy
            >>> with with_merge_strategy('newest'):
            ...     g3 = g1 | g2  # Використає 'newest'
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot OR Graph and {type(other)}")
        
        # Отримуємо стратегію з контексту або з графа
        strategy, custom_fn = self._get_effective_merge_strategy()
        
        return GraphOperations.union(
            self, other,
            merge_strategy=strategy,
            custom_merge_fn=custom_fn,
        )

    def __xor__(self, other: "Graph") -> "Graph":
        """
        Симетрична різниця графів.
        Делеговано GraphOperations.symmetric_difference().

        Args:
            other: Інший граф

        Returns:
            Новий граф (симетрична різниця)

        Example:
            >>> g3 = g1 ^ g2
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot XOR Graph and {type(other)}")
        return GraphOperations.symmetric_difference(self, other)

    # ==================== Python API: Порівняння ====================

    def __eq__(self, other: object) -> bool:
        """
        Перевіряє рівність двох графів.
        Делеговано GraphOperations.is_equal().

        Args:
            other: Інший граф

        Returns:
            True якщо графи рівні

        Example:
            >>> g1 == g2
        """
        if not isinstance(other, Graph):
            return False
        return GraphOperations.is_equal(self, other)

    def __ne__(self, other: object) -> bool:
        """Перевіряє нерівність графів."""
        return not self.__eq__(other)

    def __lt__(self, other: "Graph") -> bool:
        """
        Перевіряє чи є цей граф строгим підграфом іншого.
        Делеговано GraphOperations.is_subgraph(strict=True).

        Args:
            other: Інший граф

        Returns:
            True якщо self є строгим підграфом other

        Example:
            >>> g1 < g2  # g1 є підграфом g2
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot compare Graph and {type(other)}")
        return GraphOperations.is_subgraph(self, other, strict=True)

    def __le__(self, other: "Graph") -> bool:
        """
        Перевіряє чи є підграфом або рівним.
        Делеговано GraphOperations.is_subgraph(strict=False).
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot compare Graph and {type(other)}")
        return GraphOperations.is_subgraph(self, other, strict=False)

    def __gt__(self, other: "Graph") -> bool:
        """
        Перевіряє чи є цей граф строгим надграфом іншого.
        Делеговано GraphOperations.is_supergraph(strict=True).
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot compare Graph and {type(other)}")
        return GraphOperations.is_supergraph(self, other, strict=True)

    def __ge__(self, other: "Graph") -> bool:
        """
        Перевіряє чи є надграфом або рівним.
        Делеговано GraphOperations.is_supergraph(strict=False).
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot compare Graph and {type(other)}")
        return GraphOperations.is_supergraph(self, other, strict=False)

    # ==================== Методи теорії графів (delegation) ====================

    def is_subgraph(self, other: "Graph") -> bool:
        """
        Перевіряє чи є цей граф підграфом іншого.
        Делеговано GraphOperations.is_subgraph().

        Args:
            other: Інший граф

        Returns:
            True якщо self є підграфом other
        """
        return GraphOperations.is_subgraph(self, other, strict=False)

    def get_degree(self, node_id: str) -> int:
        """
        Повертає ступінь вузла (кількість інцидентних ребер).
        Делеговано GraphStatistics.get_degree().

        Args:
            node_id: ID вузла

        Returns:
            Ступінь вузла (in_degree + out_degree)
        """
        return GraphStatistics.get_degree(self, node_id)

    def get_in_degree(self, node_id: str) -> int:
        """
        Повертає вхідний ступінь вузла.
        Делеговано GraphStatistics.get_in_degree().
        """
        return GraphStatistics.get_in_degree(self, node_id)

    def get_out_degree(self, node_id: str) -> int:
        """
        Повертає вихідний ступінь вузла.
        Делеговано GraphStatistics.get_out_degree().
        """
        return GraphStatistics.get_out_degree(self, node_id)

    def get_neighbors(self, node_id: str) -> List[Node]:
        """
        Повертає всіх сусідів вузла.
        Делеговано GraphStatistics.get_neighbors().

        Args:
            node_id: ID вузла

        Returns:
            Список сусідніх вузлів
        """
        return GraphStatistics.get_neighbors(self, node_id)

    def is_connected(self) -> bool:
        """
        Перевіряє чи є граф зв'язаним.
        Делеговано GraphStatistics.is_connected().

        Returns:
            True якщо граф зв'язаний
        """
        return GraphStatistics.is_connected(self)

    def copy(self) -> "Graph":
        """
        Створює глибоку копію графу.

        Returns:
            Новий граф з копіями вузлів та ребер
        """
        result = Graph()
        for node in self._nodes.values():
            result.add_node(node)
        for edge in self._edges:
            result.add_edge(edge)
        return result

    # ==================== Edge Analysis Methods ====================

    def get_popular_nodes(self, top_n: int = 10, by: str = "in_degree") -> List[Node]:
        """Повертає топ N найпопулярніших nodes.

        Делеговано EdgeAnalysis.get_popular_nodes().

        Args:
            top_n: Кількість топ nodes
            by: Критерій ('in_degree', 'out_degree', 'total_degree')

        Returns:
            Список найпопулярніших Node об'єктів

        Example:
            >>> popular = graph.get_popular_nodes(top_n=10)
            >>> for node in popular:
            >>>     print(f"{node.url}: {graph.get_in_degree(node.node_id)} incoming")
        """
        return EdgeAnalysis.get_popular_nodes(self, top_n, by)

    def get_edge_statistics(self) -> Dict[str, Any]:
        """Повертає детальну статистику edges по типах.

        Делеговано EdgeAnalysis.get_edge_statistics().

        Returns:
            Словник зі статистикою (total_edges, by_type, avg_depth_diff, тощо)

        Example:
            >>> stats = graph.get_edge_statistics()
            >>> print(f"Internal links: {stats['by_type']['internal']}")
        """
        return EdgeAnalysis.get_edge_statistics(self)

    def find_cycles(self, max_cycles: Optional[int] = None) -> List[List[str]]:
        """Знаходить цикли в графі (DFS алгоритм).

        Делеговано EdgeAnalysis.find_cycles().

        Args:
            max_cycles: Максимальна кількість циклів (None = всі)

        Returns:
            Список циклів (кожен цикл - список node_id)

        Example:
            >>> cycles = graph.find_cycles(max_cycles=10)
            >>> for cycle in cycles:
            >>>     print(f"Cycle: {' -> '.join(cycle)}")
        """
        return EdgeAnalysis.find_cycles(self, max_cycles)

    def get_edges_by_type(
        self, link_types: List[str], match_mode: str = "any"
    ) -> List[Edge]:
        """Фільтрує edges по типу посилання.

        Делеговано EdgeAnalysis.get_edges_by_type().

        Args:
            link_types: Список типів для фільтрації
            match_mode: Режим ('any', 'all', 'exact')

        Returns:
            Список Edge об'єктів

        Example:
            >>> # Всі internal та deeper edges (OR)
            >>> edges = graph.get_edges_by_type(['internal', 'deeper'], match_mode='any')
            >>>
            >>> # Тільки edges що є і internal І deeper (AND)
            >>> edges = graph.get_edges_by_type(['internal', 'deeper'], match_mode='all')
        """
        return EdgeAnalysis.get_edges_by_type(self, link_types, match_mode)

    def export_edges(self, filepath: str, format: str = "json", **kwargs) -> Any:
        """Експортує edges в файл.

        Підтримує формати: json, csv, dot

        Args:
            filepath: Шлях до файлу
            format: Формат ('json', 'csv', 'dot')
            **kwargs: Додаткові параметри для експортера

        Returns:
            Результат експорту (залежить від формату)

        Example:
            >>> # JSON експорт
            >>> graph.export_edges("edges.json", format="json")
            >>>
            >>> # CSV експорт
            >>> graph.export_edges("edges.csv", format="csv")
            >>>
            >>> # DOT експорт для Graphviz
            >>> graph.export_edges("graph.dot", format="dot", edge_label="anchor_text")
        """
        from graph_crawler.application.services.exporters.edge_exporter import (
            EdgeExporter,
        )

        if format == "json":
            return EdgeExporter.export_to_json(self, filepath, **kwargs)
        elif format == "csv":
            return EdgeExporter.export_to_csv(self, filepath, **kwargs)
        elif format == "dot":
            return EdgeExporter.export_to_dot(self, filepath, **kwargs)
        else:
            raise ValueError(
                f"Unsupported format: {format}. Use 'json', 'csv', or 'dot'"
            )
