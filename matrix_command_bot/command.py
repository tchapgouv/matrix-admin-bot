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
        self.current_status_reaction: str | None = None

    @abstractmethod
    async def execute(self) -> bool: ...

    async def reply_received(self, reply: RoomMessage) -> None:  # noqa: ARG002
        return

    async def set_status_reaction(self, key: str | None) -> None:
        if key is None:
            return
        if self.current_status_reaction:
            await self.matrix_client.room_redact(
                self.room.room_id, self.current_status_reaction
            )
        if key:
            self.current_status_reaction = await self.matrix_client.send_reaction(
                self.room.room_id, self.message, key
            )
