"""Crawler package - namespace для graph_crawler бібліотеки.

NOTE: Цей файл існує для зворотної сумісності.
Рекомендований імпорт: `import graph_crawler` або `from graph_crawler import ...`
"""

from __future__ import annotations

# Прямий реекспорт з основного пакету (без sys.path маніпуляцій)
from graph_crawler import *
from graph_crawler import __version__, __author__
