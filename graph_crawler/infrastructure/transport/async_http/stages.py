"""Етапи (stages) для Async HTTP драйвера.

Аналогічно HTTP драйверу, але з додатковими етапами для session management.
"""

from enum import Enum


class AsyncHTTPStage(str, Enum):
    """
    Етапи виконання Async HTTP запиту.

    Lifecycle:
    1. SESSION_CREATING/SESSION_REUSING - управління session
    2. PREPARING_REQUEST - підготовка запиту
    3. SENDING_REQUEST - відправка
    4. RESPONSE_RECEIVED - отримання відповіді
    5. PROCESSING_RESPONSE - обробка
    6. REQUEST_FAILED/REQUEST_COMPLETED - завершення
    """

    # Session lifecycle
    SESSION_CREATING = "session_creating"
    SESSION_CREATED = "session_created"
    SESSION_REUSED = "session_reused"

    # Request lifecycle (аналогічно HTTP)
    PREPARING_REQUEST = "preparing_request"
    SENDING_REQUEST = "sending_request"
    RESPONSE_RECEIVED = "response_received"
    PROCESSING_RESPONSE = "processing_response"
    REQUEST_FAILED = "request_failed"
    REQUEST_COMPLETED = "request_completed"
