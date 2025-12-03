"""Edge Exporter - Clean Architecture з DTO.

BREAKING CHANGE (Фаза 6): Тепер використовує GraphDTO замість Graph.

Надає функціонал експорту edges з графу:
- JSON експорт (детальний з metadata)
- CSV експорт (табличний формат)
- DOT експорт (для Graphviz візуалізації)
"""

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from graph_crawler.application.dto import GraphDTO, NodeDTO, EdgeDTO

logger = logging.getLogger(__name__)


class EdgeExporter:
    """
    Експортер edges в різні формати через DTO.

    BREAKING CHANGE (Фаза 6): Тепер працює ТІЛЬКИ з GraphDTO.

    Відповідальність: експорт edges з графу в JSON, CSV, DOT формати.

    Методи:
        - export_to_json() - експорт edges в JSON з повними metadata
        - export_to_csv() - експорт edges в CSV таблицю
        - export_to_dot() - експорт в DOT формат для Graphviz
    """

    @staticmethod
    def export_to_json(
        graph_dto: GraphDTO,
        filepath: str,
        include_metadata: bool = True,
        include_nodes_info: bool = True,
        pretty: bool = True,
    ) -> Dict[str, Any]:
        """
        Експортує edges в JSON формат через DTO.

        BREAKING CHANGE (Фаза 6): Тепер приймає GraphDTO замість Graph.

        Args:
            graph_dto: GraphDTO для експорту
            filepath: Шлях до файлу для збереження
            include_metadata: Чи включати metadata edges
            include_nodes_info: Чи включати інформацію про source/target nodes
            pretty: Чи форматувати JSON з відступами

        Returns:
            Словник з даними edges

        Example:
            >>> data = EdgeExporter.export_to_json(
            ...     graph_dto,
            ...     "edges.json",
            ...     include_metadata=True
            ... )
            >>> print(f"Exported {data['total_edges']} edges")
        """
        logger.info(f" Exporting edges to JSON: {filepath}")

        # Створюємо lookup dict для швидкого доступу до nodes по ID
        nodes_by_id = {node.node_id: node for node in graph_dto.nodes}

        edges_data = []

        for edge_dto in graph_dto.edges:
            edge_dict = {
                "edge_id": edge_dto.edge_id,
                "source_node_id": edge_dto.source_node_id,
                "target_node_id": edge_dto.target_node_id,
            }

            # Додаємо інформацію про nodes
            if include_nodes_info:
                source_node = nodes_by_id.get(edge_dto.source_node_id)
                target_node = nodes_by_id.get(edge_dto.target_node_id)

                if source_node:
                    edge_dict["source_url"] = source_node.url
                    edge_dict["source_depth"] = source_node.depth

                if target_node:
                    edge_dict["target_url"] = target_node.url
                    edge_dict["target_depth"] = target_node.depth
                    edge_dict["target_scanned"] = target_node.scanned

            # Додаємо metadata
            if include_metadata and edge_dto.metadata:
                edge_dict["metadata"] = edge_dto.metadata

            edges_data.append(edge_dict)

        # Формуємо результат
        result = {
            "total_edges": len(edges_data),
            "edges": edges_data,
            "export_options": {
                "include_metadata": include_metadata,
                "include_nodes_info": include_nodes_info,
            },
        }

        # Зберігаємо в файл
        with open(filepath, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)
            else:
                json.dump(result, f, ensure_ascii=False, default=str)

        logger.info(f"Exported {len(edges_data)} edges to {filepath}")
        return result

    @staticmethod
    def export_to_csv(
        graph_dto: GraphDTO,
        filepath: str,
        include_metadata: bool = True,
        metadata_as_json: bool = True,
    ) -> int:
        """
        Експортує edges в CSV формат через DTO.

        BREAKING CHANGE (Фаза 6): Тепер приймає GraphDTO замість Graph.

        Args:
            graph_dto: GraphDTO для експорту
            filepath: Шлях до CSV файлу
            include_metadata: Чи включати metadata
            metadata_as_json: Чи зберігати metadata як JSON string
                (False - кожне поле metadata в окремій колонці)

        Returns:
            Кількість експортованих edges

        Example:
            >>> count = EdgeExporter.export_to_csv(graph_dto, "edges.csv")
            >>> print(f"Exported {count} edges")
        """
        logger.info(f" Exporting edges to CSV: {filepath}")

        if len(graph_dto.edges) == 0:
            logger.warning("No edges to export")
            return 0

        # Створюємо lookup dict для швидкого доступу до nodes по ID
        nodes_by_id = {node.node_id: node for node in graph_dto.nodes}

        # Визначаємо поля CSV
        base_fields = [
            "edge_id",
            "source_node_id",
            "target_node_id",
            "source_url",
            "target_url",
            "source_depth",
            "target_depth",
            "target_scanned",
        ]

        # Якщо metadata як JSON string
        if metadata_as_json:
            fields = base_fields + ["metadata"]
        else:
            # Збираємо всі унікальні ключі metadata
            metadata_keys = set()
            for edge_dto in graph_dto.edges:
                if edge_dto.metadata:
                    metadata_keys.update(edge_dto.metadata.keys())

            fields = base_fields + sorted(metadata_keys)

        # Записуємо CSV
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()

            for edge_dto in graph_dto.edges:
                row = {
                    "edge_id": edge_dto.edge_id,
                    "source_node_id": edge_dto.source_node_id,
                    "target_node_id": edge_dto.target_node_id,
                }

                # Додаємо інформацію про nodes
                source_node = nodes_by_id.get(edge_dto.source_node_id)
                target_node = nodes_by_id.get(edge_dto.target_node_id)

                if source_node:
                    row["source_url"] = source_node.url
                    row["source_depth"] = source_node.depth
                else:
                    row["source_url"] = ""
                    row["source_depth"] = ""

                if target_node:
                    row["target_url"] = target_node.url
                    row["target_depth"] = target_node.depth
                    row["target_scanned"] = target_node.scanned
                else:
                    row["target_url"] = ""
                    row["target_depth"] = ""
                    row["target_scanned"] = ""

                # Додаємо metadata
                if include_metadata and edge_dto.metadata:
                    if metadata_as_json:
                        row["metadata"] = json.dumps(edge_dto.metadata, ensure_ascii=False, default=str)
                    else:
                        # Додаємо кожне поле metadata
                        for key in fields:
                            if key in edge_dto.metadata:
                                value = edge_dto.metadata[key]
                                # Конвертуємо list/dict в string
                                if isinstance(value, (list, dict)):
                                    row[key] = json.dumps(value, ensure_ascii=False)
                                else:
                                    row[key] = value

                writer.writerow(row)

        logger.info(f"Exported {len(graph_dto.edges)} edges to {filepath}")
        return len(graph_dto.edges)

    @staticmethod
    def export_to_dot(
        graph_dto: GraphDTO,
        filepath: str,
        node_label: str = "url",
        edge_label: Optional[str] = None,
        max_label_length: int = 50,
        color_by: str = "depth",
    ) -> str:
        """
        Експортує граф в DOT формат через DTO.

        BREAKING CHANGE (Фаза 6): Тепер приймає GraphDTO замість Graph.

        Створює файл .dot який можна відкрити в Graphviz або конвертувати:
        - `dot -Tpng graph.dot -o graph.png` (PNG зображення)
        - `dot -Tsvg graph.dot -o graph.svg` (SVG векторна графіка)
        - `dot -Tpdf graph.dot -o graph.pdf` (PDF документ)

        Args:
            graph_dto: GraphDTO для експорту
            filepath: Шлях до .dot файлу
            node_label: Поле node для відображення ('url', 'node_id', 'depth')
            edge_label: Поле edge metadata для label (опціонально,
                наприклад 'anchor_text' або 'link_type')
            max_label_length: Максимальна довжина label (обрізає довгі URL)
            color_by: Критерій кольорування nodes:
                - 'depth' (default) - колір за глибиною
                - 'scanned' - колір за статусом сканування
                - 'none' - без кольорування

        Returns:
            DOT string (також зберігається в файл)

        Example:
            >>> # Базовий експорт
            >>> dot = EdgeExporter.export_to_dot(graph_dto, "graph.dot")
            >>>
            >>> # З кольоруванням та labels
            >>> dot = EdgeExporter.export_to_dot(
            ...     graph_dto, "graph.dot",
            ...     node_label='url',
            ...     edge_label='anchor_text',
            ...     color_by='depth'
            ... )
            >>>
            >>> # Конвертувати в PNG:
            >>> # dot -Tpng graph.dot -o graph.png
        """
        logger.info(f" Exporting graph to DOT: {filepath}")

        lines = []
        lines.append("digraph G {")
        lines.append("  rankdir=LR;")  # Left-to-right layout
        lines.append("  node [shape=box, style=filled];")
        lines.append("")

        # Додаємо nodes з DTO
        for node_dto in graph_dto.nodes:
            # Формуємо label
            if node_label == "url":
                label = node_dto.url
            elif node_label == "node_id":
                label = node_dto.node_id[:12]
            elif node_label == "depth":
                label = f"Depth {node_dto.depth}"
            else:
                label = str(getattr(node_dto, node_label, node_dto.url))

            # Обрізаємо довгі labels
            if len(label) > max_label_length:
                label = label[:max_label_length] + "..."

            # Escape спеціальних символів
            label = label.replace('"', '\\"')

            # Визначаємо колір
            if color_by == "depth":
                # Градієнт від світлого до темного
                depth = min(node_dto.depth, 10)  # Cap at 10
                color_value = 0.9 - (depth * 0.08)
                fillcolor = f"{color_value} 0.3 1.0"  # HSV
                lines.append(
                    f'  "{node_dto.node_id}" [label="{label}", fillcolor="{fillcolor}"];'
                )
            elif color_by == "scanned":
                fillcolor = "lightgreen" if node_dto.scanned else "lightgray"
                lines.append(
                    f'  "{node_dto.node_id}" [label="{label}", fillcolor="{fillcolor}"];'
                )
            else:
                lines.append(f'  "{node_dto.node_id}" [label="{label}"];')

        lines.append("")

        # Додаємо edges з DTO
        for edge_dto in graph_dto.edges:
            edge_attrs = []

            # Додаємо label якщо потрібно
            if edge_label and edge_dto.metadata:
                label_value = edge_dto.metadata.get(edge_label)
                if label_value:
                    # Обрізаємо довгі labels
                    if isinstance(label_value, list):
                        label_value = ", ".join(str(v) for v in label_value)
                    label_str = str(label_value)
                    if len(label_str) > max_label_length:
                        label_str = label_str[:max_label_length] + "..."
                    label_str = label_str.replace('"', '\\"')
                    edge_attrs.append(f'label="{label_str}"')

            # Додаємо колір edge по типу
            link_types = edge_dto.metadata.get("link_type", [])
            if "external" in link_types:
                edge_attrs.append('color="red"')
            elif "back" in link_types:
                edge_attrs.append('color="orange"')

            attrs_str = ", ".join(edge_attrs) if edge_attrs else ""
            if attrs_str:
                lines.append(
                    f'  "{edge_dto.source_node_id}" -> "{edge_dto.target_node_id}" [{attrs_str}];'
                )
            else:
                lines.append(f'  "{edge_dto.source_node_id}" -> "{edge_dto.target_node_id}";')

        lines.append("}")

        dot_content = "\n".join(lines)

        # Зберігаємо в файл
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(dot_content)

        logger.info(f"Exported graph to DOT: {filepath}")
        logger.info(f" Convert to image: dot -Tpng {filepath} -o graph.png")

        return dot_content
