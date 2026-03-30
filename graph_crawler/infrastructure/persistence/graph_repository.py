"""Репозиторій для збереження/завантаження іменованих графів через GraphDTO (Repository Pattern SRP).

ВИПРАВЛЕНО: Додано async методи з executor для неблокуючих операцій.
"""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import aiofiles
    import aiofiles.os

    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False

# Import from shared layer (Clean Architecture fix)
from graph_crawler.domain.value_objects.models import GraphMetadata
from graph_crawler.infrastructure.persistence.naming_strategy import GraphNamingStrategy
from graph_crawler.shared.dto import GraphDTO
from graph_crawler.shared.exceptions import LoadError, SaveError

logger = logging.getLogger(__name__)

# Thread pool для неблокуючих file I/O операцій
_repo_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="graph_repo_")


class GraphRepository:
    """
    Репозиторій для збереження GraphDTO з ізоляцією Domain Layer.

    """

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        naming_strategy: Optional[GraphNamingStrategy] = None,
    ):
        """
        Ініціалізує репозиторій графів.

        Args:
            storage_dir: Директорія для збереження графів (default: ./crawler_data/graphs)
            naming_strategy: Стратегія іменування (опціонально, за замовчуванням timestamp)
        """
        from graph_crawler.shared.constants import DEFAULT_GRAPHS_DIR

        self.storage_dir = Path(storage_dir or DEFAULT_GRAPHS_DIR)
        self.graphs_dir = self.storage_dir / "graphs"
        self.metadata_dir = self.storage_dir / "metadata"

        # Dependency Injection для naming strategy
        self.naming_strategy = naming_strategy or GraphNamingStrategy("timestamp")

        # Створюємо директорії
        self.graphs_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        logger.info("GraphRepository initialized at: %s", self.storage_dir)

    def save_graph(
        self,
        graph_dto: GraphDTO,
        name: str,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Зберігає GraphDTO з унікальним ім'ям.

        Args:
            graph_dto: GraphDTO для збереження
            name: Ім'я графа (без дати, додається автоматично)
            description: Опис графа
            metadata: Додаткові метадані
        Returns:
            Повне ім'я збереженого графа (з датою)
        Raises:
            SaveError: Якщо не вдалося зберегти граф
        Examples:
            >>> from graph_crawler.application.dto.mappers import GraphMapper
            >>> graph_dto = GraphMapper.to_dto(graph)
            >>> repo.save_graph(graph_dto, name='royal_road_scan',
            ...                 description='Скан Royal Road книг')
            'royal_road_scan_2025-01-15_14-30-00'
        """
        try:
            full_name = self.naming_strategy.generate_name(name)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            # Серіалізуємо GraphDTO через Pydantic model_dump()
            graph_data = graph_dto.model_dump()

            # Використовуємо stats з GraphDTO
            graph_stats = graph_dto.stats

            # Створюємо метадані через Pydantic модель
            from graph_crawler.domain.value_objects.models import GraphStats

            graph_meta = GraphMetadata(
                name=name,
                full_name=full_name,
                description=description,
                created_at=timestamp,
                stats=GraphStats(
                    total_nodes=graph_stats.total_nodes,
                    scanned_nodes=graph_stats.scanned_nodes,
                    unscanned_nodes=graph_stats.unscanned_nodes,
                    total_edges=graph_stats.total_edges,
                ),
                metadata=metadata or {},
            )

            graph_file = self.graphs_dir / self.naming_strategy.format_graph_filename(full_name)
            # Використовуємо default=str для datetime та інших non-serializable типів
            with open(graph_file, "w", encoding="utf-8") as f:
                json.dump(graph_data, f, ensure_ascii=False, indent=2, default=str)

            # Зберігаємо метадані (через model_dump)
            meta_file = self.metadata_dir / self.naming_strategy.format_metadata_filename(full_name)
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(graph_meta.model_dump(), f, ensure_ascii=False, indent=2)

            logger.info("Graph saved: %s (%s nodes)", full_name, graph_stats.total_nodes)
            return full_name

        except (IOError, OSError) as e:
            error_msg = f"Failed to save graph '{name}': {e}"
            logger.error(error_msg)
            raise SaveError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error while saving graph '{name}': {e}"
            logger.error(error_msg)
            raise SaveError(error_msg) from e

    def load_graph(self, name: str, latest: bool = True) -> Optional[GraphDTO]:
        """
        Завантажує GraphDTO за ім'ям.

        Args:
            name: Ім'я графа (без дати) або повне ім'я (з датою)
            latest: Якщо True - завантажує останню версію графа
        Returns:
            GraphDTO або None якщо не знайдено
        Raises:
            LoadError: Якщо не вдалося завантажити граф
        Examples:
            >>> graph_dto = repo.load_graph('royal_road_scan')  # Остання версія
            >>> graph_dto = repo.load_graph('royal_road_scan_2025-01-15_14-30-00')  # Конкретна версія
            >>> # Конвертація в Domain Graph (якщо потрібно)
            >>> from graph_crawler.application.dto.mappers import GraphMapper
            >>> context = {'plugin_manager': pm, 'tree_parser': parser}
            >>> graph = GraphMapper.to_domain(graph_dto, context=context)
        """
        try:
            graph_file = self.graphs_dir / self.naming_strategy.format_graph_filename(name)

            if graph_file.exists():
                # Це повне ім'я, завантажуємо напряму
                full_name = name
            else:
                # Це базове ім'я, шукаємо версії через naming_strategy
                all_graph_files = list(self.graphs_dir.glob("*.json"))
                versions = self.naming_strategy.find_versions(name, all_graph_files)

                if not versions:
                    logger.warning("No graphs found with name: %s", name)
                    return None

                # Беремо останню версію
                full_name = versions[0] if latest else versions[-1]
                graph_file = self.graphs_dir / self.naming_strategy.format_graph_filename(full_name)

            # Читаємо граф
            with open(graph_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Десеріалізуємо GraphDTO через Pydantic model_validate()
            graph_dto = GraphDTO.model_validate(data)

            logger.info("Graph loaded: %s (%s nodes)", full_name, len(graph_dto.nodes))
            return graph_dto

        except (IOError, OSError) as e:
            error_msg = f"Failed to load graph '{name}': {e}"
            logger.error(error_msg)
            raise LoadError(error_msg) from e
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            error_msg = f"Invalid graph data for '{name}': {e}"
            logger.error(error_msg)
            raise LoadError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error while loading graph '{name}': {e}"
            logger.error(error_msg)
            raise LoadError(error_msg) from e

    def list_graphs(self) -> List[GraphMetadata]:
        """
        Повертає список всіх збережених графів.

        Returns:
            Список GraphMetadata моделей з інформацією про графи

        Examples:
            >>> graphs = repo.list_graphs()
            >>> for g in graphs:
            ...     print(f"{g.name}: {g.stats.total_nodes} nodes")
        """
        graphs = []

        try:
            for meta_file in self.metadata_dir.glob("*.meta.json"):
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta_data = json.load(f)
                    # Валідуємо через Pydantic
                    meta = GraphMetadata.model_validate(meta_data)
                    graphs.append(meta)
                except Exception as e:
                    logger.warning("Failed to read metadata %s: %s", meta_file, e)

            # Сортуємо за датою створення (новіші першими)
            graphs.sort(key=lambda x: x.created_at, reverse=True)
            return graphs

        except Exception as e:
            logger.error("Failed to list graphs: %s", e)
            return []

    def delete_graph(self, name: str) -> bool:
        """
        Видаляє граф за ім'ям.

        Args:
            name: Повне ім'я графа (з датою)

        Returns:
            True якщо успішно видалено

        Examples:
            >>> repo.delete_graph('royal_road_scan_2025-01-15_14-30-00')
        """
        try:
            graph_file = self.graphs_dir / f"{name}.json"
            meta_file = self.metadata_dir / f"{name}.meta.json"

            deleted = False
            if graph_file.exists():
                graph_file.unlink()
                deleted = True
            if meta_file.exists():
                meta_file.unlink()
                deleted = True

            if deleted:
                logger.info("Graph deleted: %s", name)
            else:
                logger.warning("Graph not found: %s", name)

            return deleted

        except Exception as e:
            logger.error("Failed to delete graph '%s': %s", name, e)
            return False

    def graph_exists(self, name: str) -> bool:
        """
        Перевіряє чи існує граф з таким ім'ям.

        Args:
            name: Ім'я графа (без дати) або повне ім'я

        Returns:
            True якщо граф існує
        """
        # Спочатку перевіряємо чи існує файл з повним ім'ям
        graph_file = self.graphs_dir / f"{name}.json"
        if graph_file.exists():
            return True

        # Якщо ні, шукаємо як базове ім'я (шукаємо будь-яку версію)
        graph_files = list(self.graphs_dir.glob(f"{name}_*.json"))
        return len(graph_files) > 0

    def get_metadata(self, name: str) -> Optional[GraphMetadata]:
        """
        Повертає метадані графа без завантаження самого графа.

        Args:
            name: Повне ім'я графа

        Returns:
            GraphMetadata модель або None
        """
        try:
            meta_file = self.metadata_dir / f"{name}.meta.json"
            if not meta_file.exists():
                return None

            with open(meta_file, "r", encoding="utf-8") as f:
                meta_data = json.load(f)

            # Валідуємо через Pydantic
            return GraphMetadata.model_validate(meta_data)

        except Exception as e:
            logger.error("Failed to read metadata for '%s': %s", name, e)
            return None

    async def save_graph_async(
        self,
        graph_dto: GraphDTO,
        name: str,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Async зберігає GraphDTO з унікальним ім'ям (неблокуюча версія).

        Args:
            graph_dto: GraphDTO для збереження
            name: Ім'я графа (без дати, додається автоматично)
            description: Опис графа
            metadata: Додаткові метадані

        Returns:
            Повне ім'я збереженого графа (з датою)
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _repo_executor, partial(self.save_graph, graph_dto, name, description, metadata)
        )

    async def load_graph_async(self, name: str, latest: bool = True) -> Optional[GraphDTO]:
        """
        Async завантажує GraphDTO за ім'ям (неблокуюча версія).

        Args:
            name: Ім'я графа (без дати) або повне ім'я (з датою)
            latest: Якщо True - завантажує останню версію графа

        Returns:
            GraphDTO або None якщо не знайдено
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_repo_executor, partial(self.load_graph, name, latest))

    async def delete_graph_async(self, name: str) -> bool:
        """
        Async видаляє граф за ім'ям (неблокуюча версія).

        Args:
            name: Повне ім'я графа (з датою)

        Returns:
            True якщо успішно видалено
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_repo_executor, partial(self.delete_graph, name))

    async def get_metadata_async(self, name: str) -> Optional[GraphMetadata]:
        """
        Async повертає метадані графа (неблокуюча версія).

        Args:
            name: Повне ім'я графа

        Returns:
            GraphMetadata модель або None
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_repo_executor, partial(self.get_metadata, name))

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
