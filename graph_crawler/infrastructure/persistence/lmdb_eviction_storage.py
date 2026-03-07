"""
LMDBEvictionStorage - високопродуктивний storage для eviction operations.

LMDB (Lightning Memory-Mapped Database) переваги над SQLite:
- Memory-mapped I/O (zero-copy reads) - 10x швидше для read operations
- Batch transactions для ефективних writes
- ACID transactions з мінімальним overhead
- Copy-on-write для ефективних оновлень

Реалізовано в рамках Eviction System v3.0 Migration.
"""

import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Перевіряємо наявність lmdb
try:
    import lmdb
    LMDB_AVAILABLE = True
except ImportError:
    LMDB_AVAILABLE = False
    logger.warning(
        "lmdb not installed. Install with: pip install lmdb\n"
        "Falling back to SQLiteEvictionStorage."
    )


class LMDBEvictionStorage:
    """
    LMDB-based eviction storage для high-performance eviction.
    
    Переваги над SQLite:
    - Memory-mapped I/O (zero-copy reads) - ~10x швидше
    - Мінімальний overhead (no SQL parsing)
    - ACID transactions
    - Copy-on-write
    
    Використовується Graph у low_memory_mode для:
    - Збереження scanned нод при eviction
    - Завантаження нод по URL (lazy loading)
    - Збереження edges пов'язаних з evicted нодами
    
    LIGHTWEIGHT MODE:
    Якщо lightweight_mode=True, НЕ зберігаються metadata та user_data.
    Це економить ~30-40% RAM при великих краулінгах.
    """
    
    def __init__(
        self, 
        storage_path: str,
        map_size: int = 1 * 1024 * 1024 * 1024,  # 1GB default
        lightweight_mode: bool = False,
    ):
        """
        Ініціалізує LMDB eviction storage.
        
        Args:
            storage_path: Директорія для LMDB data files
            map_size: Максимальний розмір БД (default: 1GB)
            lightweight_mode: Якщо True - НЕ зберігати metadata/user_data
        
        Raises:
            ImportError: Якщо lmdb не встановлено
        """
        if not LMDB_AVAILABLE:
            raise ImportError(
                "lmdb not installed. Install with: pip install lmdb"
            )
        
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.lightweight_mode = lightweight_mode
        self.map_size = map_size
        
        # Створюємо LMDB environment
        self.env = lmdb.open(
            str(self.storage_path),
            map_size=map_size,
            max_dbs=2,  # nodes + edges
            writemap=True,  # Faster writes
            metasync=False,  # Async meta sync
            sync=False,  # Async data sync (safe with writemap)
        )
        
        # Окремі databases для nodes та edges
        self.nodes_db = self.env.open_db(b'nodes')
        self.edges_db = self.env.open_db(b'edges')
        
        logger.info(
            f"LMDBEvictionStorage initialized: {self.storage_path}, "
            f"map_size={map_size // (1024*1024)}MB, lightweight={lightweight_mode}"
        )
    
    def save_nodes_sync(self, nodes: List[Any]) -> int:
        """
        Batch INSERT нод з мінімальним overhead.
        
        Args:
            nodes: Список Node об'єктів для збереження
            
        Returns:
            Кількість збережених нод
        """
        if not nodes:
            return 0
        
        with self.env.begin(write=True, db=self.nodes_db) as txn:
            for node in nodes:
                key = node.url.encode('utf-8')
                
                if self.lightweight_mode:
                    # Мінімальні дані - тільки для відновлення структури
                    value = pickle.dumps({
                        'url': node.url,
                        'node_id': node.node_id,
                        'depth': node.depth,
                        'scanned': node.scanned,
                        'response_status': getattr(node, 'response_status', None),
                    })
                else:
                    # Повні дані включаючи metadata
                    value = pickle.dumps({
                        'url': node.url,
                        'node_id': node.node_id,
                        'depth': node.depth,
                        'scanned': node.scanned,
                        'response_status': getattr(node, 'response_status', None),
                        'content_hash': getattr(node, 'content_hash', None),
                        'simhash': getattr(node, 'simhash', None),
                        'priority': getattr(node, 'priority', 0),
                        'metadata': node.metadata if node.metadata else {},
                        'user_data': node.user_data if node.user_data else {},
                    })
                
                txn.put(key, value)
        
        logger.debug(f"LMDB: Evicted {len(nodes)} nodes to disk")
        return len(nodes)
    
    def save_edges_sync(self, edges: List[Any]) -> int:
        """
        Batch INSERT edges.
        
        Args:
            edges: Список Edge об'єктів для збереження
            
        Returns:
            Кількість збережених edges
        """
        if not edges:
            return 0
        
        with self.env.begin(write=True, db=self.edges_db) as txn:
            for edge in edges:
                key = f"{edge.source_node_id}:{edge.target_node_id}".encode('utf-8')
                
                value = pickle.dumps({
                    'edge_id': getattr(edge, 'edge_id', str(id(edge))),
                    'source_node_id': edge.source_node_id,
                    'target_node_id': edge.target_node_id,
                    'metadata': edge.metadata if not self.lightweight_mode and hasattr(edge, 'metadata') else {},
                })
                
                txn.put(key, value)
        
        logger.debug(f"LMDB: Saved {len(edges)} edges to eviction storage")
        return len(edges)
    
    def load_node_sync(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Zero-copy read ноди через memory mapping.
        
        Args:
            url: URL ноди для завантаження
            
        Returns:
            Dict з даними ноди або None якщо не знайдено
        """
        with self.env.begin(db=self.nodes_db) as txn:
            value = txn.get(url.encode('utf-8'))
            if value:
                data = pickle.loads(value)
                logger.debug(f"LMDB: Loaded evicted node: {url}")
                return data
        return None
    
    def load_node_without_metadata_sync(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Завантажує ноду БЕЗ metadata (для lazy loading).
        
        В lightweight_mode це ідентично load_node_sync().
        
        Args:
            url: URL ноди для завантаження
            
        Returns:
            Dict з базовими даними ноди
        """
        # В LMDB lightweight_mode вже не зберігає metadata
        # Тому просто повертаємо load_node_sync
        data = self.load_node_sync(url)
        if data and not self.lightweight_mode:
            # Видаляємо metadata для lazy loading
            data['metadata'] = None
            data['user_data'] = None
        return data
    
    def load_nodes_batch_sync(self, urls: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Batch завантаження нод по URLs.
        
        Args:
            urls: Список URLs для завантаження
            
        Returns:
            Dict[url, node_data]
        """
        if not urls:
            return {}
        
        result = {}
        with self.env.begin(db=self.nodes_db) as txn:
            for url in urls:
                value = txn.get(url.encode('utf-8'))
                if value:
                    result[url] = pickle.loads(value)
        
        logger.debug(f"LMDB: Batch loaded {len(result)} evicted nodes")
        return result
    
    def url_exists(self, url: str) -> bool:
        """
        Перевіряє чи URL існує в eviction storage.
        
        Args:
            url: URL для перевірки
            
        Returns:
            True якщо URL знайдено
        """
        with self.env.begin(db=self.nodes_db) as txn:
            return txn.get(url.encode('utf-8')) is not None
    
    def urls_exist_batch(self, urls: List[str]) -> Set[str]:
        """
        Batch перевірка URLs.
        
        Args:
            urls: Список URLs для перевірки
            
        Returns:
            Set URLs що знайдені в eviction storage
        """
        if not urls:
            return set()
        
        found = set()
        with self.env.begin(db=self.nodes_db) as txn:
            for url in urls:
                if txn.get(url.encode('utf-8')) is not None:
                    found.add(url)
        
        return found
    
    def get_all_evicted_urls(self) -> Set[str]:
        """
        Повертає всі evicted URLs.
        
        Returns:
            Set URLs що знаходяться в eviction storage
        """
        urls = set()
        with self.env.begin(db=self.nodes_db) as txn:
            cursor = txn.cursor()
            for key, _ in cursor:
                urls.add(key.decode('utf-8'))
        return urls
    
    def get_evicted_count(self) -> int:
        """Повертає кількість evicted нод."""
        with self.env.begin(db=self.nodes_db) as txn:
            return txn.stat()['entries']
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Повертає статистику eviction storage.
        
        Returns:
            Dict зі статистикою
        """
        stat = self.env.stat()
        info = self.env.info()
        
        nodes_count = 0
        edges_count = 0
        
        with self.env.begin(db=self.nodes_db) as txn:
            nodes_count = txn.stat()['entries']
        
        with self.env.begin(db=self.edges_db) as txn:
            edges_count = txn.stat()['entries']
        
        # Розмір директорії
        db_size_bytes = sum(f.stat().st_size for f in self.storage_path.iterdir() if f.is_file())
        db_size_mb = round(db_size_bytes / 1024 / 1024, 2)
        
        return {
            'evicted_nodes': nodes_count,
            'evicted_edges': edges_count,
            'db_size_mb': db_size_mb,
            'db_path': str(self.storage_path),
            'map_size_mb': info['map_size'] // (1024 * 1024),
            'last_pgno': info['last_pgno'],
            'lightweight_mode': self.lightweight_mode,
            'storage_type': 'lmdb',
        }
    
    def clear(self):
        """Очищає eviction storage."""
        with self.env.begin(write=True) as txn:
            txn.drop(self.nodes_db, delete=False)
            txn.drop(self.edges_db, delete=False)
        logger.info("LMDB: Eviction storage cleared")
    
    def close(self):
        """Закриває LMDB environment."""
        if hasattr(self, 'env') and self.env:
            self.env.close()
            logger.debug("LMDB: Eviction storage connection closed")
    
    def cleanup(self, delete_files: bool = True):
        """
        Видаляє eviction storage після завершення краулінгу.
        
        Args:
            delete_files: Якщо True - видаляє файли БД з диску
        """
        self.close()
        
        if delete_files:
            import shutil
            try:
                if self.storage_path.exists():
                    shutil.rmtree(self.storage_path)
                    logger.info(f"LMDB: Eviction storage deleted: {self.storage_path}")
            except Exception as e:
                logger.warning(f"LMDB: Failed to delete eviction storage: {e}")
    
    def __del__(self):
        """Деструктор - закриває з'єднання (але НЕ видаляє файли)."""
        self.close()


def is_lmdb_available() -> bool:
    """Перевіряє чи lmdb бібліотека доступна."""
    return LMDB_AVAILABLE


__all__ = ['LMDBEvictionStorage', 'is_lmdb_available', 'LMDB_AVAILABLE']
