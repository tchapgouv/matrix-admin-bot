from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

import structlog
from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage

logger = structlog.getLogger(__name__)


class ICommand(ABC):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        self.room = room
        self.message = message
        self.matrix_client = matrix_client
        self.extra_config = extra_config

    @abstractmethod
    async def execute(self) -> bool: ...

    async def reply_received(self, reply: RoomMessage) -> None:
        logger.debug(
            "Reply received on a command that does not handle replies",
            command=self.__class__.__name__,
            event_id=reply.event_id,
            sender=reply.sender,
        )

    async def replace_received(
        self,
        new_content: Mapping[str, Any],  # noqa: ARG002
        original_event: RoomMessage,
    ) -> None:
        logger.debug(
            "Replacement received on a command that does not handle replacements",
            command=self.__class__.__name__,
            event_id=original_event.event_id,
            sender=original_event.sender,
        )
