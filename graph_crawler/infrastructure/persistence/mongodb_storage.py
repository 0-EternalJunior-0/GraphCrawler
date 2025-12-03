"""Збереження графу у MongoDB базі даних через GraphDTO.
- Переписано на motor для async операцій
- Всі методи тепер async
- Використовує AsyncIOMotorClient замість MongoClient
"""

import logging
from typing import Any, Dict, List, Optional

from graph_crawler.application.dto import GraphDTO, NodeDTO, EdgeDTO, GraphStatsDTO
from graph_crawler.infrastructure.persistence.base import BaseStorage
from graph_crawler.shared.constants import DEFAULT_MONGODB_TIMEOUT_MS
from graph_crawler.shared.exceptions import LoadError, SaveError

logger = logging.getLogger(__name__)


class MongoDBStorage(BaseStorage):
    """
    Async збереження GraphDTO у MongoDB.

    BREAKING CHANGE: Тепер використовує GraphDTO замість Graph для ізоляції Domain Layer.

    Використовується для великих графів (>20k сторінок).
    Використовує motor для async операцій.

    Приклад конфігурації:
        config = {
            'connection_string': 'mongodb://localhost:27017/',
            'database': 'graph_crawler',
            'nodes_collection': 'nodes',
            'edges_collection': 'edges'
        }

    Приклад використання:
        >>> from graph_crawler.application.dto.mappers import GraphMapper
        >>> 
        >>> storage = MongoDBStorage(config)
        >>> await storage.init()  # Async ініціалізація
        >>> 
        >>> # Серіалізація Domain → DTO → MongoDB
        >>> graph_dto = GraphMapper.to_dto(graph)
        >>> await storage.save_graph(graph_dto)
        >>> 
        >>> # Десеріалізація MongoDB → DTO → Domain
        >>> graph_dto = await storage.load_graph()
        >>> context = {'plugin_manager': pm, 'tree_parser': parser}
        >>> graph = GraphMapper.to_domain(graph_dto, context=context)
        >>> 
        >>> await storage.close()
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Ініціалізує MongoDBStorage.

        Args:
            config: Словник з налаштуваннями підключення до MongoDB

        Raises:
            ImportError: Якщо motor не встановлений
        """
        super().__init__()
        self.config = config
        self.client = None
        self.db = None
        self.nodes_collection = None
        self.edges_collection = None
        self._initialized = False

        try:
            from motor.motor_asyncio import AsyncIOMotorClient

            self._motor_available = True
        except ImportError:
            logger.error("Motor not installed. Install it: pip install motor")
            raise ImportError(
                "MongoDB async storage requires motor. Install it: pip install motor"
            )

        # Зберігаємо параметри для async init
        self.connection_string = config.get(
            "connection_string", "mongodb://localhost:27017/"
        )
        self.database_name = config.get("database", "graph_crawler")
        self.nodes_collection_name = config.get("nodes_collection", "nodes")
        self.edges_collection_name = config.get("edges_collection", "edges")

    async def init(self) -> None:
        """
        Async ініціалізація підключення до MongoDB.

        Викликати після створення екземпляру:
            storage = MongoDBStorage(config)
            await storage.init()
        """
        if self._initialized:
            return

        from motor.motor_asyncio import AsyncIOMotorClient

        try:
            self.client = AsyncIOMotorClient(
                self.connection_string,
                serverSelectionTimeoutMS=DEFAULT_MONGODB_TIMEOUT_MS,
            )
            # Тестуємо підключення
            await self.client.admin.command("ping")
            logger.info(f"Connected to MongoDB (async): {self.connection_string}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise ConnectionError(f"Cannot connect to MongoDB: {e}") from e

        # Отримуємо посилання на БД та колекції
        self.db = self.client[self.database_name]
        self.nodes_collection = self.db[self.nodes_collection_name]
        self.edges_collection = self.db[self.edges_collection_name]

        # Створюємо індекси для швидкості
        await self._create_indexes()
        self._initialized = True
        logger.info(f"MongoDBStorage initialized successfully (async)")

    async def _create_indexes(self) -> None:
        """Async створює індекси для оптимізації запитів."""
        try:
            # Індекс для node_id (primary key)
            await self.nodes_collection.create_index("node_id", unique=True)
            # Індекс для URL (часті пошуки)
            await self.nodes_collection.create_index("url")

            # Індекси для ребер
            await self.edges_collection.create_index("edge_id", unique=True)
            await self.edges_collection.create_index("source_node_id")
            await self.edges_collection.create_index("target_node_id")

            logger.debug("MongoDB indexes created (async)")
        except Exception as e:
            logger.warning(f"Failed to create indexes: {e}")

    async def save_graph(self, graph_dto: GraphDTO) -> bool:
        """
        Async зберігає GraphDTO у MongoDB.

        BREAKING CHANGE: Тепер приймає GraphDTO замість Graph.

        Args:
            graph_dto: GraphDTO для збереження

        Returns:
            True якщо успішно збережено

        Raises:
            SaveError: Якщо не вдалося зберегти граф

        Example:
            >>> from graph_crawler.application.dto.mappers import GraphMapper
            >>> graph_dto = GraphMapper.to_dto(graph)
            >>> await storage.save_graph(graph_dto)
        """
        if not self._initialized:
            await self.init()

        try:
            from pymongo import UpdateOne

            # Зберігаємо вузли (bulk upsert) з DTO
            if graph_dto.nodes:
                nodes_operations = []
                for node_dto in graph_dto.nodes:
                    node_data = node_dto.model_dump()
                    # Конвертуємо datetime в ISO format для MongoDB
                    if node_data.get("created_at"):
                        node_data["created_at"] = node_data["created_at"].isoformat()

                    operation = UpdateOne(
                        {"node_id": node_data["node_id"]},
                        {"$set": node_data},
                        upsert=True,
                    )
                    nodes_operations.append(operation)

                if nodes_operations:
                    await self.nodes_collection.bulk_write(
                        nodes_operations, ordered=False
                    )

            # Зберігаємо ребра (bulk upsert) з DTO
            if graph_dto.edges:
                edges_operations = []
                for edge_dto in graph_dto.edges:
                    edge_data = edge_dto.model_dump()
                    # Конвертуємо datetime в ISO format для MongoDB
                    if edge_data.get("created_at"):
                        edge_data["created_at"] = edge_data["created_at"].isoformat()

                    operation = UpdateOne(
                        {"edge_id": edge_data["edge_id"]},
                        {"$set": edge_data},
                        upsert=True,
                    )
                    edges_operations.append(operation)

                if edges_operations:
                    await self.edges_collection.bulk_write(
                        edges_operations, ordered=False
                    )

            logger.info(
                f"Graph saved to MongoDB (async): {len(graph_dto.nodes)} nodes, {len(graph_dto.edges)} edges"
            )
            return True

        except Exception as e:
            error_msg = f"Failed to save graph to MongoDB: {e}"
            logger.error(error_msg)
            raise SaveError(error_msg) from e

    async def load_graph(self, context: Optional[Dict[str, Any]] = None) -> Optional[GraphDTO]:
        """
        Async завантажує GraphDTO з MongoDB.

        BREAKING CHANGE: Тепер повертає GraphDTO замість Graph.

        Args:
            context: Контекст (не використовується в MongoDBStorage, але залишений для сумісності)

        Returns:
            GraphDTO або None якщо не знайдено

        Raises:
            LoadError: Якщо не вдалося завантажити граф

        Example:
            >>> graph_dto = await storage.load_graph()
            >>> # Конвертація в Domain Graph (якщо потрібно)
            >>> from graph_crawler.application.dto.mappers import GraphMapper
            >>> context = {'plugin_manager': pm, 'tree_parser': parser}
            >>> graph = GraphMapper.to_domain(graph_dto, context=context)
        """
        if not self._initialized:
            await self.init()

        try:
            nodes_dtos = []
            edges_dtos = []

            # Завантажуємо вузли
            async for node_doc in self.nodes_collection.find({}):
                # Видаляємо MongoDB _id
                if "_id" in node_doc:
                    del node_doc["_id"]

                # Створюємо NodeDTO через Pydantic validation
                node_dto = NodeDTO.model_validate(node_doc)
                nodes_dtos.append(node_dto)

            # Завантажуємо ребра
            async for edge_doc in self.edges_collection.find({}):
                # Видаляємо MongoDB _id
                if "_id" in edge_doc:
                    del edge_doc["_id"]

                # Створюємо EdgeDTO через Pydantic validation
                edge_dto = EdgeDTO.model_validate(edge_doc)
                edges_dtos.append(edge_dto)

            if not nodes_dtos:
                return None

            # Створюємо stats
            stats = GraphStatsDTO(
                total_nodes=len(nodes_dtos),
                scanned_nodes=sum(1 for n in nodes_dtos if n.scanned),
                unscanned_nodes=sum(1 for n in nodes_dtos if not n.scanned),
                total_edges=len(edges_dtos),
                avg_depth=sum(n.depth for n in nodes_dtos) / len(nodes_dtos) if nodes_dtos else 0.0,
                max_depth=max((n.depth for n in nodes_dtos), default=0),
            )

            # Створюємо GraphDTO
            graph_dto = GraphDTO(
                nodes=nodes_dtos,
                edges=edges_dtos,
                stats=stats,
            )

            logger.info(
                f"Graph loaded from MongoDB (async): {len(nodes_dtos)} nodes, {len(edges_dtos)} edges"
            )
            return graph_dto

        except Exception as e:
            error_msg = f"Failed to load graph from MongoDB: {e}"
            logger.error(error_msg)
            raise LoadError(error_msg) from e

    async def save_partial(self, nodes: List[Dict], edges: List[Dict]) -> bool:
        """
        Async зберігає частину графу (інкрементально).

        Args:
            nodes: Список вузлів як dict
            edges: Список ребер як dict

        Returns:
            True якщо успішно
        """
        if not self._initialized:
            await self.init()

        try:
            from pymongo import UpdateOne

            # Зберігаємо вузли
            if nodes:
                operations = []
                for node_data in nodes:
                    operation = UpdateOne(
                        {"node_id": node_data["node_id"]},
                        {"$set": node_data},
                        upsert=True,
                    )
                    operations.append(operation)

                if operations:
                    await self.nodes_collection.bulk_write(operations, ordered=False)

            # Зберігаємо ребра
            if edges:
                operations = []
                for edge_data in edges:
                    operation = UpdateOne(
                        {"edge_id": edge_data["edge_id"]},
                        {"$set": edge_data},
                        upsert=True,
                    )
                    operations.append(operation)

                if operations:
                    await self.edges_collection.bulk_write(operations, ordered=False)

            return True

        except Exception as e:
            logger.error(f"Failed to save partial graph to MongoDB: {e}")
            return False

    async def clear(self) -> bool:
        """
        Async очищує колекції (видаляє всі документи).

        Returns:
            True якщо успішно
        """
        if not self._initialized:
            await self.init()

        try:
            await self.nodes_collection.delete_many({})
            await self.edges_collection.delete_many({})
            logger.info("MongoDB storage cleared (async)")
            return True
        except Exception as e:
            logger.error(f"Failed to clear MongoDB storage: {e}")
            return False

    async def exists(self) -> bool:
        """
        Async перевіряє чи є дані в колекціях.

        Returns:
            True якщо є хоча б один вузол
        """
        if not self._initialized:
            await self.init()

        try:
            count = await self.nodes_collection.count_documents({}, limit=1)
            return count > 0
        except Exception as e:
            logger.error(f"Failed to check MongoDB storage: {e}")
            return False

    async def close(self) -> None:
        """Async закриває з'єднання з MongoDB."""
        if self.client:
            self.client.close()
            self._initialized = False
            logger.debug("MongoDB connection closed (async)")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False
