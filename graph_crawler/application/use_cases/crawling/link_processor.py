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
from typing import Optional

from graph_crawler.application.use_cases.crawling.filters.domain_filter import (
    DomainFilter,
)
from graph_crawler.application.use_cases.crawling.filters.path_filter import PathFilter
from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.models import EdgeRule, URLRule
from graph_crawler.extensions.plugins.node import NodePluginManager
from graph_crawler.shared.utils.url_utils import URLUtils

logger = logging.getLogger(__name__)


class LinkProcessor:
    """
    Відповідає за обробку знайдених посилань та створення нових нод.

    Single Responsibility: ТІЛЬКИ обробка посилань, фільтрація, створення нод та edges.
    Не знає про сканування, драйвери - тільки про граф та фільтри.

    Alpha 2.0 FEATURES:
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
        url_rules: Optional[list[URLRule]] = None,
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
            url_rules: Список URLRule (Alpha 2.0)
            edge_rules: Список EdgeRule (Iteration 4)
            custom_node_class: Кастомний клас Node (опціонально)
            plugin_manager: Plugin manager для нових нод
            edge_strategy: Стратегія створення edges (Alpha 2.0)
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

        # Для стратегії FIRST_ENCOUNTER_ONLY: Set вже створених edges
        self._created_edges: set = set()  # Set[(source_url, target_url)]

        # Компілюємо regex для URLRule
        self._compiled_rules = []
        for rule in self.url_rules:
            try:
                compiled = re.compile(rule.pattern)
                self._compiled_rules.append((compiled, rule))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{rule.pattern}': {e}")

    def process_links(self, source_node: Node, links: list[str]) -> int:
        """
        Обробляє знайдені посилання з вузла (Alpha 2.0 з URLRule пріоритетом).

        Alpha 2.0 CHANGES:
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
            logger.debug(
                f"Node cannot create edges, skipping links processing: {source_node.url}"
            )
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
        Async версія process_links.

        Обробляє посилання асинхронно, yield'ить control кожні batch_size links
        для неблокуючої роботи event loop.

        Підтримує обробку HTTP редіректів через fetch_response.

        Args:
            source_node: Вузол-джерело
            links: Список знайдених URL
            batch_size: Кількість links між yield'ами (default: 100)
            fetch_response: FetchResponse з інформацією про редірект (optional)

        Returns:
            Кількість створених нових нод
        """
        import asyncio

        from graph_crawler.domain.value_objects.models import FetchResponse

        # КРИТИЧНА ПЕРЕВІРКА: чи може source_node створювати нові edges
        if not source_node.can_create_edges:
            logger.debug(
                f"Node cannot create edges, skipping links processing: {source_node.url}"
            )
            return 0

        new_nodes_count = 0

        for i, link in enumerate(links):
            # Yield control кожні batch_size links
            if i > 0 and i % batch_size == 0:
                await asyncio.sleep(0)  # Yield to event loop

            new_nodes_count += self._process_single_link(
                source_node, link, fetch_response
            )

        return new_nodes_count

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
            logger.debug(f"Invalid URL, skipping: {link}")
            return 0

        # Нормалізація URL
        link = URLUtils.normalize_url(link)

        #  Alpha 2.0: Отримуємо should_scan та can_create_edges (URLRule має пріоритет!)
        should_scan, can_create_edges = self._should_scan_url(link, source_node.url)

        if not should_scan:
            logger.debug(f"URL filtered out: {link}")
            return 0

        # Перевіряємо чи вузол вже існує
        target_node = self.graph.get_node_by_url(link)

        # FIX: Запам'ятовуємо чи нода була НОВОЮ (для NEW_ONLY стратегії)
        is_new_node = target_node is None
        new_node_created = 0

        if not target_node:
            # Створюємо новий вузол (ЕТАП 1: URL_STAGE)
            target_node = self.custom_node_class(
                url=link,
                depth=source_node.depth + 1,
                should_scan=should_scan,
                can_create_edges=can_create_edges,  #  Alpha 2.0: З URLRule
                plugin_manager=self.plugin_manager,
            )
            self.graph.add_node(target_node)
            new_node_created = 1

            # Додаємо в чергу тільки якщо треба сканувати
            if should_scan:
                self.scheduler.add_node(target_node)

        # Перевіряємо чи треба створювати edge
        # Порядок: URLRule.create_edge → EdgeRule → Edge Creation Strategies
        if self._should_create_edge(
            source_node, target_node, link, is_new_node=is_new_node
        ):
            # Створюємо ребро
            edge = Edge(
                source_node_id=source_node.node_id, target_node_id=target_node.node_id
            )

            # Заповнюємо edge metadata
            self._populate_edge_metadata(edge, source_node, target_node, link)

            #  REDIRECT INFO: Якщо source_node мав редірект, зберігаємо це в edge
            # Примітка: це НЕ стосується target (link), а source_node!
            # Редірект link буде виявлено коли target_node буде завантажуватись
            if fetch_response and fetch_response.is_redirect:
                # Це інформація про source_node редірект (для діагностики)
                edge.add_metadata("source_had_redirect", True)
                edge.add_metadata("source_original_url", fetch_response.url)
                edge.add_metadata("source_final_url", fetch_response.final_url)

            self.graph.add_edge(edge)
        else:
            logger.debug(
                f"Edge creation skipped: {source_node.url} -> {target_node.url}"
            )

        return new_node_created

    def _should_scan_url(self, url: str, source_url: str) -> tuple[bool, bool]:
        """
        Визначає should_scan та can_create_edges для URL.

         Підтримка explicit decisions від плагінів!

        НОВИЙ ПОРЯДОК ПЕРЕВІРКИ:
        0. Explicit decisions від плагінів (source_node.user_data) - НАЙВИЩИЙ ПРІОРИТЕТ
        1. URLRule (може перебити фільтри)
        2. DomainFilter
        3. PathFilter

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
        source_node = self.graph.get_node_by_url(source_url)
        if source_node:
            explicit_decisions = source_node.user_data.get(
                "explicit_scan_decisions", {}
            )
            if url in explicit_decisions:
                should_scan = explicit_decisions[url]
                logger.debug(f"URL decision from plugin: {url} (scan={should_scan})")
                # Якщо плагін заборонив - не скануємо
                if not should_scan:
                    return False, False
                # Якщо плагін дозволив - повертаємо True (перебиває всі фільтри!)
                return True, True

        #  КРОК 1: Перевіряємо URLRule ПЕРШИМИ (другий пріоритет)
        matched_rule = self._match_url_rule(url)

        if matched_rule:
            # URLRule знайдено
            should_scan = matched_rule.should_scan
            can_create_edges = matched_rule.should_follow_links

            # Якщо should_scan явно False - виключаємо URL
            if should_scan is False:
                logger.debug(f"URL excluded by rule: {url}")
                return False, False

            # Якщо should_scan явно True - дозволяємо (перебиває фільтри!)
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
            logger.debug(f"Domain not allowed: {url}")
            return False, False

        #  КРОК 3: Перевіряємо PathFilter
        path_allowed = self.path_filter.is_allowed(url, source_url)
        if not path_allowed:
            logger.debug(f"Path not allowed: {url}")
            return False, False

        # Фільтри дозволяють - звичайна поведінка
        # Але якщо URLRule встановив should_follow_links - використовуємо його
        can_create_edges = True
        if matched_rule and matched_rule.should_follow_links is not None:
            can_create_edges = matched_rule.should_follow_links

        return True, can_create_edges

    def _match_url_rule(self, url: str) -> Optional[URLRule]:
        """
        Знаходить перше правило що матчить URL.

        Alpha 2.0: URLRule мають найвищий пріоритет у фільтрації.

        Args:
            url: URL для перевірки

        Returns:
            Перший URLRule що матчить або None

        Example:
            >>> rule = self._match_url_rule('https://work.ua/job/123')
            >>> if rule:
            >>>     print(f"Matched: {rule.pattern}")
        """
        for compiled_pattern, rule in self._compiled_rules:
            if compiled_pattern.search(url):
                logger.debug(f"URLRule matched: {rule.pattern} for {url}")
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

        Порядок перевірки:
        1. URLRule.create_edge для target URL (НАЙВИЩИЙ ПРІОРИТЕТ)
        2. EdgeRule правила
        3. Edge Creation Strategies

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
                logger.debug(
                    f"Edge skipped by URLRule: {source_node.url} -> {target_url}"
                )
                return False
            # create_edge=True - дозволяємо (перебиває EdgeRule та Strategies!)
            logger.debug(f"Edge allowed by URLRule: {source_node.url} -> {target_url}")
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
        logger.warning(
            f"Unknown edge_strategy: {self.edge_strategy}, defaulting to ALL"
        )
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
        # Timestamp створення
        edge.add_metadata("created_at", datetime.utcnow().isoformat())

        # Різниця глибини
        depth_diff = target_node.depth - source_node.depth
        edge.add_metadata("depth_diff", depth_diff)

        # Статус сканування target
        edge.add_metadata("target_scanned", target_node.scanned)

        # Визначаємо типи посилання
        link_types = self._determine_link_types(
            source_node, target_node, target_url, depth_diff
        )
        edge.add_metadata("link_type", link_types)

        logger.debug(f"Edge metadata populated: {link_types}, depth_diff={depth_diff}")

    def _determine_link_types(
        self, source_node: Node, target_node: Node, target_url: str, depth_diff: int
    ) -> list[str]:
        """
        Визначає типи посилання для edge. Оптимізовано - використовує кешований urlparse

        Можливі типи (комбінації):
        - internal: той самий домен
        - external: інший домен
        - same_depth: та сама глибина (depth_diff == 0)
        - deeper: більша глибина (depth_diff > 0)
        - back: менша глибина (depth_diff < 0, посилання назад)
        - to_scanned: target вже відсканований
        - to_unscanned: target ще не відсканований

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

        return [
            t
            for condition, t in [
                (source_domain == target_domain, "internal"),
                (source_domain != target_domain, "external"),
                (depth_diff == 0, "same_depth"),
                (depth_diff > 0, "deeper"),
                (depth_diff < 0, "back"),
                (target_node.scanned, "to_scanned"),
                (not target_node.scanned, "to_unscanned"),
            ]
            if condition
        ]
