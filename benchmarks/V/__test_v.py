from typing import Optional
from pydantic import Field
import graph_crawler as gc
from graph_crawler import URLRule, AsyncDriver, EdgeCreationStrategy, PlaywrightDriver
from graph_crawler.extensions.plugins.node.vectorization import search, RealTimeVectorizerPlugin
from graph_crawler.infrastructure.transport.playwright.plugins import CloudflarePlugin, HumanBehaviorPlugin, \
    StealthPlugin

from graph_crawler.shared.utils.visualization import GraphVisualizer as v_plt

driver = PlaywrightDriver(
    # browsers=2,
    # tabs_per_browser = 5,
    config={'browser': 'chromium', 'headless': True, 'timeout': 30},
    plugins=[StealthPlugin({'stealth_mode': 'high'}),CloudflarePlugin(),HumanBehaviorPlugin(),
    ]
)
realtime_Vectorizer = RealTimeVectorizerPlugin(config={
    'enabled': True,
    'model_name': 'paraphrase-multilingual-MiniLM-L12-v2',
    'vector_size': 512,
    'field_name': 'text'
})

class CastomNode(gc.Node):
    text: Optional[str] = Field(default=None)

    def _update_from_context(self, context):
        super()._update_from_context(context)
        if context.html_tree:
            raw_text = context.html_tree.text
            clean_text = ' '.join(raw_text.split())
            clean_text = clean_text.replace('\n', ' ').replace('\t', ' ')
            self.text = clean_text
config =   {
    "broker": {
        "type": "redis",
        "host": "45.159.248.146",
        "port": 6579
    }
}
graph = gc.crawl(
    "https://www.playtechpeople.com/",
    max_depth=3,
    max_pages=100,
    node_class=CastomNode,
    wrapper = config,
    driver=AsyncDriver,
    url_rules = [
        URLRule(pattern="/blog/", should_follow_links=False, should_scan=True),
        URLRule(pattern="jobs.smartrecruiters.com", should_follow_links=False, should_scan=True, priority=6),
    ],
    edge_strategy=EdgeCreationStrategy.NEW_ONLY,
    plugins=[realtime_Vectorizer]
)

results = search(graph, "Знаю Java та Scala, а також інструменти інфраструктури на кшталт Docker, Kubernetes,"
                        " брокерів повідомлень та інше шукаю роботу, що відповідає моїм знанням і бекґраунду: 2 роки досвіду з Java та 1 рік — зі Scala.", top_k=10)
print(results)
v_plt.visualize_2d_web(graph, max_nodes=200, output_file='graph3_2d.html')


