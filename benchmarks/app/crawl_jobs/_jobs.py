"""
Це старий підхід, і він нам поки що не підходить.
"""
import re

import graph_crawler as gc
from graph_crawler import AsyncDriver

from benchmarks.app.crawl_jobs.fillter import BLACKLIST_SITEMAP, URL_HTTP_BLACKLIST
from benchmarks.app.crawl_jobs.url_test import url_test

url_test = url_test[0]

graph_sitemap = gc.crawl_sitemap(
    url_test,
    driver=AsyncDriver,
    max_urls=100000
)


def remove_blacklist(graph_sitemap: gc.Graph, blacklist: list):
    """Видаляє з графа всі URL, що відповідають патернам із blacklist."""
    node_ids = list(graph_sitemap.nodes.keys())

    for node_id in node_ids:
        node = graph_sitemap.nodes.get(node_id)
        if not node:
            continue

        url = node.url.lower()

        if any(re.search(pattern, url) for pattern in blacklist):
            graph_sitemap.remove_node(node_id)

    return graph_sitemap


# Чистимо сайтмапу від точно невалідних посилань
graph_sitemap = remove_blacklist(graph_sitemap, BLACKLIST_SITEMAP)
print(graph_sitemap)

# Чистимо сайтмапу від посилань із великим шансом бути неправильними
graph_sitemap = remove_blacklist(graph_sitemap, URL_HTTP_BLACKLIST)
print(graph_sitemap)

# Потрібно визначити, з чого починати краулінг,
# щоб прискорити процес. Не завжди оптимально починати з домену —
# на малих сайтах різниця непомітна, але на великих дає відчутний приріст.
