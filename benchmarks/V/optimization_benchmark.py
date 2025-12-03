import graph_crawler as gc

# Конфігурація для distributed
config = {
    "broker": {
        "type": "redis",
        "host": "45.159.248.146",
        "port": 6579
    },
    "database": {
        "type": "memory"  # або "mongodb", "postgresql"
    }
}

graph = gc.crawl(
    "https://example.com",
    max_depth=5,
    max_pages=10,
    wrapper=config,
    driver=gc.AsyncDriver

)