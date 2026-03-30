"""High-Level Utility Functions для роботи з DTO.

Спрощує типові операції:
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

# Використовуємо fast_json з orjson
from graph_crawler.shared.utils.fast_json import dumps as json_dumps
from graph_crawler.shared.utils.fast_json import loads as json_loads

if TYPE_CHECKING:
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node

logger = logging.getLogger(__name__)


def graph_to_json(
    graph: "Graph",
    indent: int = 2,
    ensure_ascii: bool = False,
) -> str:
    """
    Конвертує Domain Graph в JSON string через DTO.

    ОПТИМІЗОВАНО: Використовує orjson (+50% швидкості).

    Args:
        graph: Domain Graph entity
        indent: Відступ для форматування JSON
        ensure_ascii: Чи екранувати non-ASCII символи (ігнорується з orjson)

    Returns:
        JSON string

    Example:
        >>> json_str = graph_to_json(graph)
        >>> print(json_str[:100])
    """
    from graph_crawler.application.dto.mappers import GraphMapper

    graph_dto = GraphMapper.to_dto(graph)
    return json_dumps(
        graph_dto.model_dump(),
        indent=indent,
    )


def json_to_graph(
    json_str: str,
    context: Optional[Dict[str, Any]] = None,
) -> "Graph":
    """
    Конвертує JSON string в Domain Graph через DTO.

    ОПТИМІЗОВАНО: Використовує orjson (+50% швидкості).

    Args:
        json_str: JSON string з даними графу
        context: Контекст для відновлення залежностей

    Returns:
        Domain Graph entity

    Example:
        >>> graph = json_to_graph(json_str)
        >>>
        >>> # З контекстом
        >>> from graph_crawler.application.context import DependencyRegistry
        >>> context = DependencyRegistry.get_context()
        >>> graph = json_to_graph(json_str, context=context)
    """
    from graph_crawler.application.dto import GraphDTO
    from graph_crawler.application.dto.mappers import GraphMapper

    data = json_loads(json_str)
    graph_dto = GraphDTO.model_validate(data)
    return GraphMapper.to_domain(graph_dto, context=context)


def graph_to_dict(graph: "Graph") -> Dict[str, Any]:
    """
    Конвертує Domain Graph в dict через DTO.

    Args:
        graph: Domain Graph entity

    Returns:
        Dict з даними графу
    """
    from graph_crawler.application.dto.mappers import GraphMapper

    graph_dto = GraphMapper.to_dto(graph)
    return graph_dto.model_dump()


def dict_to_graph(
    data: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> "Graph":
    """
    Конвертує dict в Domain Graph через DTO.

    Args:
        data: Dict з даними графу
        context: Контекст для відновлення залежностей

    Returns:
        Domain Graph entity
    """
    from graph_crawler.application.dto import GraphDTO
    from graph_crawler.application.dto.mappers import GraphMapper

    graph_dto = GraphDTO.model_validate(data)
    return GraphMapper.to_domain(graph_dto, context=context)


def save_graph(
    graph: "Graph",
    path: Union[str, Path],
    indent: int = 2,
) -> None:
    """
    Зберігає Domain Graph в JSON файл.

    Args:
        graph: Domain Graph entity
        path: Шлях до файлу
        indent: Відступ для форматування JSON

    Example:
        >>> save_graph(graph, 'output/graph.json')
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    json_str = graph_to_json(graph, indent=indent)
    path.write_text(json_str, encoding="utf-8")

    logger.info("Graph saved to %s", path)


def load_graph(
    path: Union[str, Path],
    context: Optional[Dict[str, Any]] = None,
) -> "Graph":
    """
    Завантажує Domain Graph з JSON файлу.

    Args:
        path: Шлях до файлу
        context: Контекст для відновлення залежностей

    Returns:
        Domain Graph entity

    Example:
        >>> graph = load_graph('output/graph.json')
        >>>
        >>> # З контекстом
        >>> from graph_crawler.application.context import DependencyRegistry
        >>> context = DependencyRegistry.get_context()
        >>> graph = load_graph('output/graph.json', context=context)
    """
    path = Path(path)
    json_str = path.read_text(encoding="utf-8")

    graph = json_to_graph(json_str, context=context)
    logger.info("Graph loaded from %s: %s nodes", path, len(graph.nodes))

    return graph


def merge_graphs(
    graphs: List["Graph"],
    strategy: str = "last",
    custom_merge_fn: Optional[Callable] = None,
) -> "Graph":
    """
    Об'єднує список графів з вказаною стратегією.

    Args:
        graphs: Список графів для об'єднання
        strategy: Стратегія merge ('first', 'last', 'merge', 'newest', 'oldest', 'custom')
        custom_merge_fn: Кастомна функція для 'custom' стратегії
    Returns:
        Об'єднаний граф
    """
    if not graphs:
        from graph_crawler.domain.entities.graph import Graph

        return Graph()

    if len(graphs) == 1:
        return graphs[0]

    from graph_crawler.application.context import with_merge_strategy

    with with_merge_strategy(strategy, custom_merge_fn=custom_merge_fn):
        result = graphs[0]
        for graph in graphs[1:]:
            result = result + graph

    logger.info(
        f"Merged {len(graphs)} graphs: result has {len(result.nodes)} nodes, strategy={strategy}"
    )

    return result


def filter_graph(
    graph: "Graph",
    predicate: Callable[["Node"], bool],
    keep_edges: bool = True,
) -> "Graph":
    """
    Фільтрує граф за предикатом.

    Args:
        graph: Domain Graph entity
        predicate: Функція (Node) -> bool
        keep_edges: Чи зберігати edges між відфільтрованими нодами

    Returns:
        Новий граф з відфільтрованими нодами

    Example:
        >>> # Залишити тільки просканований ноди
        >>> filtered = filter_graph(graph, lambda n: n.scanned)
        >>>
        >>> # Залишити ноди з глибиною <= 2
        >>> filtered = filter_graph(graph, lambda n: n.depth <= 2)
    """
    from graph_crawler.domain.entities.graph import Graph

    result = Graph(default_merge_strategy=graph.default_merge_strategy)

    # Фільтруємо ноди (streaming через iter_nodes)
    for node in graph.iter_nodes():
        if predicate(node):
            result.add_node(node)

    # Зберігаємо edges якщо потрібно
    if keep_edges:
        # Використовуємо iter_nodes() для streaming доступу замість .nodes.keys()
        result_node_ids = {node.node_id for node in result.iter_nodes()}
        for edge in graph.iter_edges():
            if edge.source_node_id in result_node_ids and edge.target_node_id in result_node_ids:
                result.add_edge(edge)

    logger.debug("Filtered graph: %s -> %s nodes", len(graph.nodes), len(result.nodes))

    return result


def clone_graph(
    graph: "Graph",
    deep: bool = True,
) -> "Graph":
    """
    Клонує граф.

    Args:
        graph: Domain Graph entity
        deep: Якщо True - глибоке клонування через DTO

    Returns:
        Клон графу
    """
    if deep:
        # Через DTO - повне клонування
        json_str = graph_to_json(graph)
        return json_to_graph(json_str)
    else:
        # Shallow clone (streaming через iter_nodes)
        from graph_crawler.domain.entities.graph import Graph

        result = Graph(default_merge_strategy=graph.default_merge_strategy)
        for node in graph.iter_nodes():
            result.add_node(node)
        for edge in graph.iter_edges():
            result.add_edge(edge)
        return result
