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

    Стратегія масштабування (пороги конфігуруються):
    - < memory_threshold (default: 1000) → MemoryStorage (швидко, RAM)
    - memory_threshold - json_threshold (1000-DEFAULT_JSON_THRESHOLD) → JSONStorage (файли)
    - > json_threshold (>DEFAULT_JSON_THRESHOLD) → PostgreSQL/MongoDB/SQLite (БД)

    Приклад використання:
        storage = AutoStorage(
            memory_threshold=1000,
            json_threshold=DEFAULT_JSON_THRESHOLD,
            db_config={
                'type': 'postgresql',  # або 'mongodb'
                'host': 'localhost',
                'database': 'graph_crawler'
            }
        )

    Якщо db_config не вказано або БД не доступна - fallback на SQLite.
    """

    def __init__(
        self,
        storage_dir: str = "./tmp/graph_crawler",
        memory_threshold: int = 1000,
        json_threshold: int = DEFAULT_JSON_THRESHOLD,
        db_config: Optional[Dict[str, Any]] = None,
        event_bus=None,
    ):
        """
        Ініціалізує AutoStorage.

        Args:
            storage_dir: Директорія для JSON/SQLite storage
            memory_threshold: Поріг для переходу Memory → JSON (default: 1000)
            json_threshold: Поріг для переходу JSON → DB (default: DEFAULT_JSON_THRESHOLD)
            db_config: Конфігурація для PostgreSQL/MongoDB
            event_bus: EventBus для публікації подій (опціонально, Alpha 2.0)
        """
        self.storage_dir = storage_dir
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
        self.node_count = len(graph.nodes)

        # Перевіряємо чи потрібно оновити storage та передаємо граф
        self._check_and_upgrade(graph)

        # Зберігаємо в поточне storage
        return self.current_storage.save_graph(graph)

    def _check_and_upgrade(self, graph: Graph):
        """
        Перевіряє чи потрібно оновити storage та виконує міграцію.

        Args:
            graph: Граф який потрібно зберегти (використовується для міграції)
        """
        current_type = type(self.current_storage).__name__

        # Якщо перевищили json_threshold - переходимо на БД
        if self.node_count > self.json_threshold:
            if current_type in ["MemoryStorage", "JSONStorage"]:
                logger.info(
                    f"Node count ({self.node_count}) exceeded json_threshold ({self.json_threshold}). "
                    f"Upgrading to database storage..."
                )
                self._upgrade_to_database(graph)

        # Якщо перевищили memory_threshold - переходимо на JSON
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
        try:
            # Створюємо JSON storage
            new_storage = JSONStorage(self.storage_dir)

            # Зберігаємо граф
            new_storage.save_graph(graph)

            # Очищаємо старе storage
            self.current_storage.clear()

            # Переключаємо
            self.current_storage = new_storage

            logger.info(
                f"Successfully upgraded to JSONStorage: {len(graph.nodes)} nodes migrated"
            )

            # Подія про оновлення storage (Alpha 2.0)
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
            logger.error(f"Failed to upgrade to JSONStorage: {e}")
            raise

    def _upgrade_to_database(self, graph: Graph):
        """Міграція з JSONStorage → PostgreSQL/MongoDB/SQLite."""
        try:
            # Вибираємо тип БД
            db_type = self._get_database_type()

            # Створюємо відповідне storage
            if db_type == "postgresql":
                new_storage = self._create_postgresql_storage()
            elif db_type == "mongodb":
                new_storage = self._create_mongodb_storage()
            else:
                # Fallback на SQLite
                new_storage = SQLiteStorage(self.storage_dir)
                logger.info(
                    "Using SQLite as fallback (no PostgreSQL/MongoDB configured)"
                )

            # Зберігаємо граф (граф передається напряму, не потрібно завантажувати)
            new_storage.save_graph(graph)

            # Очищаємо старе storage
            self.current_storage.clear()

            # Переключаємо
            self.current_storage = new_storage

            logger.info(
                f"Successfully upgraded to {db_type.upper()}: {len(graph.nodes)} nodes migrated"
            )

        except Exception as e:
            logger.error(f"Failed to upgrade to database: {e}")
            # Fallback на SQLite
            try:
                logger.info("Attempting fallback to SQLite...")
                new_storage = SQLiteStorage(self.storage_dir)
                new_storage.save_graph(graph)
                self.current_storage = new_storage
                logger.info("Fallback to SQLite successful")
            except Exception as fallback_error:
                logger.error(f"Fallback to SQLite also failed: {fallback_error}")
                raise

        except Exception as e:
            logger.error(f"Failed to upgrade to database: {e}")
            # Fallback на SQLite
            try:
                logger.info("Attempting fallback to SQLite...")
                graph = self.current_storage.load_graph()
                new_storage = SQLiteStorage(self.storage_dir)
                new_storage.save_graph(graph)
                self.current_storage = new_storage
                logger.info("Fallback to SQLite successful")
            except Exception as fallback_error:
                logger.error(f"Fallback to SQLite also failed: {fallback_error}")
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
            logger.warning(
                f"Unknown database type: {db_type}, using SQLite as fallback"
            )
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
            logger.warning(f"Failed to create PostgreSQL storage: {e}")
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
            logger.warning(f"MongoDB not available: {e}. Install: pip install pymongo")
            logger.info("Falling back to SQLite")
            return SQLiteStorage(self.storage_dir)
        except Exception as e:
            logger.warning(f"Failed to create MongoDB storage: {e}")
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
        if (
            self.node_count > self.json_threshold
            or self.node_count > self.memory_threshold
        ):
            current_type = type(self.current_storage).__name__
            needs_upgrade = (
                self.node_count > self.json_threshold
                and current_type in ["MemoryStorage", "JSONStorage"]
            ) or (
                self.node_count > self.memory_threshold
                and current_type == "MemoryStorage"
            )

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
