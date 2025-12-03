"""Core utilities for graph visualization.

This module contains the actual implementation for:
- graph serialization (dict / JSON / NetworkX)
- node/edge filtering for visualization
- color and styling helpers
- PyVis-based 2D web visualization
- summary printing

The public facade for external users remains ``GraphVisualizer`` in
``graph_crawler.shared.utils.visualization`` which delegates to this module.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from graph_crawler.domain.entities.graph import Graph

logger = logging.getLogger(__name__)


def blend_colors(colors: List[str]) -> Optional[str]:
    """Blend multiple HEX colors into a single average color.

    Args:
        colors: List of HEX color strings (e.g. ["#ffffff", "#000000"]).

    Returns:
        HEX color string representing the average color or ``None``
        if the input list is empty.
    """
    if not colors:
        return None
    if len(colors) == 1:
        return colors[0]

    rgb_values: List[Tuple[int, int, int]] = []
    for color in colors:
        color = color.lstrip("#")
        rgb = tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))
        rgb_values.append(rgb)

    avg_r = int(sum(r for r, g, b in rgb_values) / len(rgb_values))
    avg_g = int(sum(g for r, g, b in rgb_values) / len(rgb_values))
    avg_b = int(sum(b for r, g, b in rgb_values) / len(rgb_values))

    return f"#{avg_r:02x}{avg_g:02x}{avg_b:02x}"


def graph_to_dict(graph: Graph, include_metadata: bool = True) -> Dict[str, Any]:
    """Export graph to a plain dictionary structure.

    This is optimized with comprehensions and used as the base for
    JSON / NetworkX exports.
    """
    nodes_data = [
        {
            "id": node.node_id,
            "url": node.url,
            "depth": node.depth,
            "scanned": node.scanned,
            "status": node.response_status,
            **(
                {"metadata": node.metadata}
                if include_metadata and getattr(node, "metadata", None)
                else {}
            ),
        }
        for node in graph.nodes.values()
    ]

    edges_data = [
        {
            "source": edge.source_node_id,
            "target": edge.target_node_id,
            **({"metadata": edge.metadata} if getattr(edge, "metadata", None) else {}),
        }
        for edge in graph.edges
    ]

    return {"nodes": nodes_data, "edges": edges_data, "stats": graph.get_stats()}


def graph_to_json(
    graph: Graph,
    filepath: Optional[str] = None,
    include_metadata: bool = True,
) -> str:
    """Export graph to JSON string and optionally persist to file."""
    data = graph_to_dict(graph, include_metadata)
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    if filepath:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json_str)
    return json_str


def graph_to_networkx(graph: Graph):
    """Convert internal Graph representation to a NetworkX ``DiGraph``.

    Raises:
        ImportError: if ``networkx`` is not installed.
    """
    try:
        import networkx as nx
    except ImportError as exc:  # pragma: no cover - defensive branch
        raise ImportError("Встановіть networkx: pip install networkx") from exc

    g_nx = nx.DiGraph()
    for node in graph.nodes.values():
        g_nx.add_node(
            node.node_id,
            url=node.url,
            depth=node.depth,
            scanned=node.scanned,
            title=node.get_title() or "",
            label=node.url or "root",
        )
    for edge in graph.edges:
        g_nx.add_edge(edge.source_node_id, edge.target_node_id)
    return g_nx


def filter_nodes_for_visualization(
    graph: Graph,
    max_nodes: int,
    structure_only: bool,
) -> List[Any]:
    """Filter nodes for visualization according to structural settings.

    This logic was previously implemented as a private static method
    on ``GraphVisualizer`` and is now extracted for reuse and testing.
    """
    nodes_list = list(graph.nodes.values())
    if structure_only:
        filtered: List[Any] = []
        for node in nodes_list:
            if hasattr(node, "node_type") and node.node_type != "url":
                filtered.append(node)
            elif node.depth == 0:
                filtered.append(node)
        logger.info(" Режим structure_only: %s структурних вузлів", len(filtered))
        return filtered

    if len(nodes_list) > max_nodes:
        structural: List[Any] = []
        url_nodes: List[Any] = []
        for node in nodes_list:
            if hasattr(node, "node_type") and node.node_type != "url":
                structural.append(node)
            else:
                url_nodes.append(node)
        remaining_slots = max_nodes - len(structural)
        if remaining_slots > 0:
            return structural + url_nodes[:remaining_slots]
        return structural[:max_nodes]

    return nodes_list


def get_base_color(scanned: bool, should_scan: bool) -> Tuple[str, str]:
    """Return base color and category label for a node."""
    if scanned and should_scan:
        return "#22C55E", "Scanned + Should Scan"
    if scanned and not should_scan:
        return "#3B82F6", "Scanned + External"
    if not scanned and should_scan:
        return "#EAB308", "Pending Scan"
    return "#9CA3AF", "External (not scanned)"


def get_border_color(
    node_data: Dict[str, Any],
    highlight_params: Optional[Dict[str, str]],
) -> Optional[str]:
    """Determine border color based on provided highlight parameters.

    ``highlight_params`` is a mapping ``{"param_name": "#RRGGBB", ...}``.
    If any of the parameters is truthy on ``node_data``, its color is
    taken into account when blending.
    """
    if not node_data or not highlight_params:
        return None

    active_colors: List[str] = []
    for param, color in highlight_params.items():
        if param in node_data and node_data[param]:
            active_colors.append(color)

    if active_colors:
        return blend_colors(active_colors)
    return None


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
    """Create interactive 2D HTML visualization with PyVis.

    This is the core implementation used by
    :meth:`graph_crawler.shared.utils.visualization.GraphVisualizer.visualize_2d_web`.
    """
    try:
        from pyvis.network import Network
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError("Встановіть: pip install pyvis") from exc

    total_nodes = len(graph.nodes)
    logger.info("Початок 2D візуалізації графу: %s вузлів", total_nodes)

    if total_nodes > max_nodes and not structure_only:
        logger.warning(" Граф містить %s вузлів, ліміт %s", total_nodes, max_nodes)
        logger.info(" Візуалізуємо перші %s вузлів", max_nodes)

    nodes_to_visualize = filter_nodes_for_visualization(graph, max_nodes, structure_only)
    logger.info(" Візуалізація %s вузлів з %s", len(nodes_to_visualize), total_nodes)

    net = Network(height=height, width=width, directed=True, notebook=notebook)

    # Physics configuration
    if physics_enabled and len(nodes_to_visualize) <= max_physicist:
        net.set_options(
            """
            {
              "physics": {
                "enabled": true,
                "forceAtlas2Based": {
                  "gravitationalConstant": -50,
                  "centralGravity": 0.01,
                  "springLength": 200,
                  "springConstant": 0.08
                },
                "maxVelocity": 50,
                "solver": "forceAtlas2Based"
              }
            }
            """
        )
    else:
        net.set_options(
            """
            {
              "physics": {
                "enabled": false
              },
              "layout": {
                "hierarchical": {
                  "enabled": true,
                  "direction": "UD",
                  "sortMethod": "directed"
                }
              }
            }
            """
        )
        if len(nodes_to_visualize) > max_physicist:
            logger.info("ℹ Фізика вимкнена для оптимізації")

    node_ids = {node.node_id for node in nodes_to_visualize}

    for node in nodes_to_visualize:
        # Collect public attributes for hover/highlight logic
        node_data: Dict[str, Any] = {}
        if hasattr(node, "__dict__"):
            for key, value in node.__dict__.items():
                if not key.startswith("_"):
                    node_data[key] = value

        base_color, _category = get_base_color(node.scanned, node.should_scan)

        border_color: Optional[str] = None
        if highlight_params:
            border_color = get_border_color(node_data, highlight_params)

        hover_text = f"<b>URL:</b> {node.url}<br>"
        if highlight_params:
            for param in highlight_params.keys():
                if param in node_data:
                    value = node_data[param]
                    icon = "" if value else ""
                    hover_text += f"<b>{param}:</b> {icon}<br>"

        label = str(node.url)[:50] or "root"
        size = 30 if node.depth == 0 else 20

        node_config: Dict[str, Any] = {
            "label": label,
            "title": hover_text,
            "color": {
                "background": base_color,
                "border": border_color if border_color else base_color,
                "highlight": {
                    "background": base_color,
                    "border": border_color if border_color else "#333333",
                },
            },
            "size": size,
            "shape": "dot" if node.scanned else "box",
            "borderWidth": 4 if border_color else 1,
            "borderWidthSelected": 6 if border_color else 2,
        }

        net.add_node(node.node_id, **node_config)

    # Add edges
    edges_added = 0
    for edge in graph.edges:
        if edge.source_node_id in node_ids and edge.target_node_id in node_ids:
            net.add_edge(
                edge.source_node_id,
                edge.target_node_id,
                color="rgba(125, 125, 125, 0.3)",
                arrows="to",
            )
            edges_added += 1
    logger.info(" Додано %s ребер", edges_added)

    net.save_graph(output_file)
    logger.info("2D граф збережено: %s", output_file)


def print_summary(graph: Graph) -> None:
    """Log a human-readable summary about the graph structure."""
    separator = "=" * 60
    logger.info("\n%s", separator)
    logger.info(" ІНФОРМАЦІЯ ПРО ГРАФ")
    logger.info("%s", separator)

    stats = graph.get_stats()
    logger.info("   Всього вузлів: %s", stats["total_nodes"])
    logger.info("   Просканованих: %s", stats["scanned_nodes"])
    logger.info("   Непросканованих: %s", stats["unscanned_nodes"])
    logger.info("   Всього ребер: %s", stats["total_edges"])

    depths: Dict[int, int] = {}
    for node in graph.nodes.values():
        depths[node.depth] = depths.get(node.depth, 0) + 1

    for depth in sorted(depths.keys()):
        logger.info("   Depth %s: %s вузлів", depth, depths[depth])

    logger.info("\n%s", separator)
