"""Node Exporter - експорт нод з вибором полів та transform.

ВИПРАВЛЕНО: Додано async методи з executor для неблокуючих операцій.

Дозволяє експортувати ноди з:
- Вибором конкретних полів (node_fields)
- Кастомною трансформацією (transform_node)
- Фільтрацією (predicate)

Example:
    >>> # Експорт з вибраними полями
    >>> graph.export_nodes(
    ...     'vacancies.json',
    ...     format='json',
    ...     node_fields=['url', 'metadata.title', 'user_data.structured_data']
    ... )
    >>>
    >>> # Експорт з трансформацією
    >>> graph.export_nodes(
    ...     'vacancies.csv',
    ...     format='csv',
    ...     transform_node=lambda n: {
    ...         'url': n.url,
    ...         'title': n.metadata.get('title'),
    ...         'company': n.user_data.get('structured_data', {}).get_property('hiringOrganization.name'),
    ...     }
    ... )
"""

import asyncio
import csv
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, Dict, List, Optional

from graph_crawler.domain.entities.node import Node

logger = logging.getLogger(__name__)

# Thread pool для неблокуючих file I/O операцій
_node_exporter_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="node_export_")


class NodeExporter:
    """
    Експортер нод з підтримкою вибору полів та трансформації.

    Працює напряму з Graph (не через DTO) для простоти використання.
    """

    @staticmethod
    def export_to_json(
        nodes: List[Node],
        filepath: str,
        node_fields: Optional[List[str]] = None,
        transform_node: Optional[Callable[[Node], Dict[str, Any]]] = None,
        predicate: Optional[Callable[[Node], bool]] = None,
        pretty: bool = True,
    ) -> Dict[str, Any]:
        """
        Експортує ноди в JSON формат.

        Args:
            nodes: Список нод для експорту
            filepath: Шлях до файлу
            node_fields: Список полів для включення (dot notation: 'metadata.title')
            transform_node: Функція трансформації ноди -> dict
            predicate: Фільтр нод (включає тільки де predicate(node) == True)
            pretty: Форматувати JSON з відступами

        Returns:
            Словник з результатами експорту

        Example:
            >>> NodeExporter.export_to_json(
            ...     graph.nodes.values(),
            ...     'jobs.json',
            ...     node_fields=['url', 'metadata.title', 'depth']
            ... )
        """
        logger.info(f"Exporting nodes to JSON: {filepath}")

        # Фільтрація
        filtered_nodes = nodes
        if predicate:
            filtered_nodes = [n for n in nodes if predicate(n)]

        nodes_data = []
        for node in filtered_nodes:
            if transform_node:
                # Кастомна трансформація
                node_dict = transform_node(node)
            elif node_fields:
                # Вибрані поля
                node_dict = NodeExporter._extract_fields(node, node_fields)
            else:
                # Всі поля
                node_dict = node.model_dump()

            nodes_data.append(node_dict)

        result = {
            "total_nodes": len(nodes_data),
            "nodes": nodes_data,
            "export_options": {
                "node_fields": node_fields,
                "has_transform": transform_node is not None,
                "has_predicate": predicate is not None,
            },
        }

        # Зберігаємо
        with open(filepath, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)
            else:
                json.dump(result, f, ensure_ascii=False, default=str)

        logger.info(f"Exported {len(nodes_data)} nodes to {filepath}")
        return result

    @staticmethod
    def export_to_csv(
        nodes: List[Node],
        filepath: str,
        node_fields: Optional[List[str]] = None,
        transform_node: Optional[Callable[[Node], Dict[str, Any]]] = None,
        predicate: Optional[Callable[[Node], bool]] = None,
    ) -> int:
        """
        Експортує ноди в CSV формат.

        Args:
            nodes: Список нод для експорту
            filepath: Шлях до CSV файлу
            node_fields: Список полів для включення
            transform_node: Функція трансформації ноди -> dict
            predicate: Фільтр нод

        Returns:
            Кількість експортованих нод

        Example:
            >>> NodeExporter.export_to_csv(
            ...     graph.nodes.values(),
            ...     'vacancies.csv',
            ...     transform_node=lambda n: {
            ...         'url': n.url,
            ...         'title': n.get_title(),
            ...         'schema_type': n.user_data.get('structured_data', {}).get_type(),
            ...     }
            ... )
        """
        logger.info(f"Exporting nodes to CSV: {filepath}")

        # Фільтрація
        filtered_nodes = list(nodes)
        if predicate:
            filtered_nodes = [n for n in filtered_nodes if predicate(n)]

        if not filtered_nodes:
            logger.warning("No nodes to export")
            return 0

        # Визначаємо поля для CSV
        if transform_node:
            # Беремо поля з першої трансформованої ноди
            first_dict = transform_node(filtered_nodes[0])
            fields = list(first_dict.keys())
        elif node_fields:
            fields = node_fields
        else:
            # Базові поля
            fields = ['url', 'node_id', 'depth', 'scanned', 'response_status']

        # Записуємо CSV
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()

            for node in filtered_nodes:
                if transform_node:
                    row = transform_node(node)
                elif node_fields:
                    row = NodeExporter._extract_fields(node, node_fields)
                else:
                    row = {
                        'url': node.url,
                        'node_id': node.node_id,
                        'depth': node.depth,
                        'scanned': node.scanned,
                        'response_status': node.response_status,
                    }

                # Конвертуємо складні типи в string
                for key, value in row.items():
                    if isinstance(value, (list, dict)):
                        row[key] = json.dumps(value, ensure_ascii=False)

                writer.writerow(row)

        logger.info(f"Exported {len(filtered_nodes)} nodes to {filepath}")
        return len(filtered_nodes)

    @staticmethod
    def _extract_fields(node: Node, fields: List[str]) -> Dict[str, Any]:
        """
        Витягує вказані поля з ноди.

        Підтримує dot notation: 'metadata.title', 'user_data.structured_data.primary_type'

        Args:
            node: Нода
            fields: Список полів

        Returns:
            Словник з вибраними полями
        """
        result = {}

        for field in fields:
            parts = field.split('.')
            value = node

            try:
                for part in parts:
                    if hasattr(value, part):
                        value = getattr(value, part)
                    elif isinstance(value, dict):
                        value = value.get(part)
                    else:
                        value = None
                        break

                # Використовуємо останню частину як ключ
                result[field] = value
            except Exception:
                result[field] = None

        return result

    @staticmethod
    def _flatten_key(prefix: str, key: str) -> str:
        """Створює плоский ключ з prefix.key."""
        return f"{prefix}.{key}" if prefix else key

    # ============= ASYNC МЕТОДИ =============

    @staticmethod
    async def export_to_json_async(
        nodes: List[Node],
        filepath: str,
        node_fields: Optional[List[str]] = None,
        transform_node: Optional[Callable[[Node], Dict[str, Any]]] = None,
        predicate: Optional[Callable[[Node], bool]] = None,
        pretty: bool = True,
    ) -> Dict[str, Any]:
        """
        Async версія експорту нод в JSON (неблокуюча).

        Args:
            nodes: Список нод для експорту
            filepath: Шлях до файлу
            node_fields: Список полів для включення
            transform_node: Функція трансформації
            predicate: Фільтр нод
            pretty: Форматувати JSON

        Returns:
            Словник з результатами експорту
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _node_exporter_executor,
            partial(
                NodeExporter.export_to_json,
                nodes, filepath, node_fields, transform_node, predicate, pretty
            )
        )

    @staticmethod
    async def export_to_csv_async(
        nodes: List[Node],
        filepath: str,
        node_fields: Optional[List[str]] = None,
        transform_node: Optional[Callable[[Node], Dict[str, Any]]] = None,
        predicate: Optional[Callable[[Node], bool]] = None,
    ) -> int:
        """
        Async версія експорту нод в CSV (неблокуюча).

        Args:
            nodes: Список нод для експорту
            filepath: Шлях до CSV файлу
            node_fields: Список полів для включення
            transform_node: Функція трансформації
            predicate: Фільтр нод

        Returns:
            Кількість експортованих нод
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _node_exporter_executor,
            partial(
                NodeExporter.export_to_csv,
                nodes, filepath, node_fields, transform_node, predicate
            )
        )
