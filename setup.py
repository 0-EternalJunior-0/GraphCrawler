"""Setup script for GraphCrawler (legacy - використовуйте pyproject.toml)."""

from setuptools import setup, find_packages
from pathlib import Path


def get_version():
    """Отримати версію з __version__.py."""
    version_file = Path(__file__).parent / "graph_crawler" / "__version__.py"
    if version_file.exists():
        with open(version_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("__version__"):
                    return line.split("=")[1].strip().strip('"').strip("'")
    return "4.0.4"


this_directory = Path(__file__).parent
long_description = ""

try:
    long_description = (this_directory / "README.md").read_text(encoding="utf-8")
except FileNotFoundError:
    pass

# Core dependencies
core_deps = [
    # HTTP клієнти
    "requests>=2.31.0",
    "aiohttp>=3.9.0",
    # HTML парсери
    "beautifulsoup4>=4.12.0",
    "lxml>=4.9.0",
    "lxml_html_clean",
    "selectolax>=0.3.0",
    # Валідація та конфіги
    "pydantic>=2.5.0",
    "pydantic-settings>=2.0.0",
    # Утиліти
    "orjson>=3.9.0",
    "fake-useragent",
    # Storage
    "aiofiles>=23.2.0",
    "aiosqlite>=0.19.0",
    # URL filtering (Bloom filter)
    "pybloom-live",
    # REST API
    "fastapi",
]

setup(
    name="graph-crawler",
    version=get_version(),
    author="0-EternalJunior-0",
    author_email="",
    description="Sync-First бібліотека для побудови графу веб-сайтів",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/0-EternalJunior-0/GraphCrawler",
    packages=find_packages(include=["graph_crawler", "graph_crawler.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    ],
    python_requires=">=3.11",
    install_requires=core_deps,
    extras_require={
        "native": [
            "cython>=3.0.0",
            "mmh3>=4.0.0",
        ],
        "playwright": ["playwright>=1.40.0"],
        "mongodb": ["motor>=3.3.0"],
        "postgresql": ["asyncpg>=0.29.0"],
        "embeddings": [
            "sentence-transformers>=2.2.0",
            "numpy>=1.24.0",
        ],
        "viz": [
            "pyvis>=0.3.0",
            "networkx>=3.6",
        ],
        "celery": [
            "celery>=5.3.0",
            "redis>=5.0.0",
        ],
        "ml": [
            "g4f>=0.3.0",
            "scikit-learn>=1.0.0",
        ],
        "performance": [
            "aiodns>=3.1.0",
            "uvloop>=0.19.0; platform_system != 'Windows'",
        ],
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
            "mypy>=1.5.0",
        ],
        "all": [
            "playwright>=1.40.0",
            "motor>=3.3.0",
            "asyncpg>=0.29.0",
            "sentence-transformers>=2.2.0",
            "numpy>=1.24.0",
            "pyvis>=0.3.0",
            "networkx>=3.6",
            "celery>=5.3.0",
            "redis>=5.0.0",
            "g4f>=0.3.0",
            "scikit-learn>=1.0.0",
            "aiodns>=3.1.0",
            "uvloop>=0.19.0; platform_system != 'Windows'",
        ],
    },
    entry_points={
        "console_scripts": [
            "graph-crawler=graph_crawler.api.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
