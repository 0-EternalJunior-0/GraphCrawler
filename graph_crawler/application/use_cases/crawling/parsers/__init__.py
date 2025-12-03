"""HTML парсери для GraphCrawler."""

from graph_crawler.application.use_cases.crawling.parsers.base import BaseHTMLParser
from graph_crawler.application.use_cases.crawling.parsers.html_parser import HTMLParser

__all__ = ["BaseHTMLParser", "HTMLParser"]
