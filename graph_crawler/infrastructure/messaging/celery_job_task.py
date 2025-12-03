"""Celery Task для Kubernetes: crawl_job

Цей task призначений для роботи з RemoteControl.
Воркери зберігають результати в MongoDB, не повертають локально.

Архітектура:
```
RemoteControl.submit()


    Redis Queue



   Celery Worker

   crawl_job_task()


   MongoDB              Результати
   (nodes + edges)


   Redis                Progress
   (progress updates)

```

Features:
- Fire-and-forget: результати в MongoDB, не повертаються
- Real-time progress: оновлення в Redis
- Cancellation support: перевірка gc:cancel:{job_id}
- Pause/Resume: перевірка gc:pause:{job_id}
- Batch processing: 24x швидше через crawl_batch
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from celery import Celery

logger = logging.getLogger(__name__)

# Import Celery app
from graph_crawler.infrastructure.messaging.celery_unified import celery

# Constants
PROGRESS_KEY_PREFIX = "gc:job:"
DEFAULT_BATCH_SIZE = 50
PROGRESS_UPDATE_INTERVAL = 100  # Update progress every N pages


@celery.task(name="graph_crawler.crawl_job", bind=True, max_retries=3)
def crawl_job_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Kubernetes-optimized crawl job task.

    Зберігає результати в MongoDB, оновлює progress в Redis.
    НЕ повертає граф локально - для великих задач це неможливо.

    Args:
        task_data: Dict з параметрами:
            - job_id: Унікальний ID job
            - url: Початковий URL
            - max_pages: Максимум сторінок
            - max_depth: Максимальна глибина
            - nodes_collection: Назва колекції для nodes
            - edges_collection: Назва колекції для edges
            - progress_key: Redis key для progress
            - driver_type: Тип драйвера (async, playwright)
            - timeout: Максимальний час (секунди)
            - url_rules: Правила фільтрації

    Returns:
        Dict з summary (не повний граф!):
            - job_id: ID job
            - status: completed/failed/cancelled/timeout
            - pages_crawled: Кількість сторінок
            - edges_created: Кількість edges
            - elapsed_time: Час виконання
    """
    job_id = task_data.get("job_id")
    logger.info(f" Starting crawl job: {job_id}")

    # Run async crawl
    result = asyncio.run(_async_crawl_job(task_data))

    return result


async def _async_crawl_job(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Async implementation of crawl job.

    Виконує краулінг та зберігає результати безпосередньо в MongoDB.
    Оновлює progress в Redis для моніторингу.
    """
    import redis.asyncio as aioredis
    from motor.motor_asyncio import AsyncIOMotorClient
    from pymongo import UpdateOne

    from graph_crawler.application.use_cases.crawling.spider import GraphSpider
    from graph_crawler.domain.entities.edge import Edge
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.domain.value_objects.configs import CrawlerConfig
    from graph_crawler.infrastructure.persistence.memory_storage import MemoryStorage
    from graph_crawler.shared.utils.url_utils import URLUtils

    # Extract parameters
    job_id = task_data["job_id"]
    url = task_data["url"]
    max_pages = task_data.get("max_pages", 1000)
    max_depth = task_data.get("max_depth", 3)
    nodes_collection = task_data["nodes_collection"]
    edges_collection = task_data["edges_collection"]
    progress_key = task_data.get("progress_key", f"{PROGRESS_KEY_PREFIX}{job_id}")
    timeout = task_data.get("timeout", 3600)  # 1 hour default
    driver_type = task_data.get("driver_type", "async")

    start_time = time.time()
    pages_crawled = 0
    edges_created = 0
    status = "running"
    error_message = None

    # Get connection URLs from environment
    redis_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    mongodb_url = os.environ.get(
        "MONGODB_URL", "mongodb://localhost:27017/graph_crawler"
    )
    database_name = os.environ.get("MONGODB_DATABASE", "graph_crawler")

    # Connect to Redis and MongoDB
    redis_client = None
    mongo_client = None

    try:
        # Redis connection
        redis_client = await aioredis.from_url(redis_url, decode_responses=True)

        # MongoDB connection
        mongo_client = AsyncIOMotorClient(mongodb_url)
        db = mongo_client[database_name]

        # Update status to running
        await redis_client.hset(
            progress_key, mapping={"status": "running", "started_at": start_time}
        )

        await db.jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "running", "started_at": start_time}},
        )

        # Create config
        config = CrawlerConfig(
            url=url,
            max_depth=max_depth,
            max_pages=max_pages,
            **{
                k: v
                for k, v in task_data.items()
                if k
                not in [
                    "job_id",
                    "url",
                    "max_pages",
                    "max_depth",
                    "nodes_collection",
                    "edges_collection",
                    "progress_key",
                    "timeout",
                    "driver_type",
                ]
            },
        )

        # Create driver
        if driver_type == "playwright":
            from graph_crawler.infrastructure.transport.playwright.driver import (
                PlaywrightDriver,
            )

            driver = PlaywrightDriver(config.get_driver_params())
        else:
            from graph_crawler.infrastructure.transport.async_http.driver import (
                AsyncDriver,
            )

            driver = AsyncDriver(config.get_driver_params())

        # Create spider with memory storage (we'll save to MongoDB manually)
        storage = MemoryStorage()
        spider = GraphSpider(config, driver, storage)

        # URL queue
        urls_to_crawl: List[Tuple[str, int]] = [(url, 0)]  # (url, depth)
        crawled_urls = set()
        pending_nodes = []  # Buffer for batch insert
        pending_edges = []  # Buffer for batch insert

        batch_size = task_data.get("batch_size", DEFAULT_BATCH_SIZE)

        logger.info(
            f"Starting crawl: {url}, max_pages={max_pages}, max_depth={max_depth}"
        )

        while urls_to_crawl and pages_crawled < max_pages:
            # Check for cancellation
            if await redis_client.exists(f"gc:cancel:{job_id}"):
                logger.info(f"Job {job_id} cancelled by user")
                status = "cancelled"
                break

            # Check for pause
            while await redis_client.exists(f"gc:pause:{job_id}"):
                await redis_client.hset(progress_key, "status", "paused")
                await asyncio.sleep(5)
                # Re-check cancellation while paused
                if await redis_client.exists(f"gc:cancel:{job_id}"):
                    status = "cancelled"
                    break
            if status == "cancelled":
                break
            await redis_client.hset(progress_key, "status", "running")

            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.warning(f"Job {job_id} timeout after {elapsed:.0f}s")
                status = "timeout"
                break

            # Get batch of URLs to crawl
            batch_urls = []
            while urls_to_crawl and len(batch_urls) < batch_size:
                next_url, depth = urls_to_crawl.pop(0)
                if next_url not in crawled_urls and depth <= max_depth:
                    batch_urls.append((next_url, depth))
                    crawled_urls.add(next_url)

            if not batch_urls:
                break

            # Fetch batch
            try:
                urls_only = [u for u, _ in batch_urls]
                depth_map = {u: d for u, d in batch_urls}

                responses = await driver.fetch_many(urls_only)

                for response in responses:
                    if response.error:
                        logger.debug(
                            f"Fetch error for {response.url}: {response.error}"
                        )
                        continue

                    current_url = response.url
                    depth = depth_map.get(current_url, 0)

                    # Create node
                    node = Node(
                        url=current_url,
                        depth=depth,
                        plugin_manager=spider.node_plugin_manager,
                    )

                    # Process HTML
                    links = []
                    if response.html:
                        try:
                            links = node.process_html(response.html)
                        except Exception as e:
                            logger.debug(
                                f"Error processing HTML for {current_url}: {e}"
                            )

                    node.response_status = response.status_code
                    node.scanned = True

                    # Add to pending batch
                    node_data = node.model_dump()
                    # Convert lifecycle_stage to string for MongoDB
                    if node_data.get("lifecycle_stage"):
                        node_data["lifecycle_stage"] = str(node_data["lifecycle_stage"])
                    pending_nodes.append(node_data)
                    pages_crawled += 1

                    # Process links
                    for link_url in links:
                        if not spider.domain_filter.is_allowed(link_url):
                            continue
                        if not spider.path_filter.is_allowed(link_url):
                            continue

                        normalized_url = URLUtils.normalize_url(link_url)

                        # Create edge
                        edge = Edge(
                            source_node_id=node.node_id, target_node_id=normalized_url
                        )
                        pending_edges.append(edge.model_dump())
                        edges_created += 1

                        # Add to queue if not crawled
                        if normalized_url not in crawled_urls:
                            urls_to_crawl.append((normalized_url, depth + 1))

            except Exception as e:
                logger.error(f"Error processing batch: {e}")
                continue

            # Save to MongoDB in batches
            if len(pending_nodes) >= 100:
                await _save_batch_to_mongodb(
                    db, nodes_collection, edges_collection, pending_nodes, pending_edges
                )
                pending_nodes = []
                pending_edges = []

            # Update progress in Redis
            if pages_crawled % PROGRESS_UPDATE_INTERVAL == 0:
                await redis_client.hset(
                    progress_key,
                    mapping={
                        "pages_crawled": pages_crawled,
                        "edges_created": edges_created,
                        "queue_remaining": len(urls_to_crawl),
                        "last_update": time.time(),
                    },
                )

        # Save remaining pending items
        if pending_nodes or pending_edges:
            await _save_batch_to_mongodb(
                db, nodes_collection, edges_collection, pending_nodes, pending_edges
            )

        # Close driver
        await driver.close()

        # Set final status
        if status == "running":
            status = "completed"

    except Exception as e:
        logger.error(f"Crawl job {job_id} failed: {e}")
        status = "failed"
        error_message = str(e)

    finally:
        elapsed_time = time.time() - start_time

        # Final progress update
        if redis_client:
            try:
                await redis_client.hset(
                    progress_key,
                    mapping={
                        "status": status,
                        "pages_crawled": pages_crawled,
                        "edges_created": edges_created,
                        "queue_remaining": 0,
                        "completed_at": time.time(),
                        "elapsed_time": elapsed_time,
                    },
                )
            except:
                pass

        # Update MongoDB job status
        if mongo_client:
            try:
                update_doc = {
                    "status": status,
                    "pages_crawled": pages_crawled,
                    "edges_created": edges_created,
                    "completed_at": time.time(),
                    "elapsed_time": elapsed_time,
                }
                if error_message:
                    update_doc["error"] = error_message

                await db.jobs.update_one({"job_id": job_id}, {"$set": update_doc})
            except:
                pass
            finally:
                mongo_client.close()

        if redis_client:
            await redis_client.close()

    logger.info(
        f"{'' if status == 'completed' else ''} Job {job_id} {status}: "
        f"{pages_crawled:,} pages, {edges_created:,} edges in {elapsed_time:.0f}s"
    )

    # Return summary (not the full graph!)
    return {
        "job_id": job_id,
        "status": status,
        "pages_crawled": pages_crawled,
        "edges_created": edges_created,
        "elapsed_time": elapsed_time,
        "error": error_message,
    }


async def _save_batch_to_mongodb(
    db,
    nodes_collection: str,
    edges_collection: str,
    nodes: List[Dict],
    edges: List[Dict],
) -> None:
    """
    Saves batch of nodes and edges to MongoDB.

    Uses bulk_write with upsert for efficiency.
    """
    from pymongo import UpdateOne

    try:
        # Save nodes
        if nodes:
            operations = [
                UpdateOne({"node_id": n["node_id"]}, {"$set": n}, upsert=True)
                for n in nodes
            ]
            await db[nodes_collection].bulk_write(operations, ordered=False)

        # Save edges
        if edges:
            operations = [
                UpdateOne({"edge_id": e["edge_id"]}, {"$set": e}, upsert=True)
                for e in edges
            ]
            await db[edges_collection].bulk_write(operations, ordered=False)

    except Exception as e:
        logger.error(f"Failed to save batch to MongoDB: {e}")
        raise


# Export task
__all__ = ["crawl_job_task"]
