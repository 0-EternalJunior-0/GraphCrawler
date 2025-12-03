"""NodeScanner - відповідає тільки за сканування окремих нод .
- Всі методи тепер async
- Використовує async driver.fetch() та fetch_many()
- scan_node() -> async scan_node()
- scan_batch() -> async scan_batch()
- Підтримка HTTP редіректів через FetchResponse
"""

import logging
from typing import List, Optional, Tuple

from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.models import FetchResponse
from graph_crawler.infrastructure.transport.base import BaseDriver

logger = logging.getLogger(__name__)


class NodeScanner:
    """
    Async-First сканер вузлів .

    Single Responsibility: ТІЛЬКИ завантаження HTML та обробка через плагіни.
    Не знає про граф, scheduler, фільтри - тільки про окремі ноди.
    """

    def __init__(self, driver: BaseDriver):
        """
        Args:
            driver: Async драйвер для завантаження сторінок
        """
        self.driver = driver

    async def scan_node(self, node: Node) -> Tuple[List[str], Optional[FetchResponse]]:
        """
        Async сканує один вузол (сторінку).

        Args:
            node: Вузол для сканування

        Returns:
            Tuple (список знайдених URL посилань, FetchResponse з redirect info)
        """
        logger.debug(f"Scanning node: {node.url}")

        try:
            # Async завантажуємо сторінку через driver
            result = await self.driver.fetch(node.url)

            if not result or result.error:
                logger.warning(
                    f"Failed to fetch {node.url}: {result.error if result else 'Unknown error'}"
                )
                node.mark_as_scanned()
                return ([], result)

            # Зберігаємо статус
            node.response_status = result.status_code

            # Обробляємо HTML одразу (метадані + посилання)
            # HTML НЕ зберігається для економії пам'яті
            html = result.html
            if not html:
                node.mark_as_scanned()
                return ([], result)

            # Node.process_html() викликає плагіни та повертає посилання
            links = await node.process_html(html)

            # Позначаємо вузол як просканований
            node.mark_as_scanned()

            redirect_info = ""
            if result.is_redirect:
                redirect_info = f" [REDIRECT: {result.url} -> {result.final_url}]"

            logger.info(
                f"Scanned: {node.url} - {len(links)} links found{redirect_info}"
            )
            return (links, result)

        except Exception as e:
            logger.error(f"Error scanning {node.url}: {e}")
            node.mark_as_scanned()
            return ([], None)

    async def scan_batch(
        self, nodes: List[Node]
    ) -> List[Tuple[Node, List[str], Optional[FetchResponse]]]:
        """
        Async сканує батч вузлів паралельно.

        Args:
            nodes: Список вузлів для сканування

        Returns:
            Список кортежів (node, links, fetch_response)
        """
        if not nodes:
            return []

        # Async паралельно завантажуємо всі URLs
        urls = [node.url for node in nodes]
        logger.info(f"Fetching batch: {len(urls)} URLs")

        results = await self.driver.fetch_many(urls)

        # Обробляємо результати
        scan_results = []
        for node, result in zip(nodes, results):
            if not result or result.error:
                logger.warning(
                    f"Failed to fetch {node.url}: {result.error if result else 'Unknown error'}"
                )
                node.mark_as_scanned()
                scan_results.append((node, [], result))
                continue

            # Зберігаємо статус
            node.response_status = result.status_code

            # Обробляємо HTML
            html = result.html
            if html:
                links = await node.process_html(html)
                node.mark_as_scanned()

                redirect_info = ""
                if result.is_redirect:
                    redirect_info = f" [REDIRECT: {result.url} -> {result.final_url}]"

                logger.info(
                    f"Scanned: {node.url} - {len(links)} links found{redirect_info}"
                )
                scan_results.append((node, links, result))
            else:
                node.mark_as_scanned()
                scan_results.append((node, [], result))

        return scan_results
