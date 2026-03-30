"""LinkProcessor - відповідає за обробку знайдених посилань.

Features:
- URLRule має ВИЩИЙ ПРІОРИТЕТ за фільтри
- Підтримка should_scan/should_follow_links перебивання фільтрів
- Новий порядок перевірки: URLRule → DomainFilter → PathFilter
- EdgeRule підтримка для складного контролю edges
- URLRule.create_edge для простого контролю edges на рівні URL
"""

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from graph_crawler.domain.value_objects.models import FetchResponse

from graph_crawler.application.use_cases.crawling.filters.domain_filter import (
    DomainFilter,
)
from graph_crawler.application.use_cases.crawling.filters.path_filter import PathFilter
from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.models import EdgeRule, Rule, SmartURLRule
from graph_crawler.extensions.plugins.node import NodePluginManager
from graph_crawler.shared.utils.url_utils import URLUtils

logger = logging.getLogger(__name__)


class LinkProcessor:
    """
    Відповідає за обробку знайдених посилань та створення нових нод.

    Single Responsibility: ТІЛЬКИ обробка посилань, фільтрація, створення нод та edges.
    Не знає про сканування, драйвери - тільки про граф та фільтри.

    - URLRule пріоритет: перевіряється ПЕРШИЙ (перед фільтрами)
    - Повертає (should_scan, can_create_edges) замість просто bool
    - URLRule може перебивати фільтри через should_scan=True/False
    """

    def __init__(
        self,
        graph: Graph,
        scheduler: CrawlScheduler,
        domain_filter: DomainFilter,
        path_filter: PathFilter,
        url_rules: Optional[list[Rule]] = None,
        edge_rules: Optional[list[EdgeRule]] = None,
        custom_node_class: Optional[type] = None,
        plugin_manager: Optional[NodePluginManager] = None,
        edge_strategy: str = "all",
        max_in_degree_threshold: int = 100,
    ):
        """
        Args:
            graph: Граф для додавання нод та edges
            scheduler: Scheduler для додавання нових нод у чергу
            domain_filter: Фільтр доменів
            path_filter: Фільтр шляхів
            url_rules: Список URLRule або SmartURLRule (Rule = Union[URLRule, SmartURLRule])
            edge_rules: Список EdgeRule (Iteration 4)
            custom_node_class: Кастомний клас Node (опціонально)
            plugin_manager: Plugin manager для нових нод
            edge_strategy: Стратегія створення edges
            max_in_degree_threshold: Максимальна кількість incoming edges
        """
        self.graph = graph
        self.scheduler = scheduler
        self.domain_filter = domain_filter
        self.path_filter = path_filter
        self.url_rules = url_rules or []
        self.edge_rules = edge_rules or []
        self.custom_node_class = custom_node_class or Node
        self.plugin_manager = plugin_manager

        # Edge Creation Strategy
        self.edge_strategy = edge_strategy
        self.max_in_degree_threshold = max_in_degree_threshold

        # Для стратегії FIRST_ENCOUNTER_ONLY використовуємо Bloom Filter замість set
        # Це запобігає memory leak при великих графах (100k+ сторінок)
        self._use_bloom_for_edges = True
        self._created_edges: Any  # Union[BloomFilter, set]
        try:
            from graph_crawler.shared.utils.bloom_filter import BloomFilter

            self._created_edges = BloomFilter(capacity=1_000_000, error_rate=0.001)
            logger.debug("Using Bloom Filter for _created_edges (memory efficient)")
        except ImportError:
            # Fallback на set якщо Bloom Filter недоступний
            self._created_edges = set()  # Set[(source_url, target_url)]
            self._use_bloom_for_edges = False
            logger.debug("Bloom Filter not available, using set for _created_edges")

        # Компілюємо regex для URLRule, зберігаємо SmartURLRule як є
        self._compiled_rules: list[tuple[re.Pattern | None, Rule]] = []
        for rule in self.url_rules:
            if isinstance(rule, SmartURLRule):
                # SmartURLRule використовує власний метод matches()
                self._compiled_rules.append((None, rule))
            else:
                # URLRule - компілюємо regex
                try:
                    compiled = re.compile(rule.pattern)
                    self._compiled_rules.append((compiled, rule))
                except re.error as e:
                    logger.warning("Invalid regex pattern '%s': %s", rule.pattern, e)

    def process_links(self, source_node: Node, links: list[str]) -> int:
        """
        Обробляє знайдені посилання з вузла.

        - URLRule перевіряється ПЕРШИЙ
        - can_create_edges встановлюється згідно URLRule
        - URLRule може перебивати фільтри

        Args:
            source_node: Вузол-джерело
            links: Список знайдених URL

        Returns:
            Кількість створених нових нод
        """
        # КРИТИЧНА ПЕРЕВІРКА: чи може source_node створювати нові edges
        if not source_node.can_create_edges:
            logger.debug("Node cannot create edges, skipping links processing: %s", source_node.url)
            return 0

        new_nodes_count = 0

        for link in links:
            new_nodes_count += self._process_single_link(source_node, link)

        return new_nodes_count

    async def process_links_async(
        self,
        source_node: Node,
        links: list[str],
        batch_size: int = 100,
        fetch_response: Optional["FetchResponse"] = None,
    ) -> int:
        """

        Обробляє посилання асинхронно з використанням async версій graph методів
        для thread-safety при batch mode з asyncio.gather().

        Args:
            source_node: Вузол-джерело
            links: Список знайдених URL
            batch_size: Кількість links між yield'ами (default: 100)
            fetch_response: FetchResponse з інформацією про редірект (optional)

        Returns:
            Кількість створених нових нод
        """
        import asyncio

        # КРИТИЧНА ПЕРЕВІРКА: чи може source_node створювати нові edges
        if not source_node.can_create_edges:
            logger.debug("Node cannot create edges, skipping links processing: %s", source_node.url)
            return 0

        new_nodes_count = 0

        for i, link in enumerate(links):
            # Yield control кожні batch_size links
            if i > 0 and i % batch_size == 0:
                await asyncio.sleep(0)  # Yield to event loop
            count = await self._process_single_link_async(source_node, link, fetch_response)
            new_nodes_count += count

        return new_nodes_count

    async def _process_single_link_async(
        self,
        source_node: Node,
        link: str,
        fetch_response: Optional["FetchResponse"] = None,
    ) -> int:
        """

        Використовує async версії graph.add_node_async() та graph.add_edge_async()
        для запобігання race conditions при batch mode.

        Args:
            source_node: Вузол-джерело
            link: URL посилання
            fetch_response: FetchResponse з інформацією про редірект source_node (optional)

        Returns:
            1 якщо створено нову ноду, 0 інакше
        """
        # Валідація URL
        if not URLUtils.is_valid_url(link):
            logger.debug("Invalid URL, skipping: %s", link)
            return 0

        # Нормалізація URL
        link = URLUtils.normalize_url(link)

        should_scan, can_create_edges = self._should_scan_url(link, source_node.url)

        if not should_scan:
            logger.debug("URL filtered out: %s", link)
            return 0
        url_already_known = self.scheduler.has_url(link)
        url_known_in_graph, target_node = self.graph.get_url_status(link)

        # Запам'ятовуємо чи нода була НОВОЮ (для NEW_ONLY стратегії)
        is_new_node = target_node is None and not url_already_known and not url_known_in_graph
        new_node_created = 0

        # ML PLUGIN SUPPORT: Отримуємо пріоритет з child_priorities батьківської ноди
        child_priority = None
        if source_node and source_node.user_data:
            child_priorities = source_node.user_data.get("child_priorities", {})
            if link in child_priorities:
                child_priority = child_priorities[link]
                logger.debug("Using ML plugin priority %s for %s", child_priority, link)

        if not target_node and not url_already_known and not url_known_in_graph:
            target_node = self.custom_node_class(
                url=link,
                depth=source_node.depth + 1,
                should_scan=should_scan,
                can_create_edges=can_create_edges,
                plugin_manager=self.plugin_manager,
            )

            # ML PLUGIN: Встановлюємо пріоритет в user_data для Scheduler
            if child_priority is not None:
                target_node.user_data["ml_priority"] = child_priority
            await self.graph.add_node_async(target_node)
            new_node_created = 1

            # Додаємо в чергу тільки якщо треба сканувати
            if should_scan:
                # Scheduler буде використовувати ml_priority якщо є
                self.scheduler.add_node(target_node, priority=child_priority)

        # Edge вже був створений коли ноду вперше знайшли
        if (url_already_known or url_known_in_graph) and target_node is None:
            logger.debug("URL already processed (evicted), skipping edge: %s", link)
            return new_node_created
        if target_node is None:
            logger.debug("Target node is None, skipping edge creation: %s", link)
            return new_node_created
        if target_node is not None and self._should_create_edge(
            source_node, target_node, link, is_new_node=is_new_node
        ):
            edge = Edge(source_node_id=source_node.node_id, target_node_id=target_node.node_id)

            # Заповнюємо edge metadata
            self._populate_edge_metadata(edge, source_node, target_node, link)

            # REDIRECT INFO: Якщо source_node мав редірект, зберігаємо це в edge
            if fetch_response and fetch_response.is_redirect:
                edge.add_metadata("source_had_redirect", True)
                edge.add_metadata("source_original_url", fetch_response.url)
                edge.add_metadata("source_final_url", fetch_response.final_url)
            await self.graph.add_edge_async(edge)
        elif target_node is not None:
            logger.debug("Edge creation skipped: %s -> %s", source_node.url, target_node.url)

        return new_node_created

    def _process_single_link(
        self,
        source_node: Node,
        link: str,
        fetch_response: Optional["FetchResponse"] = None,
    ) -> int:
        """

        Обробляє одне посилання. Винесено для DRY між sync та async версіями.

        Підтримує обробку HTTP редіректів - якщо source_node була завантажена
        і мала редірект, ця інформація зберігається в edges.

        Args:
            source_node: Вузол-джерело
            link: URL посилання
            fetch_response: FetchResponse з інформацією про редірект source_node (optional)

        Returns:
            1 якщо створено нову ноду, 0 інакше
        """
        # Валідація URL
        if not URLUtils.is_valid_url(link):
            logger.debug("Invalid URL, skipping: %s", link)
            return 0

        # Нормалізація URL
        link = URLUtils.normalize_url(link)

        should_scan, can_create_edges = self._should_scan_url(link, source_node.url)

        if not should_scan:
            logger.debug("URL filtered out: %s", link)
            return 0

        url_already_known = self.scheduler.has_url(link)
        url_known_in_graph, target_node = self.graph.get_url_status(link)

        # Запам'ятовуємо чи нода була НОВОЮ (для NEW_ONLY стратегії)
        is_new_node = target_node is None and not url_already_known and not url_known_in_graph
        new_node_created = 0

        # ML PLUGIN SUPPORT: Отримуємо пріоритет з child_priorities батьківської ноди
        child_priority = None
        if source_node and source_node.user_data:
            child_priorities = source_node.user_data.get("child_priorities", {})
            if link in child_priorities:
                child_priority = child_priorities[link]
                logger.debug("Using ML plugin priority %s for %s", child_priority, link)

        if not target_node and not url_already_known and not url_known_in_graph:
            target_node = self.custom_node_class(
                url=link,
                depth=source_node.depth + 1,
                should_scan=should_scan,
                can_create_edges=can_create_edges,
                plugin_manager=self.plugin_manager,
            )

            # ML PLUGIN: Встановлюємо пріоритет в user_data для Scheduler
            if child_priority is not None:
                target_node.user_data["ml_priority"] = child_priority

            self.graph.add_node(target_node)
            new_node_created = 1

            # Додаємо в чергу тільки якщо треба сканувати
            if should_scan:
                # Scheduler буде використовувати ml_priority якщо є
                self.scheduler.add_node(target_node, priority=child_priority)

        if (url_already_known or url_known_in_graph) and target_node is None:
            logger.debug("URL already processed (evicted), skipping edge: %s", link)
            return new_node_created
        if target_node is None:
            logger.debug("Target node is None, skipping edge creation: %s", link)
            return new_node_created
        # Порядок: URLRule.create_edge → EdgeRule → Edge Creation Strategies
        if target_node is not None and self._should_create_edge(
            source_node, target_node, link, is_new_node=is_new_node
        ):
            edge = Edge(source_node_id=source_node.node_id, target_node_id=target_node.node_id)

            # Заповнюємо edge metadata
            self._populate_edge_metadata(edge, source_node, target_node, link)

            # REDIRECT INFO: Якщо source_node мав редірект, зберігаємо це в edge
            if fetch_response and fetch_response.is_redirect:
                edge.add_metadata("source_had_redirect", True)
                edge.add_metadata("source_original_url", fetch_response.url)
                edge.add_metadata("source_final_url", fetch_response.final_url)

            self.graph.add_edge(edge)
        elif target_node is not None:
            logger.debug("Edge creation skipped: %s -> %s", source_node.url, target_node.url)

        return new_node_created

    def _should_scan_url(self, url: str, source_url: str) -> tuple[bool, bool]:
        """
        Визначає should_scan та can_create_edges для URL.

        Args:
            url: URL для перевірки
            source_url: URL вузла-джерела
        Returns:
            Tuple[bool, bool]: (should_scan, can_create_edges)
                - should_scan: Чи сканувати сторінку
                - can_create_edges: Чи може створювати нові edges
        Example:
            >>> # Плагін може примусово дозволити URL:
            >>> source_node.user_data['explicit_scan_decisions'] = {'https://external.com': True}
            >>> should_scan, can_create = self._should_scan_url('https://external.com', source_url)
            >>> # should_scan=True (від плагіна), незважаючи на фільтри
        """
        #  КРОК 0: НОВИЙ МЕХАНІЗМ - Explicit decisions від плагінів (НАЙВИЩИЙ ПРІОРИТЕТ)
        # Дозволяє плагінам (ML, SEO, тощо) повністю контролювати які URL обробляти

        # Використовуємо load_from_disk=False для економії RAM
        source_node = self.graph.get_node_by_url(source_url, load_from_disk=False)
        if source_node:
            explicit_decisions = source_node.user_data.get("explicit_scan_decisions", {})
            if url in explicit_decisions:
                should_scan = explicit_decisions[url]
                logger.debug("URL decision from plugin: %s (scan=%s)", url, should_scan)
                if not should_scan:
                    return False, False
                return True, True

        #  КРОК 1: Перевіряємо URLRule ПЕРШИМИ (другий пріоритет)
        matched_rule = self._match_url_rule(url)

        if matched_rule:
            # URLRule знайдено
            should_scan = matched_rule.should_scan
            can_create_edges = matched_rule.should_follow_links
            if should_scan is False:
                logger.debug("URL excluded by rule: %s", url)
                return False, False
            if should_scan is True:
                # can_create_edges може бути None - тоді True
                if can_create_edges is None:
                    can_create_edges = True

                logger.debug(
                    f"URL allowed by rule: {url} (scan={should_scan}, follow={can_create_edges})"
                )
                return True, can_create_edges

            # should_scan is None - продовжуємо до фільтрів

        #  КРОК 2: URLRule не перебив - перевіряємо DomainFilter
        domain_allowed = self.domain_filter.is_allowed(url, source_url)
        if not domain_allowed:
            logger.debug("Domain not allowed: %s", url)
            return False, False

        #  КРОК 3: Перевіряємо PathFilter
        path_allowed = self.path_filter.is_allowed(url, source_url)
        if not path_allowed:
            logger.debug("Path not allowed: %s", url)
            return False, False

        # Фільтри дозволяють - звичайна поведінка
        # Але якщо URLRule встановив should_follow_links - використовуємо його
        can_create_edges = True
        if matched_rule and matched_rule.should_follow_links is not None:
            can_create_edges = matched_rule.should_follow_links

        return True, can_create_edges

    def _match_url_rule(self, url: str) -> Optional[Rule]:
        """
        Знаходить перше правило що матчить URL.

        Підтримує як URLRule (regex по всьому URL) так і SmartURLRule (з scope).

        Args:
            url: URL для перевірки

        Returns:
            Перший URLRule або SmartURLRule що матчить, або None

        Example:
            >>> rule = self._match_url_rule('https://work.ua/job/123')
            >>> if rule:
            >>>     print(f"Matched: {rule.pattern}")
        """
        for compiled_pattern, rule in self._compiled_rules:
            if isinstance(rule, SmartURLRule):
                # SmartURLRule використовує власний метод matches() з урахуванням scope
                if rule.matches(url):
                    logger.debug(
                        f"SmartURLRule matched: {rule.pattern} (scope={rule.scope.value}) for {url}"
                    )
                    return rule
            else:
                # URLRule - використовуємо скомпільований regex
                if compiled_pattern and compiled_pattern.search(url):
                    logger.debug("URLRule matched: %s for %s", rule.pattern, url)
                    return rule
        return None

    def _should_create_edge(
        self,
        source_node: Node,
        target_node: Node,
        target_url: str,
        is_new_node: bool = False,
    ) -> bool:
        """
        Визначає чи треба створювати edge між source та target nodes.

        Args:
            source_node: Source node
            target_node: Target node
            target_url: URL target node (для перевірки URLRule)
            is_new_node: Чи була target_node щойно створена (для NEW_ONLY стратегії)
        Returns:
            bool: True якщо треба створювати edge, False інакше
        Example:
            >>> if self._should_create_edge(source, target, target_url, is_new_node=True):
            >>>     edge = Edge(source_node_id=source.node_id, target_node_id=target.node_id)
            >>>     self.graph.add_edge(edge)
        """
        # КРОК 1: Перевіряємо URLRule.create_edge (НАЙВИЩИЙ ПРІОРИТЕТ)
        matched_rule = self._match_url_rule(target_url)
        if matched_rule and matched_rule.create_edge is not None:
            if matched_rule.create_edge is False:
                logger.debug("Edge skipped by URLRule: %s -> %s", source_node.url, target_url)
                return False
            # create_edge=True - дозволяємо (перебиває EdgeRule та Strategies!)
            logger.debug("Edge allowed by URLRule: %s -> %s", source_node.url, target_url)
            return True

        # КРОК 2: Перевіряємо EdgeRule
        for edge_rule in self.edge_rules:
            should_create = edge_rule.should_create_edge(
                source_node.url, target_node.url, source_node.depth, target_node.depth
            )

            if should_create is not None:
                if should_create is False:
                    logger.debug(
                        f"Edge skipped by EdgeRule: {source_node.url} -> {target_node.url} "
                        f"(rule: {edge_rule})"
                    )
                    return False
                # should_create=True - дозволяємо (перебиває Strategies!)
                logger.debug(
                    f"Edge allowed by EdgeRule: {source_node.url} -> {target_node.url} "
                    f"(rule: {edge_rule})"
                )
                return True

        # КРОК 3: Застосовуємо Edge Creation Strategies
        from graph_crawler.domain.value_objects.models import EdgeCreationStrategy

        # ALL: Створювати всі edges (default)
        if self.edge_strategy == EdgeCreationStrategy.ALL.value:
            return True

        # NEW_ONLY: Створювати edge ТІЛЬКИ якщо target node щойно створена
        # (її не було в графі до цього виклику process_links)
        # Це означає: кожна нода матиме максимум 1 incoming edge (від того хто її знайшов першим)
        if self.edge_strategy == EdgeCreationStrategy.NEW_ONLY.value:
            if not is_new_node:
                logger.debug(
                    f"Skipping edge by strategy NEW_ONLY: target already existed in graph: "
                    f"{source_node.url} -> {target_node.url}"
                )
            return is_new_node

        # MAX_IN_DEGREE: Не створювати edge якщо target має >= threshold incoming edges
        if self.edge_strategy == EdgeCreationStrategy.MAX_IN_DEGREE.value:
            in_degree = self.graph.get_in_degree(target_node.node_id)
            if in_degree >= self.max_in_degree_threshold:
                logger.debug(
                    f"Skipping edge by strategy MAX_IN_DEGREE: target has {in_degree} incoming edges "
                    f"(threshold={self.max_in_degree_threshold}): {target_node.url}"
                )
                return False
            return True

        # SAME_DEPTH_ONLY: Створювати edges тільки на nodes тієї ж глибини
        if self.edge_strategy == EdgeCreationStrategy.SAME_DEPTH_ONLY.value:
            return source_node.depth == target_node.depth

        # DEEPER_ONLY: Створювати edges тільки на глибші рівні (не назад)
        if self.edge_strategy == EdgeCreationStrategy.DEEPER_ONLY.value:
            return target_node.depth > source_node.depth

        # FIRST_ENCOUNTER_ONLY: Створювати тільки перший edge на кожен target URL
        if self.edge_strategy == EdgeCreationStrategy.FIRST_ENCOUNTER_ONLY.value:
            in_degree = self.graph.get_in_degree(target_node.node_id)
            if in_degree > 0:
                logger.debug(
                    f"Skipping edge by strategy FIRST_ENCOUNTER_ONLY: target already has edges: {target_node.url}"
                )
                return False
            return True

        # Unknown strategy - default to True
        logger.warning("Unknown edge_strategy: %s, defaulting to ALL", self.edge_strategy)
        return True

    def _populate_edge_metadata(
        self, edge: Edge, source_node: Node, target_node: Node, target_url: str
    ) -> None:
        """
        Заповнює metadata edge автоматичними полями.

        Додає наступні поля в edge.metadata:
        - link_type: List[str] - типи посилання (internal, external, deeper, тощо)
        - depth_diff: int - різниця глибини між source та target
        - created_at: str - timestamp створення edge (ISO format)
        - target_scanned: bool - чи відсканована цільова сторінка

        Args:
            edge: Edge об'єкт для заповнення
            source_node: Вузол-джерело
            target_node: Цільовий вузол
            target_url: URL цільового вузла
        """
        # Timestamp створення (використовуємо timezone-aware datetime)
        from datetime import timezone

        edge.add_metadata("created_at", datetime.now(timezone.utc).isoformat())

        # Різниця глибини
        depth_diff = target_node.depth - source_node.depth
        edge.add_metadata("depth_diff", depth_diff)

        # Статус сканування target
        edge.add_metadata("target_scanned", target_node.scanned)

        # Визначаємо типи посилання
        link_types = self._determine_link_types(source_node, target_node, target_url, depth_diff)
        edge.add_metadata("link_type", link_types)

        logger.debug("Edge metadata populated: %s, depth_diff=%s", link_types, depth_diff)

    def _determine_link_types(
        self, source_node: Node, target_node: Node, target_url: str, depth_diff: int
    ) -> list[str]:
        """
        OPTIMIZATION-003: Оптимізоване визначення типів посилання.

        Args:
            source_node: Вузол-джерело
            target_node: Цільовий вузол
            target_url: URL цільового вузла
            depth_diff: Різниця глибини
        Returns:
            Список типів посилання
        """
        # Використовуємо кешований urlparse
        source_domain = URLUtils.get_domain(source_node.url)
        target_domain = URLUtils.get_domain(target_url)

        # OPTIMIZATION-003: Пряма побудова списку - швидше за list comprehension з tuple
        link_types = []

        # Domain type (взаємовиключні)
        if source_domain == target_domain:
            link_types.append("internal")
        else:
            link_types.append("external")

        # Depth type (взаємовиключні)
        if depth_diff == 0:
            link_types.append("same_depth")
        elif depth_diff > 0:
            link_types.append("deeper")
        else:
            link_types.append("back")

        # Scan status (взаємовиключні)
        if target_node.scanned:
            link_types.append("to_scanned")
        else:
            link_types.append("to_unscanned")

        return link_types
