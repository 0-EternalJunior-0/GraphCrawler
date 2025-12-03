"""
CheckpointManager - система збереження та відновлення стану краулінгу.

Дозволяє зберігати стан краулінгу кожні N сторінок та відновлювати його після збою.

Features:
- Всі file I/O операції async через aiofiles
- save_checkpoint() → async save_checkpoint()
- load_checkpoint() → async load_checkpoint()
- Sync методи залишені для зворотньої сумісності з DEPRECATED міткою
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import aiofiles
    import aiofiles.os

    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False

from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Async-First менеджер для збереження та відновлення стану краулінгу .

    Основні функції:
    - Async збереження стану графу та черги URL кожні N сторінок
    - Async відновлення стану після збою
    - Автоматичне видалення старих checkpoint'ів
    - Зберігання в JSON файли з timestamp Використовує aiofiles для неблокуючого file I/O.

    Attributes:
        checkpoint_dir: Директорія для збереження checkpoint'ів
        checkpoint_interval: Інтервал між checkpoint'ами (кількість сторінок)
        max_checkpoints: Максимальна кількість checkpoint'ів (старі видаляються)
        pages_since_last_checkpoint: Лічильник сторінок з останнього checkpoint
    """

    def __init__(
        self,
        checkpoint_dir: str = "./checkpoints",
        checkpoint_interval: int = 100,
        max_checkpoints: int = 5,
    ):
        """
        Ініціалізує CheckpointManager.

        Args:
            checkpoint_dir: Директорія для збереження checkpoint'ів
            checkpoint_interval: Через скільки сторінок робити checkpoint
            max_checkpoints: Скільки останніх checkpoint'ів зберігати
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_interval = checkpoint_interval
        self.max_checkpoints = max_checkpoints
        self.pages_since_last_checkpoint = 0

        # Створюємо директорію якщо не існує
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        if not AIOFILES_AVAILABLE:
            logger.warning("aiofiles not installed, falling back to sync I/O")

        logger.info(
            f"CheckpointManager (async) initialized: dir={checkpoint_dir}, "
            f"interval={checkpoint_interval}, max={max_checkpoints}"
        )

    def should_checkpoint(self) -> bool:
        """
        Перевіряє чи треба робити checkpoint.

        Returns:
            True якщо досягнуто інтервалу для checkpoint
        """
        return self.pages_since_last_checkpoint >= self.checkpoint_interval

    def increment_page_count(self) -> None:
        """
        Збільшує лічильник оброблених сторінок.
        """
        self.pages_since_last_checkpoint += 1

    async def save_checkpoint(
        self,
        graph: Graph,
        queue_urls: List[str],
        seen_urls: set,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Async зберігає checkpoint з поточним станом краулінгу .

        Args:
            graph: Поточний граф
            queue_urls: Список URL що залишились в черзі
            seen_urls: Множина вже побачених URL
            metadata: Додаткові метадані (опціонально)

        Returns:
            Шлях до збереженого checkpoint файлу
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        checkpoint_file = self.checkpoint_dir / f"checkpoint_{timestamp}.json"

        # Формуємо дані для збереження
        checkpoint_data = {
            "timestamp": timestamp,
            "graph": graph.to_dict(),
            "queue_urls": queue_urls,
            "seen_urls": list(seen_urls),
            "metadata": metadata or {},
            "stats": graph.get_stats(),
        }

        # Серіалізуємо в JSON
        json_content = json.dumps(checkpoint_data, indent=2, ensure_ascii=False)

        try:
            if AIOFILES_AVAILABLE:
                async with aiofiles.open(checkpoint_file, "w", encoding="utf-8") as f:
                    await f.write(json_content)
            else:
                # Fallback до sync якщо aiofiles не встановлено
                with open(checkpoint_file, "w", encoding="utf-8") as f:
                    f.write(json_content)

            logger.info(
                f"Checkpoint saved: {checkpoint_file.name} "
                f"(nodes={len(graph.nodes)}, queue={len(queue_urls)})"
            )

            # Скидаємо лічильник
            self.pages_since_last_checkpoint = 0

            # Видаляємо старі checkpoint'и
            await self._cleanup_old_checkpoints()

            return str(checkpoint_file)

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}", exc_info=True)
            raise

    async def load_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        Async завантажує останній checkpoint .

        Returns:
            Словник з даними checkpoint або None якщо checkpoint'ів немає
        """
        checkpoints = self._get_checkpoint_files()

        if not checkpoints:
            logger.info("No checkpoints found")
            return None

        # Беремо останній checkpoint (файли відсортовані за датою)
        latest_checkpoint = checkpoints[-1]

        return await self.load_checkpoint(str(latest_checkpoint))

    async def load_checkpoint(self, checkpoint_path: str) -> Optional[Dict[str, Any]]:
        """
        Async завантажує конкретний checkpoint .

        Args:
            checkpoint_path: Шлях до checkpoint файлу

        Returns:
            Словник з даними checkpoint або None при помилці
        """
        try:
            if AIOFILES_AVAILABLE:
                async with aiofiles.open(checkpoint_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                checkpoint_data = json.loads(content)
            else:
                # Fallback до sync якщо aiofiles не встановлено
                with open(checkpoint_path, "r", encoding="utf-8") as f:
                    checkpoint_data = json.load(f)

            logger.info(
                f"Checkpoint loaded: {Path(checkpoint_path).name} "
                f"(nodes={checkpoint_data.get('stats', {}).get('total_nodes', 0)})"
            )

            return checkpoint_data

        except Exception as e:
            logger.error(
                f"Failed to load checkpoint {checkpoint_path}: {e}", exc_info=True
            )
            return None

    def restore_from_checkpoint(
        self, checkpoint_data: Dict[str, Any]
    ) -> tuple[Graph, List[str], set]:
        """
        Відновлює граф та чергу з checkpoint даних.

        Sync операція (in-memory), не потребує async.

        Args:
            checkpoint_data: Дані checkpoint

        Returns:
            Tuple з (graph, queue_urls, seen_urls)
        """
        # Відновлюємо граф
        graph = Graph()

        # Відновлюємо nodes
        for node_data in checkpoint_data["graph"]["nodes"]:
            try:
                node = Node.model_validate(node_data)
                graph.add_node(node)
            except Exception as e:
                logger.warning(f"Failed to restore node {node_data.get('url')}: {e}")

        # Відновлюємо edges
        for edge_data in checkpoint_data["graph"]["edges"]:
            try:
                edge = Edge.model_validate(edge_data)
                graph.add_edge(edge)
            except Exception as e:
                logger.warning(f"Failed to restore edge: {e}")

        # Відновлюємо чергу та seen URLs
        queue_urls = checkpoint_data["queue_urls"]
        seen_urls = set(checkpoint_data["seen_urls"])

        logger.info(
            f"Graph restored: {len(graph.nodes)} nodes, "
            f"{len(graph.edges)} edges, {len(queue_urls)} URLs in queue"
        )

        return graph, queue_urls, seen_urls

    def _get_checkpoint_files(self) -> List[Path]:
        """
        Отримує список файлів checkpoint'ів, відсортований за датою.

        Returns:
            Список Path об'єктів
        """
        checkpoints = list(self.checkpoint_dir.glob("checkpoint_*.json"))
        # Сортуємо за іменем (timestamp в імені)
        checkpoints.sort()
        return checkpoints

    async def _cleanup_old_checkpoints(self) -> None:
        """
        Async видаляє старі checkpoint'и, залишаючи тільки останні max_checkpoints .
        """
        checkpoints = self._get_checkpoint_files()

        if len(checkpoints) <= self.max_checkpoints:
            return

        # Видаляємо старі checkpoint'и
        checkpoints_to_delete = checkpoints[: -self.max_checkpoints]

        for checkpoint_file in checkpoints_to_delete:
            try:
                if AIOFILES_AVAILABLE:
                    await aiofiles.os.remove(checkpoint_file)
                else:
                    checkpoint_file.unlink()
                logger.debug(f"Deleted old checkpoint: {checkpoint_file.name}")
            except Exception as e:
                logger.warning(f"Failed to delete checkpoint {checkpoint_file}: {e}")

        if checkpoints_to_delete:
            logger.info(f"Cleaned up {len(checkpoints_to_delete)} old checkpoint(s)")

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """
        Повертає список всіх доступних checkpoint'ів з їх інформацією.

        Sync операція (тільки читання метаданих файлів).

        Returns:
            Список словників з інформацією про checkpoint'и
        """
        checkpoints = self._get_checkpoint_files()
        result = []

        for checkpoint_file in checkpoints:
            try:
                with open(checkpoint_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                result.append(
                    {
                        "file": str(checkpoint_file),
                        "filename": checkpoint_file.name,
                        "timestamp": data.get("timestamp"),
                        "stats": data.get("stats", {}),
                        "size_bytes": checkpoint_file.stat().st_size,
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to read checkpoint {checkpoint_file}: {e}")

        return result

    async def delete_all_checkpoints(self) -> int:
        """
        Async видаляє всі checkpoint'и .

        Returns:
            Кількість видалених checkpoint'ів
        """
        checkpoints = self._get_checkpoint_files()
        deleted_count = 0

        for checkpoint_file in checkpoints:
            try:
                if AIOFILES_AVAILABLE:
                    await aiofiles.os.remove(checkpoint_file)
                else:
                    checkpoint_file.unlink()
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete checkpoint {checkpoint_file}: {e}")

        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} checkpoint(s)")

        return deleted_count

    # ==================== DEPRECATED: Sync методи для зворотньої сумісності ====================

    def save_checkpoint_sync(
        self,
        graph: Graph,
        queue_urls: List[str],
        seen_urls: set,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        DEPRECATED: Використовуйте async save_checkpoint() замість цього.

        Sync зберігає checkpoint (для зворотньої сумісності).
        """
        import warnings

        warnings.warn(
            "save_checkpoint_sync() is deprecated, use async save_checkpoint() instead",
            DeprecationWarning,
            stacklevel=2,
        )

        import asyncio

        return asyncio.run(self.save_checkpoint(graph, queue_urls, seen_urls, metadata))

    def load_checkpoint_sync(self, checkpoint_path: str) -> Optional[Dict[str, Any]]:
        """
        DEPRECATED: Використовуйте async load_checkpoint() замість цього.

        Sync завантажує checkpoint (для зворотньої сумісності).
        """
        import warnings

        warnings.warn(
            "load_checkpoint_sync() is deprecated, use async load_checkpoint() instead",
            DeprecationWarning,
            stacklevel=2,
        )

        import asyncio

        return asyncio.run(self.load_checkpoint(checkpoint_path))
