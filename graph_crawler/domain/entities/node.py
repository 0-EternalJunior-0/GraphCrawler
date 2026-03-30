"""Node - вузол графу (веб-сторінка). Pydantic модель з підтримкою Python 3.14 free-threading."""

import asyncio
import logging
import os
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, Tuple

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

from graph_crawler.domain.interfaces.node_interfaces import IPluginManager
from graph_crawler.domain.value_objects.lifecycle import NodeLifecycle, NodeLifecycleError
from graph_crawler.domain.value_objects.models import ContentType

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _detect_free_threading() -> bool:
    """True якщо GIL disabled (Python 3.14 free-threading)."""
    if not hasattr(sys, "_is_gil_enabled"):
        return False
    return not sys._is_gil_enabled()


_is_free_threaded = _detect_free_threading()

if _is_free_threaded:
    _max_html_workers = (os.cpu_count() or 4) * 2
    logger.info("Python 3.14 Free-threading! HTML parser: %d workers", _max_html_workers)
else:
    _max_html_workers = os.cpu_count() or 4
    logger.info("GIL enabled. HTML parser: %d threads", _max_html_workers)

_parser_thread_lock = threading.Lock()
_parser_thread_parsers: Dict[int, Any] = {}


def _init_parser_thread():
    """Ініціалізує parser для thread. Thread-local для уникнення contention."""
    global _parser_thread_parsers
    thread_id = threading.get_ident()

    with _parser_thread_lock:
        if thread_id in _parser_thread_parsers:
            return

        try:
            from lxml import etree

            parser = etree.HTMLParser(
                remove_blank_text=True,
                remove_comments=True,
                encoding="utf-8",
                huge_tree=False,
            )
            _parser_thread_parsers[thread_id] = parser
            logger.debug("Parser initialized for thread %d", thread_id)
        except ImportError:
            logger.warning("lxml not available, falling back to html.parser")


import atexit

_html_executor_semaphore: Optional[asyncio.Semaphore] = None
_html_executor_semaphore_loop_id: Optional[int] = None
_semaphore_lock = threading.Lock()


def _get_html_executor_semaphore() -> asyncio.Semaphore:
    """Lazy init semaphore для обмеження черги HTML парсера."""
    global _html_executor_semaphore, _html_executor_semaphore_loop_id

    try:
        current_loop = asyncio.get_running_loop()
        current_loop_id = id(current_loop)
    except RuntimeError:
        current_loop_id = None

    need_new = _html_executor_semaphore is None or (
        current_loop_id is not None and _html_executor_semaphore_loop_id != current_loop_id
    )

    if need_new:
        with _semaphore_lock:
            if _html_executor_semaphore is None or (
                current_loop_id is not None and _html_executor_semaphore_loop_id != current_loop_id
            ):
                _html_executor_semaphore = asyncio.Semaphore(_max_html_workers * 2)
                _html_executor_semaphore_loop_id = current_loop_id

    return _html_executor_semaphore


_html_executor = ThreadPoolExecutor(
    max_workers=_max_html_workers,
    thread_name_prefix="html_parser_",
    initializer=_init_parser_thread,
)

atexit.register(_html_executor.shutdown, wait=True)
logger.info("HTML executor: workers=%d, free_threaded=%s", _max_html_workers, _is_free_threaded)


class ITreeAdapter(Protocol):
    """Protocol для Tree Adapter."""

    def parse(self, html: str) -> Any: ...


class IContentHashStrategy(Protocol):
    """Protocol для content hash. Повертає SHA256 hex digest (64 символи)."""

    def compute_hash(self, node: "Node") -> str: ...


class ISimHashStrategyLocal(Protocol):
    """Protocol для SimHash. Повертає 64-бітний hex (16 символів)."""

    def compute_simhash(self, node: "Node") -> str: ...


class Node(BaseModel):
    """
    Вузол графу (веб-сторінка). Pydantic модель.

    Життєвий цикл:
    1. URL_STAGE: Створення - доступний url, depth, should_scan, can_create_edges
    2. HTML_STAGE: Після process_html() - metadata, user_data, extracted_links

    HTML не зберігається в пам'яті - обробляється і видаляється.
    """

    url: str
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    depth: int = Field(default=0, ge=0)
    should_scan: bool = True
    can_create_edges: bool = True
    created_at: datetime = Field(default_factory=datetime.now)

    metadata: Dict[str, Any] = Field(default_factory=dict)
    user_data: Dict[str, Any] = Field(default_factory=dict)
    scanned: bool = False
    response_status: Optional[int] = None

    _response_final_url: Optional[str] = PrivateAttr(default=None)
    _response_original_url: Optional[str] = PrivateAttr(default=None)
    _response_is_redirect: bool = PrivateAttr(default=False)

    content_type: ContentType = ContentType.UNKNOWN
    content_hash: Optional[str] = None
    simhash: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=1, le=10)
    lifecycle_stage: NodeLifecycle = NodeLifecycle.URL_STAGE

    plugin_manager: Optional[Any] = Field(default=None, exclude=True)
    tree_parser: Optional[Any] = Field(default=None, exclude=True)
    hash_strategy: Optional[Any] = Field(default=None, exclude=True)
    simhash_strategy: Optional[Any] = Field(default=None, exclude=True)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        use_enum_values=False,
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        from urllib.parse import urlparse

        from graph_crawler.shared.exceptions import InvalidURLError

        if not v:
            raise InvalidURLError("URL cannot be empty")
        if not v.startswith(("http://", "https://")):
            raise InvalidURLError(f"URL must start with http:// or https://, got: {v}")
        parsed = urlparse(v)
        if not parsed.netloc:
            raise InvalidURLError(f"URL must have a valid domain: {v}")
        return v

    def model_post_init(self, __context: Any) -> None:
        self._trigger_node_created_hook()

    def _trigger_node_created_hook(self):
        """Викликає хук ON_NODE_CREATED. URL_STAGE - доступний тільки URL."""
        if not self.plugin_manager:
            return

        from graph_crawler.extensions.plugins.node import NodePluginContext, NodePluginType

        context = NodePluginContext(
            node=self,
            url=self.url,
            depth=self.depth,
            should_scan=self.should_scan,
            can_create_edges=self.can_create_edges,
        )
        context = self.plugin_manager.execute_sync(NodePluginType.ON_NODE_CREATED, context)
        self.should_scan = context.should_scan
        self.can_create_edges = context.can_create_edges
        self.user_data.update(context.user_data)

    async def process_html(
        self,
        html: str,
        crawl_context: Optional[Any] = None,
        control_channel: Optional[Any] = None,
    ) -> List[str]:
        """
        Обробляє HTML через плагінну систему. HTML_STAGE.

        Returns: Список знайдених URL
        """
        if self.lifecycle_stage == NodeLifecycle.HTML_STAGE:
            logger.warning("Node already processed: %s", self.url)
            return []

        self.lifecycle_stage = NodeLifecycle.HTML_STAGE
        parser, html_tree = await self._parse_html_async(html)
        context = await self._execute_plugins(
            html, html_tree, parser, crawl_context, control_channel
        )
        self.user_data.update(context.user_data)
        self._compute_content_hash()
        self._cleanup_memory(html, html_tree, context)

        logger.debug("Processed %s: %d links", self.url, len(context.extracted_links))
        return context.extracted_links

    def _parse_html_sync(self, html: str) -> Tuple[Any, Any]:
        """Синхронний парсинг HTML. Новий parser instance для кожного виклику."""
        if self.tree_parser is None:
            from graph_crawler.domain.interfaces.parser import create_parser

            parser = create_parser()
            if parser is None:
                raise RuntimeError(
                    "Parser factory not configured. Call set_parser_factory() during bootstrap."
                )
        else:
            parser = self.tree_parser
        return parser, parser.parse(html)

    async def _parse_html_async(self, html: str) -> Tuple[Any, Any]:
        """Async парсинг через ThreadPoolExecutor."""
        semaphore = _get_html_executor_semaphore()
        async with semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(_html_executor, self._parse_html_sync, html)

    async def _execute_plugins(
        self,
        html: str,
        html_tree: Any,
        parser: Any,
        crawl_context: Optional[Any] = None,
        control_channel: Optional[Any] = None,
    ) -> Any:
        """Виконує плагіни для обробки HTML."""
        import copy as copy_module

        from graph_crawler.extensions.plugins.node import NodePluginContext, NodePluginType

        context = NodePluginContext(
            node=self,
            url=self.url,
            depth=self.depth,
            should_scan=self.should_scan,
            can_create_edges=self.can_create_edges,
            html=html,
            html_tree=html_tree,
            parser=parser,
            metadata=copy_module.deepcopy(self.metadata) if self.metadata else {},
            user_data=copy_module.deepcopy(self.user_data) if self.user_data else {},
            crawl_context=crawl_context,
            control_channel=control_channel,
        )

        if self.plugin_manager:
            context = await self.plugin_manager.execute(NodePluginType.ON_BEFORE_SCAN, context)
            context = await self.plugin_manager.execute(NodePluginType.ON_HTML_PARSED, context)
            self._update_from_context(context)
            context = await self.plugin_manager.execute(NodePluginType.ON_AFTER_SCAN, context)

        return context

    def _update_from_context(self, context: Any):
        """Оновлює ноду з контексту плагінів. Deep copy для уникнення shared references."""
        import copy as copy_module

        if context.metadata:
            self.metadata = copy_module.deepcopy(context.metadata)
        else:
            self.metadata = {}
        if context.user_data:
            for key, value in context.user_data.items():
                if isinstance(value, (dict, list)):
                    self.user_data[key] = copy_module.deepcopy(value)
                else:
                    self.user_data[key] = value

    def _compute_content_hash(self):
        """Обчислює content_hash та SimHash."""
        try:
            self.content_hash = self.get_content_hash()
        except Exception as e:
            logger.warning("Failed to compute content_hash for %s: %s", self.url, e)
            self.content_hash = None

        try:
            self.simhash = self.get_simhash()
        except Exception as e:
            logger.warning("Failed to compute simhash for %s: %s", self.url, e)
            self.simhash = None

    def _cleanup_memory(self, html: str, html_tree: Any, context: Any):
        """Видаляє HTML з пам'яті."""
        del html
        del html_tree
        context.html = None
        context.html_tree = None

    def get_content_hash(self) -> str:
        """
        SHA256 hash контенту. Викликати тільки після process_html().
        Можна задати кастомну стратегію через hash_strategy.
        """
        import hashlib
        import re

        if self.lifecycle_stage != NodeLifecycle.HTML_STAGE:
            raise NodeLifecycleError(
                f"Cannot compute content_hash at {self.lifecycle_stage.value}. Call process_html() first."
            )

        if self.hash_strategy:
            hash_value = self.hash_strategy.compute_hash(self)
            if not isinstance(hash_value, str):
                raise ValueError(
                    f"Hash strategy must return string, got {type(hash_value).__name__}"
                )
            from graph_crawler.shared.constants import SHA256_HASH_PATTERN

            if not re.match(SHA256_HASH_PATTERN, hash_value):
                raise ValueError(f"Invalid SHA256 hash from strategy: {hash_value[:20]}...")
            if not hasattr(self, "_hash_determinism_validated"):
                self._validate_hash_strategy_deterministic(hash_value)
                self._hash_determinism_validated = True
            return hash_value

        from graph_crawler.shared.constants import DEFAULT_HASH_ENCODING

        text = self.user_data.get("text_content", "")
        return hashlib.sha256(text.encode(DEFAULT_HASH_ENCODING)).hexdigest()

    def _validate_hash_strategy_deterministic(self, first_hash: str) -> None:
        """Перевіряє детермінованість hash_strategy."""
        if not self.hash_strategy:
            return
        second_hash = self.hash_strategy.compute_hash(self)
        if first_hash != second_hash:
            raise ValueError(
                f"Hash strategy NOT DETERMINISTIC! 1st: {first_hash[:32]}... 2nd: {second_hash[:32]}..."
            )

    def mark_as_scanned(self):
        self.scanned = True

    def get_simhash(self) -> str:
        """
        SimHash для near-duplicate detection. Викликати тільки після process_html().
        Схожі документи мають схожий SimHash (мала Hamming distance).
        """
        import re

        if self.lifecycle_stage != NodeLifecycle.HTML_STAGE:
            raise NodeLifecycleError(
                f"Cannot compute simhash at {self.lifecycle_stage.value}. Call process_html() first."
            )

        if self.simhash_strategy:
            simhash_value = self.simhash_strategy.compute_simhash(self)
            if not isinstance(simhash_value, str):
                raise ValueError("SimHash strategy must return string")
            from graph_crawler.shared.constants import SIMHASH_PATTERN

            if not re.match(SIMHASH_PATTERN, simhash_value):
                raise ValueError(f"Invalid SimHash: {simhash_value}")
            if not hasattr(self, "_simhash_determinism_validated"):
                self._validate_simhash_strategy_deterministic(simhash_value)
                self._simhash_determinism_validated = True
            return simhash_value

        from graph_crawler.shared.constants import DEFAULT_SIMHASH_NGRAM_SIZE, SIMHASH_BITS

        text = self.user_data.get("text_content", "")
        return self._compute_simhash_default(text, DEFAULT_SIMHASH_NGRAM_SIZE, SIMHASH_BITS)

    def _compute_simhash_default(self, text: str, ngram_size: int = 3, bits: int = 64) -> str:
        """SimHash через n-grams. Numba JIT якщо доступний."""
        if not text:
            return "0" * (bits // 4)

        text = text.lower().strip()
        tokens = []
        words = text.split()
        for i in range(max(1, len(words) - ngram_size + 1)):
            tokens.append(" ".join(words[i : i + ngram_size]))
        if not tokens:
            tokens = words if words else [text]

        try:
            from graph_crawler.optimizations.simhash_numba import (
                compute_simhash_fast,
                is_numba_available,
            )

            if is_numba_available():
                return compute_simhash_fast(tokens, bits)
        except ImportError:
            pass

        import hashlib
        from array import array

        v = array("i", [0] * bits)
        mask = (1 << bits) - 1

        for token in tokens:
            token_hash = hashlib.md5(token.encode("utf-8"), usedforsecurity=False).hexdigest()
            hash_int = int(token_hash[: bits // 4], 16) & mask
            temp = hash_int
            for i in range(bits):
                v[i] += ((temp & 1) << 1) - 1
                temp >>= 1

        simhash = 0
        for i in range(bits):
            if v[i] >= 0:
                simhash |= 1 << i

        return format(simhash, f"0{bits // 4}x")

    def _validate_simhash_strategy_deterministic(self, first_simhash: str) -> None:
        if not self.simhash_strategy:
            return
        second_simhash = self.simhash_strategy.compute_simhash(self)
        if first_simhash != second_simhash:
            raise ValueError("SimHash strategy NOT DETERMINISTIC!")

    @staticmethod
    def hamming_distance(simhash1: str, simhash2: str) -> int:
        """Hamming distance між SimHash. 0-3: ідентичні, 4-10: схожі, >20: різні."""
        xor_result = int(simhash1, 16) ^ int(simhash2, 16)
        return bin(xor_result).count("1")

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        data = super().model_dump(**kwargs)
        if "lifecycle_stage" in data and isinstance(data["lifecycle_stage"], NodeLifecycle):
            data["lifecycle_stage"] = data["lifecycle_stage"].value
        if "content_type" in data and isinstance(data["content_type"], ContentType):
            data["content_type"] = data["content_type"].value
        if "created_at" in data and isinstance(data["created_at"], datetime):
            data["created_at"] = data["created_at"].isoformat()
        return data

    @classmethod
    def model_validate(cls, obj: Any, context: Optional[Dict] = None, **kwargs) -> "Node":
        if isinstance(obj, dict):
            if "lifecycle_stage" in obj and isinstance(obj["lifecycle_stage"], str):
                obj["lifecycle_stage"] = NodeLifecycle(obj["lifecycle_stage"])
            if "content_type" in obj and isinstance(obj["content_type"], str):
                obj["content_type"] = ContentType(obj["content_type"])
            if "created_at" in obj and isinstance(obj["created_at"], str):
                obj["created_at"] = datetime.fromisoformat(obj["created_at"])

        node = super().model_validate(obj, **kwargs)
        if context:
            if "plugin_manager" in context:
                node.plugin_manager = context["plugin_manager"]
            if "tree_parser" in context:
                node.tree_parser = context["tree_parser"]
        return node

    def restore_dependencies(
        self,
        plugin_manager: Optional[IPluginManager] = None,
        tree_parser: Optional[ITreeAdapter] = None,
        hash_strategy: Optional[IContentHashStrategy] = None,
        simhash_strategy: Optional[ISimHashStrategyLocal] = None,
    ):
        """Відновлює залежності після десеріалізації."""
        if plugin_manager is not None:
            self.plugin_manager = plugin_manager
        if tree_parser is not None:
            self.tree_parser = tree_parser
        if hash_strategy is not None:
            self.hash_strategy = hash_strategy
        if simhash_strategy is not None:
            self.simhash_strategy = simhash_strategy

    def _get_metadata_field(self, field: str, default: Any = None) -> Any:
        return self.metadata.get(field, default) if self.metadata else default

    def get_title(self) -> Optional[str]:
        return self._get_metadata_field("title")

    def get_description(self) -> Optional[str]:
        return self._get_metadata_field("description")

    def get_h1(self) -> Optional[str]:
        return self._get_metadata_field("h1")

    def get_keywords(self) -> Optional[str]:
        return self._get_metadata_field("keywords")

    def get_canonical_url(self) -> Optional[str]:
        return self._get_metadata_field("canonical_url")

    def get_language(self) -> Optional[str]:
        return self._get_metadata_field("language")

    def get_meta_value(self, key: str, default: Any = None) -> Any:
        return self._get_metadata_field(key, default)

    def __repr__(self):
        return (
            f"Node(url={self.url}, lifecycle={self.lifecycle_stage.value}, "
            f"scanned={self.scanned}, depth={self.depth})"
        )
