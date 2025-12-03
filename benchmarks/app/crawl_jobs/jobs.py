"""Після коду потрібно доп сканування не відсканованих енженів які тупо 100 мають тригер бажано конкретні тригери """

import re
from typing import Optional

import graph_crawler as gc
from graph_crawler import AsyncDriver, URLRule
from graph_crawler.shared.utils.visualization import GraphVisualizer
from urllib.parse import urlparse

from benchmarks.app.crawl_jobs.fillter import (
    BLACKLIST_SITEMAP,
    URL_HTTP_BLACKLIST,
    URL_HTTP_BLACKLIST_2,
    whitelist_patterns,
    ALLOWED_CRAWLING_DOMAINS,
    EXTERNAL_VACANCY_PATTERNS,
)
from benchmarks.app.crawl_jobs.url_test import url_test
from graph_crawler import  PlaywrightDriver

url_test
# Повний чорний список — сюди НЕ ходимо
RULES_BLACKLIST = (
        [URLRule(pattern=p, should_follow_links=False, should_scan=False, priority=4)for p in BLACKLIST_SITEMAP] +
        [URLRule(pattern=p, should_follow_links=False, should_scan=False, priority=4)for p in URL_HTTP_BLACKLIST] +
        [URLRule(pattern=p, should_follow_links=False, should_scan=False, priority=4)for p in URL_HTTP_BLACKLIST_2]
)

# Дозволені домени компанії — у них є свої піддомени
RULES_ALLOWED_DOMAINS = [
    URLRule(pattern=p, should_follow_links=True, should_scan=True, priority=6)
    for p in ALLOWED_CRAWLING_DOMAINS
]

# Зовнішні вакансії — скануємо сторінку, але не переходимо по лінках
RULES_EXTERNAL_VACANCIES = [
    URLRule(pattern=p, should_follow_links=False, should_scan=True, priority=7)
    for p in EXTERNAL_VACANCY_PATTERNS
]

URL_RULES = RULES_BLACKLIST + (RULES_ALLOWED_DOMAINS + RULES_EXTERNAL_VACANCIES)

class CustomNode(gc.Node):
    text: Optional[str] = None
    is_jobs_url: bool = False

    def _extract_text(self, context):
        raw = context.html_tree.text or ""
        self.text = " ".join(raw.split()).replace("\n", " ").replace("\t", " ")
    def _update_from_context(self, context):
        super()._update_from_context(context)
        if context.html_tree: self._extract_text(context)
        if not self.text: return
        try:
            url = urlparse(self.url).path
        except Exception:
            return
        self.is_jobs_url = any(re.search(pattern, url, flags=re.IGNORECASE) for pattern in whitelist_patterns + EXTERNAL_VACANCY_PATTERNS)


from graph_crawler.infrastructure.transport.playwright.plugins import StealthPlugin, CloudflarePlugin,HumanBehaviorPlugin, UltraStealthPlugin
HEADLESS = False
rescan_driver = PlaywrightDriver(
    config={
        "headless": HEADLESS,
        "browser": "chromium",
        "wait_until": "networkidle",
        "wait_timeout": 5000,
        "timeout": 10000,
        'block_resources': ['image', 'media', 'font'],
    },
)

config =   {
    "broker": {
        "type": "redis",
        "host": "45.159.248.146",
        "port": 6579
    }
}

graph = gc.crawl(
    url = "https://mhp4u.com.ua/vacancy/3645",
    same_domain =True,
    driver=AsyncDriver,
    max_pages=500,
    timeout=300,
    node_class=CustomNode,
    max_depth=4,
    url_rules=URL_RULES,
    edge_strategy=gc.EdgeCreationStrategy.NEW_ONLY,

)

for node in graph.nodes.values():
    if node.is_jobs_url:
        print(node.url)

print(graph)

GraphVisualizer.visualize_2d_web(
    graph,
    max_nodes=1500,
    output_file='graph3_2d.html',
    highlight_params={'is_jobs_url': '#FF6B6B'},
    max_physicist=2000
)