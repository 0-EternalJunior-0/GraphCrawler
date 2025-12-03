"""Репозиторій для збереження/завантаження іменованих графів через GraphDTO (Repository Pattern SRP)."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from graph_crawler.application.dto import GraphDTO, GraphStatsDTO
from graph_crawler.domain.value_objects.models import GraphMetadata
from graph_crawler.infrastructure.persistence.naming_strategy import GraphNamingStrategy
from graph_crawler.shared.exceptions import LoadError, SaveError, StorageError

logger = logging.getLogger(__name__)


class GraphRepository:
    """
    Репозиторій для збереження GraphDTO з ізоляцією Domain Layer.

    BREAKING CHANGE: Тепер використовує GraphDTO замість Graph для повної ізоляції Domain Layer.

    Логіка іменування винесена в GraphNamingStrategy (Strategy Pattern).
    Це покращує:
    - Single Responsibility - кожен клас має одну відповідальність
    - Тестованість - можна тестувати окремо збереження та іменування
    - Гнучкість - можна змінити схему іменування без зміни репозиторію

    Дозволяє зберігати множинні графи з унікальними іменами
    та завантажувати їх пізніше для порівняння або інкрементального сканування.

    Структура збереження:
    storage_dir/
        graphs/
            scan_name_2025-01-15.json
            scan_name_2025-01-20.json
        metadata/
            scan_name.meta.json

    Examples:
        >>> from graph_crawler.application.dto.mappers import GraphMapper
        >>> 
        >>> repo = GraphRepository('/data/graphs')
        >>> # Серіалізація Domain → DTO → Repository
        >>> graph_dto = GraphMapper.to_dto(graph)
        >>> repo.save_graph(graph_dto, name='mysite_v1')
        >>> 
        >>> # Десеріалізація Repository → DTO → Domain
        >>> graph_dto = repo.load_graph('mysite_v1')
        >>> context = {'plugin_manager': pm, 'tree_parser': parser}
        >>> graph = GraphMapper.to_domain(graph_dto, context=context)
        >>> 
        >>> graphs = repo.list_graphs()
    """

    def __init__(
        self,
        storage_dir: str = "./graphs_storage",
        naming_strategy: Optional[GraphNamingStrategy] = None,
    ):
        """
        Ініціалізує репозиторій графів.

        Args:
            storage_dir: Директорія для збереження графів
            naming_strategy: Стратегія іменування (опціонально, за замовчуванням timestamp)
        """
        self.storage_dir = Path(storage_dir)
        self.graphs_dir = self.storage_dir / "graphs"
        self.metadata_dir = self.storage_dir / "metadata"

        # Dependency Injection для naming strategy
        self.naming_strategy = naming_strategy or GraphNamingStrategy("timestamp")

        # Створюємо директорії
        self.graphs_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"GraphRepository initialized at: {self.storage_dir}")

    def save_graph(
        self,
        graph_dto: GraphDTO,
        name: str,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Зберігає GraphDTO з унікальним ім'ям.

        BREAKING CHANGE: Тепер приймає GraphDTO замість Graph.

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

            graph_file = self.graphs_dir / self.naming_strategy.format_graph_filename(
                full_name
            )
            # Використовуємо default=str для datetime та інших non-serializable типів
            with open(graph_file, "w", encoding="utf-8") as f:
                json.dump(graph_data, f, ensure_ascii=False, indent=2, default=str)

            # Зберігаємо метадані (через model_dump)
            meta_file = (
                self.metadata_dir
                / self.naming_strategy.format_metadata_filename(full_name)
            )
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(graph_meta.model_dump(), f, ensure_ascii=False, indent=2)

            logger.info(f"Graph saved: {full_name} ({graph_stats.total_nodes} nodes)")
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

        BREAKING CHANGE: Тепер повертає GraphDTO замість Graph.

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
            graph_file = self.graphs_dir / self.naming_strategy.format_graph_filename(
                name
            )

            if graph_file.exists():
                # Це повне ім'я, завантажуємо напряму
                full_name = name
            else:
                # Це базове ім'я, шукаємо версії через naming_strategy
                all_graph_files = list(self.graphs_dir.glob("*.json"))
                versions = self.naming_strategy.find_versions(name, all_graph_files)

                if not versions:
                    logger.warning(f"No graphs found with name: {name}")
                    return None

                # Беремо останню версію
                full_name = versions[0] if latest else versions[-1]
                graph_file = (
                    self.graphs_dir
                    / self.naming_strategy.format_graph_filename(full_name)
                )

            # Читаємо граф
            with open(graph_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Десеріалізуємо GraphDTO через Pydantic model_validate()
            graph_dto = GraphDTO.model_validate(data)

            logger.info(f"Graph loaded: {full_name} ({len(graph_dto.nodes)} nodes)")
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
                    logger.warning(f"Failed to read metadata {meta_file}: {e}")

            # Сортуємо за датою створення (новіші першими)
            graphs.sort(key=lambda x: x.created_at, reverse=True)
            return graphs

        except Exception as e:
            logger.error(f"Failed to list graphs: {e}")
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
                logger.info(f"Graph deleted: {name}")
            else:
                logger.warning(f"Graph not found: {name}")

            return deleted

        except Exception as e:
            logger.error(f"Failed to delete graph '{name}': {e}")
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
            logger.error(f"Failed to read metadata for '{name}': {e}")
            return None
