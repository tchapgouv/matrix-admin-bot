from abc import ABC, abstractmethod

from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessageText

from matrix_admin_bot.command import Command


class Validator(ABC):
    @abstractmethod
    def validation_prompt(self) -> str: ...

    @abstractmethod
    async def validate(
        self,
        room: MatrixRoom,
        user_response: RoomMessageText,
        command: Command,
        matrix_client: MatrixClient,
    ) -> bool: ...
