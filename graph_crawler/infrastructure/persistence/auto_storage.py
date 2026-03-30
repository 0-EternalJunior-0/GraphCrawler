"""Автоматичне масштабування storage базуючись на розмірі графа."""

import logging
from typing import Any, Dict, List, Optional

from graph_crawler.domain.entities.graph import Graph
from graph_crawler.infrastructure.persistence.base import BaseStorage
from graph_crawler.infrastructure.persistence.json_storage import JSONStorage
from graph_crawler.infrastructure.persistence.memory_storage import MemoryStorage
from graph_crawler.infrastructure.persistence.sqlite_storage import SQLiteStorage
from graph_crawler.shared.constants import DEFAULT_JSON_THRESHOLD

logger = logging.getLogger(__name__)


class AutoStorage(BaseStorage):
    """
    Автоматично вибирає storage базуючись на розмірі графа.

    """

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        memory_threshold: int = 1000,
        json_threshold: int = DEFAULT_JSON_THRESHOLD,
        db_config: Optional[Dict[str, Any]] = None,
        event_bus=None,
    ):
        """
        Ініціалізує AutoStorage.

        Args:
            storage_dir: Директорія для JSON/SQLite storage (default: ./crawler_data)
            memory_threshold: Поріг для переходу Memory → JSON (default: 1000)
            json_threshold: Поріг для переходу JSON → DB (default: DEFAULT_JSON_THRESHOLD)
            db_config: Конфігурація для PostgreSQL/MongoDB
            event_bus: EventBus для публікації подій (опціонально,)
        """
        from graph_crawler.shared.constants import DEFAULT_DATA_DIR

        self.storage_dir = storage_dir or DEFAULT_DATA_DIR
        self.memory_threshold = memory_threshold
        self.json_threshold = json_threshold
        self.db_config = db_config
        self.event_bus = event_bus

        # Починаємо з MemoryStorage
        self.current_storage = MemoryStorage()
        self.node_count = 0

        logger.info(
            f"AutoStorage initialized: "
            f"memory_threshold={memory_threshold}, "
            f"json_threshold={json_threshold}, "
            f"db_config={'configured' if db_config else 'not configured'}"
        )

    def save_graph(self, graph: Graph) -> bool:
        """
        Зберігає граф, автоматично вибираючи storage.

        Args:
            graph: Граф для збереження

        Returns:
            True якщо успішно
        """
        from graph_crawler.application.dto.mappers.graph_mapper import GraphMapper

        self.node_count = len(graph.nodes)
        self._check_and_upgrade(graph)

        # Конвертуємо Graph в GraphDTO для збереження
        graph_dto = GraphMapper.to_dto(graph)

        # Зберігаємо в поточне storage (потрібен async виклик)
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self.current_storage.save_graph(graph_dto)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self.current_storage.save_graph(graph_dto))
        except RuntimeError:
            # Немає event loop - створюємо новий
            return asyncio.run(self.current_storage.save_graph(graph_dto))

    def _check_and_upgrade(self, graph: Graph):
        """
        Перевіряє чи потрібно оновити storage та виконує міграцію.

        Args:
            graph: Граф який потрібно зберегти (використовується для міграції)
        """
        current_type = type(self.current_storage).__name__
        if self.node_count > self.json_threshold:
            if current_type in ["MemoryStorage", "JSONStorage"]:
                logger.info(
                    f"Node count ({self.node_count}) exceeded json_threshold ({self.json_threshold}). "
                    f"Upgrading to database storage..."
                )
                self._upgrade_to_database(graph)
        elif self.node_count > self.memory_threshold:
            if current_type == "MemoryStorage":
                logger.info(
                    f"Node count ({self.node_count}) exceeded memory_threshold ({self.memory_threshold}). "
                    f"Upgrading to JSON storage..."
                )
                self._upgrade_to_json(graph)

    def _upgrade_to_json(self, graph: Graph):
        """
        Міграція з MemoryStorage → JSONStorage.

        Args:
            graph: Граф для міграції
        """
        import asyncio

        from graph_crawler.application.dto.mappers.graph_mapper import GraphMapper

        try:
            new_storage = JSONStorage(self.storage_dir)

            # Конвертуємо Graph в GraphDTO
            graph_dto = GraphMapper.to_dto(graph)

            # Зберігаємо граф (async виклик)
            asyncio.run(new_storage.save_graph(graph_dto))

            # Очищаємо старе storage
            asyncio.run(self.current_storage.clear())

            # Переключаємо
            self.current_storage = new_storage

            logger.info("Successfully upgraded to JSONStorage: %s nodes migrated", len(graph.nodes))

            # Подія про оновлення storage
            if self.event_bus:
                from graph_crawler.domain.events import CrawlerEvent, EventType

                self.event_bus.publish(
                    CrawlerEvent.create(
                        EventType.STORAGE_UPGRADED,
                        data={
                            "from_storage": "MemoryStorage",
                            "to_storage": "JSONStorage",
                            "node_count": len(graph.nodes),
                            "reason": f"exceeded memory_threshold ({self.memory_threshold})",
                        },
                    )
                )

        except Exception as e:
            logger.error("Failed to upgrade to JSONStorage: %s", e)
            raise

    def _upgrade_to_database(self, graph: Graph):
        """Міграція з JSONStorage → PostgreSQL/MongoDB/SQLite."""
        import asyncio

        from graph_crawler.application.dto.mappers.graph_mapper import GraphMapper

        try:
            # Вибираємо тип БД
            db_type = self._get_database_type()
            if db_type == "postgresql":
                new_storage = self._create_postgresql_storage()
            elif db_type == "mongodb":
                new_storage = self._create_mongodb_storage()
            else:
                # Fallback на SQLite
                new_storage = SQLiteStorage(self.storage_dir)
                logger.info("Using SQLite as fallback (no PostgreSQL/MongoDB configured)")

            # Конвертуємо Graph в GraphDTO
            graph_dto = GraphMapper.to_dto(graph)

            # Зберігаємо граф (async виклик)
            asyncio.run(new_storage.save_graph(graph_dto))

            # Очищаємо старе storage
            asyncio.run(self.current_storage.clear())

            # Переключаємо
            self.current_storage = new_storage

            logger.info(
                f"Successfully upgraded to {db_type.upper()}: {len(graph.nodes)} nodes migrated"
            )

        except Exception as e:
            logger.error("Failed to upgrade to database: %s", e)
            # Fallback на SQLite
            try:
                logger.info("Attempting fallback to SQLite...")
                new_storage = SQLiteStorage(self.storage_dir)
                graph_dto = GraphMapper.to_dto(graph)
                asyncio.run(new_storage.save_graph(graph_dto))
                self.current_storage = new_storage
                logger.info("Fallback to SQLite successful")
            except Exception as fallback_error:
                logger.error("Fallback to SQLite also failed: %s", fallback_error)
                raise

    def _get_database_type(self) -> str:
        """
        Визначає тип БД з конфігурації.

        Returns:
            'postgresql', 'mongodb', або 'sqlite' (fallback)
        """
        if not self.db_config:
            logger.warning("No db_config provided, using SQLite as fallback")
            return "sqlite"

        db_type = self.db_config.get("type", "").lower()

        if db_type in ["postgresql", "postgres", "pg"]:
            return "postgresql"
        elif db_type in ["mongodb", "mongo"]:
            return "mongodb"
        else:
            logger.warning("Unknown database type: %s, using SQLite as fallback", db_type)
            return "sqlite"

    def _create_postgresql_storage(self):
        """Створює PostgreSQLStorage."""
        try:
            # CIRCULAR IMPORT WORKAROUND:
            # PostgreSQLStorage імпортується тут для уникнення залежностей при старті
            # Це дозволяє не встановлювати psycopg2, якщо PostgreSQL не використовується
            from graph_crawler.infrastructure.persistence.postgresql_storage import (
                PostgreSQLStorage,
            )

            return PostgreSQLStorage(self.db_config)
        except ImportError as e:
            logger.warning(
                f"PostgreSQL not available: {e}. Install: pip install sqlalchemy psycopg2-binary"
            )
            logger.info("Falling back to SQLite")
            return SQLiteStorage(self.storage_dir)
        except Exception as e:
            logger.warning("Failed to create PostgreSQL storage: %s", e)
            logger.info("Falling back to SQLite")
            return SQLiteStorage(self.storage_dir)

    def _create_mongodb_storage(self):
        """Створює MongoDBStorage."""
        try:
            # CIRCULAR IMPORT WORKAROUND:
            # MongoDBStorage імпортується тут для уникнення залежностей при старті
            # Це дозволяє не встановлювати pymongo, якщо MongoDB не використовується
            from graph_crawler.infrastructure.persistence.mongodb_storage import (
                MongoDBStorage,
            )

            return MongoDBStorage(self.db_config)
        except ImportError as e:
            logger.warning("MongoDB not available: %s. Install: pip install pymongo", e)
            logger.info("Falling back to SQLite")
            return SQLiteStorage(self.storage_dir)
        except Exception as e:
            logger.warning("Failed to create MongoDB storage: %s", e)
            logger.info("Falling back to SQLite")
            return SQLiteStorage(self.storage_dir)

    def load_graph(self) -> Optional[Graph]:
        """
        Завантажує граф з поточного storage.

        Returns:
            Граф або None
        """
        return self.current_storage.load_graph()

    def save_partial(self, nodes: List[Dict], edges: List[Dict]) -> bool:
        """
        Зберігає частину графу.

        Args:
            nodes: Список вузлів
            edges: Список ребер

        Returns:
            True якщо успішно
        """
        # Оновлюємо лічильник
        self.node_count += len(nodes)

        # Для save_partial потрібно завантажити існуючий граф для міграції
        if self.node_count > self.json_threshold or self.node_count > self.memory_threshold:
            current_type = type(self.current_storage).__name__
            needs_upgrade = (
                self.node_count > self.json_threshold
                and current_type in ["MemoryStorage", "JSONStorage"]
            ) or (self.node_count > self.memory_threshold and current_type == "MemoryStorage")

            if needs_upgrade:
                # Завантажуємо існуючий граф для міграції
                graph = self.current_storage.load_graph()
                if graph is not None:
                    self._check_and_upgrade(graph)

        # Зберігаємо в поточне storage
        return self.current_storage.save_partial(nodes, edges)

    def clear(self) -> bool:
        """Очищує поточне storage."""
        self.node_count = 0
        return self.current_storage.clear()

    def exists(self) -> bool:
        """Перевіряє чи існує збережений граф."""
        return self.current_storage.exists()

    def get_current_storage_type(self) -> str:
        """
        Повертає тип поточного storage.

        Returns:
            Назва класу поточного storage
        """
        return type(self.current_storage).__name__
