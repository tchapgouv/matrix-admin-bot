from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage


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

    async def reply_received(self, reply: RoomMessage) -> None:  # noqa: ARG002
        return

    async def replace_received(
        self,
        new_content: Mapping[str, Any],  # noqa: ARG002
        original_event: RoomMessage,  # noqa: ARG002
    ) -> None:
        return
