"""
WebSocket Connection Manager

Відповідає виключно за управління WebSocket з'єднаннями.
"""

import logging
import threading
from typing import Any, Dict, List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """
    Управління WebSocket з'єднаннями.

    Responsibilities:
    - Підключення/відключення клієнтів
    - Broadcasting повідомлень
    - Thread-safe операції з підключеннями
    """

    def __init__(self):
        """Initialize manager with empty connections list."""
        self.active_connections: List[WebSocket] = []
        self._lock = threading.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """
        Підключення нового WebSocket клієнта.

        Args:
            websocket: WebSocket connection
        """
        await websocket.accept()
        with self._lock:
            self.active_connections.append(websocket)
        logger.info(
            f"WebSocket client connected. Total connections: {len(self.active_connections)}"
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Відключення WebSocket клієнта.

        Args:
            websocket: WebSocket connection
        """
        with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(
            f"WebSocket client disconnected. Total connections: {len(self.active_connections)}"
        )

    async def broadcast(self, data: Dict[str, Any]) -> None:
        """
        Broadcast повідомлення всім підключеним клієнтам.

        Args:
            data: Дані для відправки
        """
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.error(f"Error sending to WebSocket client: {e}")
                disconnected.append(connection)

        # Видалити мертві з'єднання
        if disconnected:
            with self._lock:
                for conn in disconnected:
                    if conn in self.active_connections:
                        self.active_connections.remove(conn)

    def get_connection_count(self) -> int:
        """
        Отримати кількість активних підключень.

        Returns:
            Кількість активних WebSocket з'єднань
        """
        with self._lock:
            return len(self.active_connections)
