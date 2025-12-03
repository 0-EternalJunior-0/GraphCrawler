"""Domain Entities - Core business objects for GraphCrawler.

Основні сутності:
- Node - вузол графу (веб-сторінка)
- Edge - ребро графу (посилання)
- Graph - граф веб-сайту

Використання:
    from graph_crawler.domain.entities import Node, Edge, Graph

    node = Node(url="https://example.com")
    graph = Graph()
    graph.add_node(node)
"""

from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.edge_analysis import EdgeAnalysis
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.graph_operations import GraphOperations
from graph_crawler.domain.entities.graph_statistics import GraphStatistics
from graph_crawler.domain.entities.node import Node

__all__ = [
    "Node",
    "Edge",
    "Graph",
    "GraphOperations",
    "GraphStatistics",
    "EdgeAnalysis",
]
