"""High-Level Utility Functions для роботи з DTO.

Спрощує типові операції:
- Серіалізація/десеріалізація графів
- Робота з JSON/файлами
- Batch операції

Приклад:
    >>> from graph_crawler.application.dto.utils import (
    ...     graph_to_json,
    ...     json_to_graph,
    ...     save_graph,
    ...     load_graph,
    ...     merge_graphs,
    ... )
    >>>
    >>> # Серіалізація в JSON
    >>> json_str = graph_to_json(graph)
    >>>
    >>> # Десеріалізація з JSON
    >>> graph = json_to_graph(json_str)
    >>>
    >>> # Збереження/завантаження з файлу
    >>> save_graph(graph, 'graph.json')
    >>> graph = load_graph('graph.json')
    >>>
    >>> # Об'єднання графів з custom стратегією
    >>> merged = merge_graphs([g1, g2, g3], strategy='merge')
"""

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


def graph_to_json(
    graph: "Graph",
    indent: int = 2,
    ensure_ascii: bool = False,
) -> str:
    """
    Конвертує Domain Graph в JSON string через DTO.
    
    Args:
        graph: Domain Graph entity
        indent: Відступ для форматування JSON
        ensure_ascii: Чи екранувати non-ASCII символи
        
    Returns:
        JSON string
        
    Example:
        >>> json_str = graph_to_json(graph)
        >>> print(json_str[:100])
    """
    from graph_crawler.application.dto.mappers import GraphMapper
    
    graph_dto = GraphMapper.to_dto(graph)
    return json.dumps(
        graph_dto.model_dump(), 
        indent=indent, 
        ensure_ascii=ensure_ascii,
        default=str,  # Для datetime та інших non-serializable
    )


def json_to_graph(
    json_str: str,
    context: Optional[Dict[str, Any]] = None,
) -> "Graph":
    """
    Конвертує JSON string в Domain Graph через DTO.
    
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
    
    data = json.loads(json_str)
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
    path.write_text(json_str, encoding='utf-8')
    
    logger.info(f"Graph saved to {path}")


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
    json_str = path.read_text(encoding='utf-8')
    
    graph = json_to_graph(json_str, context=context)
    logger.info(f"Graph loaded from {path}: {len(graph.nodes)} nodes")
    
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
        
    Example:
        >>> # Об'єднання з дефолтною стратегією 'last'
        >>> merged = merge_graphs([g1, g2, g3])
        >>>
        >>> # Об'єднання з 'merge' стратегією
        >>> merged = merge_graphs([g1, g2, g3], strategy='merge')
        >>>
        >>> # Об'єднання з кастомною функцією
        >>> def my_merge(n1, n2):
        ...     return n1 if n1.scanned else n2
        >>> merged = merge_graphs([g1, g2], strategy='custom', custom_merge_fn=my_merge)
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
        f"Merged {len(graphs)} graphs: "
        f"result has {len(result.nodes)} nodes, "
        f"strategy={strategy}"
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
    from graph_crawler.domain.entities.edge import Edge
    
    result = Graph(default_merge_strategy=graph.default_merge_strategy)
    
    # Фільтруємо ноди
    for node in graph.nodes.values():
        if predicate(node):
            result.add_node(node)
    
    # Зберігаємо edges якщо потрібно
    if keep_edges:
        result_node_ids = set(result.nodes.keys())
        for edge in graph.edges:
            if (edge.source_node_id in result_node_ids and 
                edge.target_node_id in result_node_ids):
                result.add_edge(edge)
    
    logger.debug(
        f"Filtered graph: {len(graph.nodes)} -> {len(result.nodes)} nodes"
    )
    
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
        # Shallow clone
        from graph_crawler.domain.entities.graph import Graph
        
        result = Graph(default_merge_strategy=graph.default_merge_strategy)
        for node in graph.nodes.values():
            result.add_node(node)
        for edge in graph.edges:
            result.add_edge(edge)
        return result


# Type hints для IDE
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node
