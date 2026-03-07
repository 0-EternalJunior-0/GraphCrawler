"""Збереження графу у JSON файлах .

Використовує aiofiles для неблокуючого файлового I/O.
При відсутності aiofiles використовує asyncio executor для неблокуючих операцій.
"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

try:
    import aiofiles
    import aiofiles.os

    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False

if TYPE_CHECKING:
    from graph_crawler.domain.events.event_bus import EventBus

import logging
import time

# Thread pool для неблокуючих file I/O операцій (fallback)
_file_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="json_storage_")

from graph_crawler.shared.dto import GraphDTO
from graph_crawler.infrastructure.persistence.base import BaseStorage
from graph_crawler.shared.exceptions import LoadError, SaveError

logger = logging.getLogger(__name__)


class JSONStorage(BaseStorage):
    """
    Async збереження графу у JSON файлах через DTO .

    Використовує GraphDTO для ізоляції Domain Layer.

    Використовується для сайтів до 10k сторінок (~100MB).
    Зберігає граф у JSON файл для простого доступу. Використовує aiofiles для неблокуючого file I/O.

    Приклад:
        >>> from graph_crawler.application.dto.mappers import GraphMapper
        >>>
        >>> # Серіалізація Domain → DTO → JSON
        >>> graph_dto = GraphMapper.to_dto(graph)
        >>> await storage.save_graph(graph_dto)
        >>>
        >>> # Десеріалізація JSON → DTO → Domain
        >>> graph_dto = await storage.load_graph()
        >>> context = {'plugin_manager': pm, 'tree_parser': parser}
        >>> graph = GraphMapper.to_domain(graph_dto, context=context)
    """

    def __init__(self, storage_dir: str, event_bus: Optional["EventBus"] = None):
        """
        Ініціалізує JSONStorage.

        Args:
            storage_dir: Директорія для збереження JSON файлів
            event_bus: EventBus для публікації подій (опціонально)
        """
        super().__init__(event_bus=event_bus)
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.graph_file = self.storage_dir / "graph.json"

        if not AIOFILES_AVAILABLE:
            logger.warning("aiofiles not installed, falling back to sync I/O")

        logger.info(f"JSONStorage initialized at: {self.storage_dir}")

    async def save_graph(self, graph_dto: GraphDTO) -> bool:
        """
        Async зберігає весь граф у JSON через DTO .

        Приймає GraphDTO.

        Використовує aiofiles для неблокуючого запису.

        Args:
            graph_dto: GraphDTO для збереження

        Returns:
            True якщо успішно

        Raises:
            SaveError: Якщо не вдалося зберегти граф

        Example:
            >>> from graph_crawler.application.dto.mappers import GraphMapper
            >>> graph_dto = GraphMapper.to_dto(graph)
            >>> await storage.save_graph(graph_dto)
        """
        from graph_crawler.domain.events.events import EventType

        start_time = time.time()

        self.publish_event(
            EventType.STORAGE_SAVE_STARTED,
            data={
                "storage_type": "json",
                "nodes_count": len(graph_dto.nodes),
                "edges_count": len(graph_dto.edges),
            },
        )

        try:
            # Серіалізуємо GraphDTO через Pydantic model_dump()
            data = graph_dto.model_dump()
            # Використовуємо default=str для datetime та інших non-serializable типів
            json_content = json.dumps(data, ensure_ascii=False, indent=2, default=str)

            if AIOFILES_AVAILABLE:
                async with aiofiles.open(self.graph_file, "w", encoding="utf-8") as f:
                    await f.write(json_content)
            else:
                # Використовуємо executor для неблокуючого запису
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    _file_executor,
                    partial(self._sync_write_file, self.graph_file, json_content)
                )

            duration = time.time() - start_time

            self.publish_event(
                EventType.STORAGE_SAVE_SUCCESS,
                data={
                    "storage_type": "json",
                    "nodes_count": len(data["nodes"]),
                    "edges_count": len(data["edges"]),
                    "duration": round(duration, 3),
                    "file_path": str(self.graph_file),
                },
            )

            logger.info(
                f"Graph saved: {len(data['nodes'])} nodes, {len(data['edges'])} edges"
            )
            return True

        except (IOError, OSError) as e:
            error_msg = f"Failed to save graph to {self.graph_file}: {e}"
            logger.error(error_msg)

            self.publish_event(
                EventType.STORAGE_SAVE_ERROR,
                data={
                    "storage_type": "json",
                    "error": error_msg,
                    "error_type": type(e).__name__,
                },
            )

            raise SaveError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error while saving graph: {e}"
            logger.error(error_msg)

            self.publish_event(
                EventType.STORAGE_SAVE_ERROR,
                data={
                    "storage_type": "json",
                    "error": error_msg,
                    "error_type": type(e).__name__,
                },
            )

            raise SaveError(error_msg) from e

    async def load_graph(self, context: Optional[Dict[str, Any]] = None) -> Optional[GraphDTO]:
        """
        Async завантажує граф з JSON через DTO .

        Повертає GraphDTO.

        Використовує aiofiles для неблокуючого читання.

        Args:
            context: Контекст (не використовується в JSONStorage, але залишений для сумісності)

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
        from graph_crawler.domain.events.events import EventType

        if not await self.exists():
            logger.warning("No saved graph found")
            return None

        start_time = time.time()

        self.publish_event(
            EventType.STORAGE_LOAD_STARTED,
            data={"storage_type": "json", "file_path": str(self.graph_file)},
        )

        try:
            if AIOFILES_AVAILABLE:
                async with aiofiles.open(self.graph_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                data = json.loads(content)
            else:
                # Використовуємо executor для неблокуючого читання
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(
                    _file_executor,
                    partial(self._sync_read_json_file, self.graph_file)
                )

            # Десеріалізуємо GraphDTO через Pydantic model_validate()
            graph_dto = GraphDTO.model_validate(data)

            duration = time.time() - start_time

            self.publish_event(
                EventType.STORAGE_LOAD_SUCCESS,
                data={
                    "storage_type": "json",
                    "nodes_count": len(graph_dto.nodes),
                    "edges_count": len(graph_dto.edges),
                    "duration": round(duration, 3),
                    "file_path": str(self.graph_file),
                },
            )

            logger.info(
                f"Graph loaded: {len(graph_dto.nodes)} nodes, {len(graph_dto.edges)} edges"
            )
            return graph_dto

        except (IOError, OSError) as e:
            error_msg = f"Failed to load graph from {self.graph_file}: {e}"
            logger.error(error_msg)

            self.publish_event(
                EventType.STORAGE_LOAD_ERROR,
                data={
                    "storage_type": "json",
                    "error": error_msg,
                    "error_type": type(e).__name__,
                },
            )

            raise LoadError(error_msg) from e
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            error_msg = f"Invalid graph data in {self.graph_file}: {e}"
            logger.error(error_msg)

            self.publish_event(
                EventType.STORAGE_LOAD_ERROR,
                data={
                    "storage_type": "json",
                    "error": error_msg,
                    "error_type": type(e).__name__,
                },
            )

            raise LoadError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error while loading graph: {e}"
            logger.error(error_msg)

            self.publish_event(
                EventType.STORAGE_LOAD_ERROR,
                data={
                    "storage_type": "json",
                    "error": error_msg,
                    "error_type": type(e).__name__,
                },
            )

            raise LoadError(error_msg) from e

    async def save_partial(self, nodes: List[Dict], edges: List[Dict]) -> bool:
        """
        Async зберігає частину графу (додає до існуючого) .

        Args:
            nodes: Список вузлів (у вигляді dict)
            edges: Список ребер (у вигляді dict)

        Returns:
            True якщо успішно

        Raises:
            SaveError: Якщо не вдалося зберегти частину графу
        """
        try:
            # Завантажуємо існуючий граф або створюємо новий
            if await self.exists():
                if AIOFILES_AVAILABLE:
                    async with aiofiles.open(
                        self.graph_file, "r", encoding="utf-8"
                    ) as f:
                        content = await f.read()
                    data = json.loads(content)
                else:
                    # Використовуємо executor для неблокуючого читання
                    loop = asyncio.get_event_loop()
                    data = await loop.run_in_executor(
                        _file_executor,
                        partial(self._sync_read_json_file, self.graph_file)
                    )
            else:
                data = {"nodes": [], "edges": []}

            # Додаємо нові дані
            data["nodes"].extend(nodes)
            data["edges"].extend(edges)

            # Async зберігаємо
            json_content = json.dumps(data, ensure_ascii=False, indent=2)
            if AIOFILES_AVAILABLE:
                async with aiofiles.open(self.graph_file, "w", encoding="utf-8") as f:
                    await f.write(json_content)
            else:
                # Використовуємо executor для неблокуючого запису
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    _file_executor,
                    partial(self._sync_write_file, self.graph_file, json_content)
                )

            return True
        except (IOError, OSError, json.JSONDecodeError) as e:
            error_msg = f"Failed to save partial graph: {e}"
            logger.error(error_msg)
            raise SaveError(error_msg) from e

    async def clear(self) -> bool:
        """Async видаляє JSON файл з графом ."""
        try:
            if self.graph_file.exists():
                if AIOFILES_AVAILABLE:
                    await aiofiles.os.remove(self.graph_file)
                else:
                    self.graph_file.unlink()
                logger.info("Storage cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing storage: {e}")
            return False

    async def exists(self) -> bool:
        """Async перевіряє чи існує файл з графом ."""
        # Path.exists() is synchronous, but very fast
        # For true async, we could use aiofiles.os.path.exists in future
        return self.graph_file.exists()

    @staticmethod
    def _sync_write_file(file_path: Path, content: str) -> None:
        """Синхронний запис файлу (для виконання в executor)."""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def _sync_read_json_file(file_path: Path) -> Dict[str, Any]:
        """Синхронне читання JSON файлу (для виконання в executor)."""
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
