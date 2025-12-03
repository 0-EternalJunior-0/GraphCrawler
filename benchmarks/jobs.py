import redis
import sys
import time
from functools import wraps
import graph_crawler as gc
from graph_crawler import AsyncDriver, PlaywrightDriver
from graph_crawler.shared.utils.visualization import GraphVisualizer

test = [
    "http://www.playtech.com/",
    "https://www.playtechpeople.com/",
    "https://ukrsibbank.com/",
    "https://company.plarium.com/",
    "https://www.gen.tech/",
    "http://www.ciklum.com/",
]
url_test = test[0]
def jobs_sitemap():
    graph = gc.crawl_sitemap(
        url_test,
        driver=AsyncDriver,
    )
    print(f"Знідено {len(graph.nodes)} елементів")
    return graph




def jobs_crawl():
    graph = gc.crawl(
        url_test,
        driver=AsyncDriver,
        max_pages=500,
        edge_strategy=gc.EdgeCreationStrategy.NEW_ONLY,
        timeout=120,
        request_delay=0.001,


    )
    print(f"Знідено {len(graph.nodes)} елементів")
    return graph

r1 = jobs_sitemap()


GraphVisualizer.visualize_2d_web(r1, max_nodes=1000)


