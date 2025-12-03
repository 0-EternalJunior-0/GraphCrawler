"""Утиліти для веб-візуалізації графу.

Цей модуль тепер виконує роль фасаду над ``visualization_core`` і
надає сумісний з попередніми версіями клас ``GraphVisualizer``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from graph_crawler.domain.entities.graph import Graph

from .visualization_core import (
    blend_colors,
    filter_nodes_for_visualization,
    get_base_color,
    get_border_color,
    graph_to_dict,
    graph_to_json,
    graph_to_networkx,
    print_summary as _print_summary,
    visualize_2d_web as _visualize_2d_web,
)


class GraphVisualizer:
    """Утиліти для веб-візуалізації та експорту графу.

    Підтримує:
    - 2D інтерактивну візуалізацію (PyVis)
    - NetworkX експорт
    - JSON експорт
    - Базове кольорове кодування за scanned/should_scan
    - Додаткове підсвічування (обводка) за довільними параметрами

    Використання (зворотно сумісне з попередніми версіями):

        GraphVisualizer.visualize_2d_web(graph, output_file="graph.html")

        GraphVisualizer.to_json(graph, filepath="graph.json")
    """

    # ---- Serialization helpers -------------------------------------------------
    @staticmethod
    def to_dict(graph: Graph, include_metadata: bool = True) -> Dict[str, Any]:
        """Експортує граф у словник."""
        return graph_to_dict(graph, include_metadata)

    @staticmethod
    def to_json(
        graph: Graph,
        filepath: Optional[str] = None,
        include_metadata: bool = True,
    ) -> str:
        """Експортує граф у JSON формат (опціонально у файл)."""
        return graph_to_json(graph, filepath=filepath, include_metadata=include_metadata)

    @staticmethod
    def to_networkx(graph: Graph):
        """Конвертує граф у NetworkX граф."""
        return graph_to_networkx(graph)

    # ---- Internal helpers (kept for backward compatibility) --------------------
    @staticmethod
    def _filter_nodes_for_visualization(
        graph: Graph,
        max_nodes: int,
        structure_only: bool,
    ) -> List[Any]:
        """Зберігаємо приватний метод як обгортку над core-функцією."""
        return filter_nodes_for_visualization(graph, max_nodes, structure_only)

    @staticmethod
    def _get_base_color(scanned: bool, should_scan: bool) -> Tuple[str, str]:
        """Обгортка над core-функцією базового кольору."""
        return get_base_color(scanned, should_scan)

    @staticmethod
    def _get_border_color(
        node_data: Dict[str, Any],
        highlight_params: Optional[Dict[str, str]],
    ) -> Optional[str]:
        """Обгортка над core-функцією кольору обводки."""
        return get_border_color(node_data, highlight_params)

    # ---- Visualization ----------------------------------------------------------
    @staticmethod
    def visualize_2d_web(
        graph: Graph,
        output_file: str = "graph_2d.html",
        height: str = "900px",
        width: str = "100%",
        notebook: bool = False,
        physics_enabled: bool = True,
        max_nodes: int = 1000,
        structure_only: bool = False,
        highlight_params: Optional[Dict[str, str]] = None,
        max_physicist: int = 1000,
    ) -> None:
        """Створює інтерактивну 2D HTML візуалізацію за допомогою PyVis."""
        _visualize_2d_web(
            graph=graph,
            output_file=output_file,
            height=height,
            width=width,
            notebook=notebook,
            physics_enabled=physics_enabled,
            max_nodes=max_nodes,
            structure_only=structure_only,
            highlight_params=highlight_params,
            max_physicist=max_physicist,
        )

    # ---- Summary ----------------------------------------------------------------
    @staticmethod
    def print_summary(graph: Graph) -> None:
        """Виводить інформацію про граф (summary)."""
        _print_summary(graph)


__all__ = [
    "GraphVisualizer",
    "blend_colors",
]
