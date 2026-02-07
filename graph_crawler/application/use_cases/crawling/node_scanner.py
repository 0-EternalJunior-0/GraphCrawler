"""NodeScanner - відповідає тільки за сканування окремих нод.

- Всі методи тепер async
- Використовує async driver.fetch() та fetch_many()
- scan_node() -> async scan_node()
- scan_batch() -> async scan_batch()
- Підтримка HTTP редіректів через FetchResponse
- Детекція content_type делегована ContentType.detect() (Domain Layer)
"""
import asyncio
import logging
from typing import List, Optional, Tuple

from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.models import ContentType, FetchResponse
from graph_crawler.infrastructure.transport.base import BaseDriver

logger = logging.getLogger(__name__)


class NodeScanner:
    """
    Async-First сканер вузлів.

    Single Responsibility: ТІЛЬКИ завантаження HTML та обробка через плагіни.
    Не знає про граф, scheduler, фільтри - тільки про окремі ноди.
    
    Детекція content_type делегована ContentType.detect() (Domain Layer).
    """

    def __init__(self, driver: BaseDriver):
        """
        Args:
            driver: Async драйвер для завантаження сторінок
        """
        self.driver = driver

    def _process_fetch_result(
        self, node: Node, result: Optional[FetchResponse]
    ) -> Tuple[List[str], Optional[FetchResponse], bool]:
        """
        Обробляє результат fetch та визначає чи потрібно сканувати HTML.

        Єдина точка обробки для scan_node() та scan_batch() (DRY principle).

        Args:
            node: Вузол для обробки
            result: FetchResponse від драйвера

        Returns:
            Tuple (links, result, should_process_html):
                - links: порожній список якщо не потрібно сканувати
                - result: оригінальний FetchResponse
                - should_process_html: True якщо потрібно викликати process_html()
        """
        html = result.html if result else None
        
        # Визначаємо content_type через Domain Layer метод
        content_type_header = None
        if result and result.headers:
            content_type_header = result.headers.get("content-type") or result.headers.get("Content-Type")
        
        node.content_type = ContentType.detect(
            content_type_header=content_type_header,
            url=node.url,
            content=html,
            status_code=result.status_code if result else None,
            has_error=not result or bool(result.error),
        )

        # Помилка завантаження
        if not result or result.error:
            logger.warning(
                f"Failed to fetch {node.url}: {result.error if result else 'Unknown error'} "
                f"[content_type={node.content_type.value}]"
            )
            node.mark_as_scanned()
            return ([], result, False)

        # Зберігаємо статус та redirect info
        node.response_status = result.status_code
        node._response_final_url = result.final_url
        node._response_original_url = result.url
        node._response_is_redirect = result.is_redirect

        # Пустий контент
        if not html or node.content_type == ContentType.EMPTY:
            logger.info(
                f"Empty content for {node.url} [status={result.status_code}, "
                f"content_type={node.content_type.value}]"
            )
            node.mark_as_scanned()
            return ([], result, False)

        # Не scannable контент (image, pdf, etc.)
        if not node.content_type.is_scannable():
            logger.debug(
                f"Non-scannable content type for {node.url}: {node.content_type.value}"
            )
            node.mark_as_scanned()
            return ([], result, False)

        # Потрібно обробити HTML
        return ([], result, True)

    def _log_scan_result(
        self, node: Node, links: List[str], result: Optional[FetchResponse]
    ) -> None:
        """Логує результат сканування."""
        redirect_info = ""
        if result and result.is_redirect:
            redirect_info = f" [REDIRECT: {result.url} -> {result.final_url}]"

        logger.info(
            f"Scanned: {node.url} - {len(links)} links found "
            f"[content_type={node.content_type.value}]{redirect_info}"
        )

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

            # Обробляємо результат через спільний метод
            links, result, should_process = self._process_fetch_result(node, result)
            
            if not should_process:
                return (links, result)

            # Обробляємо HTML через плагіни
            html = result.html
            links = await node.process_html(html)
            node.mark_as_scanned()

            self._log_scan_result(node, links, result)
            return (links, result)

        except Exception as e:
            logger.error(f"Error scanning {node.url}: {e}")
            node.content_type = ContentType.ERROR
            node.mark_as_scanned()
            return ([], None)

    async def scan_batch(
            self, nodes: List[Node]
    ) -> List[Tuple[Node, List[str], Optional[FetchResponse]]]:
        """
        Async сканує батч вузлів ПАРАЛЕЛЬНО.

        # HTML парсинг тепер паралельний через asyncio.gather()!

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

        # Паралельна обробка HTML через asyncio.gather()
        async def process_single(node: Node, result: Optional[FetchResponse]) -> Tuple[Node, List[str], Optional[FetchResponse]]:
            """Обробляє одну ноду асинхронно."""
            try:
                # Обробляємо результат через спільний метод
                links, result, should_process = self._process_fetch_result(node, result)
                
                if not should_process:
                    return (node, links, result)

                # Обробляємо HTML через плагіни (async!)
                html = result.html
                links = await node.process_html(html)
                node.mark_as_scanned()

                self._log_scan_result(node, links, result)
                return (node, links, result)

            except Exception as e:
                logger.error(f"Error scanning {node.url}: {e}")
                node.content_type = ContentType.ERROR
                node.mark_as_scanned()
                return (node, [], None)

        # Запускаємо ВСІ обробки паралельно!
        tasks = [process_single(node, result) for node, result in zip(nodes, results)]
        scan_results = await asyncio.gather(*tasks, return_exceptions=False)

        return list(scan_results)

