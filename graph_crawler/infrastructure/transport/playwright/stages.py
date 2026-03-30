"""Етапи (stages) для Playwright драйвера.

Найскладніший lifecycle з багатьма етапами:
- Browser lifecycle (launch, close)
- Context lifecycle (create, close)
- Page lifecycle (create, navigate, close)
- Content loading (wait, scroll)
- Screenshots
"""

from enum import Enum


class BrowserStage(str, Enum):
    """
    Етапи виконання Playwright драйвера.

    """

    BROWSER_LAUNCHING = "browser_launching"
    BROWSER_LAUNCHED = "browser_launched"
    CONTEXT_CREATING = "context_creating"
    CONTEXT_CREATED = "context_created"  #  Stealth scripts інжектяться тут
    PAGE_CREATING = "page_creating"
    PAGE_CREATED = "page_created"
    NAVIGATION_STARTING = "navigation_starting"
    NAVIGATION_COMPLETED = "navigation_completed"
    WAITING_FOR_SELECTOR = "waiting_for_selector"
    SCROLLING = "scrolling"
    CONTENT_READY = "content_ready"  #  CAPTCHA detection тут
    BEFORE_FETCH_MANY = "before_fetch_many"
    BEFORE_SCREENSHOT = "before_screenshot"
    AFTER_SCREENSHOT = "after_screenshot"
    PAGE_CLOSING = "page_closing"
    CONTEXT_CLOSING = "context_closing"
