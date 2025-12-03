"""Setup script for GraphCrawler."""

from setuptools import setup, find_packages
from pathlib import Path

def get_version():
    version_file = Path(__file__).parent / "graph_crawler" / "__version__.py"
    if version_file.exists():
        with open(version_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('__version__'):
                    return line.split('=')[1].strip().strip('"').strip("'")
    return "3.2.0"

this_directory = Path(__file__).parent
long_description = ""


try:
    long_description = (this_directory / "README.md").read_text(encoding='utf-8')  # <-- encoding
except FileNotFoundError:
    pass


requirements = []
try:
    with open('requirements.txt') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
except FileNotFoundError:
    pass

setup(
    name="graph-crawler",
    version=get_version(),
    author="0-EternalJunior-0",
    author_email="",
    description="Бібліотека для побудови графу веб-сайтів з підтримкою векторизації",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/demoprogrammer/web_graf",
    packages=find_packages(include=['graph_crawler', 'graph_crawler.*']),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
        "embeddings": [
            "sentence-transformers>=2.2.0",
            "numpy>=1.24.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "graph-crawler=graph_crawler.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
